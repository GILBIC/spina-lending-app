"""Independent funded renewal coordinates on the task-owned synthetic schema."""

from decimal import Decimal
from pathlib import Path

import pytest
from psycopg.types.json import Jsonb
from test_native_regular_historical_postgres import dated_native as _dated_native
from test_treasury_receipt_accounting_postgres import install

native_source = _dated_native


@pytest.fixture
def dated_native(native_source):
    for filename in (
        "0165_add_regular_chronological_cash.sql",
        "0166_add_native_regular_renewals.sql",
    ):
        install(
            native_source["conn"],
            Path(__file__).resolve().parents[1] / "sql" / filename,
        )
    return native_source


@pytest.mark.parametrize(
    (
        "treatment",
        "revised",
        "settlement",
        "fair_value",
        "old_difference",
        "new_difference",
    ),
    [
        ("modification_no_derecognition", "1450.00", "1000.00", None, "-50.00", "0.00"),
        ("modification_no_derecognition", "1500.00", "1000.00", None, "0.00", "0.00"),
        ("derecognition", "1450.00", "980.00", "1460.00", "-20.00", "-20.00"),
        # Opposite signed components must remain explicit, never net to zero.
        ("derecognition", "1450.00", "980.00", "1500.00", "-20.00", "20.00"),
    ],
)
def test_funded_native_renewal_measurement_is_independent_and_balanced(
    dated_native,
    treatment,
    revised,
    settlement,
    fair_value,
    old_difference,
    new_difference,
):
    basis = {
        "decision": treatment,
        "old_loan_component": "900.00",
        "old_accrued_interest": "100.00",
        "old_allowance": "0.00",
        "fresh_cash": "500.00",
        "revised_pv": revised,
        "settlement_consideration": settlement,
        "new_initial_fair_value": fair_value,
    }
    result = (
        dated_native["conn"]
        .execute(
            "SELECT accounting.native_renewal_measurement(%s) AS value", (Jsonb(basis),)
        )
        .fetchone()["value"]
    )
    assert Decimal(result["old_asset_difference"]) == Decimal(old_difference)
    assert Decimal(result["new_asset_difference"]) == Decimal(new_difference)
    assert result["accounting_asset_continues"] == (
        treatment == "modification_no_derecognition"
    )
    lines = result["lines"]
    assert sum(Decimal(row["debit"]) - Decimal(row["credit"]) for row in lines) == 0
    assert sum(
        Decimal(row["credit"]) for row in lines if row["account_code"] == "1050"
    ) == Decimal(500)
    assert not {"1010", "1020", "1030"}.intersection(
        row["account_code"] for row in lines
    )
    if old_difference == "-20.00" and new_difference == "20.00":
        assert any(
            row["account_code"] == "5010" and Decimal(row["debit"]) == 20
            for row in lines
        )
        assert any(
            row["account_code"] == "4020" and Decimal(row["credit"]) == 20
            for row in lines
        )


def test_native_derecognition_does_not_infer_new_measurement(dated_native):
    import psycopg

    conn = dated_native["conn"]
    with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
        conn.execute(
            "SELECT accounting.native_renewal_measurement(%s)",
            (
                Jsonb(
                    {
                        "decision": "derecognition",
                        "old_loan_component": "900.00",
                        "old_accrued_interest": "100.00",
                        "old_allowance": "0",
                        "fresh_cash": "500.00",
                        "revised_pv": "1450.00",
                        "settlement_consideration": "1000.00",
                    }
                ),
            ),
        )


@pytest.mark.parametrize("adjustment", ["-81.38", "18.62"])
def test_impaired_renewal_separates_unwind_from_reviewed_impairment(
    dated_native, adjustment
):
    # Pure independently specified interval amounts, not dated posting evidence.
    before, unwind, delta = Decimal(300), Decimal("31.38"), Decimal(adjustment)
    after = before + unwind + delta
    boundary = {
        "allowance_before": str(before),
        "allowance_unwind": str(unwind),
        "impairment_adjustment": str(delta),
        "allowance_after": str(after),
    }
    basis = {
        "decision": "modification_no_derecognition",
        "old_loan_component": "900.00",
        "old_accrued_interest": "104.62",
        "old_allowance": str(after),
        "fresh_cash": "500.00",
        "revised_pv": "1450.00",
        "credit_impaired_boundary": boundary,
    }
    measured = (
        dated_native["conn"]
        .execute(
            "SELECT accounting.native_renewal_measurement(%s) AS value", (Jsonb(basis),)
        )
        .fetchone()["value"]
    )
    assert measured["credit_impaired_boundary"] == boundary
    lines = measured["lines"]
    assert sum(Decimal(x["debit"]) - Decimal(x["credit"]) for x in lines) == 0
    by_role = {}
    for line in lines:
        key = (line["loan_role"], line["account_code"])
        by_role[key] = (
            by_role.get(key, Decimal(0))
            + Decimal(line["debit"])
            - Decimal(line["credit"])
        )
    assert by_role["old", "1190"] == before
    assert by_role["new", "1190"] == -after
    assert by_role["old", "4000"] == unwind
    assert by_role["old", "5000"] == delta
