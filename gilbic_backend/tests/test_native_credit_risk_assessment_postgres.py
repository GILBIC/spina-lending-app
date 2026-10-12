"""Actual native cutoff risk reviews, with independent lifetime loss arithmetic."""

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
from test_native_regular_same_day_cash_postgres import (
    _actual_debit,
    _complete,
    _schedule,
    actual_first_application,
    native_origin,
    payout_accounting,
    payout_database,
    post_application,
    private_fixture_configuration,
    same_day_native,
)


@pytest.fixture
def native_risk(same_day_native, monkeypatch, tmp_path, request):
    f = same_day_native
    migration = (
        Path(__file__).resolve().parents[1]
        / "sql/0168_add_native_credit_risk_assessments.sql"
    )
    if migration.exists():
        install_native_fixture_migration(f["conn"], migration)
    assert_native_schema_preserved(f["conn"], request)
    applied = actual_first_application(
        f,
        monkeypatch,
        tmp_path,
        amount_override=Decimal("100.00"),
        captured_reconciliation=False,
    )
    post_application(f, applied)
    return f


def reviewed_stage(f, stage):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.review_ecl_credit_risk_labels(%s,%s,%s,'none','none',%s,%s,%s,false,false,NULL,NULL,NULL,NULL,NULL,%s) AS id",
            (
                f["loan_id"],
                stage,
                stage == "stage_3_credit_impaired",
                "verified_qualitative_credit_event",
                "SYNTHETIC-CURRENT-RISK-" + uuid4().hex,
                "Actual current synthetic borrower risk event and signed contract reviewed.",
                f["actor_id"],
            ),
        )
        .fetchone()["id"]
    )


