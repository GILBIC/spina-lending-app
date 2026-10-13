"""Stable real-current-day native release and cash, with no substituted clock."""

# Imported fixtures are registered with pytest.
# ruff: noqa: F401, F811

from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from native_current_schema_test_support import (
    assert_native_schema_preserved,
    install_native_fixture_migration,
)
from psycopg.types.json import Jsonb
from test_native_payout_regular_origin_postgres import (
    _actual_debit,
    _complete,
    _schedule,
    native_origin,
    payout_accounting,
    payout_database,
    private_fixture_configuration,
)
from test_native_regular_chronological_cash_postgres import post_application
from test_native_regular_historical_postgres import actual_first_application


@pytest.fixture
def same_day_native(native_origin, request):
    f = native_origin
    for name in (
        "0163_add_native_regular_assessment_integration.sql",
        "0165_add_regular_chronological_cash.sql",
        "0167_add_regular_payoff_accounting.sql",
    ):
        install_native_fixture_migration(
            f["conn"], Path(__file__).resolve().parents[1] / "sql" / name
        )
    assert_native_schema_preserved(f["conn"], request)
    prepared, _ = _actual_debit(f)
    _complete(f, prepared)
    release, installments = _schedule(f)
    f.update(
        payout_id=prepared["target_id"],
        actor_id=f["actor"].user_id,
        device_id=f["actor"].registered_device_id,
        release_day=release["date_released"],
        installments=installments,
        application_period_id=f["period"],
    )
    f["conn"].execute(
        "UPDATE accounting.fiscal_periods SET end_date=%s WHERE id=%s",
        (f["today"], f["period"]),
    )
    return f


