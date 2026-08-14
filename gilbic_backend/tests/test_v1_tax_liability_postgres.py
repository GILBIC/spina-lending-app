from __future__ import annotations

import importlib.util
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
EVIDENCE_HELPER_PATH = TEST_DIR / "test_v1_tax_evidence_postgres.py"
_spec = importlib.util.spec_from_file_location(
    "v1_tax_liability_evidence_helpers", EVIDENCE_HELPER_PATH
)
assert _spec is not None and _spec.loader is not None
tax_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tax_helpers)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0082 = (SQL_ROOT / "0082_add_v1_tax_evidence_readiness.sql").read_text(
    encoding="utf-8"
)
SQL_0083 = (SQL_ROOT / "0083_add_protected_v1_tax_liability_posting.sql").read_text(
    encoding="utf-8"
)

POSTING_POLICY = "v1_tax_liability_posting_v1"
CONFIRMATION_TOKEN = "a" * 64


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _install(connection: psycopg.Connection) -> None:
    connection.execute(_transaction_body(SQL_0082))
    connection.execute(_transaction_body(SQL_0083))


def _open_period(connection: psycopg.Connection, suffix: str, start: date, end: date):
    return connection.execute(
        """
        INSERT INTO accounting.fiscal_periods(label, start_date, end_date, status)
        VALUES(%s,%s,%s,'open') RETURNING id
        """,
        (f"V1 tax liability {suffix}", start, end),
    ).fetchone()[0]


def _queue(connection: psycopg.Connection, tax_type: str, evidence_id):
    return connection.execute(
        """
        SELECT accounting_status, accounting_blocker, journal_entry_id,
               journal_status, entry_number, fiscal_period_id, posting_id,
               expense_account_code, tax_payable_account_code,
               protected_tax_liability_posting_enabled,
               tax_settlement_enabled, tax_adjustment_reversal_enabled,
               automatic_source_posting
        FROM accounting.v1_tax_liability_queue
        WHERE tax_type=%s AND evidence_id=%s
        """,
        (tax_type, evidence_id),
    ).fetchone()


def _post(
    connection: psycopg.Connection,
    *,
    tax_type: str,
    evidence_id,
    actor_id,
    evidence_digest: str,
    tax_due: str,
    expense_code: str,
    posting_date: date,
    period_id,
    token: str = CONFIRMATION_TOKEN,
):
    return connection.execute(
        """
        SELECT accounting.post_v1_tax_liability_journal(
            %s,%s,%s,%s,%s,%s,%s,'2100',%s,%s,%s
        )
        """,
        (
            tax_type,
            evidence_id,
            actor_id,
            token,
            evidence_digest,
            tax_due,
            expense_code,
            posting_date,
            period_id,
            POSTING_POLICY,
        ),
    ).fetchone()[0]