def lifetime_scenarios(f, source):
    evidence = (
        f["conn"]
        .execute(
            "SELECT accounting.record_ecl_forward_looking_evidence(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL) AS id",
            (
                "lifetime-" + uuid4().hex,
                "Synthetic current credit forecast",
                "Explicit lifetime credit-loss scenarios",
                f["today"] - timedelta(days=30),
                f["today"],
                f["today"],
                f["today"] + timedelta(days=180),
                datetime.now(timezone.utc),
                f["today"],
                "Actual available current forecast retained for synthetic lifetime measurement.",
                f["actor_id"],
            ),
        )
        .fetchone()["id"]
    )
    return [
        {
            "scenario_key": name,
            "probability": probability,
            "evidence_reference": "Explicit synthetic " + name,
            "management_rationale": "Independently supplied synthetic expected receipts over the remaining life.",
            "forward_evidence_ids": [str(evidence)],
            "expected_cash_flows": [
                {
                    "cash_date": flow["due_date"],
                    "amount": f"{Decimal(str(flow['remaining_amount'])) * multiplier:.2f}",
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


def test_native_stage_two_uses_retained_risk_and_lifetime_loss(native_risk):
    f = native_risk
    risk_id = reviewed_stage(f, "stage_2_lifetime")
    source = (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
            (f["period"], f["loan_id"]),
        )
        .fetchone()["source"]
    )
    assert source["ready"], source["blockers"]
    scenarios = lifetime_scenarios(f, source)
    prepared = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
            (
                f["period"],
                f["loan_id"],
                f["actor_id"],
                source["source_digest"],
                risk_id,
                Jsonb(scenarios),
                "Explicit retained Stage 2 risk and lifetime expected receipts reviewed.",
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
    measured = retained["measurement_snapshot"]
    assert measured["policy_version"] == "historical_native_lifetime_cash_shortfall_v1"
    assert measured["loss_horizon"] == "lifetime"
    assert measured["credit_risk_review_id"] == risk_id
    with localcontext() as context:
        context.prec = 50
        rate = Decimal(str(source["snapshot"]["eir"]["daily_eir"]))
        contractual_pv = sum(
            Decimal(str(flow["remaining_amount"]))
            / (1 + rate)
            ** (datetime.fromisoformat(flow["due_date"]).date() - f["today"]).days
            for flow in source["snapshot"]["contractual_cash_flows"]
        )
    assert Decimal(str(measured["ecl_amount"])) == (
        contractual_pv * Decimal("0.1")
    ).quantize(Decimal("0.01"))
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


def test_lifetime_review_cannot_be_inferred_reused_or_downgraded(native_risk):
    f = native_risk
    conn = f["conn"]
    risk_id = reviewed_stage(f, "stage_2_lifetime")
    source = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
        (f["period"], f["loan_id"]),
    ).fetchone()["source"]
    scenarios = lifetime_scenarios(f, source)
    exact_risk = {"credit_risk_review_id": risk_id}
    changed_sources = [
        source["snapshot"]
        | {"cutoff_date": (f["today"] - timedelta(days=1)).isoformat()},
        source["snapshot"] | {"dpd": 91},
        source["snapshot"] | {"due_unpaid_amount": "1.00"},
        source["snapshot"]
        | {"anchor": source["snapshot"]["anchor"] | {"schedule_id": str(uuid4())}},
    ]
    for changed in changed_sources:
        with pytest.raises(psycopg.Error), conn.transaction():
            conn.execute(
                "SELECT accounting.calculate_elapsed_assessment_ecl(%s,%s,%s)",
                (Jsonb(changed), Jsonb(exact_risk), Jsonb(scenarios)),
            )
    with pytest.raises(psycopg.Error), conn.transaction():
        conn.execute(
            "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s::bigint,%s,%s)",
            (
                f["period"],
                f["loan_id"],
                uuid4(),
                source["source_digest"],
                risk_id,
                Jsonb(scenarios),
                "Unrelated actor must never supply reviewed measurement authority.",
            ),
        )
    # A new actual authorized review supersedes the earlier decision; callers
    # cannot choose the less conservative old label or the Stage 1 JSON route.
    reviewed_stage(f, "stage_3_credit_impaired")
    for risk in [
        exact_risk,
        {
            "as_of_date": f["today"].isoformat(),
            "stage_label": "stage_1_12_month",
            "default_label": False,
            "write_off_label": "none",
            "recovery_label": "none",
            "primary_evidence_basis": "contractual_dpd",
            "evidence_reference": "signed-contract",
            "review_note": "Attempt to bypass the retained actual impaired risk decision.",
        },
    ]:
        with pytest.raises(psycopg.Error), conn.transaction():
            conn.execute(
                "SELECT accounting.calculate_elapsed_assessment_ecl(%s,%s,%s)",
                (Jsonb(source["snapshot"]), Jsonb(risk), Jsonb(scenarios)),
            )
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.loan_elapsed_assessment_preparations WHERE loan_id=%s",
            (f["loan_id"],),
        ).fetchone()["n"]
        == 0
    )


def test_retained_stage_one_keeps_twelve_month_basis_and_current_source(native_risk):
    f = native_risk
    conn = f["conn"]
    risk_id = reviewed_stage(f, "stage_1_12_month")
    source = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
        (f["period"], f["loan_id"]),
    ).fetchone()["source"]
    scenarios = lifetime_scenarios(f, source)
    prepared = conn.execute(
        "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s::bigint,%s,%s) AS id",
        (
            f["period"],
            f["loan_id"],
            f["actor_id"],
            source["source_digest"],
            risk_id,
            Jsonb(scenarios),
            "Actual retained Stage 1 review and twelve-month loss forecasts checked.",
        ),
    ).fetchone()["id"]
    retained = conn.execute(
        "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (prepared,),
    ).fetchone()
    measured = retained["measurement_snapshot"]
    assert (
        measured["policy_version"]
        == "historical_native_reviewed_12_month_cash_shortfall_v1"
    )
    assert measured["loss_horizon"] == "12_month"
    assert measured["loss_basis"] == "contractual_cash_shortfall"
    assert measured["credit_risk_review_id"] == risk_id
    assert measured["risk_review"]["stage_label"] == "stage_1_12_month"
    # Pure admission checks exercise the inherited rebuttal policy, without
    # creating false aged loans or backdating an operational risk review.
    reviewed = measured["risk_review"] | {
        "snapshot_days_past_due": 90,
        "sicr_backstop_rebutted": True,
        "default_backstop_rebutted": True,
        "rebuttal_evidence_reference": "ILLUSTRATIVE-SEPARATE-EVIDENCE",
        "rebuttal_note": "Illustrative independent evidence supports both reviewed rebuttals.",
    }
    assert conn.execute(
        "SELECT accounting.native_reviewed_stage_one_admitted(%s) AS admitted",
        (Jsonb(reviewed),),
    ).fetchone()["admitted"]
    for change in [
        {"sicr_backstop_rebutted": False},
        {"default_backstop_rebutted": False},
        {"rebuttal_evidence_reference": None},
        {"primary_evidence_basis": "contractual_dpd"},
        {"default_label": True},
    ]:
        assert not conn.execute(
            "SELECT accounting.native_reviewed_stage_one_admitted(%s) AS admitted",
            (Jsonb(reviewed | change),),
        ).fetchone()["admitted"]
    conn.execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (prepared, f["actor_id"], retained["confirmation_digest"]),
    )
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert conn.execute(
        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
        (f["period"], f["loan_id"]),
    ).fetchone()["exact"]


