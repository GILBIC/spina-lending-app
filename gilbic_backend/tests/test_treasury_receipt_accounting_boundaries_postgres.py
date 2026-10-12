from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from test_treasury_receipt_accounting_postgres import (
    MIGRATION,
    RECEIPT_FILE,
    install,
    mapping,
    post,
    prepare,
)
from test_treasury_receipt_accounting_postgres import receipt_db as _receipt_db

receipt_db = _receipt_db


@pytest.mark.parametrize("code", ["1030", "2200"])
def test_posted_receipt_chart_drift_preserves_history_but_blocks_current_coverage(
    receipt_db, code
):
    f = receipt_db
    prep = prepare(f, mapping(f))
    original = post(f, prep)
    f["conn"].execute(
        "UPDATE accounting.accounts SET account_type='expense',normal_balance='debit' WHERE code=%s",
        (code,),
    )
    state = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.treasury_receipt_posting_status WHERE receipt_id=%s",
            (f["receipt"],),
        )
        .fetchone()
    )
    assert state["exact_posted"] is True
    assert state["correction_pending"] is True
    assert post(f, prep) == original


def test_retired_receipt_cash_account_does_not_erase_historical_proof(receipt_db):
    f = receipt_db
    post(f, prepare(f, mapping(f)))
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_active=false WHERE code='1030'"
    )
    state = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.treasury_receipt_posting_status WHERE receipt_id=%s",
            (f["receipt"],),
        )
        .fetchone()
    )
    assert state == {"exact_posted": True, "correction_pending": False}


def test_receipt_cash_proof_cannot_be_erased_by_truncating_lines(receipt_db):
    f = receipt_db
    post(f, prepare(f, mapping(f)))
    with (
        pytest.raises(psycopg.Error, match="immutable|protected|receipt"),
        f["conn"].transaction(),
    ):
        f["conn"].execute("TRUNCATE accounting.journal_lines CASCADE")


def test_prepare_exact_retry_and_wrong_digest_never_create_new_review(receipt_db):
    f = receipt_db
    mapped, request = mapping(f), uuid4()
    first = prepare(f, mapped, request=request)
    assert prepare(f, mapped, request=request)["id"] == first["id"]
    with pytest.raises(psycopg.Error, match="retry"), f["conn"].transaction():
        prepare(f, mapped, request=request, digest="0" * 64)
    with pytest.raises(psycopg.Error, match="stale"), f["conn"].transaction():
        prepare(f, mapped, digest="0" * 64)
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.treasury_receipt_preparations")
        .fetchone()["n"]
        == 1
    )


@pytest.mark.parametrize(
    "change", ["chart", "extra_movement", "source_reuse", "live_permission"]
)
def test_changed_source_dependencies_fail_closed(receipt_db, change):
    f = receipt_db
    prep = prepare(f, mapping(f))
    if change == "chart":
        f["conn"].execute(
            "UPDATE accounting.accounts SET name='Changed synthetic chart definition' WHERE code='1030'"
        )
    elif change == "extra_movement":
        f["conn"].execute(
            "INSERT INTO treasury.movement_lines(id,event_id,account_id,ledger_context_id,component,signed_amount,effective_at,evidence_id) SELECT %s,event_id,account_id,ledger_context_id,'correction',-147.25,effective_at,evidence_id FROM treasury.movement_lines WHERE event_id=%s",
            (uuid4(), f["event"]),
        )
    elif change == "source_reuse":
        f["conn"].execute(
            "INSERT INTO treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount) VALUES(%s,%s,%s,'synthetic_other_source',%s,1,147.25)",
            (uuid4(), f["event"], f["context"], uuid4()),
        )
    else:
        f["conn"].execute(
            "DELETE FROM core.role_permissions WHERE permission_code='accounting.journal.manage'"
        )
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        post(f, prep)
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.treasury_receipt_postings")
        .fetchone()["n"]
        == 0
    )


def test_generic_post_cannot_admit_receipt_without_adapter_or_audit(receipt_db):
    f = receipt_db
    prep = prepare(f, mapping(f))
    source = prep["snapshot"]
    f["conn"].execute(
        "SELECT set_config('accounting.treasury_receipt_post',%s,true)",
        (str(prep["id"]),),
    )
    entry = (
        f["conn"]
        .execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id) VALUES(%s,%s,'Synthetic generic bypass','treasury_verified_receipt',%s,%s,%s) RETURNING id",
            (
                f["period"],
                f["day"],
                str(f["receipt"]),
                source["source_event_key"],
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )
    f["conn"].execute(
        "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,debit,credit,client_id) VALUES(%s,1,%s,147.25,0,%s),(%s,2,%s,0,147.25,%s)",
        (
            entry,
            source["cash_account_id"],
            f["client"],
            entry,
            source["liability_account_id"],
            f["client"],
        ),
    )
    f["conn"].execute("SELECT set_config('accounting.treasury_receipt_post','',true)")
    with (
        pytest.raises(psycopg.Error, match="protected|Protected|adapter"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "SELECT accounting.post_journal_entry(%s,%s)", (entry, f["actor"].user_id)
        )
    with pytest.raises(psycopg.Error, match="audit"), f["conn"].transaction():
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_later_revision_keeps_cash_once_proof_and_exposes_correction_pending(
    receipt_db,
):
    f = receipt_db
    prep = prepare(f, mapping(f))
    entry = post(f, prep)
    f["conn"].execute(
        "INSERT INTO treasury.event_revisions(id,event_id,version,action,classification,reason,actor_id) VALUES(%s,%s,2,'correct',NULL,'Synthetic later correction',%s)",
        (uuid4(), f["event"], f["actor"].user_id),
    )
    status = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_receipt_posting_status WHERE event_id=%s",
            (f["event"],),
        )
        .fetchone()
    )
    assert status["exact_posted"] is True and status["correction_pending"] is True
    assert post(f, prep) == entry


