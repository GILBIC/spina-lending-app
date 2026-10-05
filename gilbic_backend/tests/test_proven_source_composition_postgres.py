"""Only exact, current application and cutoff proofs discharge their own gaps."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_ecl_read_only_measurement_postgres as measurement
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_retained_cutoff_assessment_postgres import (
    _backdated_collection,
    _exact,
    _post,
    _prepare,
)
from test_retained_cutoff_assessment_postgres import (
    cutoff_assessment as _cutoff_assessment,
)
from test_treasury_application_accounting_postgres import (
    application_db as _application_db,
)
from test_treasury_receipt_accounting_postgres import install
from treasury_application_accounting_test_support import (
    application_post,
    application_prepare,
    create_application_source,
    late_prior_collection,
)

application_db = _application_db
cutoff_assessment = _cutoff_assessment
SQL = Path(__file__).resolve().parents[1] / "sql"
MIGRATION = SQL / "0149_compose_proven_source_assessments.sql"


def _install(conn):
    # Both adapters are real protected authorities; this suite only changes
    # which retained proofs the existing source guards consume.
    install(conn, SQL / "0146_add_treasury_application_accounting.sql")
    install(conn, SQL / "0148_add_retained_cutoff_assessments.sql")
    if os.getenv("SPINA_PROVEN_COMPOSITION_BASELINE") != "1" and MIGRATION.exists():
        install(conn, MIGRATION)


def _rows(case, public=False):
    function = "period_source_blockers" if public else "period_legacy_source_blockers"
    with case["conn"].cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            f"SELECT * FROM accounting.{function}(%s)", (case["period"],)
        ).fetchall()


def _own_application_rows(case, public=False):
    return [
        row
        for row in _rows(case, public)
        if (row["source_type"], row["source_id"])
        in {
            ("collection", case["transaction"]),
            ("treasury_application", case["application"]),
        }
    ]


def test_raw_application_is_inventoried_at_collection_date_with_private_scope(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    _install(f["conn"])
    for public in (False, True):
        row = next(
            row
            for row in _own_application_rows(f, public)
            if row["source_type"] == "treasury_application"
        )
        assert row["effective_date"] == f["day"]
        assert row["account_id"] == f["wallet"]
        assert row["amount"] == 50
        assert row["reason"] == "treasury_application_protected_posting_incomplete"


def test_exact_application_clears_only_matching_collection_and_application(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    _install(f["conn"])
    before = _rows(f)
    application_post(f, application_prepare(f))
    for public in (False, True):
        assert not _own_application_rows(f, public)
        rows = _rows(f, public)
        assert any(row["source_type"] == "tax_percentage" for row in rows)
        assert {row["source_type"] for row in rows}.issuperset(
            {"eir_period_end", "ecl_period_end"}
        )
    assert any(row["source_type"] == "collection" for row in before)
    assert not any(row["source_type"] == "treasury_event" for row in _rows(f, True))


@pytest.mark.parametrize("change", ["receipt_revision", "late_prior_source"])
def test_historical_application_post_does_not_clear_changed_source(
    application_db, monkeypatch, change
):
    f = create_application_source(application_db, monkeypatch, collection_delay=1)
    _install(f["conn"])
    application_post(f, application_prepare(f))
    if change == "receipt_revision":
        f["conn"].execute(
            "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) VALUES(%s,%s,2,'correct','Synthetic retained source correction',%s)",
            (uuid4(), f["event"], f["actor"].user_id),
        )
    else:
        late_prior_collection(f)
    for public in (False, True):
        assert {row["source_type"] for row in _own_application_rows(f, public)} == {
            "collection",
            "treasury_application",
        }


def test_reversed_unposted_application_remains_visible(application_db, monkeypatch):
    f = create_application_source(application_db, monkeypatch)
    _install(f["conn"])
    f["conn"].execute(
        "UPDATE treasury.applications SET status='reversed' WHERE id=%s",
        (f["application"],),
    )
    for public in (False, True):
        assert any(
            row["source_type"] == "treasury_application"
            for row in _own_application_rows(f, public)
        )


@pytest.mark.parametrize("link", ["missing", "wrong_funding"])
def test_missing_application_transaction_cannot_hide_source(
    application_db, monkeypatch, link
):
    f = create_application_source(application_db, monkeypatch)
    _install(f["conn"])
    transaction = "invalid" if link == "missing" else str(late_prior_collection(f))
    unsupported = uuid4()
    f["conn"].execute(
        "INSERT INTO treasury.applications(id,receipt_id,account_id,ledger_context_id,amount,status,source_result,created_by,created_at) SELECT %s,receipt_id,account_id,ledger_context_id,amount,'active',%s,created_by,(%s::date+time '00:30') AT TIME ZONE 'Asia/Manila' FROM treasury.applications WHERE id=%s",
        (
            unsupported,
            Jsonb({"transaction_ids": [transaction]}),
            f["day"],
            f["application"],
        ),
    )
    f = f | {"application": unsupported}
    for public in (False, True):
        assert any(
            row["source_type"] == "treasury_application"
            and row["effective_date"] == f["day"]
            and row["account_id"] == f["wallet"]
            for row in _own_application_rows(f, public)
        )


def test_exact_cutoff_proof_clears_only_assessment_gaps(cutoff_assessment):
    f = cutoff_assessment
    _install(f["conn"])
    for public in (False, True):
        assert {row["source_type"] for row in _rows(f, public)}.issuperset(
            {"eir_period_end", "ecl_period_end", "tax_dst"}
        )
    prepared, digest = _prepare(f)
    _post(f, prepared, digest)
    for public in (False, True):
        rows = _rows(f, public)
        assert not {row["source_type"] for row in rows}.intersection(
            {"eir_period_end", "ecl_period_end"}
        )
        assert any(row["source_type"] == "tax_dst" for row in rows)
    # Remaining source obligations still reach the authoritative private gate.
    with (
        pytest.raises(psycopg.Error, match="unreconciled legacy"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "SELECT accounting.assert_period_legacy_source_complete(%s)",
            (f["period"],),
        )


def test_late_source_restores_assessment_gaps_without_erasing_confirmation(
    cutoff_assessment,
):
    f = cutoff_assessment
    _install(f["conn"])
    prepared, digest = _prepare(f)
    confirmation = _post(f, prepared, digest)
    _backdated_collection(f)
    assert not _exact(f)
    assert _post(f, prepared, digest) == confirmation
    for public in (False, True):
        assert {row["source_type"] for row in _rows(f, public)}.issuperset(
            {"eir_period_end", "ecl_period_end", "collection", "tax_percentage"}
        )


@pytest.mark.parametrize("control", ["unallocated", "negative"])
def test_assessment_composition_preserves_unallocated_and_negative_controls(
    cutoff_assessment, control
):
    f = cutoff_assessment
    _install(f["conn"])
    # The extra entry is deliberately outside the assessed loan's ledger.
    journal = (
        f["conn"]
        .execute(
            "SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s)",
            (
                f["cutoff"],
                "Synthetic separate unallocated loan control",
                f["actor"],
                Jsonb(
                    [
                        {"account_code": "1100", "debit": "1.00", "credit": "0.00"},
                        {"account_code": "1110", "debit": "0.00", "credit": "1.00"},
                    ]
                ),
            ),
        )
        .fetchone()[0]
    )
    if control == "negative":
        # An unrelated loan is needed to preserve a valid exact proof for f.loan.
        other_client, other = measurement._loan(
            f["conn"], suffix=uuid4().hex, actor_id=f["actor"], release_date=f["cutoff"]
        )
        f["conn"].execute(
            "UPDATE accounting.journal_lines SET loan_id=%s,client_id=%s WHERE journal_entry_id=%s",
            (other, other_client, journal),
        )
    f["conn"].execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)", (journal, f["actor"])
    )
    prepared, digest = _prepare(f)
    _post(f, prepared, digest)
    assert _exact(f)
    reason = (
        "unallocated_control_balance"
        if control == "unallocated"
        else "negative_1110_balance_requires_borrower_credit_review"
    )
    for public in (False, True):
        assert any(row["reason"] == reason for row in _rows(f, public))
        assert not any(
            row["source_type"] in {"eir_period_end", "ecl_period_end"}
            and row["source_id"] == f["loan"]
            for row in _rows(f, public)
        )