@pytest.mark.parametrize(
    "stage,default,write_off,recovery",
    [
        ("stage_2_lifetime", True, "none", "none"),
        ("stage_3_credit_impaired", False, "none", "none"),
        (
            "stage_3_credit_impaired",
            True,
            "supported_no_reasonable_expectation_of_recovery",
            "none",
        ),
        ("stage_3_credit_impaired", False, "none", "cash_recovery_observed"),
        ("stage_2_lifetime", False, "none", "cured"),
    ],
)
def test_existing_review_semantics_remain_explicit_without_financial_execution(
    native_risk, stage, default, write_off, recovery, monkeypatch, tmp_path
):
    f = native_risk
    conn = f["conn"]
    transaction = None
    prior_review = None
    if recovery != "none":
        prior_review = reviewed_stage(f, "stage_3_credit_impaired")

    def review_labels(recovery_transaction):
        return conn.execute(
            "SELECT accounting.review_ecl_credit_risk_labels(%s,%s,%s,%s,%s,%s,%s,%s,false,false,NULL,NULL,%s,%s,%s,%s) AS id",
            (
                f["loan_id"],
                stage,
                default,
                write_off,
                recovery,
                "verified_qualitative_credit_event",
                "SYNTHETIC-SEPARATE-RISK-EVIDENCE",
                "Explicit actual synthetic credit evidence independently reviewed for this label.",
                "SYNTHETIC-WRITEOFF-SUPPORT" if write_off != "none" else None,
                "Synthetic support evidence only; no financial writeoff executed."
                if write_off != "none"
                else None,
                recovery_transaction,
                f["actor_id"],
            ),
        ).fetchone()["id"]

    if recovery == "cash_recovery_observed":
        earlier_cash = conn.execute(
            "SELECT t.id,t.accepted_at,r.created_at AS reviewed_at "
            "FROM accounting.treasury_application_postings p "
            "JOIN lending.collection_transactions t ON t.id=p.transaction_id "
            "JOIN accounting.ecl_credit_risk_label_reviews r ON r.id=%s "
            "WHERE p.loan_id=%s",
            (prior_review, f["loan_id"]),
        ).fetchone()
        assert earlier_cash["accepted_at"] < earlier_cash["reviewed_at"]
        with (
            pytest.raises(psycopg.errors.RaiseException) as rejected,
            conn.transaction(),
        ):
            review_labels(earlier_cash["id"])
        assert rejected.value.diag.message_primary == (
            "Recovery transaction must be a later non-voided positive protected "
            "collection accepted after the prior deteriorated review."
        )
        assert (
            conn.execute(
                "SELECT id FROM accounting.ecl_credit_risk_label_reviews "
                "WHERE loan_id=%s ORDER BY review_version DESC LIMIT 1",
                (f["loan_id"],),
            ).fetchone()["id"]
            == prior_review
        )
        # Record new money through the ordinary protected receipt/application
        # workflow after the deterioration review; never rewrite chronology.
        applied = actual_first_application(
            f, monkeypatch, tmp_path, captured_reconciliation=False
        )
        _, journal = post_application(f, applied)
        later_cash = conn.execute(
            "SELECT t.id,t.accepted_at FROM accounting.treasury_application_postings p "
            "JOIN lending.collection_transactions t ON t.id=p.transaction_id "
            "WHERE p.application_id=%s",
            (applied["application_id"],),
        ).fetchone()
        assert later_cash["id"] != earlier_cash["id"]
        assert later_cash["accepted_at"] > earlier_cash["reviewed_at"]
        assert conn.execute(
            "SELECT exact_posted AND NOT correction_pending AS exact "
            "FROM accounting.treasury_application_posting_status WHERE journal_entry_id=%s",
            (journal,),
        ).fetchone()["exact"]
        transaction = later_cash["id"]
    risk_id = review_labels(transaction)
    if recovery == "cash_recovery_observed":
        retained_review = conn.execute(
            "SELECT supersedes_review_id,recovery_transaction_id "
            "FROM accounting.ecl_credit_risk_label_reviews WHERE id=%s",
            (risk_id,),
        ).fetchone()
        assert retained_review["supersedes_review_id"] == prior_review
        assert retained_review["recovery_transaction_id"] == transaction
    candidate = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
        (f["period"], f["loan_id"]),
    ).fetchone()["source"]
    assert candidate["ready"], candidate.get("blockers")
    scenarios = lifetime_scenarios(f, candidate)
    measured = conn.execute(
        "SELECT accounting.calculate_elapsed_assessment_ecl(%s,%s,%s) AS value",
        (
            Jsonb(candidate["snapshot"]),
            Jsonb({"credit_risk_review_id": risk_id}),
            Jsonb(scenarios),
        ),
    ).fetchone()["value"]
    assert measured["risk_review"]["stage_label"] == stage
    assert measured["risk_review"]["default_label"] is default
    assert measured["risk_review"]["write_off_label"] == write_off
    assert measured["risk_review"]["recovery_label"] == recovery
    assert measured["loss_basis"] == (
        "gross_carrying_less_expected_pv"
        if stage == "stage_3_credit_impaired"
        else "contractual_cash_shortfall"
    )
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.ecl_accounting_writeoffs WHERE loan_id=%s",
            (f["loan_id"],),
        ).fetchone()["n"]
        == 0
    )
