"""Impaired cash reviews are dated measurements, not invented allowance caps."""

# Imported fixtures are registered with pytest.
# ruff: noqa: F401, F811

from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_native_credit_risk_assessment_postgres import (
    _actual_debit,
    _complete,
    _schedule,
    actual_first_application,
    lifetime_scenarios,
    native_origin,
    native_risk,
    payout_accounting,
    payout_database,
    private_fixture_configuration,
    same_day_native,
)
from test_treasury_receipt_accounting_postgres import install


@pytest.fixture
def impaired_cash(native_risk):
    migration = (
        Path(__file__).resolve().parents[1]
        / "sql/0169_add_native_impaired_cash_reviews.sql"
    )
    if migration.exists():
        install(native_risk["conn"], migration)
    return native_risk


def test_actual_cash_cannot_invent_an_opening_impaired_assessment(impaired_cash):
    f = impaired_cash
    application = (
        f["conn"]
        .execute(
            "SELECT application_id FROM accounting.treasury_application_postings WHERE loan_id=%s LIMIT 1",
            (f["loan_id"],),
        )
        .fetchone()["application_id"]
    )
    candidate = (
        f["conn"]
        .execute(
            "SELECT accounting.native_impaired_cash_candidate(%s,%s,%s) AS source",
            (f["period"], f["loan_id"], application),
        )
        .fetchone()["source"]
    )
    assert not candidate["ready"]
    assert "posted_opening_impaired_assessment_required" in candidate["blockers"]


def test_reviewed_cash_targets_drive_later_net_interest_without_clipping(impaired_cash):
    # A pure interval chain with illustrative dates; no dated operational facts
    # or source clocks are changed to claim a future accounting lifecycle.
    conn = impaired_cash["conn"]
    event = {
        "cash_date": "2030-01-02",
        "cash": "500.00",
        "target_allowance": "400.00",
        "full_payoff": False,
    }
    measured = conn.execute(
        "SELECT accounting.native_credit_impaired_chain('2030-01-01',1000,600,0.01,'2030-01-03','2030-01-10',%s) AS value",
        (Jsonb([event]),),
    ).fetchone()["value"]
    assert Decimal(str(measured["gross_interest"])) == Decimal("15.10")
    assert Decimal(str(measured["net_interest"])) == Decimal("5.10")
    assert Decimal(str(measured["allowance_unwind"])) == Decimal("10.00")
    assert Decimal(str(measured["gross_after"])) == Decimal("515.10")
    assert Decimal(str(measured["virtual_allowance_before_final_review"])) == Decimal(
        "404.00"
    )
    assert Decimal(str(measured["virtual_impairment_adjustment"])) == Decimal("-206.00")
    for changed in [
        event | {"target_allowance": "600.00"},
        event | {"target_allowance": None},
        event | {"cash_date": "2029-12-31"},
    ]:
        with pytest.raises(psycopg.Error), conn.transaction():
            conn.execute(
                "SELECT accounting.native_credit_impaired_chain('2030-01-01',1000,600,0.01,'2030-01-03','2030-01-10',%s)",
                (Jsonb([changed]),),
            )


def test_exact_payoff_stops_unwind_and_separates_settlement_from_loss_release(
    impaired_cash,
):
    measured = (
        impaired_cash["conn"]
        .execute(
            "SELECT accounting.native_credit_impaired_chain('2030-01-01',1000,600,0.01,'2030-01-05','2030-01-10',%s) AS value",
            (
                Jsonb(
                    [
                        {
                            "cash_date": "2030-01-02",
                            "cash": "1010.00",
                            "target_allowance": "0.00",
                            "full_payoff": True,
                        }
                    ]
                ),
            ),
        )
        .fetchone()["value"]
    )
    assert Decimal(str(measured["gross_interest"])) == Decimal("10.00")
    assert Decimal(str(measured["net_interest"])) == Decimal("4.00")
    assert Decimal(str(measured["allowance_unwind"])) == Decimal("6.00")
    assert Decimal(str(measured["gross_settlement_difference"])) == 0
    assert Decimal(str(measured["virtual_impairment_adjustment"])) == Decimal("-606.00")
    assert Decimal(str(measured["gross_after"])) == 0


