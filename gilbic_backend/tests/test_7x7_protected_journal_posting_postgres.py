from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timezone
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
DRAFT_HELPER_PATH = TEST_DIR / "test_7x7_protected_journal_draft_postgres.py"
_spec = importlib.util.spec_from_file_location("x7_draft_helpers", DRAFT_HELPER_PATH)
assert _spec is not None and _spec.loader is not None
draft_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(draft_helpers)

SQL_0066 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0066_add_protected_7x7_source_event_journal_posting.sql"
).read_text(encoding="utf-8")

POSTING_POLICY = "seven_by_seven_source_event_journal_posting_v1"
POSTING_TOKEN = "d" * 64


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _posting_status(connection, transaction_id):
    return connection.execute(
        """
        select preparation_id, transaction_id, loan_id, client_id, journal_entry_id,
               source_event_key, source_event_review_token, coordinate_digest,
               posting_date, fiscal_period_id, source_cash_amount,
               eir_interest_accrual, accounting_eir_interest_received,
               accounting_7x7_principal_received, coordinate_line_count,
               prepared_total_debit, prepared_total_credit, journal_status,
               entry_number, line_count, total_debit, total_credit, posting_id,
               posting_review_token, posting_policy_version, posting_ready,
               posted_audit_exact, protected_posting_enabled, reversal_enabled,
               automatic_source_posting
        from accounting.seven_by_seven_journal_posting_status
        where transaction_id = %s
        """,
        (transaction_id,),
    ).fetchone()


