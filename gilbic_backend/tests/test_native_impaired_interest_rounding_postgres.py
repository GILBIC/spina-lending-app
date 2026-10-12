"""Exercise installed impaired-interest paths with independently worked cents.

These are bounded SQL measurement examples, not evidence of an aged posting.
No persisted economic dates or clocks are changed for these examples.
"""

# Imported fixtures are registered by pytest.
# ruff: noqa: F401, F811

from decimal import Decimal

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_native_renewal_lifecycle_postgres import (
    dated_native,
    native_measurement_source,
    native_source,
)


@pytest.mark.parametrize("boundary", ["cash", "deferred", "tail", "empty_tail"])
def test_installed_chain_rounds_net_basis_at_each_cash_boundary(dated_native, boundary):
    # 10 x .0015 = .015 -> GI .02; 9 x .0015 = .0135 -> NI .01.
    # U must be .01. Rounding 1 x .0015 by itself incorrectly yields zero.
    gross = "11.00" if boundary == "tail" else "10.00"
    event = {
        "cash_date": "2030-01-01" if boundary == "tail" else "2030-01-02",
        "cash": "1.00",
        "full_payoff": False,
        "target_allowance": "1.00",
    }
    if boundary == "tail":
        event["opening_day_cash"] = True
    elif boundary == "deferred":
        event.update(target_allowance=None, defer_final_measurement=True)
    else:
        event.update(verified_gross_interest="0.02", verified_gross_after="9.02")
    measured = (
        dated_native["conn"]
        .execute(
            "SELECT accounting.native_credit_impaired_chain('2030-01-01',%s,1,.0015,'2030-01-02','2030-01-10',%s) AS value",
            (gross, Jsonb([] if boundary == "empty_tail" else [event])),
        )
        .fetchone()["value"]
    )
    assert Decimal(str(measured["gross_interest"])) == Decimal("0.02")
    assert Decimal(str(measured["net_interest"])) == Decimal("0.01")
    assert Decimal(str(measured["allowance_unwind"])) == Decimal("0.01")
    assert Decimal(str(measured["gross_after"])) == Decimal(
        "10.02" if boundary in {"tail", "empty_tail"} else "9.02"
    )
    assert Decimal(str(measured["virtual_impairment_adjustment"])) == Decimal(
        "-0.01" if boundary == "cash" else "0.00"
    )
    assert Decimal(str(measured["virtual_allowance_before_final_review"])) == Decimal(
        "1.00" if boundary == "cash" else "1.01"
    )


def test_installed_chain_uses_verified_gross_but_independent_net_interest(dated_native):
    event = {
        "cash_date": "2030-01-02",
        "cash": "1.00",
        "full_payoff": False,
        "target_allowance": "0.50",
        "verified_gross_interest": "0.03",
        "verified_gross_after": "9.03",
    }
    conn = dated_native["conn"]
    statement = "SELECT accounting.native_credit_impaired_chain('2030-01-01',10,1,.0015,'2030-01-02','2030-01-10',%s) AS value"
    measured = conn.execute(statement, (Jsonb([event]),)).fetchone()["value"]
    assert Decimal(str(measured["gross_interest"])) == Decimal("0.03")
    assert Decimal(str(measured["net_interest"])) == Decimal("0.01")
    assert Decimal(str(measured["allowance_unwind"])) == Decimal("0.02")
    assert Decimal(str(measured["virtual_impairment_adjustment"])) == Decimal("-0.52")
    assert Decimal(str(measured["gross_after"])) == Decimal("9.03")
    signed = conn.execute(
        statement,
        (
            Jsonb(
                [
                    event
                    | {
                        "verified_gross_interest": "0.00",
                        "verified_gross_after": "9.00",
                    }
                ]
            ),
        ),
    ).fetchone()["value"]
    assert Decimal(str(signed["net_interest"])) == Decimal(".01")
    assert Decimal(str(signed["allowance_unwind"])) == Decimal("-.01")
    assert Decimal(str(signed["currency_rounding_adjustment"])) == Decimal("-.02")
    assert Decimal(str(signed["virtual_impairment_adjustment"])) == Decimal("-.49")