def test_impaired_cash_review_cannot_be_written_without_source_authority(impaired_cash):
    f = impaired_cash
    conn = f["conn"]
    application = conn.execute(
        "SELECT application_id FROM accounting.treasury_application_postings WHERE loan_id=%s LIMIT 1",
        (f["loan_id"],),
    ).fetchone()["application_id"]
    with pytest.raises(psycopg.Error), conn.transaction():
        conn.execute(
            "SELECT accounting.record_native_impaired_cash_review(%s,%s,%s,%s,%s,%s,%s)",
            (
                f["period"],
                f["loan_id"],
                application,
                f["actor_id"],
                "0" * 64,
                Jsonb([]),
                "A cash record cannot invent a previous-day impaired assessment.",
            ),
        )
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.native_impaired_cash_reviews"
        ).fetchone()["n"]
        == 0
    )
    assert conn.execute(
        "SELECT NOT EXISTS(SELECT 1 FROM pg_proc p CROSS JOIN LATERAL "
        "aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a "
        "LEFT JOIN pg_roles r ON r.oid=a.grantee "
        "WHERE p.oid='accounting.record_native_impaired_cash_review(uuid,uuid,uuid,uuid,text,jsonb,text)'::regprocedure "
        "AND (a.grantee=0 OR r.rolname IN('anon','authenticated','service_role')) "
        "AND a.privilege_type='EXECUTE') AS private"
    ).fetchone()["private"]
    with pytest.raises(psycopg.Error), conn.transaction():
        conn.execute("TRUNCATE accounting.native_impaired_cash_reviews")


def test_cash_measurement_uses_gross_less_dated_expected_receipts(impaired_cash):
    f = impaired_cash
    conn = f["conn"]
    source = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
        (f["period"], f["loan_id"]),
    ).fetchone()["source"]
    scenarios = lifetime_scenarios(f, source)
    # Calculator-only source. The protected candidate above separately proves
    # this actual loan has no historical Stage 3 opening; no dated row is made.
    import datetime
    from uuid import uuid4

    sample = source["snapshot"] | {
        "gross_carrying_amount": "510.00",
        "opening_assessment": {
            "id": str(uuid4()),
            "as_of_date": (f["today"] - datetime.timedelta(days=1)).isoformat(),
            "measurement_snapshot": {
                "risk_review": {
                    "stage_label": "stage_3_credit_impaired",
                    "default_label": True,
                }
            },
        },
    }
    for scenario in scenarios:
        scenario["expected_cash_flows"] = [
            {"cash_date": f["today"].isoformat(), "amount": "400.00"}
        ]
    measured = conn.execute(
        "SELECT accounting.calculate_native_impaired_cash_ecl(%s,'{}'::jsonb,%s) AS value",
        (Jsonb(sample), Jsonb(scenarios)),
    ).fetchone()["value"]
    assert measured["policy_version"] == "native_impaired_cash_expected_receipts_v1"
    assert measured["loss_basis"] == "gross_carrying_less_expected_pv"
    assert Decimal(str(measured["expected_cash_present_value"])) == Decimal("400.00")
    assert Decimal(str(measured["ecl_amount"])) == Decimal("110.00")
    for scenario in scenarios:
        scenario["expected_cash_flows"] = []
    measured = conn.execute(
        "SELECT accounting.calculate_native_impaired_cash_ecl(%s,'{}'::jsonb,%s) AS value",
        (Jsonb(sample), Jsonb(scenarios)),
    ).fetchone()["value"]
    assert Decimal(str(measured["ecl_amount"])) == Decimal("510.00")
    sample["gross_carrying_amount"] = "100.00"
    for scenario, amount in zip(scenarios, ("99.99", "100.00"), strict=True):
        scenario["probability"] = "0.5"
        scenario["expected_cash_flows"] = [
            {"cash_date": f["today"].isoformat(), "amount": amount}
        ]
    measured = conn.execute(
        "SELECT accounting.calculate_native_impaired_cash_ecl(%s,'{}'::jsonb,%s) AS value",
        (Jsonb(sample), Jsonb(scenarios)),
    ).fetchone()["value"]
    assert Decimal(str(measured["ecl_amount"])) == Decimal("0.01")
    assert Decimal(str(measured["expected_cash_present_value"])) == Decimal("100.00")
    assert Decimal(measured["weighted_expected_cash_present_value_raw"]) == Decimal(
        "99.995"
    )
    assert Decimal(str(measured["currency_rounding_adjustment"])) == Decimal("0.01")
    sample["opening_assessment"]["measurement_snapshot"]["risk_review"][
        "stage_label"
    ] = "stage_2_lifetime"
    with pytest.raises(psycopg.Error), conn.transaction():
        conn.execute(
            "SELECT accounting.calculate_native_impaired_cash_ecl(%s,'{}'::jsonb,%s)",
            (Jsonb(sample), Jsonb(scenarios)),
        )
