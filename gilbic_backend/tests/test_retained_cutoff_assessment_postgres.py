"""Actual cutoff measurements, protected postings, and retained no-change proof."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_ecl_allowance_posting_postgres as allowance
import test_ecl_read_only_measurement_postgres as measurement
import test_regular_journal_posting_postgres as regular
from psycopg.types.json import Jsonb
from test_source_close_guard_postgres import _connect

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0151_add_retained_cutoff_assessments.sql"
)


def _seed(conn, *, zero_loss=False):
    if os.getenv("SPINA_CUTOFF_ASSESSMENT_BASELINE") != "1":
        conn.execute(allowance._transaction_body(MIGRATION.read_text()))
    suffix = uuid4().hex
    actor = measurement._actor(conn, suffix)
    book = conn.execute("SELECT id FROM accounting.book_identity").fetchone()
    if book is None:
        book = conn.execute(
            "SELECT accounting.configure_book_identity('synthetic',%s,%s,%s,%s)",
            ("Cutoff " + suffix, "Synthetic measurement test", "a" * 64, actor),
        ).fetchone()
    cutoff = conn.execute("SELECT current_date").fetchone()[0]
    period = conn.execute(
        "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) VALUES(%s,%s,%s,'open') RETURNING id",
        ("Cutoff " + suffix, cutoff, cutoff),
    ).fetchone()[0]
    client, loan = measurement._loan(
        conn, suffix=suffix, actor_id=actor, release_date=cutoff
    )
    release = measurement._record_release(
        conn,
        loan_id=loan,
        actor_id=actor,
        business_date=cutoff,
        reference="CUTOFF-" + suffix,
    )
    measurement._prepare_and_post_release(
        conn, event_id=release, actor_id=actor, token_char="a"
    )
    measurement._register_schedule(
        conn, loan_id=loan, actor_id=actor, release_date=cutoff, suffix=suffix
    )
    measurement._review_stage(
        conn,
        loan_id=loan,
        actor_id=actor,
        stage="stage_1_12_month",
        basis="contractual_dpd",
        reference="Cutoff signed contract " + suffix,
    )
    evidence = measurement._forward_evidence(
        conn,
        actor_id=actor,
        key="cutoff-" + suffix,
        reference="Cutoff " + suffix,
    )
    measured_id = measurement._measure(
        conn,
        loan_id=loan,
        actor_id=actor,
        scenarios=measurement._scenario_payload(
            evidence_ids=[evidence],
            release_date=cutoff,
            downside_amount="50.00" if zero_loss else "40.00",
        ),
    )
    measured = conn.execute(
        "SELECT id,loan_id,measurement_version,measurement_date,calculation_digest,ecl_amount FROM accounting.ecl_quantitative_measurements WHERE id=%s",
        (measured_id,),
    ).fetchone()
    accounts = conn.execute(
        "SELECT (SELECT id FROM accounting.accounts WHERE system_key='credit_loss_expense'),(SELECT id FROM accounting.accounts WHERE system_key='allowance_expected_credit_loss')"
    ).fetchone()
    if measured[5] > 0:
        prepared = allowance._prepare(conn, actor, period, measured, accounts)
        allowance._post(conn, actor, allowance._preparation(conn, prepared))
    return {
        "conn": conn,
        "actor": actor,
        "period": period,
        "book": book[0],
        "loan": loan,
        "client": client,
        "cutoff": cutoff,
        "measurement": measured_id,
        "evidence": evidence,
        "suffix": suffix,
    }


@pytest.fixture
def cutoff_assessment(request):
    with _connect() as conn:
        try:
            yield _seed(conn, zero_loss=getattr(request, "param", None) == "zero")
        finally:
            conn.rollback()


def _candidate(case):
    return (
        case["conn"]
        .execute(
            "SELECT accounting.loan_period_assessment_candidate(%s,%s)",
            (case["period"], case["loan"]),
        )
        .fetchone()[0]
    )


def _prepare(case):
    candidate = _candidate(case)
    assert candidate["ready"], candidate["blockers"]
    return case["conn"].execute(
        "SELECT accounting.prepare_loan_period_assessment(%s,%s,%s,%s,%s)",
        (
            case["period"],
            case["loan"],
            case["actor"],
            candidate["source_digest"],
            "Reviewed actual dated source, exact carrying components, and protected allowance.",
        ),
    ).fetchone()[0], candidate["source_digest"]


def _post(case, prepared, digest):
    return (
        case["conn"]
        .execute(
            "SELECT accounting.post_loan_period_assessment(%s,%s,%s)",
            (prepared, case["actor"], digest),
        )
        .fetchone()[0]
    )


def _exact(case):
    return (
        case["conn"]
        .execute(
            "SELECT accounting.period_loan_assessment_exact(%s,%s)",
            (case["period"], case["loan"]),
        )
        .fetchone()[0]
    )


def _backdated_collection(case):
    device = uuid4()
    case["conn"].execute(
        "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) VALUES(%s,%s,%s,'web','active')",
        (device, case["actor"], device.hex),
    )
    return regular._create_collection(
        case["conn"],
        suffix=case["suffix"],
        loan_id=case["loan"],
        client_id=case["client"],
        actor_id=case["actor"],
        device_id=device,
        sequence=1,
        collection_date=case["cutoff"],
        amount="1.00",
    )


def test_actual_cutoff_proof_retains_evidence_without_manufacturing_journal(
    cutoff_assessment,
):
    case = cutoff_assessment
    conn = case["conn"]
    before = conn.execute("SELECT count(*) FROM accounting.journal_entries").fetchone()[
        0
    ]
    assert not _exact(case)
    prepared, digest = _prepare(case)
    assert not _exact(case)
    posted = _post(case, prepared, digest)
    assert _exact(case)
    assert _prepare(case) == (prepared, digest)
    assert _post(case, prepared, digest) == posted
    assert (
        conn.execute("SELECT count(*) FROM accounting.journal_entries").fetchone()[0]
        == before
    )
    assert conn.execute(
        "SELECT book_id,fiscal_period_id,loan_id,source_digest FROM accounting.loan_period_assessment_preparations WHERE id=%s",
        (prepared,),
    ).fetchone() == (case["book"], case["period"], case["loan"], digest)


def test_cutoff_confirmation_requires_an_existing_preparation(cutoff_assessment):
    case = cutoff_assessment
    with pytest.raises(psycopg.Error, match="preparation"):
        _post(case, uuid4(), "a" * 64)


def test_cutoff_prepare_rejects_wrong_digest(cutoff_assessment):
    case = cutoff_assessment
    with pytest.raises(psycopg.Error, match="changed|digest"):
        case["conn"].execute(
            "SELECT accounting.prepare_loan_period_assessment(%s,%s,%s,%s,%s)",
            (
                case["period"],
                case["loan"],
                case["actor"],
                "b" * 64,
                "Reviewed actual dated source and protected allowance evidence.",
            ),
        )


def test_later_cutoff_never_treats_unposted_eir_tail_as_no_change(cutoff_assessment):
    case = cutoff_assessment
    case["conn"].execute(
        "UPDATE accounting.fiscal_periods SET end_date=end_date+1 WHERE id=%s",
        (case["period"],),
    )
    candidate = _candidate(case)
    assert not candidate["ready"]
    assert "elapsed_eir_boundary_adapter_required" in candidate["blockers"]


def test_changed_loan_fact_stales_confirmation_and_blocks_post(cutoff_assessment):
    case = cutoff_assessment
    prepared, digest = _prepare(case)
    _post(case, prepared, digest)
    case["conn"].execute(
        "UPDATE lending.loans SET principal=principal+1 WHERE id=%s", (case["loan"],)
    )
    assert not _exact(case)
    assert not _candidate(case)["ready"]


def test_revoked_forward_evidence_stales_retained_proof(cutoff_assessment):
    case = cutoff_assessment
    prepared, digest = _prepare(case)
    _post(case, prepared, digest)
    case["conn"].execute(
        "SELECT accounting.revoke_ecl_forward_looking_evidence(%s,%s,%s)",
        (
            case["evidence"],
            "Authoritative economic source corrected after measurement",
            case["actor"],
        ),
    )
    assert not _exact(case)
    assert "dated_forward_evidence_required" in _candidate(case)["blockers"]


def test_retained_assessment_rechecks_current_actor_on_post(cutoff_assessment):
    case = cutoff_assessment
    prepared, digest = _prepare(case)
    case["conn"].execute(
        "UPDATE core.users SET status='inactive' WHERE id=%s", (case["actor"],)
    )
    with pytest.raises(psycopg.Error, match="active Management"):
        _post(case, prepared, digest)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE accounting.loan_period_assessment_preparations SET review_rationale='changed'",
        "DELETE FROM accounting.loan_period_assessment_preparations",
        "TRUNCATE accounting.loan_period_assessment_postings",
    ],
)
def test_retained_assessment_audit_is_immutable(cutoff_assessment, statement):
    case = cutoff_assessment
    prepared, digest = _prepare(case)
    _post(case, prepared, digest)
    with pytest.raises(psycopg.Error, match="immutable"):
        case["conn"].execute(statement)


def test_backdated_actual_receipt_is_retained_but_blocks_prepared_confirmation(
    cutoff_assessment,
):
    case = cutoff_assessment
    prepared, digest = _prepare(case)
    source = _backdated_collection(case)
    with (
        pytest.raises(psycopg.Error, match="changed or is blocked"),
        case["conn"].transaction(),
    ):
        _post(case, prepared, digest)
    assert (
        case["conn"]
        .execute(
            "SELECT amount FROM lending.collection_transactions WHERE id=%s", (source,)
        )
        .fetchone()[0]
        == 1
    )
    assert (
        case["conn"]
        .execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
            (case["period"],),
        )
        .fetchone()[0]
        == "open"
    )
    assert not _exact(case)


@pytest.mark.parametrize("cutoff_assessment", ["zero"], indirect=True)
def test_real_zero_ecl_calculation_needs_no_fake_allowance_journal(cutoff_assessment):
    case = cutoff_assessment
    assert (
        case["conn"]
        .execute(
            "SELECT ecl_amount FROM accounting.ecl_quantitative_measurements WHERE id=%s",
            (case["measurement"],),
        )
        .fetchone()[0]
        == 0
    )
    before = (
        case["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
    )
    prepared, digest = _prepare(case)
    _post(case, prepared, digest)
    assert _exact(case)
    assert (
        case["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
        == before
    )


def test_net_zero_unexplained_control_entries_cannot_hide_in_balances(
    cutoff_assessment,
):
    case = cutoff_assessment
    prepared, digest = _prepare(case)
    _post(case, prepared, digest)
    journal = (
        case["conn"]
        .execute(
            "SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s::jsonb)",
            (
                case["cutoff"],
                "Synthetic offsetting loan control entries",
                case["actor"],
                Jsonb(
                    [
                        {"account_code": "1100", "debit": "1.00", "credit": "0"},
                        {"account_code": "1100", "debit": "0", "credit": "1.00"},
                    ]
                ),
            ),
        )
        .fetchone()[0]
    )
    case["conn"].execute(
        "UPDATE accounting.journal_lines SET loan_id=%s,client_id=%s WHERE journal_entry_id=%s",
        (case["loan"], case["client"], journal),
    )
    case["conn"].execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)", (journal, case["actor"])
    )
    candidate = _candidate(case)
    assert candidate["snapshot"]["receivable_1100"] == 5000
    assert "unrecognized_loan_control_journal" in candidate["blockers"]
    assert not _exact(case)


def test_repeatable_read_cannot_confirm_using_a_stale_source_snapshot():
    with _connect() as other:
        other.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        other.execute(allowance._transaction_body(MIGRATION.read_text()))
        with pytest.raises(psycopg.Error, match="READ COMMITTED"):
            other.execute("SELECT accounting.lock_loan_period_assessment_sources()")
