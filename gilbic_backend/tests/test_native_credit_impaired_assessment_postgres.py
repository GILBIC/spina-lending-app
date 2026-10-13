"""Actual impairment boundary plus independent subsequent-period arithmetic."""

# Imported fixtures are registered with pytest.
# ruff: noqa: F401, F811

from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from native_current_schema_test_support import (
    assert_native_schema_preserved,
    install_native_fixture_migration,
)
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
    reviewed_stage,
    same_day_native,
)
from test_native_current_schema_cycle_postgres import (
    close_period,
    report,
    retain_application_tax,
    retain_native_dst,
    retained_cash_policy,
)


def test_initial_impaired_cutoff_retains_actual_boundary_for_subsequent_net_eir(
    native_risk,
    tmp_path,
    request,
):
    f = native_risk
    conn = f["conn"]
    for name in (
        "0164_bound_accounting_close_lock_waits.sql",
        "0170_add_reporting_source_proof.sql",
    ):
        install_native_fixture_migration(
            conn, Path(__file__).resolve().parents[1] / "sql" / name
        )
    assert_native_schema_preserved(conn, request)
    risk_id = reviewed_stage(f, "stage_3_credit_impaired")
    source = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
        (f["period"], f["loan_id"]),
    ).fetchone()["source"]
    assert source["ready"], source["blockers"]
    scenarios = lifetime_scenarios(f, source)
    for scenario in scenarios:
        for flow in scenario["expected_cash_flows"]:
            flow["amount"] = f"{Decimal(flow['amount']) * Decimal('0.5'):.2f}"
    zero_recovery = [scenario | {"expected_cash_flows": []} for scenario in scenarios]
    zero_loss = conn.execute(
        "SELECT accounting.calculate_elapsed_assessment_ecl(%s,%s,%s) AS measured",
        (
            Jsonb(source["snapshot"]),
            Jsonb({"credit_risk_review_id": risk_id}),
            Jsonb(zero_recovery),
        ),
    ).fetchone()["measured"]
    assert zero_loss["loss_basis"] == "gross_carrying_less_expected_pv"
    assert Decimal(str(zero_loss["expected_cash_present_value"])) == 0
    assert Decimal(str(zero_loss["ecl_amount"])) == Decimal(
        str(source["snapshot"]["gross_carrying_amount"])
    )
    prepared = conn.execute(
        "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s::bigint,%s,%s) AS id",
        (
            f["period"],
            f["loan_id"],
            f["actor_id"],
            source["source_digest"],
            risk_id,
            Jsonb(scenarios),
            "Actual current impaired cutoff establishes the dated next-period net EIR boundary.",
        ),
    ).fetchone()["id"]
    retained = conn.execute(
        "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (prepared,),
    ).fetchone()
    measured = retained["measurement_snapshot"]
    assert Decimal(str(measured["ecl_amount"])) > 0
    assert measured["risk_review"]["stage_label"] == "stage_3_credit_impaired"
    assert measured["risk_review"]["default_label"] is True
    assert measured["loss_basis"] == "gross_carrying_less_expected_pv"
    interest = measured["credit_impaired_interest"]
    assert interest["basis"] == "gross_before_initial_impaired_cutoff"
    assert interest["impairment_boundary_date"] == f["today"].isoformat()
    assert Decimal(str(interest["allowance_unwind"])) == 0
    assert interest["gross_interest"] == interest["net_interest"]
    conn.execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (prepared, f["actor_id"], retained["confirmation_digest"]),
    )
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")

    assert conn.execute(
        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
        (f["period"], f["loan_id"]),
    ).fetchone()["exact"]
    conn.execute("SET CONSTRAINTS ALL DEFERRED")
    retain_native_dst(f, period_id=f["period"])
    application = conn.execute(
        "SELECT application_id FROM accounting.treasury_application_postings WHERE loan_id=%s LIMIT 1",
        (f["loan_id"],),
    ).fetchone()["application_id"]
    retain_application_tax(f, f["period"], application)
    retained_cash_policy(f, f["period"])
    close_period(f, f["period"])
    statements = report(f, f["period"])
    assert statements["financial_position"]["balanced"]
    assert statements["reporting_supplement"]["cash_flows"]["reconciled"]
    assert conn.execute(
        "SELECT accounting.period_review_manifest_state(%s) AS state", (f["period"],)
    ).fetchone()["state"]["current"]
    assert conn.execute(
        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
        (f["period"], f["loan_id"]),
    ).fetchone()["exact"]
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")

    from native_stage3_capture import capture_if_requested

    capture_if_requested(f, tmp_path, prepared)


def test_impaired_interval_separates_income_unwind_and_reviewed_loss(native_risk):
    # This ten-day arithmetic example does not claim an actual dated posting.
    conn = native_risk["conn"]
    result = conn.execute(
        "SELECT accounting.native_credit_impaired_interval(1000,300,0.01,10,100,250,false) AS measured"
    ).fetchone()["measured"]
    assert Decimal(str(result["gross_interest"])) == Decimal("104.62")
    assert Decimal(str(result["net_interest"])) == Decimal("73.24")
    assert Decimal(str(result["allowance_unwind"])) == Decimal("31.38")
    assert Decimal(str(result["gross_after"])) == Decimal("1004.62")
    assert Decimal(str(result["allowance_delta"])) == Decimal("-81.38")
    assert Decimal(str(result["net_after"])) == Decimal("754.62")
    with pytest.raises(psycopg.Error), conn.transaction():
        conn.execute(
            "SELECT accounting.native_credit_impaired_interval(1000,300,0.01,10,100,1100,false)"
        )