def test_control_account_collision_is_rejected_without_overwrite(receipt_db):
    f = receipt_db
    f["conn"].execute(
        "UPDATE accounting.accounts SET name='Existing differently defined control' WHERE code='2200'"
    )
    with pytest.raises(psycopg.Error, match="conflicts"), f["conn"].transaction():
        install(f["conn"], MIGRATION)
    assert (
        f["conn"]
        .execute("SELECT name FROM accounting.accounts WHERE code='2200'")
        .fetchone()["name"]
        == "Existing differently defined control"
    )


def test_private_receipt_tables_and_entrypoints_deny_unprivileged_role(receipt_db):
    from psycopg import sql

    f = receipt_db
    role = sql.Identifier("receipt_probe_" + uuid4().hex)
    f["conn"].execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(role))
    f["conn"].execute(sql.SQL("GRANT USAGE ON SCHEMA accounting TO {}").format(role))
    for statement in (
        "SELECT * FROM accounting.treasury_cash_mappings",
        "SELECT * FROM accounting.treasury_receipt_preparations",
        "SELECT * FROM accounting.treasury_receipt_postings",
        "SELECT * FROM accounting.treasury_receipt_posting_status",
        "SELECT accounting.treasury_receipt_coordinates(NULL,NULL)",
        "SELECT accounting.prepare_treasury_receipt(NULL,NULL,NULL,NULL,NULL)",
        "SELECT accounting.post_treasury_receipt(NULL,NULL,NULL,NULL)",
        "SELECT accounting.configure_treasury_cash_mapping(NULL,NULL,NULL,NULL,NULL,NULL,NULL)",
    ):
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege),
            f["conn"].transaction(),
        ):
            f["conn"].execute(sql.SQL("SET LOCAL ROLE {}").format(role))
            f["conn"].execute(statement)


def test_repository_verifies_private_bytes_and_preserves_exact_retry(
    receipt_db, tmp_path
):
    from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
    from gilbic_backend.treasury_authorization import TreasuryUnavailable
    from gilbic_backend.treasury_receipt_accounting_repository import (
        PostgresTreasuryReceiptAccountingRepository,
    )

    f = receipt_db

    @contextmanager
    def existing_transaction():
        with f["conn"].transaction():
            yield f["conn"]

    store = PrivateEvidenceStore(tmp_path)
    store.put(f["evidence"], RECEIPT_FILE, "application/pdf")
    repository = PostgresTreasuryReceiptAccountingRepository(
        connection_factory=existing_transaction, evidence_store=store
    )
    mapped = mapping(f)
    source = repository.review(f["actor"], receipt_id=f["receipt"], mapping_id=mapped)
    assert source["amount"] == "147.25" and source["event"]["amount"] == "147.25"
    reviewed = repository.prepare(
        f["actor"],
        receipt_id=f["receipt"],
        mapping_id=mapped,
        source_digest=source["source_digest"],
        request_id=uuid4(),
    )["preparation"]
    evidence_path = tmp_path / f"{f['evidence'].hex}.bin"
    evidence_path.write_bytes(b"tampered")
    with pytest.raises(TreasuryUnavailable, match="evidence"):
        repository.post(
            f["actor"],
            preparation_id=reviewed["id"],
            source_digest=reviewed["source_digest"],
            confirmation_token=reviewed["confirmation_token"],
        )
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.treasury_receipt_postings")
        .fetchone()["n"]
        == 0
    )
    evidence_path.write_bytes(RECEIPT_FILE)
    posted = repository.post(
        f["actor"],
        preparation_id=reviewed["id"],
        source_digest=reviewed["source_digest"],
        confirmation_token=reviewed["confirmation_token"],
    )
    assert posted["posting"]["exact_posted"] is True
    f["conn"].execute(
        "UPDATE treasury.receipts SET applied_amount=1,version=version+1 WHERE id=%s",
        (f["receipt"],),
    )
    evidence_path.unlink()
    assert (
        repository.post(
            f["actor"],
            preparation_id=reviewed["id"],
            source_digest=reviewed["source_digest"],
            confirmation_token=reviewed["confirmation_token"],
        )["journal_entry_id"]
        == posted["journal_entry_id"]
    )