@pytest.mark.parametrize("full_payoff", [False, True])
def test_actual_release_day_cash_has_zero_elapsed_interest_and_exact_source(
    same_day_native, monkeypatch, tmp_path, full_payoff
):
    f = same_day_native
    applied = actual_first_application(
        f,
        monkeypatch,
        tmp_path,
        amount_override=Decimal(1200 if full_payoff else 100),
        captured_reconciliation=False,
    )
    if full_payoff:
        source = (
            f["conn"]
            .execute(
                "SELECT accounting.regular_payoff_candidate(%s) AS source",
                (applied["application_id"],),
            )
            .fetchone()["source"]
        )
        assert source["ready"], source["blockers"]
        f["conn"].execute(
            "SELECT accounting.record_regular_payoff_review(%s,%s,%s,%s,%s,%s,%s)",
            (
                applied["application_id"],
                source["source_digest"],
                uuid4(),
                "full_contractual_payoff_no_rebate",
                source["contract_evidence_reference"],
                "Actual synthetic same-day full signed-contract settlement without rebate.",
                f["actor_id"],
            ),
        )
    source, journal = post_application(f, applied)
    assert Decimal(source["measurement"]["incremental_interest"]) == 0
    assert Decimal(source["measurement"]["loan_component_after"]) == (
        0 if full_payoff else 900
    )
    assert Decimal(source["measurement"].get("settlement_difference", "0")) == (
        200 if full_payoff else 0
    )
    assert not {"1010", "1020", "1030", "1050"}.intersection(
        line["account_code"] for line in source["lines"]
    )
    assert (
        f["conn"]
        .execute(
            "SELECT exact_posted AND NOT correction_pending AS exact FROM accounting.treasury_application_posting_status WHERE journal_entry_id=%s",
            (journal,),
        )
        .fetchone()["exact"]
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    # Pure measurement of the genuine signed future maturity does not change
    # any economic source date or ask the posting path to accept future cash.
    maturity = max(row["due_date"] for row in f["installments"])
    rate = Decimal(str(source["measurement"]["daily_eir"]))
    measured = (
        f["conn"]
        .execute(
            "SELECT accounting.regular_original_interval_gross(1000,0,%s,%s,%s,%s) AS value",
            (rate, f["today"], maturity + timedelta(days=30), maturity),
        )
        .fetchone()["value"]
    )
    with localcontext() as context:
        context.prec = 50
        expected = Decimal(1000) * (1 + rate) ** (maturity - f["today"]).days
    assert abs(measured - expected) < Decimal("0.00000001")
    blocked = (
        f["conn"]
        .execute(
            "SELECT accounting.regular_closed_term_candidate(%s) AS value",
            (applied["application_id"],),
        )
        .fetchone()["value"]
    )
    assert (
        not blocked["ready"]
        and "closed_original_contract_required" in blocked["blockers"]
    )


def test_same_day_partial_payment_retains_nonzero_allowance_assessment(
    same_day_native, monkeypatch, tmp_path
):
    f = same_day_native
    applied = actual_first_application(
        f,
        monkeypatch,
        tmp_path,
        amount_override=Decimal(100),
        captured_reconciliation=False,
    )
    post_application(f, applied)
    source = (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
            (f["period"], f["loan_id"]),
        )
        .fetchone()["source"]
    )
    assert source["ready"], source["blockers"]
    evidence = (
        f["conn"]
        .execute(
            "SELECT accounting.record_ecl_forward_looking_evidence(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL) AS id",
            (
                "same-day-" + uuid4().hex,
                "Synthetic actual current forecast",
                "Explicit same-day credit loss scenarios",
                f["today"] - timedelta(days=30),
                f["today"],
                f["today"],
                f["today"] + timedelta(days=180),
                datetime.now(timezone.utc),
                f["today"],
                "Synthetic actual current credit outlook retained without source backdating.",
                f["actor_id"],
            ),
        )
        .fetchone()["id"]
    )
    risk = {
        "as_of_date": f["today"].isoformat(),
        "stage_label": "stage_1_12_month",
        "default_label": False,
        "write_off_label": "none",
        "recovery_label": "none",
        "primary_evidence_basis": "contractual_dpd",
        "evidence_reference": "Actual signed native contract",
        "review_note": "Actual first-day contractual status and current forecast reviewed.",
    }
    scenarios = [
        {
            "scenario_key": name,
            "probability": probability,
            "evidence_reference": "Synthetic explicit " + name,
            "management_rationale": "Explicit synthetic potential shortfall in the original signed receivables.",
            "forward_evidence_ids": [str(evidence)],
            "expected_cash_flows": [
                {
                    "cash_date": flow["due_date"],
                    "amount": str(Decimal(str(flow["remaining_amount"])) * multiplier),
                }
                for flow in source["snapshot"]["contractual_cash_flows"]
                if Decimal(str(flow["remaining_amount"])) > 0
            ],
        }
        for name, probability, multiplier in [
            ("base", "0.8", Decimal(1)),
            ("downside", "0.2", Decimal("0.5")),
        ]
    ]
    prepared = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
            (
                f["period"],
                f["loan_id"],
                f["actor_id"],
                source["source_digest"],
                Jsonb(risk),
                Jsonb(scenarios),
                "Actual current first-day carrying and nonzero allowance independently reviewed.",
            ),
        )
        .fetchone()["id"]
    )
    retained = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
            (prepared,),
        )
        .fetchone()
    )
    assert Decimal(str(retained["measurement_snapshot"]["ecl_amount"])) > 0
    f["conn"].execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (prepared, f["actor_id"], retained["confirmation_digest"]),
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert (
        f["conn"]
        .execute(
            "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
            (f["period"], f["loan_id"]),
        )
        .fetchone()["exact"]
    )
    audit = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_elapsed_assessment_postings WHERE preparation_id=%s",
            (prepared,),
        )
        .fetchone()
    )
    journal = audit["allowance_journal_entry_id"]
    assert (
        f["conn"]
        .execute(
            "SELECT accounting.regular_elapsed_journal_structurally_exact(%s) AS exact",
            (journal,),
        )
        .fetchone()["exact"]
    )
    # Structural admission only resolves the origin/assessment dependency. It
    # neither grants a generic journal writer nor weakens immutable evidence.
    for statement, parameters, expected_error, expected_message in (
        (
            "UPDATE accounting.loan_elapsed_assessment_postings SET posted_by=posted_by WHERE id=%s",
            (audit["id"],),
            psycopg.errors.ObjectNotInPrerequisiteState,
            "Historical assessment audits are immutable and require their protected workflow.",
        ),
        (
            "UPDATE accounting.loan_elapsed_assessment_preparations SET source_digest=repeat('0',64) WHERE id=%s",
            (prepared,),
            psycopg.errors.ObjectNotInPrerequisiteState,
            "Historical assessment audits are immutable and require their protected workflow.",
        ),
        (
            "UPDATE accounting.journal_lines SET debit=debit+1 WHERE journal_entry_id=%s AND debit>0",
            (journal,),
            psycopg.errors.RaiseException,
            "Lines of a posted journal entry are immutable.",
        ),
        (
            "INSERT INTO accounting.journal_entries(posting_date,fiscal_period_id,source_type,source_reference,source_event_key,created_by_user_id) SELECT posting_date,fiscal_period_id,source_type,source_reference,source_event_key||':forged',created_by_user_id FROM accounting.journal_entries WHERE id=%s",
            (journal,),
            psycopg.errors.ObjectNotInPrerequisiteState,
            "Protected historical journal requires the exact retained assessment.",
        ),
    ):
        with (
            pytest.raises(expected_error) as rejected,
            f["conn"].transaction(),
        ):
            f["conn"].execute(statement, parameters)
        assert rejected.value.diag.message_primary == expected_message
    assert (
        f["conn"]
        .execute(
            "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
            (f["period"], f["loan_id"]),
        )
        .fetchone()["exact"]
    )
    with f["conn"].transaction(force_rollback=True):
        f["conn"].execute(
            "UPDATE accounting.accounts SET is_posting=false WHERE code='5000'"
        )
        assert (
            not f["conn"]
            .execute(
                "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
                (f["period"], f["loan_id"]),
            )
            .fetchone()["exact"]
        )