def test_dst_tax_liability_posts_exact_expense_payable_and_blocks_generic_bypass() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id = tax_helpers._management_actor(connection, suffix)
            loan_id, client_id, event_id, release_date = tax_helpers._simple_loan(
                connection, actor_id, suffix
            )
            period_id = _open_period(
                connection,
                suffix,
                release_date,
                release_date.replace(month=12, day=31),
            )
            rule_id = tax_helpers._record_rule(
                connection,
                actor_id=actor_id,
                tax_type="documentary_stamp_tax",
                key=f"dst-post-{suffix}",
                effective_from=release_date,
                rate="0.0075000000",
                maturity_max_days=None,
                digest_char="c",
            )
            evidence_id = tax_helpers._record_dst(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                rule_id=rule_id,
                tax_due="7.40",
                token="d",
            )

            before = _queue(connection, "documentary_stamp_tax", evidence_id)
            assert before is not None
            assert before[0] == "evidence_ready"
            assert before[7:9] == ("5310", "2100")
            assert before[9:] == (True, False, False, False)

            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
                ("documentary_stamp_tax", evidence_id, actor_id),
            ).fetchone()[0]
            retry_journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
                ("documentary_stamp_tax", evidence_id, actor_id),
            ).fetchone()[0]
            assert retry_journal_id == journal_id

            journal = connection.execute(
                """
                SELECT status, entry_number, source_type, source_reference,
                       source_event_key, posting_date, fiscal_period_id
                FROM accounting.journal_entries WHERE id=%s
                """,
                (journal_id,),
            ).fetchone()
            assert journal == (
                "draft",
                None,
                "v1_tax_liability",
                f"documentary_stamp_tax:{evidence_id}",
                f"v1_tax_liability:documentary_stamp_tax:{evidence_id}",
                release_date,
                period_id,
            )

            lines = connection.execute(
                """
                SELECT line.line_number, account.code, line.debit, line.credit,
                       line.client_id, line.loan_id
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s ORDER BY line.line_number
                """,
                (journal_id,),
            ).fetchall()
            assert [(row[0], row[1], row[2], row[3]) for row in lines] == [
                (1, "5310", 7.40, 0),
                (2, "2100", 0, 7.40),
            ]
            assert all(row[4] == client_id and row[5] == loan_id for row in lines)

            with pytest.raises(psycopg.Error, match="protected Management posting function"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.post_journal_entry(%s,%s)",
                        (journal_id, actor_id),
                    )

            posting_id = _post(
                connection,
                tax_type="documentary_stamp_tax",
                evidence_id=evidence_id,
                actor_id=actor_id,
                evidence_digest="d" * 64,
                tax_due="7.40",
                expense_code="5310",
                posting_date=release_date,
                period_id=period_id,
            )
            assert _post(
                connection,
                tax_type="documentary_stamp_tax",
                evidence_id=evidence_id,
                actor_id=actor_id,
                evidence_digest="d" * 64,
                tax_due="7.40",
                expense_code="5310",
                posting_date=release_date,
                period_id=period_id,
            ) == posting_id

            after = _queue(connection, "documentary_stamp_tax", evidence_id)
            assert after is not None
            assert after[0] == "posted"
            assert after[3] == "posted"
            assert after[4] is not None
            assert after[6] == posting_id

            with pytest.raises(psycopg.Error, match="immutable retry identity"):
                with connection.transaction():
                    _post(
                        connection,
                        tax_type="documentary_stamp_tax",
                        evidence_id=evidence_id,
                        actor_id=actor_id,
                        evidence_digest="d" * 64,
                        tax_due="7.40",
                        expense_code="5310",
                        posting_date=release_date,
                        period_id=period_id,
                        token="b" * 64,
                    )

            with pytest.raises(psycopg.Error, match="posting audit is immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE accounting.v1_tax_liability_postings SET confirmation_token=%s WHERE id=%s",
                        ("f" * 64, posting_id),
                    )

            with pytest.raises(psycopg.Error, match="cannot be reversed through the manual General Journal"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.create_reversal_draft(%s,%s,%s,%s)",
                        (journal_id, actor_id, release_date, "manual tax reversal attempt"),
                    )
        finally:
            connection.rollback()