def _post(connection, actor_id, status, token=POSTING_TOKEN):
    return connection.execute(
        """
        select accounting.post_seven_by_seven_journal(
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            status[0],
            actor_id,
            token,
            status[4],
            status[5],
            status[6],
            status[7],
            status[8],
            status[9],
            status[10],
            status[11],
            status[12],
            status[13],
            status[14],
            status[15],
            status[16],
            POSTING_POLICY,
        ),
    ).fetchone()[0]


def _prepared_case(connection, suffix: str):
    actor_id, loan_id, period_id, transaction_id = draft_helpers._ready_case(
        connection, suffix
    )
    review = draft_helpers._review(connection, transaction_id)
    assert review is not None and review[15] is True
    preparation_id = draft_helpers._prepare(connection, actor_id, review)
    status = _posting_status(connection, transaction_id)
    assert status is not None
    assert status[0] == preparation_id
    assert status[1] == transaction_id
    assert status[2] == loan_id
    assert status[9] == period_id
    assert status[17:19] == ("draft", None)
    assert status[19] == status[14]
    assert status[20] == status[15]
    assert status[21] == status[16]
    assert status[22:25] == (None, None, None)
    assert status[25:] == (True, False, True, False, False)
    return actor_id, loan_id, period_id, transaction_id, status


def test_explicit_management_7x7_posting_is_exact_audited_idempotent_and_void_blocked() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0066))
            actor_id, loan_id, _, transaction_id, before = _prepared_case(
                connection, suffix
            )
            journal_entry_id = before[4]

            # Generic/manual posting must still be rejected by the 0065 protected
            # journal guard; only the 0066 posting function may open the GUC.
            with pytest.raises(psycopg.Error, match="protected 7x7 posting workflow"):
                with connection.transaction():
                    connection.execute(
                        "select accounting.post_journal_entry(%s, %s)",
                        (journal_entry_id, actor_id),
                    )

            posting_id = _post(connection, actor_id, before)
            retry_id = _post(connection, actor_id, before)
            assert retry_id == posting_id

            after = _posting_status(connection, transaction_id)
            assert after is not None
            assert after[22] == posting_id
            assert after[23] == POSTING_TOKEN
            assert after[24] == POSTING_POLICY
            assert after[17] == "posted"
            assert after[18]
            assert after[25:] == (False, True, True, False, False)

            journal_lines = connection.execute(
                """
                select line.line_number, account.system_key, line.debit, line.credit,
                       line.client_id, line.loan_id
                from accounting.journal_lines line
                join accounting.accounts account on account.id = line.account_id
                where line.journal_entry_id = %s
                order by line.line_number
                """,
                (journal_entry_id,),
            ).fetchall()
            audit_lines = connection.execute(
                """
                select line_number, account_system_key, debit, credit, client_id, loan_id
                from accounting.seven_by_seven_journal_posting_lines
                where posting_id = %s
                order by line_number
                """,
                (posting_id,),
            ).fetchall()
            assert audit_lines == journal_lines
            assert len(audit_lines) == before[14]
            assert all(row[5] == loan_id for row in audit_lines)

            with pytest.raises(psycopg.Error, match="posting audit is immutable"):
                with connection.transaction():
                    connection.execute(
                        "update accounting.seven_by_seven_journal_postings set posting_review_token = %s where id = %s",
                        ("e" * 64, posting_id),
                    )

            with pytest.raises(psycopg.Error, match="posting audit is immutable"):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.seven_by_seven_journal_posting_lines where posting_id = %s",
                        (posting_id,),
                    )

            with pytest.raises(psycopg.Error, match="does not match the confirmed posting identity"):
                with connection.transaction():
                    _post(connection, actor_id, before, token="e" * 64)

            # A manual reversal journal cannot bypass the future controlled path.
            with pytest.raises(psycopg.Error, match="cannot be reversed through the manual General Journal"):
                with connection.transaction():
                    connection.execute(
                        """
                        insert into accounting.journal_entries (
                            fiscal_period_id, posting_date, description, status,
                            source_type, source_reference, source_event_key,
                            reversal_of_entry_id, created_by_user_id
                        ) values (%s, %s, 'manual reversal attempt', 'draft',
                                  'manual_reversal_attempt', %s, %s, %s, %s)
                        """,
                        (
                            before[9],
                            before[8],
                            transaction_id.hex,
                            "manual-seven-by-seven-reversal:" + uuid4().hex,
                            journal_entry_id,
                            actor_id,
                        ),
                    )

            # Supply the operational void evidence first so the 0044 evidence
            # guard passes; the new posted-7x7 guard must then stop the void until
            # the controlled reversal slice exists.
            voided_at = datetime.now(timezone.utc)
            connection.execute(
                """
                insert into lending.collection_transaction_voids (
                    transaction_id, voided_by_user_id, reason,
                    transaction_snapshot, state_before, state_after, voided_at
                ) values (%s, %s, 'test posted 7x7 void', '{}'::jsonb,
                          '{}'::jsonb, '{}'::jsonb, %s)
                """,
                (transaction_id, actor_id, voided_at),
            )
            with pytest.raises(psycopg.Error, match="cannot be voided until the protected 7x7 reversal workflow"):
                with connection.transaction():
                    connection.execute(
                        """
                        update lending.collection_transactions
                        set is_voided = true,
                            voided_at = %s,
                            voided_by_user_id = %s,
                            void_reason = 'test posted 7x7 void'
                        where id = %s
                        """,
                        (voided_at, actor_id, transaction_id),
                    )

            still_active = connection.execute(
                "select is_voided from lending.collection_transactions where id = %s",
                (transaction_id,),
            ).fetchone()[0]
            assert still_active is False
        finally:
            connection.rollback()


def test_7x7_posting_revalidates_open_period_and_rolls_back_if_audit_insert_fails() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0066))

            actor_id, _, period_id, transaction_id, status = _prepared_case(
                connection, suffix + "p"
            )
            connection.execute(
                "select accounting.set_fiscal_period_status(%s, 'review', %s)",
                (period_id, actor_id),
            )
            with pytest.raises(psycopg.Error, match="stale|open containing fiscal period"):
                with connection.transaction():
                    _post(connection, actor_id, status)
            assert connection.execute(
                "select status from accounting.journal_entries where id = %s",
                (status[4],),
            ).fetchone()[0] == "draft"

            actor_id, _, _, transaction_id, status = _prepared_case(
                connection, suffix + "a"
            )
            connection.execute(
                """
                create or replace function accounting.test_fail_7x7_posting_audit_insert()
                returns trigger language plpgsql as $$
                begin
                    raise exception 'forced 7x7 posting audit failure';
                end;
                $$
                """
            )
            connection.execute(
                """
                create trigger zz_test_fail_7x7_posting_audit_insert
                before insert on accounting.seven_by_seven_journal_postings
                for each row execute function accounting.test_fail_7x7_posting_audit_insert()
                """
            )

            with pytest.raises(psycopg.Error, match="forced 7x7 posting audit failure"):
                with connection.transaction():
                    _post(connection, actor_id, status)

            # The journal transition and immutable posting audit are one atomic
            # transaction: forcing the audit insert to fail leaves the draft intact.
            journal_state = connection.execute(
                "select status, entry_number, posted_by_user_id, posted_at from accounting.journal_entries where id = %s",
                (status[4],),
            ).fetchone()
            assert journal_state == ("draft", None, None, None)
            assert connection.execute(
                "select count(*) from accounting.seven_by_seven_journal_postings where transaction_id = %s",
                (transaction_id,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