def test_installed_no_cash_interest_uses_the_same_rounded_net_basis(dated_native):
    source = {
        "cutoff_date": "2030-01-02",
        "anchor": {"contractual_due_date": "2030-01-10"},
        "eir": {"daily_eir": ".0015", "cumulative_interest": ".02"},
        "prior_prefixes": [
            {
                "preparation": {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "as_of_date": "2030-01-01",
                    "source_snapshot": {
                        "gross_carrying_amount": "10.00",
                        "eir": {"cumulative_interest": "0.00"},
                    },
                    "measurement_snapshot": {
                        "ecl_amount": "1.00",
                        "risk_review": {"stage_label": "stage_3_credit_impaired"},
                    },
                }
            }
        ],
    }
    measured = (
        dated_native["conn"]
        .execute(
            "SELECT accounting.native_credit_impaired_interest(%s) AS value",
            (Jsonb(source),),
        )
        .fetchone()["value"]
    )
    assert Decimal(measured["gross_interest"]) == Decimal("0.02")
    assert Decimal(measured["net_interest"]) == Decimal("0.01")
    assert Decimal(measured["allowance_unwind"]) == Decimal("0.01")


def test_installed_chain_carries_reviewed_target_into_next_net_interval(dated_native):
    # Day 1: GI .02, NI .01, U .01, gross after cash 9.02, reviewed A .50.
    # Day 2: GI .01, NI .01, U zero; total GI .03, NI .02, U .01.
    events = [
        {
            "cash_date": "2030-01-02",
            "cash": "1.00",
            "full_payoff": False,
            "target_allowance": ".50",
            "verified_gross_interest": ".02",
            "verified_gross_after": "9.02",
        }
    ]
    measured = (
        dated_native["conn"]
        .execute(
            "SELECT accounting.native_credit_impaired_chain('2030-01-01',10,1,.0015,'2030-01-03','2030-01-10',%s) AS value",
            (Jsonb(events),),
        )
        .fetchone()["value"]
    )
    for key, expected in {
        "gross_interest": ".03",
        "net_interest": ".02",
        "allowance_unwind": ".01",
        "gross_after": "9.03",
        "virtual_allowance_before_final_review": ".50",
        "virtual_impairment_adjustment": "-.51",
    }.items():
        assert Decimal(str(measured[key])) == Decimal(expected)


