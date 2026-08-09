from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_0037 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0037_add_opening_balance_journal_draft.sql"
).read_text(encoding="utf-8")
SQL_0038 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0038_add_protected_opening_balance_journal_posting.sql"
).read_text(encoding="utf-8")


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def test_protected_opening_balance_posting_is_explicit_idempotent_and_ledger_guarded() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        required = (
            "core.users",
            "accounting.accounts",
            "accounting.fiscal_periods",
            "accounting.journal_entries",
            "accounting.opening_balance_workbooks",
            "accounting.loan_cutover_readiness",
        )
        for relation in required:
            if connection.execute("select to_regclass(%s)", (relation,)).fetchone()[0] is None:
                pytest.skip(f"Accounting prerequisite is not installed: {relation}")

        blocked = connection.execute(
            """
            select count(*)
            from accounting.loan_cutover_readiness
            where status = 'active' and readiness_status = 'blocked'
            """
        ).fetchone()[0]
        if blocked:
            pytest.skip("Test database has blocked live-style loan cutover sources")

        try:
            connection.execute(_transaction_body(SQL_0037))
            connection.execute(_transaction_body(SQL_0038))

            actor_id = connection.execute(
                """
                insert into core.users (username, full_name, status)
                values (%s, %s, 'active')
                returning id
                """,
                (f"opening-post-{suffix}", f"Opening Posting {suffix}"),
            ).fetchone()[0]

            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            cutover_date = max_end + timedelta(days=7)
            period_id = connection.execute(
                """
                insert into accounting.fiscal_periods (
                    label, start_date, end_date, status
                )
                values (%s, %s, %s, 'open')
                returning id
                """,
                (f"Synthetic opening post {suffix}", cutover_date, cutover_date),
            ).fetchone()[0]

            debit_account = connection.execute(
                """
                select id from accounting.accounts
                where code = '1010' and is_active = true and is_posting = true
                """
            ).fetchone()
            credit_account = connection.execute(
                """
                select id from accounting.accounts
                where code = '3000' and is_active = true and is_posting = true
                """
            ).fetchone()
            if debit_account is None or credit_account is None:
                pytest.skip("Required synthetic posting accounts 1010/3000 are unavailable")

            connection.execute(
                "select set_config('accounting.cutover_write_allowed', 'on', true)"
            )
            workbook_id = connection.execute(
                """
                insert into accounting.opening_balance_workbooks (
                    cutover_date,
                    status,
                    profit_loss_policy_confirmed,
                    profit_loss_policy_note,
                    created_by_user_id,
                    updated_by_user_id
                )
                values (%s, 'review_ready', true, %s, %s, %s)
                returning id
                """,
                (
                    cutover_date,
                    "Synthetic rollback-only opening balance posting test.",
                    actor_id,
                    actor_id,
                ),
            ).fetchone()[0]

            connection.execute(
                """
                insert into accounting.opening_balance_workbook_lines (
                    workbook_id,
                    account_id,
                    source_reference_amount,
                    source_basis,
                    requirement_type,
                    guidance,
                    proposed_debit,
                    proposed_credit,
                    verification_status,
                    evidence_note,
                    updated_by_user_id
                )
                values
                    (%s, %s, 100.00, 'synthetic_test', 'manual_required',
                     'Rollback-only synthetic debit.', 100.00, 0.00, 'verified', %s, %s),
                    (%s, %s, 100.00, 'synthetic_test', 'manual_required',
                     'Rollback-only synthetic credit.', 0.00, 100.00, 'verified', %s, %s)
                """,
                (
                    workbook_id,
                    debit_account[0],
                    "Synthetic cash evidence.",
                    actor_id,
                    workbook_id,
                    credit_account[0],
                    "Synthetic capital evidence.",
                    actor_id,
                ),
            )

            journal_id = connection.execute(
                "select accounting.create_opening_balance_journal_draft(%s, %s)",
                (workbook_id, actor_id),
            ).fetchone()[0]

            draft = connection.execute(
                """
                select fiscal_period_id, status, source_type, source_reference, entry_number
                from accounting.journal_entries where id = %s
                """,
                (journal_id,),
            ).fetchone()
            assert draft == (
                period_id,
                "draft",
                "opening_balance",
                str(workbook_id),
                None,
            )

            # The ordinary General Journal wrapper must remain unable to post this
            # system-generated opening balance. A savepoint keeps the synthetic
            # transaction usable after the expected database exception.
            with connection.transaction():
                with pytest.raises(psycopg.Error):
                    connection.execute(
                        "select accounting.post_manual_journal_entry(%s, %s)",
                        (journal_id, actor_id),
                    )

            still_draft = connection.execute(
                "select status, entry_number from accounting.journal_entries where id = %s",
                (journal_id,),
            ).fetchone()
            assert still_draft == ("draft", None)

            status_before = connection.execute(
                """
                select posting_ready, posting_blocker, automatic_source_posting_enabled
                from accounting.opening_balance_journal_posting_status
                where workbook_id = %s
                """,
                (workbook_id,),
            ).fetchone()
            assert status_before == (True, None, False)

            entry_number = connection.execute(
                "select accounting.post_opening_balance_journal(%s, %s)",
                (workbook_id, actor_id),
            ).fetchone()[0]
            assert str(entry_number).startswith("JE-")

            posted = connection.execute(
                """
                select status, entry_number, posted_by_user_id, posted_at
                from accounting.journal_entries where id = %s
                """,
                (journal_id,),
            ).fetchone()
            assert posted[0] == "posted"
            assert posted[1] == entry_number
            assert posted[2] == actor_id
            assert posted[3] is not None

            posting_audit = connection.execute(
                """
                select journal_entry_id, entry_number, posted_by_user_id
                from accounting.opening_balance_journal_postings
                where workbook_id = %s
                """,
                (workbook_id,),
            ).fetchone()
            assert posting_audit == (journal_id, entry_number, actor_id)

            event_count = connection.execute(
                """
                select count(*)
                from accounting.journal_events
                where journal_entry_id = %s
                  and event_type = 'posted'
                  and details ->> 'protected_posting' = 'true'
                """,
                (journal_id,),
            ).fetchone()[0]
            assert event_count == 1

            repeated_number = connection.execute(
                "select accounting.post_opening_balance_journal(%s, %s)",
                (workbook_id, actor_id),
            ).fetchone()[0]
            assert repeated_number == entry_number
            assert connection.execute(
                "select count(*) from accounting.opening_balance_journal_postings where workbook_id = %s",
                (workbook_id,),
            ).fetchone()[0] == 1
            assert connection.execute(
                """
                select count(*) from accounting.journal_events
                where journal_entry_id = %s
                  and event_type = 'posted'
                  and details ->> 'protected_posting' = 'true'
                """,
                (journal_id,),
            ).fetchone()[0] == 1

            status_after = connection.execute(
                """
                select posting_ready, posting_blocker, automatic_source_posting_enabled
                from accounting.opening_balance_journal_posting_status
                where workbook_id = %s
                """,
                (workbook_id,),
            ).fetchone()
            assert status_after == (False, "Opening-balance journal is already posted.", False)
        finally:
            connection.rollback()