def test_percentage_tax_liability_forced_audit_failure_rolls_back_and_supersession_requests_adjustment() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, loan_id, period_id, transaction_id, source_status = (
                tax_helpers.x7_posting._prepared_case(connection, suffix)
            )
            tax_helpers.x7_posting._post(connection, actor_id, source_status)
            collection_date = connection.execute(
                "SELECT collection_date FROM lending.collection_transactions WHERE id=%s",
                (transaction_id,),
            ).fetchone()[0]
            rule_id = tax_helpers._record_rule(
                connection,
                actor_id=actor_id,
                tax_type="percentage_tax_lending",
                key=f"percentage-post-{suffix}",
                effective_from=collection_date,
                rate="0.0500000000",
                maturity_max_days=1825,
                digest_char="e",
            )
            evidence_id = tax_helpers._record_percentage(
                connection,
                actor_id=actor_id,
                transaction_id=transaction_id,
                rule_id=rule_id,
                taxable="21.00",
                principal="29.00",
                tax_due="1.05",
                digest_char="1",
            )

            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
                ("percentage_tax_lending", evidence_id, actor_id),
            ).fetchone()[0]
            prepared = _queue(connection, "percentage_tax_lending", evidence_id)
            assert prepared is not None
            assert prepared[0] == "prepared_not_posted"
            assert prepared[2] == journal_id
            assert prepared[7:9] == ("5300", "2100")

            with pytest.raises(psycopg.Error, match="Forced V1 tax-liability audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.v1_tax_liability_force_audit_failure','on',true)"
                    )
                    _post(
                        connection,
                        tax_type="percentage_tax_lending",
                        evidence_id=evidence_id,
                        actor_id=actor_id,
                        evidence_digest="1" * 64,
                        tax_due="1.05",
                        expense_code="5300",
                        posting_date=collection_date,
                        period_id=period_id,
                    )

            rolled_back = connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone()
            assert rolled_back == ("draft", None)
            assert connection.execute(
                "SELECT count(*) FROM accounting.v1_tax_liability_postings WHERE journal_entry_id=%s",
                (journal_id,),
            ).fetchone()[0] == 0

            posting_id = _post(
                connection,
                tax_type="percentage_tax_lending",
                evidence_id=evidence_id,
                actor_id=actor_id,
                evidence_digest="1" * 64,
                tax_due="1.05",
                expense_code="5300",
                posting_date=collection_date,
                period_id=period_id,
            )
            assert posting_id is not None

            evidence_v2 = tax_helpers._record_percentage(
                connection,
                actor_id=actor_id,
                transaction_id=transaction_id,
                rule_id=rule_id,
                taxable="21.00",
                principal="29.00",
                tax_due="1.05",
                digest_char="2",
                supersedes=evidence_id,
            )
            old_status = _queue(connection, "percentage_tax_lending", evidence_id)
            new_status = _queue(connection, "percentage_tax_lending", evidence_v2)
            assert old_status is not None and old_status[0] == "posted_adjustment_review_required"
            assert new_status is not None and new_status[0] == "evidence_ready"
            assert new_status[9:] == (True, False, False, False)
        finally:
            connection.rollback()


def test_zero_percentage_tax_evidence_creates_no_fake_liability_journal() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, _, _, transaction_id, source_status = (
                tax_helpers.x7_posting._prepared_case(connection, suffix)
            )
            tax_helpers.x7_posting._post(connection, actor_id, source_status)
            collection_date = connection.execute(
                "SELECT collection_date FROM lending.collection_transactions WHERE id=%s",
                (transaction_id,),
            ).fetchone()[0]
            rule_id = tax_helpers._record_rule(
                connection,
                actor_id=actor_id,
                tax_type="percentage_tax_lending",
                key=f"percentage-zero-{suffix}",
                effective_from=collection_date,
                rate="0.0500000000",
                maturity_max_days=1825,
                digest_char="7",
            )
            evidence_id = tax_helpers._record_percentage(
                connection,
                actor_id=actor_id,
                transaction_id=transaction_id,
                rule_id=rule_id,
                taxable="0.00",
                principal="50.00",
                tax_due="0.00",
                digest_char="8",
            )
            status = _queue(connection, "percentage_tax_lending", evidence_id)
            assert status is not None and status[0] == "no_liability_required"

            before = connection.execute(
                "SELECT count(*) FROM accounting.journal_entries WHERE source_event_key=%s",
                (f"v1_tax_liability:percentage_tax_lending:{evidence_id}",),
            ).fetchone()[0]
            assert before == 0

            with pytest.raises(psycopg.Error, match="No positive V1 tax liability"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
                        ("percentage_tax_lending", evidence_id, actor_id),
                    )

            after = connection.execute(
                "SELECT count(*) FROM accounting.journal_entries WHERE source_event_key=%s",
                (f"v1_tax_liability:percentage_tax_lending:{evidence_id}",),
            ).fetchone()[0]
            assert after == 0
        finally:
            connection.rollback()
