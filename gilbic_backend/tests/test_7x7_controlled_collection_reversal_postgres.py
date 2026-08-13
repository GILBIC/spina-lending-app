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
POSTING_HELPER_PATH = TEST_DIR / "test_7x7_protected_journal_posting_postgres.py"
_spec = importlib.util.spec_from_file_location("x7_posting_helpers", POSTING_HELPER_PATH)
assert _spec is not None and _spec.loader is not None
posting_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(posting_helpers)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0066 = (SQL_ROOT / "0066_add_protected_7x7_source_event_journal_posting.sql").read_text(
    encoding="utf-8"
)
SQL_0067 = (SQL_ROOT / "0067_add_controlled_7x7_collection_reversals.sql").read_text(
    encoding="utf-8"
)
SQL_0068 = (SQL_ROOT / "0068_harden_controlled_7x7_collection_reversal_guard.sql").read_text(
    encoding="utf-8"
)


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _posted_case(connection, suffix: str):
    connection.execute(_transaction_body(SQL_0066))
    actor_id, loan_id, period_id, transaction_id, before = posting_helpers._prepared_case(
        connection, suffix
    )
    posting_id = posting_helpers._post(connection, actor_id, before)
    original_journal_id = before[4]
    connection.execute(_transaction_body(SQL_0067))
    connection.execute(_transaction_body(SQL_0068))
    return actor_id, loan_id, period_id, transaction_id, posting_id, original_journal_id


def _insert_void_evidence(connection, transaction_id, actor_id, reason: str, voided_at):
    return connection.execute(
        """
        insert into lending.collection_transaction_voids (
            transaction_id, voided_by_user_id, reason,
            transaction_snapshot, state_before, state_after, voided_at
        ) values (%s, %s, %s, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, %s)
        returning id
        """,
        (transaction_id, actor_id, reason, voided_at),
    ).fetchone()[0]


def _void_source(connection, transaction_id, actor_id, reason: str, voided_at) -> None:
    connection.execute(
        """
        update lending.collection_transactions
        set is_voided = true,
            voided_at = %s,
            voided_by_user_id = %s,
            void_reason = %s
        where id = %s and is_voided = false
        """,
        (voided_at, actor_id, reason, transaction_id),
    )


