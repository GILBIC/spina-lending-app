"""Receipt cash is recognized once, with retained evidence and an equal liability."""

import hashlib
import os
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from treasury_test_support import actor, connect, grant_live

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
MIGRATION = SQL_ROOT / "0145_add_treasury_receipt_accounting.sql"
RECEIPT_FILE = b"%PDF-1.4\nSynthetic receipt evidence\n%%EOF"


def install(conn, path):
    source = path.read_text(encoding="utf-8").strip()
    conn.execute(source[len("BEGIN;") : -len("COMMIT;")])


def seed(conn, *, install_migrations=True, book_kind="owner_operations"):
    if install_migrations:
        install(conn, SQL_ROOT / "0144_add_accounting_book_identity.sql")
        if MIGRATION.exists():
            install(conn, MIGRATION)
    manager = actor(conn)
    grant_live(conn, manager.user_id, "treasury.view", "treasury.account.manage")
    book = conn.execute(
        "SELECT accounting.configure_book_identity(%s,'Synthetic receipt book','test:receipt-book',%s,%s)",
        (book_kind, "a" * 64, manager.user_id),
    ).fetchone()["configure_book_identity"]
    context, wallet, evidence, client, event, receipt = (uuid4() for _ in range(6))
    conn.execute(
        "INSERT INTO treasury.contexts(id,kind,created_by) VALUES(%s,%s,%s)",
        (context, book_kind, manager.user_id),
    )
    conn.execute(
        "INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) VALUES(%s,%s,'gcash','Synthetic receipt wallet',%s,%s)",
        (
            wallet,
            context,
            {
                "owner_operations": "owner_business",
                "corporate_legal": "corporate",
                "synthetic": "synthetic",
            }[book_kind],
            manager.user_id,
        ),
    )
    conn.execute(
        "INSERT INTO treasury.account_access(account_id,user_id,permissions,private_history,granted_by) VALUES(%s,%s,ARRAY['treasury.view','treasury.account.manage'],true,%s)",
        (wallet, manager.user_id, manager.user_id),
    )
    conn.execute(
        "INSERT INTO treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256) VALUES(%s,%s,%s,%s,'recipient','application/pdf',%s,%s)",
        (
            evidence,
            wallet,
            manager.user_id,
            manager.registered_device_id,
            len(RECEIPT_FILE),
            hashlib.sha256(RECEIPT_FILE).hexdigest(),
        ),
    )
    conn.execute(
        "INSERT INTO lending.clients(id,client_code,full_name) VALUES(%s,%s,'Synthetic receipt borrower')",
        (client, client.hex),
    )
    start = conn.execute(
        "SELECT least(coalesce(min(start_date)-20,DATE '2000-01-01'),DATE '2000-01-01') AS day FROM accounting.fiscal_periods"
    ).fetchone()["day"]
    period = conn.execute(
        "SELECT accounting.create_fiscal_period('Synthetic receipt period',%s,%s,%s)",
        (start, start + timedelta(days=9), manager.user_id),
    ).fetchone()["create_fiscal_period"]
    effective = datetime.combine(
        start + timedelta(days=1), time(0, 30), tzinfo=timezone(timedelta(hours=8))
    )
    conn.execute(
        """INSERT INTO treasury.events(id,account_id,ledger_context_id,provider,reference,direction,amount,fee,effective_at,recorded_by_user_id,verified_by_user_id,device_id,evidence_id,recipient_attestation,classification,reason)
        VALUES(%s,%s,%s,'gcash',%s,'credit',147.25,0,%s,%s,%s,%s,%s,'Synthetic recipient verification','borrower_receipt','Synthetic test')""",
        (
            event,
            wallet,
            context,
            event.hex,
            effective,
            manager.user_id,
            manager.user_id,
            manager.registered_device_id,
            evidence,
        ),
    )
    conn.execute(
        "INSERT INTO treasury.movement_lines(id,event_id,account_id,ledger_context_id,component,signed_amount,effective_at,evidence_id) VALUES(%s,%s,%s,%s,'principal',147.25,%s,%s)",
        (uuid4(), event, wallet, context, effective, evidence),
    )
    conn.execute(
        "INSERT INTO treasury.receipts(id,event_id,account_id,ledger_context_id,client_id,amount,effective_at) VALUES(%s,%s,%s,%s,%s,147.25,%s)",
        (receipt, event, wallet, context, client, effective),
    )
    return {
        "conn": conn,
        "actor": manager,
        "book": book,
        "context": context,
        "wallet": wallet,
        "evidence": evidence,
        "client": client,
        "event": event,
        "receipt": receipt,
        "period": period,
        "day": effective.date(),
    }


