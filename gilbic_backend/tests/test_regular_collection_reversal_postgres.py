from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_ROOT = Path(__file__).resolve().parent
SQL_ROOT = TEST_ROOT.parent / "sql"
SQL_0043 = (SQL_ROOT / "0043_add_controlled_regular_collection_reversals.sql").read_text(
    encoding="utf-8"
)
SQL_0044 = (SQL_ROOT / "0044_harden_collection_void_reversal_evidence.sql").read_text(
    encoding="utf-8"
)

# Reuse the already-proven Stage 5D.17 synthetic fixture builders instead of
# creating a second independent interpretation of protected Regular posting.
_HELPER_PATH = TEST_ROOT / "test_regular_journal_posting_postgres.py"
_HELPER_SPEC = importlib.util.spec_from_file_location(
    "_stage5d17_posting_helpers",
    _HELPER_PATH,
)
assert _HELPER_SPEC is not None and _HELPER_SPEC.loader is not None
H = importlib.util.module_from_spec(_HELPER_SPEC)
_HELPER_SPEC.loader.exec_module(H)


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _create_posted_set(
    connection,
    *,
    suffix: str,
    review_char: str,
    bundle_char: str,
):
    actor_id, device_id, client_id, loan_id, base_date = H._create_fixture(
        connection, suffix
    )
    accounts = H._account_ids(connection)
    eir_date = base_date
    collection_date = base_date + H.timedelta(days=1)
    eir_period_id = H._create_period(
        connection,
        suffix=suffix,
        label="Synthetic reversal EIR",
        period_date=eir_date,
    )
    collection_period_id = H._create_period(
        connection,
        suffix=suffix,
        label="Synthetic reversal collection",
        period_date=collection_date,
    )
    transaction_id = H._create_collection(
        connection,
        suffix=suffix,
        loan_id=loan_id,
        client_id=client_id,
        actor_id=actor_id,
        device_id=device_id,
        sequence=1,
        collection_date=collection_date,
    )
    review_token = review_char * 64
    original_ids = H._create_protected_review_set(
        connection,
        actor_id=actor_id,
        client_id=client_id,
        loan_id=loan_id,
        transaction_id=transaction_id,
        eir_period_id=eir_period_id,
        eir_date=eir_date,
        collection_period_id=collection_period_id,
        collection_date=collection_date,
        accounts=accounts,
        review_token=review_token,
        bundle_token=bundle_char * 64,
    )
    posting_set_id = connection.execute(
        "select accounting.post_regular_journal_review_set(%s, %s, %s)",
        (loan_id, review_token, actor_id),
    ).fetchone()[0]
    return {
        "actor_id": actor_id,
        "loan_id": loan_id,
        "transaction_id": transaction_id,
        "collection_date": collection_date,
        "original_ids": original_ids,
        "posting_set_id": posting_set_id,
    }


def _void_time(collection_date):
    # 04:00 UTC is noon in Asia/Manila, so the protected trigger resolves the
    # same local business date without depending on the runner's own timezone.
    return datetime(
        collection_date.year,
        collection_date.month,
        collection_date.day,
        4,
        0,
        tzinfo=timezone.utc,
    )


def _insert_void_audit(connection, *, fixture, void_id, reason: str, voided_at):
    connection.execute(
        """
        insert into lending.collection_transaction_voids (
            id,
            transaction_id,
            voided_by_user_id,
            reason,
            transaction_snapshot,
            previous_covered_dates,
            state_before,
            state_after,
            voided_at
        )
        values (
            %s, %s, %s, %s,
            '{}'::jsonb,
            ARRAY[]::date[],
            '{}'::jsonb,
            '{}'::jsonb,
            %s
        )
        """,
        (
            void_id,
            fixture["transaction_id"],
            fixture["actor_id"],
            reason,
            voided_at,
        ),
    )


def _mark_voided(connection, *, fixture, reason: str, voided_at):
    connection.execute(
        """
        update lending.collection_transactions
        set is_voided = true,
            voided_at = %s,
            voided_by_user_id = %s,
            void_reason = %s
        where id = %s
        """,
        (
            voided_at,
            fixture["actor_id"],
            reason,
            fixture["transaction_id"],
        ),
    )


def _original_snapshot(connection, fixture):
    return connection.execute(
        """
        select id, status, entry_number, source_event_key, posted_by_user_id, posted_at
        from accounting.journal_entries
        where id = any(%s)
        order by posting_date, id
        """,
        (list(fixture["original_ids"]),),
    ).fetchall()


