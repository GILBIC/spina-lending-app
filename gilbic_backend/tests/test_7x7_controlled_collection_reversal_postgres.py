from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import gilbic_backend.collection_void_repository as void_repository_module
import psycopg
import pytest
from gilbic_backend.collection_void_repository import (
    CollectionVoidRecord,
    PostgresCollectionVoidRepository,
)
from test_seven_by_seven_extra_principal_reversal_requests_postgres import (
    _seed_extra_principal_case,
    _test_connection,
)

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


def _post_seeded_extra_principal_to_accounting(
    connection,
    *,
    transaction_id,
    actor_id,
):
    loan_id, client_id, source_date = connection.execute(
        """
        select loan_id, client_id, collection_date
        from lending.collection_transactions where id = %s
        """,
        (transaction_id,),
    ).fetchone()
    # This fixture proves coexistence with a previously protected posting. Keep
    # its synthetic posting period isolated from the older 2099 accounting
    # scenarios in this module, which intentionally share one disposable DB.
    posting_date = source_date + timedelta(days=365)
    period_id = posting_helpers.draft_helpers.preview_helpers._open_period(
        connection,
        uuid4().hex[:10],
        posting_date,
        posting_date,
    )
    today = datetime.now(timezone.utc).date()
    posting_helpers.draft_helpers.preview_helpers._open_period(
        connection,
        uuid4().hex[:10],
        today,
        today,
    )
    account_rows = connection.execute(
        """
        select id, system_key
        from accounting.accounts
        where system_key in ('cash_collector_custody', 'loans_receivable_7x7')
        order by system_key
        """,
    ).fetchall()
    accounts = {system_key: account_id for account_id, system_key in account_rows}
    assert set(accounts) == {"cash_collector_custody", "loans_receivable_7x7"}

    journal_entry_id = uuid4()
    source_event_key = f"collection:{transaction_id}"
    connection.execute(
        """
        insert into accounting.journal_entries (
            id, fiscal_period_id, posting_date, description, status,
            source_type, source_reference, source_event_key, created_by_user_id
        ) values (
            %s, %s, %s, 'Protected posted Extra Principal fixture', 'draft',
            'seven_by_seven_collection', %s, %s, %s
        )
        """,
        (
            journal_entry_id,
            period_id,
            posting_date,
            str(transaction_id),
            source_event_key,
            actor_id,
        ),
    )
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            insert into accounting.journal_lines (
                journal_entry_id, line_number, account_id, description,
                debit, credit, client_id, loan_id
            ) values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                (
                    journal_entry_id,
                    1,
                    accounts["cash_collector_custody"],
                    "Extra Principal cash received",
                    33,
                    0,
                    client_id,
                    loan_id,
                ),
                (
                    journal_entry_id,
                    2,
                    accounts["loans_receivable_7x7"],
                    "Extra Principal reduction",
                    0,
                    33,
                    client_id,
                    loan_id,
                ),
            ),
        )
    preparation_id = uuid4()
    connection.execute(
        "select set_config('accounting.seven_by_seven_journal_prepare_allowed', 'on', true)"
    )
    connection.execute(
        """
        insert into accounting.seven_by_seven_journal_draft_preparations (
            id, transaction_id, loan_id, client_id, journal_entry_id,
            source_event_key, source_event_review_token, coordinate_digest,
            draft_policy_version, posting_date, fiscal_period_id,
            source_cash_amount, eir_interest_accrual,
            accounting_eir_interest_received,
            accounting_7x7_principal_received, coordinate_line_count,
            total_debit, total_credit, prepared_by_user_id
        ) values (
            %s, %s, %s, %s, %s, %s, %s, %s,
            'seven_by_seven_source_event_journal_draft_v1', %s, %s,
            33.00, 0.00, 0.00, 33.00, 2, 33.00, 33.00, %s
        )
        """,
        (
            preparation_id,
            transaction_id,
            loan_id,
            client_id,
            journal_entry_id,
            source_event_key,
            "a" * 64,
            "b" * 64,
            posting_date,
            period_id,
            actor_id,
        ),
    )
    connection.execute(
        "select set_config('accounting.seven_by_seven_journal_post_allowed', 'on', true)"
    )
    entry_number = connection.execute(
        "select accounting.post_journal_entry(%s, %s)",
        (journal_entry_id, actor_id),
    ).fetchone()[0]
    posting_id = uuid4()
    connection.execute(
        "select set_config('accounting.seven_by_seven_journal_post_record_allowed', 'on', true)"
    )
    connection.execute(
        """
        insert into accounting.seven_by_seven_journal_postings (
            id, preparation_id, transaction_id, loan_id, client_id,
            journal_entry_id, source_event_key, source_event_review_token,
            coordinate_digest, posting_review_token, draft_policy_version,
            posting_policy_version, posting_date, fiscal_period_id,
            source_cash_amount, eir_interest_accrual,
            accounting_eir_interest_received,
            accounting_7x7_principal_received, coordinate_line_count,
            total_debit, total_credit, entry_number, posted_by_user_id
        ) values (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            'seven_by_seven_source_event_journal_draft_v1',
            'seven_by_seven_source_event_journal_posting_v1',
            %s, %s, 33.00, 0.00, 0.00, 33.00, 2,
            33.00, 33.00, %s, %s
        )
        """,
        (
            posting_id,
            preparation_id,
            transaction_id,
            loan_id,
            client_id,
            journal_entry_id,
            source_event_key,
            "a" * 64,
            "b" * 64,
            "c" * 64,
            posting_date,
            period_id,
            entry_number,
            actor_id,
        ),
    )
    connection.execute(
        """
        insert into accounting.seven_by_seven_journal_posting_lines (
            posting_id, line_number, journal_component, account_id,
            account_system_key, debit, credit, client_id, loan_id
        )
        select %s, line.line_number,
               case line.line_number when 1 then 'cash_received'
                    else 'principal_received' end,
               line.account_id, account.system_key, line.debit, line.credit,
               line.client_id, line.loan_id
        from accounting.journal_lines line
        join accounting.accounts account on account.id = line.account_id
        where line.journal_entry_id = %s
        order by line.line_number
        """,
        (posting_id, journal_entry_id),
    )
    return loan_id, posting_id, journal_entry_id


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