@pytest.fixture
def receipt_db():
    if not os.getenv("GILBIC_TEST_DATABASE_URL"):
        pytest.skip("Explicit disposable PostgreSQL URL required")
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    with connect() as conn:
        try:
            yield seed(conn)
        finally:
            conn.rollback()


def mapping(f, *, request=None, version=0, reference="test:reviewed-wallet-mapping"):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.configure_treasury_cash_mapping(%s,'1030',%s,%s,%s,%s,%s) AS id",
            (
                f["wallet"],
                version,
                request or uuid4(),
                reference,
                "c" * 64,
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )


def coordinates(f, mapping_id):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.treasury_receipt_coordinates(%s,%s) AS result",
            (f["receipt"], mapping_id),
        )
        .fetchone()["result"]
    )


def prepare(f, mapping_id, *, request=None, digest=None):
    source = coordinates(f, mapping_id)
    prep = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_treasury_receipt(%s,%s,%s,%s,%s) AS id",
            (
                f["receipt"],
                mapping_id,
                digest or source["source_digest"],
                request or uuid4(),
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )
    return (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_receipt_preparations WHERE id=%s",
            (prep,),
        )
        .fetchone()
    )


def post(f, prep, *, token=None, digest=None):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.post_treasury_receipt(%s,%s,%s,%s) AS id",
            (
                prep["id"],
                digest or prep["source_digest"],
                token or prep["confirmation_token"],
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )


def test_reviewed_receipt_adapter_exists_without_seeded_mappings(receipt_db):
    conn = receipt_db["conn"]
    assert (
        conn.execute(
            "SELECT to_regclass('accounting.treasury_cash_mappings') AS relation"
        ).fetchone()["relation"]
        is not None
    ), "Receipt accounting migration is missing"
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.treasury_cash_mappings"
        ).fetchone()["n"]
        == 0
    )
    assert conn.execute(
        "SELECT code,account_type,normal_balance FROM accounting.accounts WHERE system_key='unapplied_borrower_funds'"
    ).fetchone() == {
        "code": "2200",
        "account_type": "liability",
        "normal_balance": "credit",
    }


def test_prepare_retains_exact_coordinates_without_moving_cash(receipt_db):
    f = receipt_db
    prep = prepare(f, mapping(f))
    assert prep["snapshot"]["posting_date"] == f["day"].isoformat()
    assert Decimal(prep["snapshot"]["amount"]) == Decimal("147.25")
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.journal_entries WHERE source_event_key=%s",
            ("treasury_receipt:" + str(f["event"]),),
        )
        .fetchone()["n"]
        == 0
    )


def test_post_records_exact_cash_and_liability_once_with_immutable_audit(receipt_db):
    f = receipt_db
    prep = prepare(f, mapping(f))
    entry = post(f, prep)
    assert post(f, prep) == entry
    lines = (
        f["conn"]
        .execute(
            "SELECT a.code,l.debit,l.credit,l.client_id,l.loan_id FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=%s ORDER BY l.line_number",
            (entry,),
        )
        .fetchall()
    )
    assert lines == [
        {
            "code": "1030",
            "debit": Decimal("147.25"),
            "credit": Decimal(0),
            "client_id": f["client"],
            "loan_id": None,
        },
        {
            "code": "2200",
            "debit": Decimal(0),
            "credit": Decimal("147.25"),
            "client_id": f["client"],
            "loan_id": None,
        },
    ]
    status = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_receipt_posting_status WHERE event_id=%s",
            (f["event"],),
        )
        .fetchone()
    )
    assert status["exact_posted"] is True and status["correction_pending"] is False
    assert status["journal_entry_id"] == entry and status["book_id"] == f["book"]
    with pytest.raises(psycopg.Error, match="immutable"), f["conn"].transaction():
        f["conn"].execute(
            "UPDATE accounting.treasury_receipt_postings SET source_digest=%s",
            ("f" * 64,),
        )