def test_posted_7x7_void_posts_exact_swap_and_is_immutably_audited() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    reason = "correct posted 7x7 collection"
    voided_at = datetime(2099, 1, 2, 4, 0, tzinfo=timezone.utc)

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            actor_id, loan_id, period_id, transaction_id, posting_id, original_journal_id = _posted_case(
                connection, suffix
            )

            posting_status = posting_helpers._posting_status(connection, transaction_id)
            assert posting_status is not None
            assert posting_status[26:] == (True, True, True, False)

            original_lines = connection.execute(
                """
                select line_number, journal_component, account_id, account_system_key,
                       debit, credit, client_id, loan_id
                from accounting.seven_by_seven_journal_posting_lines
                where posting_id = %s
                order by line_number
                """,
                (posting_id,),
            ).fetchall()
            assert original_lines

            void_id = _insert_void_evidence(
                connection, transaction_id, actor_id, reason, voided_at
            )
            _void_source(connection, transaction_id, actor_id, reason, voided_at)

            assert connection.execute(
                "select is_voided from lending.collection_transactions where id = %s",
                (transaction_id,),
            ).fetchone()[0] is True

            reversal = connection.execute(
                """
                select id, collection_void_id, posting_id, transaction_id, loan_id,
                       original_journal_entry_id, reversal_journal_entry_id,
                       original_entry_number, reversal_entry_number,
                       original_source_event_key, reversal_source_event_key,
                       reversal_posting_date, fiscal_period_id, reason,
                       expected_line_count, total_debit, total_credit, reversed_by_user_id
                from accounting.seven_by_seven_journal_reversals
                where transaction_id = %s
                """,
                (transaction_id,),
            ).fetchone()
            assert reversal is not None
            reversal_id = reversal[0]
            reversal_journal_id = reversal[6]
            assert reversal[1:6] == (
                void_id,
                posting_id,
                transaction_id,
                loan_id,
                original_journal_id,
            )
            assert reversal[9] == f"collection:{transaction_id}"
            assert reversal[10] == f"seven-by-seven-collection-void-reversal:{posting_id}"
            assert reversal[11].isoformat() == "2099-01-02"
            assert reversal[12] == period_id
            assert reversal[13] == reason
            assert reversal[14] == len(original_lines)
            assert reversal[15] == reversal[16]
            assert reversal[17] == actor_id

            original_journal = connection.execute(
                "select status, entry_number from accounting.journal_entries where id = %s",
                (original_journal_id,),
            ).fetchone()
            assert original_journal == ("posted", reversal[7])

            reversal_journal = connection.execute(
                """
                select status, entry_number, source_type, source_reference,
                       source_event_key, reversal_of_entry_id
                from accounting.journal_entries where id = %s
                """,
                (reversal_journal_id,),
            ).fetchone()
            assert reversal_journal == (
                "posted",
                reversal[8],
                "seven_by_seven_collection_reversal",
                str(void_id),
                reversal[10],
                original_journal_id,
            )

            reversal_lines = connection.execute(
                """
                select line_number, journal_component, account_id, account_system_key,
                       debit, credit, client_id, loan_id
                from accounting.seven_by_seven_journal_reversal_lines
                where reversal_id = %s order by line_number
                """,
                (reversal_id,),
            ).fetchall()
            expected_lines = [
                (line[0], line[1], line[2], line[3], line[5], line[4], line[6], line[7])
                for line in original_lines
            ]
            assert reversal_lines == expected_lines
            assert all(line[7] == loan_id for line in reversal_lines)

            actual_reversal_lines = connection.execute(
                """
                select line.line_number, snapshot.journal_component,
                       line.account_id, snapshot.account_system_key,
                       line.debit, line.credit, line.client_id, line.loan_id
                from accounting.journal_lines line
                join accounting.seven_by_seven_journal_reversal_lines snapshot
                  on snapshot.reversal_id = %s
                 and snapshot.line_number = line.line_number
                where line.journal_entry_id = %s order by line.line_number
                """,
                (reversal_id, reversal_journal_id),
            ).fetchall()
            assert actual_reversal_lines == reversal_lines

            lifecycle = connection.execute(
                """
                select reversal_audit_exact, protected_reversal_enabled,
                       automatic_source_posting
                from accounting.seven_by_seven_journal_reversal_status
                where transaction_id = %s
                """,
                (transaction_id,),
            ).fetchone()
            assert lifecycle == (True, True, False)

            retry_id = connection.execute(
                "select accounting.reverse_posted_seven_by_seven_collection(%s, %s, %s, %s, %s)",
                (transaction_id, void_id, actor_id, voided_at.date(), reason),
            ).fetchone()[0]
            assert retry_id == reversal_id

            with pytest.raises(psycopg.Error, match="actor, reason, or business date"):
                with connection.transaction():
                    connection.execute(
                        "select accounting.reverse_posted_seven_by_seven_collection(%s, %s, %s, %s, %s)",
                        (transaction_id, void_id, actor_id, voided_at.date(), reason + " changed"),
                    )

            with pytest.raises(psycopg.Error, match="reversal audit is immutable"):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.seven_by_seven_journal_reversal_lines where reversal_id = %s",
                        (reversal_id,),
                    )

            with pytest.raises(psycopg.Error, match="controlled collection-void workflow"):
                with connection.transaction():
                    connection.execute(
                        """
                        insert into accounting.journal_entries (
                            fiscal_period_id, posting_date, description, status,
                            source_type, source_reference, source_event_key,
                            reversal_of_entry_id, created_by_user_id
                        ) values (
                            %s, %s, 'manual protected 7x7 reversal attempt', 'draft',
                            'manual_reversal_attempt', %s, %s, %s, %s
                        )
                        """,
                        (
                            period_id,
                            voided_at.date(),
                            str(void_id),
                            "manual-seven-by-seven-reversal:" + uuid4().hex,
                            original_journal_id,
                            actor_id,
                        ),
                    )
        finally:
            connection.rollback()


def test_7x7_void_and_reversal_roll_back_atomically_when_audit_insert_fails() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    reason = "forced reversal audit rollback"
    voided_at = datetime(2099, 1, 2, 4, 0, tzinfo=timezone.utc)

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            actor_id, _, _, transaction_id, _, original_journal_id = _posted_case(
                connection, suffix
            )

            connection.execute(
                """
                create or replace function accounting.test_fail_7x7_reversal_audit_insert()
                returns trigger language plpgsql as $$
                begin
                    raise exception 'forced 7x7 reversal audit failure';
                end;
                $$
                """
            )
            connection.execute(
                """
                create trigger zz_test_fail_7x7_reversal_audit_insert
                before insert on accounting.seven_by_seven_journal_reversals
                for each row execute function accounting.test_fail_7x7_reversal_audit_insert()
                """
            )

            with pytest.raises(psycopg.Error, match="forced 7x7 reversal audit failure"):
                with connection.transaction():
                    _insert_void_evidence(connection, transaction_id, actor_id, reason, voided_at)
                    _void_source(connection, transaction_id, actor_id, reason, voided_at)

            assert connection.execute(
                "select is_voided from lending.collection_transactions where id = %s",
                (transaction_id,),
            ).fetchone()[0] is False
            assert connection.execute(
                "select count(*) from lending.collection_transaction_voids where transaction_id = %s",
                (transaction_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.seven_by_seven_journal_reversals where transaction_id = %s",
                (transaction_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.journal_entries where reversal_of_entry_id = %s",
                (original_journal_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select status from accounting.journal_entries where id = %s",
                (original_journal_id,),
            ).fetchone()[0] == "posted"
        finally:
            connection.rollback()
