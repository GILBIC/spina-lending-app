from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb
from test_treasury_application_accounting_postgres import (
    application_db as _application_db,
)
from test_treasury_receipt_accounting_postgres import RECEIPT_FILE
from treasury_application_accounting_test_support import (
    additional_loan_gl,
    application_coordinates,
    application_post,
    application_prepare,
    create_application_source,
    late_prior_collection,
)

application_db = _application_db


def test_prepare_post_exact_audit_preserves_cash_and_consumes_only_liability(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    conn = f["conn"]
    prep = application_prepare(f)
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.journal_entries WHERE source_type='treasury_receipt_application'"
        ).fetchone()["n"]
        == 0
    )
    journal = application_post(f, prep)
    assert application_post(f, prep) == journal
    status = conn.execute(
        "SELECT * FROM accounting.treasury_application_posting_status WHERE application_id=%s",
        (f["application"],),
    ).fetchone()
    assert status["exact_posted"] is True and status["correction_pending"] is False
    balances = {
        row["code"]: row["amount"]
        for row in conn.execute(
            "SELECT a.code,sum(l.debit-l.credit) AS amount FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id JOIN accounting.journal_entries j ON j.id=l.journal_entry_id WHERE j.status='posted' AND l.client_id=%s GROUP BY a.code",
            (f["client"],),
        ).fetchall()
    }
    assert balances["1030"] == Decimal("147.25")
    assert balances["2200"] == Decimal("-97.25")
    assert balances["1110"] == f["measurement"]["closing_7x7_loan_component"]
    assert balances["1120"] == f["measurement"]["closing_accrued_eir_interest"]
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_review_retry_and_confirmation_are_exact(application_db, monkeypatch):
    f = create_application_source(application_db, monkeypatch)
    request = uuid4()
    prep = application_prepare(f, request=request)
    assert application_prepare(f, request=request)["id"] == prep["id"]
    for operation in (
        lambda: application_prepare(f, request=request, digest="0" * 64),
        lambda: application_post(f, prep, digest="0" * 64),
        lambda: application_post(f, prep, token="0" * 64),
    ):
        with (
            pytest.raises(psycopg.Error, match="retry|confirmation"),
            f["conn"].transaction(),
        ):
            operation()
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.treasury_application_postings")
        .fetchone()["n"]
        == 0
    )


@pytest.mark.parametrize(
    "change",
    [
        "principal",
        "interest",
        "chart",
        "receipt_revision",
        "private_authority",
        "journal_authority",
    ],
)
def test_stale_authoritative_evidence_rejects_post(application_db, monkeypatch, change):
    f = create_application_source(application_db, monkeypatch)
    prep = application_prepare(f)
    conn = f["conn"]
    if change in {"principal", "interest"}:
        additional_loan_gl(f, code="1110" if change == "principal" else "1120")
    elif change == "chart":
        conn.execute(
            "UPDATE accounting.accounts SET name='Changed synthetic chart' WHERE code='4010'"
        )
    elif change == "receipt_revision":
        conn.execute(
            "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) VALUES(%s,%s,2,'correct','Synthetic later source correction',%s)",
            (uuid4(), f["event"], f["actor"].user_id),
        )
    elif change == "private_authority":
        conn.execute(
            "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
            (f["wallet"],),
        )
    else:
        conn.execute(
            "DELETE FROM core.role_permissions WHERE permission_code='accounting.journal.manage'"
        )
    with pytest.raises(psycopg.Error), conn.transaction():
        application_post(f, prep)
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.treasury_application_postings"
        ).fetchone()["n"]
        == 0
    )


def test_prior_borrower_liability_must_match_retained_receipts(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    additional_loan_gl(f, code="2200", loan=False)
    with (
        pytest.raises(psycopg.Error, match="liability|Liability"),
        f["conn"].transaction(),
    ):
        application_coordinates(f)


def test_eir_account_type_cannot_change_the_meaning_of_protected_coordinates(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    f["conn"].execute(
        "UPDATE accounting.accounts SET account_type='expense',normal_balance='debit' WHERE code='4010'"
    )
    with (
        pytest.raises(psycopg.Error, match="chart|Chart|account"),
        f["conn"].transaction(),
    ):
        application_coordinates(f)


def test_generic_post_cannot_bypass_exact_application_audit(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    conn = f["conn"]
    prep = application_prepare(f)
    source = prep["snapshot"]
    conn.execute(
        "SELECT set_config('accounting.treasury_application_post',%s,true)",
        (str(prep["id"]),),
    )
    journal = conn.execute(
        "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id) VALUES(%s,%s,'Synthetic generic bypass','treasury_receipt_application',%s,%s,%s) RETURNING id",
        (
            f["period"],
            f["day"],
            str(f["application"]),
            source["source_event_key"],
            f["actor"].user_id,
        ),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,debit,credit,client_id,loan_id) SELECT %s,x.line_number,x.account_id,x.debit,x.credit,x.client_id,x.loan_id FROM jsonb_to_recordset(%s) x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID)",
        (journal, Jsonb(source["lines"])),
    )
    conn.execute("SELECT set_config('accounting.treasury_application_post','',true)")
    with (
        pytest.raises(psycopg.Error, match="Protected application"),
        conn.transaction(),
    ):
        conn.execute(
            "SELECT accounting.post_journal_entry(%s,%s)", (journal, f["actor"].user_id)
        )
    with pytest.raises(psycopg.Error, match="audit"), conn.transaction():
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_late_cash_is_retained_and_flags_earlier_accounting_for_correction(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch, collection_delay=1)
    prep = application_prepare(f)
    journal = application_post(f, prep)
    prior = late_prior_collection(f)
    assert prior is not None
    status = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.treasury_application_posting_status WHERE application_id=%s",
            (f["application"],),
        )
        .fetchone()
    )
    assert status == {"exact_posted": True, "correction_pending": True}
    assert application_post(f, prep) == journal