def test_controlled_regular_collection_reversal_executes_and_rolls_back_atomically() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        required = (
            "core.users",
            "core.devices",
            "lending.clients",
            "lending.loan_types",
            "lending.loans",
            "lending.collection_transactions",
            "lending.collection_transaction_voids",
            "accounting.accounts",
            "accounting.fiscal_periods",
            "accounting.journal_entries",
            "accounting.journal_lines",
            "accounting.journal_events",
        )
        for relation in required:
            if connection.execute(
                "select to_regclass(%s)",
                (relation,),
            ).fetchone()[0] is None:
                pytest.skip(f"Accounting prerequisite is not installed: {relation}")

        try:
            for migration in (H.SQL_0040, H.SQL_0041, H.SQL_0042, SQL_0043, SQL_0044):
                connection.execute(_transaction_body(migration))

            fixture = _create_posted_set(
                connection,
                suffix=f"{suffix}a",
                review_char="a",
                bundle_char="b",
            )
            original_before = _original_snapshot(connection, fixture)
            assert len(original_before) == 2
            assert all(row[1] == "posted" for row in original_before)

            # Generic General Journal reversal must not bypass the protected
            # Regular source-event path even though the journal is posted.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.create_reversal_draft(%s, %s, %s, %s)",
                        (
                            fixture["original_ids"][0],
                            fixture["actor_id"],
                            fixture["collection_date"],
                            "Forbidden generic reversal",
                        ),
                    )

            reason = "Payment posted to the wrong borrower"
            void_id = uuid4()
            voided_at = _void_time(fixture["collection_date"])
            with connection.transaction():
                _insert_void_audit(
                    connection,
                    fixture=fixture,
                    void_id=void_id,
                    reason=reason,
                    voided_at=voided_at,
                )
                _mark_voided(
                    connection,
                    fixture=fixture,
                    reason=reason,
                    voided_at=voided_at,
                )

            assert connection.execute(
                "select is_voided from lending.collection_transactions where id = %s",
                (fixture["transaction_id"],),
            ).fetchone() == (True,)

            reversal_set = connection.execute(
                """
                select
                    id,
                    posting_set_id,
                    expected_entry_count,
                    reversed_entry_count,
                    reversed_by_user_id,
                    reason
                from accounting.regular_journal_reversal_sets
                where transaction_id = %s
                  and collection_void_id = %s
                """,
                (fixture["transaction_id"], void_id),
            ).fetchone()
            assert reversal_set is not None
            assert reversal_set[1] == fixture["posting_set_id"]
            assert reversal_set[2:4] == (2, 2)
            assert reversal_set[4] == fixture["actor_id"]
            assert reversal_set[5] == reason

            reversal_rows = connection.execute(
                """
                select
                    audit.original_journal_entry_id,
                    audit.reversal_journal_entry_id,
                    journal.status,
                    journal.source_type,
                    journal.reversal_of_entry_id
                from accounting.regular_journal_reversal_entries audit
                join accounting.journal_entries journal
                  on journal.id = audit.reversal_journal_entry_id
                where audit.reversal_set_id = %s
                order by audit.sequence_order
                """,
                (reversal_set[0],),
            ).fetchall()
            assert len(reversal_rows) == 2
            assert all(row[2] == "posted" for row in reversal_rows)
            assert all(row[3] == "regular_collection_void_reversal" for row in reversal_rows)
            assert all(row[0] == row[4] for row in reversal_rows)

            mismatch_count, paired_count = connection.execute(
                """
                select
                    count(*) filter (
                        where original.debit <> reversal.credit
                           or original.credit <> reversal.debit
                           or original.account_id <> reversal.account_id
                           or original.client_id is distinct from reversal.client_id
                           or original.loan_id is distinct from reversal.loan_id
                    ),
                    count(*)
                from accounting.regular_journal_reversal_entries audit
                join accounting.journal_lines original
                  on original.journal_entry_id = audit.original_journal_entry_id
                join accounting.journal_lines reversal
                  on reversal.journal_entry_id = audit.reversal_journal_entry_id
                 and reversal.line_number = original.line_number
                where audit.reversal_set_id = %s
                """,
                (reversal_set[0],),
            ).fetchone()
            assert mismatch_count == 0
            assert paired_count == 5
            assert _original_snapshot(connection, fixture) == original_before

            # Both accounting reversal audit and the operational void evidence
            # must now be append-only at the database boundary.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.regular_journal_reversal_sets where id = %s",
                        (reversal_set[0],),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from lending.collection_transaction_voids where id = %s",
                        (void_id,),
                    )

            # Evidence mismatch must fail before a void/reversal is allowed.
            mismatch_fixture = _create_posted_set(
                connection,
                suffix=f"{suffix}m",
                review_char="e",
                bundle_char="f",
            )
            mismatch_void_id = uuid4()
            mismatch_time = _void_time(mismatch_fixture["collection_date"])
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _insert_void_audit(
                        connection,
                        fixture=mismatch_fixture,
                        void_id=mismatch_void_id,
                        reason="Evidence reason",
                        voided_at=mismatch_time,
                    )
                    _mark_voided(
                        connection,
                        fixture=mismatch_fixture,
                        reason="Different operational reason",
                        voided_at=mismatch_time,
                    )
            assert connection.execute(
                "select is_voided from lending.collection_transactions where id = %s",
                (mismatch_fixture["transaction_id"],),
            ).fetchone() == (False,)
            assert connection.execute(
                "select count(*) from lending.collection_transaction_voids where id = %s",
                (mismatch_void_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.regular_journal_reversal_sets where transaction_id = %s",
                (mismatch_fixture["transaction_id"],),
            ).fetchone()[0] == 0

            # Force the second reversal journal to fail. Because reversal creation
            # runs inside the same UPDATE transaction that marks the collection
            # voided, every reversal row and the operational void must roll back.
            failed_fixture = _create_posted_set(
                connection,
                suffix=f"{suffix}b",
                review_char="c",
                bundle_char="d",
            )
            failed_original_before = _original_snapshot(connection, failed_fixture)

            connection.execute(
                """
                create or replace function pg_temp.stage5d18_force_second_reversal_failure()
                returns trigger
                language plpgsql
                as $$
                begin
                    if new.source_type = 'regular_collection_void_reversal'
                       and old.status = 'draft'
                       and new.status = 'posted'
                       and (
                           select count(*)
                           from accounting.journal_entries candidate
                           where candidate.source_type = 'regular_collection_void_reversal'
                             and candidate.source_reference = new.source_reference
                       ) >= 2 then
                        raise exception 'Synthetic Stage 5D.18 second-reversal failure.';
                    end if;
                    return new;
                end;
                $$
                """
            )
            trigger_name = f"zz_stage5d18_force_failure_{suffix}"
            connection.execute(
                sql.SQL(
                    """
                    create trigger {}
                    before update on accounting.journal_entries
                    for each row execute function pg_temp.stage5d18_force_second_reversal_failure()
                    """
                ).format(sql.Identifier(trigger_name))
            )

            failed_reason = "Synthetic rollback proof"
            failed_void_id = uuid4()
            failed_voided_at = _void_time(failed_fixture["collection_date"])
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _insert_void_audit(
                        connection,
                        fixture=failed_fixture,
                        void_id=failed_void_id,
                        reason=failed_reason,
                        voided_at=failed_voided_at,
                    )
                    _mark_voided(
                        connection,
                        fixture=failed_fixture,
                        reason=failed_reason,
                        voided_at=failed_voided_at,
                    )

            assert connection.execute(
                """
                select is_voided, voided_at, voided_by_user_id, void_reason
                from lending.collection_transactions
                where id = %s
                """,
                (failed_fixture["transaction_id"],),
            ).fetchone() == (False, None, None, None)
            assert connection.execute(
                "select count(*) from lending.collection_transaction_voids where id = %s",
                (failed_void_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.regular_journal_reversal_sets where transaction_id = %s",
                (failed_fixture["transaction_id"],),
            ).fetchone()[0] == 0
            assert connection.execute(
                """
                select count(*)
                from accounting.journal_entries
                where source_reference = %s
                  and source_type = 'regular_collection_void_reversal'
                """,
                (str(failed_void_id),),
            ).fetchone()[0] == 0
            assert connection.execute(
                """
                select count(*)
                from accounting.journal_entries
                where reversal_of_entry_id = any(%s)
                """,
                (list(failed_fixture["original_ids"]),),
            ).fetchone()[0] == 0
            assert _original_snapshot(connection, failed_fixture) == failed_original_before
        finally:
            connection.rollback()