def test_outer_cash_interest_reconciles_source_gross_to_direct_net_basis(
    dated_native, monkeypatch, tmp_path
):
    from copy import deepcopy
    from datetime import date, timedelta
    from uuid import uuid4

    from native_stage3_elapsed_support import independent_interest, money
    from test_native_regular_chronological_cash_postgres import post_application
    from test_native_regular_historical_postgres import (
        actual_first_application,
        post_prefix,
    )

    f = dated_native
    conn = f["conn"]
    post_prefix(f)
    period = conn.execute(
        "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) VALUES(%s,%s,%s,'open') RETURNING id",
        (
            "Actual cash rounding " + uuid4().hex,
            f["cutoff"] + timedelta(days=1),
            f["today"],
        ),
    ).fetchone()["id"]
    applied = actual_first_application(f, monkeypatch, tmp_path)
    post_application(f, applied)
    candidate = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
        (period, f["loan_id"]),
    ).fetchone()["value"]
    assert candidate["ready"], candidate["blockers"]
    # The cash preparation is real and retains its own independently proved GI.
    # Only copied calculator inputs below label an illustrative impaired opening
    # and vary the supplied final gross rounding. No stored date/risk is changed.
    source = deepcopy(candidate["snapshot"])
    opening = source["prior_prefixes"][-1]["preparation"]
    opening["measurement_snapshot"]["risk_review"]["stage_label"] = (
        "stage_3_credit_impaired"
    )
    opening["measurement_snapshot"]["ecl_amount"] = "100.00"
    gross = money(opening["source_snapshot"]["gross_carrying_amount"])
    days = (f["today"] - date.fromisoformat(opening["as_of_date"])).days
    rounded_gross, unwind = independent_interest(
        gross, "100.00", source["eir"]["daily_eir"], days
    )
    expected_net = rounded_gross - unwind
    prior = Decimal(str(opening["source_snapshot"]["eir"]["cumulative_interest"]))
    original_gi = Decimal(str(source["eir"]["cumulative_interest"])) - prior
    original_after = money(source["gross_carrying_amount"])
    statement = "SELECT accounting.native_credit_impaired_interest(%s) AS value"
    for change in (Decimal(".01"), Decimal("-.01"), Decimal(0)):
        sample = deepcopy(source)
        sample["eir"]["cumulative_interest"] = str(prior + original_gi + change)
        sample["gross_carrying_amount"] = str(original_after + change)
        measured = conn.execute(statement, (Jsonb(sample),)).fetchone()["value"]
        assert Decimal(measured["gross_interest"]) == original_gi + change
        assert Decimal(measured["net_interest"]) == expected_net
        assert (
            Decimal(measured["allowance_unwind"]) == original_gi + change - expected_net
        )
        assert (
            money(measured["currency_rounding_adjustment"])
            == original_gi + change - rounded_gross
        )
        chain = measured["cash_chain_measurement"]
        assert money(chain["gross_interest"]) == original_gi + change
        assert money(chain["net_interest"]) == expected_net
        assert money(chain["allowance_unwind"]) == original_gi + change - expected_net
        assert money(chain["gross_after"]) == original_after + change
        assert money(chain["virtual_allowance_before_final_review"]) == (
            Decimal(100) + original_gi + change - expected_net
        )
    sample = deepcopy(source)
    sample["eir"]["cumulative_interest"] = str(prior + expected_net - Decimal(".01"))
    sample["gross_carrying_amount"] = str(
        original_after + expected_net - Decimal(".01") - original_gi
    )
    signed = conn.execute(statement, (Jsonb(sample),)).fetchone()["value"]
    assert money(signed["net_interest"]) == expected_net
    assert money(signed["allowance_unwind"]) == Decimal("-.01")