def test_prior_unposted_financial_source_cannot_be_absorbed_by_application(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch, collection_delay=1)
    late_prior_collection(f)
    with (
        pytest.raises(psycopg.Error, match="prior loan source"),
        f["conn"].transaction(),
    ):
        application_coordinates(f)


def test_protected_source_cannot_reverse_or_use_legacy_collector_key(
    application_db, monkeypatch
):
    f = create_application_source(application_db, monkeypatch)
    conn = f["conn"]
    journal = application_post(f, application_prepare(f))
    for statement, values in (
        (
            "SELECT accounting.create_manual_reversal_draft(%s,%s,%s,'Synthetic unreviewed reversal')",
            (journal, f["actor"].user_id, f["day"]),
        ),
        (
            "UPDATE treasury.applications SET status='reversed' WHERE id=%s",
            (f["application"],),
        ),
        (
            "UPDATE lending.collection_transactions SET is_voided=true WHERE id=%s",
            (f["transaction"],),
        ),
        (
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_event_key,created_by_user_id) VALUES(%s,%s,'Synthetic spoof','manual',%s,%s)",
            (
                f["period"],
                f["day"],
                "collection:" + str(f["transaction"]),
                f["actor"].user_id,
            ),
        ),
    ):
        with pytest.raises(psycopg.Error), conn.transaction():
            if "SET is_voided=true" in statement:
                conn.execute(
                    "SELECT set_config('spina.treasury_application_reversal','on',true)"
                )
            conn.execute(statement, values)


def test_post_and_audit_are_atomic(application_db, monkeypatch):
    f = create_application_source(application_db, monkeypatch)
    prep = application_prepare(f)
    f["conn"].execute(
        "CREATE FUNCTION pg_temp.fail_application_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic audit failure'; END $$"
    )
    f["conn"].execute(
        "CREATE TRIGGER synthetic_application_audit_failure BEFORE INSERT ON accounting.treasury_application_postings FOR EACH ROW EXECUTE FUNCTION pg_temp.fail_application_audit()"
    )
    with (
        pytest.raises(psycopg.Error, match="synthetic audit failure"),
        f["conn"].transaction(),
    ):
        application_post(f, prep)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.journal_entries WHERE source_type='treasury_receipt_application'"
        )
        .fetchone()["n"]
        == 0
    )


def test_evidence_cannot_be_mutated_or_truncated(application_db, monkeypatch):
    f = create_application_source(application_db, monkeypatch)
    application_post(f, application_prepare(f))
    for statement in (
        "UPDATE accounting.treasury_application_preparations SET source_digest=repeat('0',64)",
        "DELETE FROM accounting.treasury_application_postings",
        "TRUNCATE accounting.treasury_application_postings",
        "TRUNCATE accounting.journal_lines",
    ):
        with pytest.raises(psycopg.Error), f["conn"].transaction():
            f["conn"].execute(statement)


def test_private_tables_and_functions_deny_unprivileged_role(application_db):
    conn = application_db["conn"]
    role = sql.Identifier("application_probe_" + uuid4().hex)
    conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(role))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA accounting TO {}").format(role))
    for statement in (
        "SELECT * FROM accounting.treasury_application_preparations",
        "SELECT * FROM accounting.treasury_application_postings",
        "SELECT * FROM accounting.treasury_application_posting_status",
        "SELECT accounting.treasury_application_origin(NULL)",
        "SELECT accounting.treasury_application_coordinates(NULL)",
        "SELECT accounting.prepare_treasury_application(NULL,NULL,NULL,NULL)",
        "SELECT accounting.post_treasury_application(NULL,NULL,NULL,NULL)",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(role))
            conn.execute(statement)


def test_private_bytes_are_verified_but_exact_post_retry_keeps_original_audit(
    application_db, monkeypatch, tmp_path
):
    from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
    from gilbic_backend.treasury_application_accounting_repository import (
        PostgresTreasuryApplicationAccountingRepository,
    )
    from gilbic_backend.treasury_authorization import TreasuryUnavailable

    f = create_application_source(application_db, monkeypatch)

    @contextmanager
    def existing_transaction():
        with f["conn"].transaction():
            yield f["conn"]

    store = PrivateEvidenceStore(tmp_path)
    store.put(f["evidence"], RECEIPT_FILE, "application/pdf")
    repo = PostgresTreasuryApplicationAccountingRepository(
        connection_factory=existing_transaction, evidence_store=store
    )
    source = repo.review(f["actor"], application_id=f["application"])
    assert source["amount"] == "50.00"
    prep = repo.prepare(
        f["actor"],
        application_id=f["application"],
        source_digest=source["source_digest"],
        request_id=uuid4(),
    )["preparation"]
    inputs = {
        "preparation_id": prep["id"],
        "source_digest": prep["source_digest"],
        "confirmation_token": prep["confirmation_token"],
    }
    evidence_path = tmp_path / f"{f['evidence'].hex}.bin"
    evidence_path.write_bytes(b"tampered")
    with pytest.raises(TreasuryUnavailable, match="evidence"):
        repo.post(f["actor"], **inputs)
    evidence_path.write_bytes(RECEIPT_FILE)
    posted = repo.post(f["actor"], **inputs)
    assert posted["posting"]["exact_posted"] is True
    evidence_path.unlink()
    assert (
        repo.post(f["actor"], **inputs)["journal_entry_id"]
        == posted["journal_entry_id"]
    )