def test_posted_extra_principal_void_reconstructs_then_posts_exact_accounting_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    adjustment_id, transaction_id, actor_id = _seed_extra_principal_case(
        include_advance=False
    )

    with psycopg.connect(DATABASE_URL) as connection:
        loan_id, posting_id, original_journal_id = (
            _post_seeded_extra_principal_to_accounting(
                connection,
                transaction_id=transaction_id,
                actor_id=actor_id,
            )
        )

    monkeypatch.setattr(void_repository_module, "open_connection", _test_connection)
    voided = PostgresCollectionVoidRepository().void_unremitted(
        actor_user_id=actor_id,
        transaction_id=transaction_id,
        reason="Reverse accounted Extra Principal receipt",
        idempotency_key=uuid4(),
    )
    assert isinstance(voided, CollectionVoidRecord)

    with psycopg.connect(DATABASE_URL) as connection:
        reversal = connection.execute(
            """
            select reversal.id, reversal.original_journal_entry_id,
                   reversal.reversal_journal_entry_id,
                   operational_reversal.id
            from accounting.seven_by_seven_journal_reversals reversal
            join lending.seven_by_seven_extra_principal_reversals operational_reversal
              on operational_reversal.collection_void_id = reversal.collection_void_id
            where reversal.transaction_id = %s
              and operational_reversal.adjustment_id = %s
            """,
            (transaction_id, adjustment_id),
        ).fetchone()
        assert reversal is not None
        assert reversal[1] == original_journal_id

        original_lines = connection.execute(
            """
            select line_number, account_id, debit, credit, client_id, loan_id
            from accounting.seven_by_seven_journal_posting_lines
            where posting_id = %s order by line_number
            """,
            (posting_id,),
        ).fetchall()
        reversal_lines = connection.execute(
            """
            select line_number, account_id, debit, credit, client_id, loan_id
            from accounting.seven_by_seven_journal_reversal_lines
            where reversal_id = %s order by line_number
            """,
            (reversal[0],),
        ).fetchall()
        assert reversal_lines == [
            (line[0], line[1], line[3], line[2], line[4], line[5])
            for line in original_lines
        ]
        assert all(line[5] == loan_id for line in reversal_lines)
        assert connection.execute(
            """
            select count(*)
            from lending.seven_by_seven_extra_principal_adjustments
            where id = %s
            """,
            (adjustment_id,),
        ).fetchone()[0] == 1


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