def test_mapping_exact_retry_and_changed_request_conflict(receipt_db):
    f = receipt_db
    request = uuid4()
    first = mapping(f, request=request)
    assert mapping(f, request=request) == first
    with pytest.raises(psycopg.Error, match="retry|request"), f["conn"].transaction():
        mapping(f, request=request, reference="changed")
    with pytest.raises(psycopg.Error, match="immutable"), f["conn"].transaction():
        f["conn"].execute(
            "DELETE FROM accounting.treasury_cash_mappings WHERE id=%s", (first,)
        )


def test_changed_mapping_invalidates_unposted_preparation(receipt_db):
    f = receipt_db
    prep = prepare(f, mapping(f))
    mapping(f, version=1)
    with pytest.raises(psycopg.Error, match="mapping|stale"), f["conn"].transaction():
        post(f, prep)


@pytest.mark.parametrize(
    "change", ["applied", "refunded", "corrected", "classification"]
)
def test_changed_source_cannot_post_old_preparation(receipt_db, change):
    f = receipt_db
    prep = prepare(f, mapping(f))
    if change in {"applied", "refunded"}:
        column = "applied_amount" if change == "applied" else "refunded_amount"
        f["conn"].execute(
            f"UPDATE treasury.receipts SET {column}=1,version=version+1 WHERE id=%s",
            (f["receipt"],),
        )
    else:
        f["conn"].execute(
            "INSERT INTO treasury.event_revisions(id,event_id,version,action,classification,reason,actor_id) VALUES(%s,%s,2,%s,%s,'Synthetic changed source',%s)",
            (
                uuid4(),
                f["event"],
                "correct" if change == "corrected" else "classify",
                None if change == "corrected" else "unclassified",
                f["actor"].user_id,
            ),
        )
    with (
        pytest.raises(psycopg.Error, match="source|receipt|revision|correct|applied"),
        f["conn"].transaction(),
    ):
        post(f, prep)


def test_exact_post_retry_survives_later_operational_application(receipt_db):
    f = receipt_db
    prep = prepare(f, mapping(f))
    entry = post(f, prep)
    f["conn"].execute(
        "UPDATE treasury.receipts SET applied_amount=1,version=version+1 WHERE id=%s",
        (f["receipt"],),
    )
    assert post(f, prep) == entry
    with (
        pytest.raises(psycopg.Error, match="confirmation|retry"),
        f["conn"].transaction(),
    ):
        post(f, prep, token="0" * 64)


def test_preparation_cannot_be_manually_reversed_or_spoofed(receipt_db):
    f = receipt_db
    prep = prepare(f, mapping(f))
    entry = post(f, prep)
    with (
        pytest.raises(psycopg.Error, match="protected|receipt|adapter"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "SELECT accounting.create_manual_reversal_draft(%s,%s,%s,'Unreviewed reversal')",
            (entry, f["actor"].user_id, f["day"]),
        )
    with (
        pytest.raises(psycopg.Error, match="protected|receipt|adapter"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_event_key,created_by_user_id) VALUES(%s,%s,'Spoof','treasury_verified_receipt',%s,%s)",
            (
                f["period"],
                f["day"],
                "treasury_receipt:" + str(uuid4()),
                f["actor"].user_id,
            ),
        )


def test_revoked_private_account_access_blocks_current_actor(receipt_db):
    f = receipt_db
    prep = prepare(f, mapping(f))
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
        (f["wallet"],),
    )
    with (
        pytest.raises(psycopg.Error, match="permission|private|Management"),
        f["conn"].transaction(),
    ):
        post(f, prep)


def test_post_and_audit_failure_roll_back_all_gl_effects(receipt_db):
    f = receipt_db
    prep = prepare(f, mapping(f))
    f["conn"].execute(
        """CREATE FUNCTION pg_temp.fail_receipt_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic audit failure'; END $$"""
    )
    f["conn"].execute(
        "CREATE TRIGGER synthetic_receipt_audit_failure BEFORE INSERT ON accounting.treasury_receipt_postings FOR EACH ROW EXECUTE FUNCTION pg_temp.fail_receipt_audit()"
    )
    with (
        pytest.raises(psycopg.Error, match="synthetic audit failure"),
        f["conn"].transaction(),
    ):
        post(f, prep)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.journal_entries WHERE source_event_key=%s",
            ("treasury_receipt:" + str(f["event"]),),
        )
        .fetchone()["n"]
        == 0
    )