@pytest.mark.parametrize("allowance", [".01", "0.00"])
@pytest.mark.parametrize("payoff", [False, True])
def test_legitimate_cumulative_rounding_can_have_signed_reconciliation(
    dated_native, allowance, payoff
):
    from decimal import ROUND_HALF_UP, localcontext

    with localcontext() as context:
        context.prec = 50
        rate = Decimal("1.05") ** (Decimal(1) / Decimal(30)) - 1
        gross4 = (Decimal(1000) * (1 + rate) ** 4).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )
        gross5 = (Decimal(1000) * (1 + rate) ** 5).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )
        net = ((gross4 - Decimal(allowance)) * rate).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )
    assert (gross4, gross5 - gross4, net) == (
        Decimal("1006.53"),
        Decimal("1.63"),
        Decimal("1.64"),
    )
    event = {
        "cash_date": "2030-01-06",
        "cash": "1008.16" if payoff else "1.00",
        "full_payoff": payoff,
        "target_allowance": "0.00",
        "verified_gross_interest": "1.63",
        "verified_gross_after": "0.00" if payoff else "1007.16",
    }
    conn = dated_native["conn"]
    measured = conn.execute(
        "SELECT accounting.native_credit_impaired_chain('2030-01-05',1006.53,%s,%s,'2030-01-06','2030-01-31',%s) AS value",
        (allowance, rate, Jsonb([event])),
    ).fetchone()["value"]
    for key, value in {
        "gross_interest": "1.63",
        "net_interest": "1.64",
        "allowance_unwind": "-.01",
        "currency_rounding_adjustment": "-.01",
        "virtual_allowance_before_final_review": "0.00",
        "gross_after": "0.00" if payoff else "1007.16",
        "gross_settlement_difference": "0.00",
    }.items():
        assert Decimal(str(measured[key])) == Decimal(value)
    assert (
        Decimal(allowance)
        + Decimal(str(measured["allowance_unwind"]))
        + Decimal(str(measured["virtual_impairment_adjustment"]))
        == 0
    )
    source = {
        "cutoff_date": "2030-01-06",
        "anchor": {"contractual_due_date": "2030-01-31"},
        "eir": {"daily_eir": str(rate), "cumulative_interest": "8.16"},
        "prior_prefixes": [
            {
                "preparation": {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "as_of_date": "2030-01-05",
                    "source_snapshot": {
                        "gross_carrying_amount": "1006.53",
                        "eir": {"cumulative_interest": "6.53"},
                    },
                    "measurement_snapshot": {
                        "ecl_amount": allowance,
                        "risk_review": {"stage_label": "stage_3_credit_impaired"},
                    },
                }
            }
        ],
    }
    outer = conn.execute(
        "SELECT accounting.native_credit_impaired_interest(%s) AS value",
        (Jsonb(source),),
    ).fetchone()["value"]
    assert Decimal(outer["net_interest"]) == net
    assert Decimal(outer["allowance_unwind"]) == Decimal("-.01")
    assert Decimal(outer["currency_rounding_adjustment"]) == Decimal("-.01")


@pytest.mark.parametrize("unwind", ["-.01", ".01", "0.00"])
def test_signed_reconciliation_journal_legs_and_renewal_conserve_allowance(
    dated_native, unwind
):
    conn = dated_native["conn"]
    value = Decimal(unwind)
    lines = conn.execute(
        "SELECT * FROM accounting.native_credit_impaired_unwind_lines(%s)", (value,)
    ).fetchall()
    assert len(lines) == (2 if value else 0)
    assert all(row["debit"] >= 0 and row["credit"] >= 0 for row in lines)
    assert sum(row["debit"] - row["credit"] for row in lines) == 0
    if value:
        by_code = {row["account_code"]: row for row in lines}
        assert by_code["4000"]["debit"] - by_code["4000"]["credit"] == value
        assert by_code["1190"]["credit"] - by_code["1190"]["debit"] == value
    basis = {
        "decision": "modification_no_derecognition",
        "old_loan_component": "1000.00",
        "old_accrued_interest": "8.16",
        "old_allowance": "0.00",
        "fresh_cash": "100.00",
        "revised_pv": "1108.16",
        "credit_impaired_boundary": {
            "allowance_before": "0.00",
            "allowance_unwind": unwind,
            "impairment_adjustment": str(-value),
            "allowance_after": "0.00",
        },
    }
    measured = conn.execute(
        "SELECT accounting.native_renewal_measurement(%s) AS value", (Jsonb(basis),)
    ).fetchone()["value"]
    all_lines = measured["lines"]
    assert all(
        Decimal(row["debit"]) >= 0 and Decimal(row["credit"]) >= 0 for row in all_lines
    )
    assert sum(Decimal(row["debit"]) - Decimal(row["credit"]) for row in all_lines) == 0
    allowance_lines = [row for row in all_lines if row["account_code"] == "1190"]
    assert (
        sum(Decimal(row["credit"]) - Decimal(row["debit"]) for row in allowance_lines)
        == 0
    )
    signed_pair = [
        row for row in all_lines if row["component"] == "old_asset_allowance_unwind"
    ]
    assert len(signed_pair) == (2 if value else 0)
    for invalid in ("NaN", "Infinity", "-.001"):
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "SELECT * FROM accounting.native_credit_impaired_unwind_lines(%s)",
                (invalid,),
            )
