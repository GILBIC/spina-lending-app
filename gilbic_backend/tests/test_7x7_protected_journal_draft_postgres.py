from __future__ import annotations

import importlib.util
import os
from datetime import date, timedelta
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
PREVIEW_HELPER_PATH = TEST_DIR / "test_7x7_source_event_accounting_preview_postgres.py"
_spec = importlib.util.spec_from_file_location("x7_preview_helpers", PREVIEW_HELPER_PATH)
assert _spec is not None and _spec.loader is not None
preview_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preview_helpers)

SQL_0065 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0065_add_protected_7x7_source_event_journal_drafts.sql"
).read_text(encoding="utf-8")


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _ready_case(connection, suffix: str):
    release_date = date(2099, 1, 1)
    actor_id, loan_id, _, device_id = preview_helpers._anchored_case(
        connection,
        suffix,
        release_date,
    )
    period_id = preview_helpers._open_period(
        connection,
        suffix,
        release_date,
        release_date + timedelta(days=120),
    )
    transaction_id = preview_helpers._collection(
        connection,
        actor_id=actor_id,
        device_id=device_id,
        loan_id=loan_id,
        suffix=suffix,
        collection_date=release_date + timedelta(days=1),
        amount="50.00",
        device_sequence=1,
    )
    return actor_id, loan_id, period_id, transaction_id


def _review(connection, transaction_id):
    return connection.execute(
        """
        select transaction_id, loan_id, client_id, source_event_key,
               source_event_review_token, coordinate_digest, posting_date,
               fiscal_period_id, source_cash_amount, eir_interest_accrual,
               accounting_eir_interest_received, accounting_7x7_principal_received,
               coordinate_line_count, total_debit, total_credit,
               draft_review_ready, posting_enabled, automatic_source_posting
        from accounting.seven_by_seven_journal_draft_review
        where transaction_id = %s
        """,
        (transaction_id,),
    ).fetchone()


def _prepare(connection, actor_id, review):
    return connection.execute(
        """
        select accounting.create_seven_by_seven_journal_draft(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            'seven_by_seven_source_event_journal_draft_v1'
        )
        """,
        (
            review[0],
            actor_id,
            review[4],
            review[5],
            review[3],
            review[6],
            review[7],
            review[8],
            review[13],
            review[14],
        ),
    ).fetchone()[0]


def test_management_confirmed_7x7_draft_is_exact_immutable_and_idempotent() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0065))
            actor_id, loan_id, period_id, transaction_id = _ready_case(connection, suffix)
            review = _review(connection, transaction_id)
            assert review is not None
            assert review[0] == transaction_id
            assert review[1] == loan_id
            assert review[3] == f"collection:{transaction_id}"
            assert len(review[4]) == 64
            assert len(review[5]) == 64
            assert review[6] == date(2099, 1, 2)
            assert review[7] == period_id
            assert review[8] == 50
            assert review[9] > 0
            assert review[10] > 0
            assert review[10] + review[11] == 50
            assert review[12] in (4, 5)
            assert review[13] == review[14]
            assert review[15:] == (True, False, False)

            before_journals = connection.execute(
                "select count(*) from accounting.journal_entries where source_event_key = %s",
                (review[3],),
            ).fetchone()[0]
            assert before_journals == 0

            preparation_id = _prepare(connection, actor_id, review)
            retry_id = _prepare(connection, actor_id, review)
            assert retry_id == preparation_id

            status = connection.execute(
                """
                select preparation_id, transaction_id, journal_entry_id,
                       source_event_key, source_event_review_token, coordinate_digest,
                       journal_status, entry_number, coordinate_line_count,
                       line_count, prepared_total_debit, prepared_total_credit,
                       total_debit, total_credit, draft_integrity_ready,
                       posting_enabled, automatic_source_posting
                from accounting.seven_by_seven_journal_draft_status
                where transaction_id = %s
                """,
                (transaction_id,),
            ).fetchone()
            assert status is not None
            assert status[0] == preparation_id
            assert status[1] == transaction_id
            journal_entry_id = status[2]
            assert status[3:6] == (review[3], review[4], review[5])
            assert status[6:8] == ("draft", None)
            assert status[8] == status[9] == review[12]
            assert status[10] == status[11] == status[12] == status[13] == review[13]
            assert status[14:] == (True, False, False)

            exact_lines = connection.execute(
                """
                select line.line_number, account.system_key, line.debit, line.credit
                from accounting.journal_lines line
                join accounting.accounts account on account.id = line.account_id
                where line.journal_entry_id = %s
                order by line.line_number
                """,
                (journal_entry_id,),
            ).fetchall()
            coordinate_lines = connection.execute(
                """
                select line_number, account_system_key, debit, credit
                from accounting.seven_by_seven_source_event_journal_coordinate_preview
                where transaction_id = %s
                order by line_number
                """,
                (transaction_id,),
            ).fetchall()
            assert exact_lines == coordinate_lines
            assert sum(row[2] for row in exact_lines) == sum(row[3] for row in exact_lines)

            with pytest.raises(psycopg.Error, match="system generated and cannot be edited"):
                connection.execute(
                    "update accounting.journal_entries set description = 'tamper' where id = %s",
                    (journal_entry_id,),
                )
            connection.rollback()
        finally:
            connection.rollback()


def test_7x7_draft_fails_closed_on_stale_confirmation_or_coordinate_change() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0065))
            actor_id, _, _, transaction_id = _ready_case(connection, suffix)
            review = _review(connection, transaction_id)
            assert review is not None and review[15] is True

            with pytest.raises(psycopg.Error, match="coordinates changed"):
                connection.execute(
                    """
                    select accounting.create_seven_by_seven_journal_draft(
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'seven_by_seven_source_event_journal_draft_v1'
                    )
                    """,
                    (
                        transaction_id,
                        actor_id,
                        review[4],
                        "0" * 64,
                        review[3],
                        review[6],
                        review[7],
                        review[8],
                        review[13],
                        review[14],
                    ),
                )
            connection.rollback()

            connection.execute(_transaction_body(SQL_0065))
            actor_id, _, _, transaction_id = _ready_case(connection, suffix + "b")
            review = _review(connection, transaction_id)
            assert review is not None and review[15] is True

            custody_account_id = connection.execute(
                "select id from accounting.accounts where system_key = 'cash_collector_custody'"
            ).fetchone()[0]
            connection.execute(
                "update accounting.accounts set is_active = false where id = %s",
                (custody_account_id,),
            )
            with pytest.raises(psycopg.Error, match="coordinates changed|not coordinate-ready"):
                _prepare(connection, actor_id, review)
            connection.rollback()
        finally:
            connection.rollback()
