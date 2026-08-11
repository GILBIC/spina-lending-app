from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
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

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0040 = (SQL_ROOT / "0040_add_protected_regular_journal_drafts.sql").read_text(
    encoding="utf-8"
)
SQL_0041 = (SQL_ROOT / "0041_harden_regular_journal_manual_post_guard.sql").read_text(
    encoding="utf-8"
)
SQL_0042 = (SQL_ROOT / "0042_add_protected_regular_journal_posting.sql").read_text(
    encoding="utf-8"
)
SQL_0043 = (SQL_ROOT / "0043_add_controlled_regular_collection_reversals.sql").read_text(
    encoding="utf-8"
)


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _create_fixture(connection, suffix: str):
    actor_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"regular-reversal-{suffix}", f"Regular Reversal {suffix}"),
    ).fetchone()[0]
    device_id = connection.execute(
        """
        insert into core.devices (
            user_id, device_identifier_hash, platform, status
        )
        values (%s, %s, 'desktop', 'active')
        returning id
        """,
        (actor_id, f"regular-reversal-device-{suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        )
        values (%s, %s, 120, 'fixed_daily', 0)
        returning id
        """,
        (f"RR-{suffix}", f"Regular Reversal {suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"RR-C-{suffix}", f"Regular Reversal Client {suffix}"),
    ).fetchone()[0]

    max_end = connection.execute(
        "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
    ).fetchone()[0]
    release_date = max_end + timedelta(days=7)
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number,
            client_id,
            loan_type_id,
            principal,
            daily_amount,
            date_released,
            due_date,
            status
        )
        values (%s, %s, %s, 1000.00, 10.00, %s, %s, 'active')
        returning id
        """,
        (
            f"RR-L-{suffix}",
            client_id,
            loan_type_id,
            release_date,
            release_date + timedelta(days=120),
        ),
    ).fetchone()[0]
    return actor_id, device_id, client_id, loan_id, release_date


def _create_period(connection, *, suffix: str, label: str, period_date):
    return connection.execute(
        """
        insert into accounting.fiscal_periods (
            label, start_date, end_date, status
        )
        values (%s, %s, %s, 'open')
        returning id
        """,
        (f"{label} {suffix}", period_date, period_date),
    ).fetchone()[0]


def _account_ids(connection):
    required = {
        "accrued_interest_receivable",
        "interest_income_regular",
        "cash_collector_custody",
        "loans_receivable_regular",
    }
    rows = connection.execute(
        """
        select system_key, id
        from accounting.accounts
        where system_key = any(%s)
          and is_active = true
          and is_posting = true
        """,
        (list(required),),
    ).fetchall()
    result = {str(key): account_id for key, account_id in rows}
    if set(result) != required:
        pytest.skip("Required protected Regular accounting system accounts are unavailable")
    return result


def _create_collection(
    connection,
    *,
    suffix: str,
    loan_id,
    client_id,
    actor_id,
    device_id,
    sequence: int,
    collection_date,
):
    return connection.execute(
        """
        insert into lending.collection_transactions (
            idempotency_key,
            loan_id,
            client_id,
            collector_user_id,
            registered_device_id,
            route_entry_id,
            collection_date,
            entry_type,
            amount,
            recorded_at,
            device_sequence,
            note,
            previous_balance,
            official_balance,
            pass_count_after,
            advance_until_after,
            receipt_number,
            details
        )
        values (
            %s, %s, %s, %s, %s, %s, %s, 'payment', 100.00, now(), %s,
            '', 1000.00, 900.00, 0, null, %s, '{}'::jsonb
        )
        returning id
        """,
        (
            uuid4(),
            loan_id,
            client_id,
            actor_id,
            device_id,
            loan_id,
            collection_date,
            sequence,
            f"RR-R-{suffix}-{sequence}",
        ),
    ).fetchone()[0]


def _create_protected_review_set(
    connection,
    *,
    actor_id,
    client_id,
    loan_id,
    transaction_id,
    eir_period_id,
    eir_date,
    collection_period_id,
    collection_date,
    accounts,
    review_token: str,
    bundle_token: str,
):
    eir_entry_id = connection.execute(
        """
        insert into accounting.journal_entries (
            fiscal_period_id, posting_date, description, status,
            source_type, source_reference, source_event_key,
            created_by_user_id, updated_at
        )
        values (
            %s, %s, 'Synthetic protected Regular EIR draft', 'draft',
            'regular_eir_accrual', %s, %s, %s, now()
        )
        returning id
        """,
        (
            eir_period_id,
            eir_date,
            f"{transaction_id}:fiscal_period:{eir_period_id}",
            f"eir_accrual:collection:{transaction_id}:fiscal_period:{eir_period_id}",
            actor_id,
        ),
    ).fetchone()[0]
    collection_entry_id = connection.execute(
        """
        insert into accounting.journal_entries (
            fiscal_period_id, posting_date, description, status,
            source_type, source_reference, source_event_key,
            created_by_user_id, updated_at
        )
        values (
            %s, %s, 'Synthetic protected Regular collection draft', 'draft',
            'collection', %s, %s, %s, now()
        )
        returning id
        """,
        (
            collection_period_id,
            collection_date,
            str(transaction_id),
            f"collection:{transaction_id}",
            actor_id,
        ),
    ).fetchone()[0]

    connection.execute(
        """
        insert into accounting.journal_lines (
            journal_entry_id, line_number, account_id, description,
            debit, credit, client_id, loan_id
        )
        values
            (%s, 1, %s, 'EIR accrued interest', 2.00, 0.00, %s, %s),
            (%s, 2, %s, 'Regular interest income', 0.00, 2.00, %s, %s),
            (%s, 1, %s, 'Collector custody cash', 100.00, 0.00, %s, %s),
            (%s, 2, %s, 'Clear accrued interest', 0.00, 2.00, %s, %s),
            (%s, 3, %s, 'Reduce Regular loan principal', 0.00, 98.00, %s, %s)
        """,
        (
            eir_entry_id,
            accounts["accrued_interest_receivable"], client_id, loan_id,
            eir_entry_id,
            accounts["interest_income_regular"], client_id, loan_id,
            collection_entry_id,
            accounts["cash_collector_custody"], client_id, loan_id,
            collection_entry_id,
            accounts["accrued_interest_receivable"], client_id, loan_id,
            collection_entry_id,
            accounts["loans_receivable_regular"], client_id, loan_id,
        ),
    )

    connection.execute(
        "select set_config('accounting.regular_journal_prepare_allowed', 'on', true)"
    )
    preparation_id = connection.execute(
        """
        insert into accounting.regular_journal_draft_preparations (
            loan_id, transaction_id, review_set_fingerprint, bundle_fingerprint,
            evidence_policy_version, draft_policy_version,
            expected_set_transaction_count, expected_entry_count, prepared_by_user_id
        )
        values (
            %s, %s, %s, %s,
            'regular_cross_period_posting_ready_evidence_v1',
            'regular_journal_draft_v1', 1, 2, %s
        )
        returning id
        """,
        (loan_id, transaction_id, review_token, bundle_token, actor_id),
    ).fetchone()[0]
    connection.execute(
        """
        insert into accounting.regular_journal_draft_preparation_entries (
            preparation_id, sequence_order, entry_type, journal_entry_id,
            bundle_entry_key, source_event_key
        )
        values
            (%s, 1, 'eir_accrual_period', %s, %s, %s),
            (%s, 2, 'collection', %s, %s, %s)
        """,
        (
            preparation_id,
            eir_entry_id,
            f"bundle:eir:{transaction_id}:{eir_period_id}",
            f"eir_accrual:collection:{transaction_id}:fiscal_period:{eir_period_id}",
            preparation_id,
            collection_entry_id,
            f"bundle:collection:{transaction_id}",
            f"collection:{transaction_id}",
        ),
    )
    return eir_entry_id, collection_entry_id


def _create_posted_set(connection, *, suffix: str, token_char: str):
    actor_id, device_id, client_id, loan_id, base_date = _create_fixture(connection, suffix)
    accounts = _account_ids(connection)
    eir_date = base_date
    collection_date = base_date + timedelta(days=1)
    eir_period_id = _create_period(
        connection, suffix=suffix, label="Synthetic reversal EIR", period_date=eir_date
    )
    collection_period_id = _create_period(
        connection,
        suffix=suffix,
        label="Synthetic reversal collection",
        period_date=collection_date,
    )
    transaction_id = _create_collection(
        connection,
        suffix=suffix,
        loan_id=loan_id,
        client_id=client_id,
        actor_id=actor_id,
        device_id=device_id,
        sequence=1,
        collection_date=collection_date,
    )
    review_token = token_char * 64
    original_ids = _create_protected_review_set(
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
        bundle_token=(token_char.upper() if token_char.isalpha() else "f") * 64,
    )
    posting_set_id = connection.execute(
        "select accounting.post_regular_journal_review_set(%s, %s, %s)",
        (loan_id, review_token, actor_id),
    ).fetchone()[0]
    return {
        "actor_id": actor_id,
        "client_id": client_id,
        "loan_id": loan_id,
        "transaction_id": transaction_id,
        "collection_date": collection_date,
        "original_ids": original_ids,
        "posting_set_id": posting_set_id,
    }


def _insert_void_audit(connection, *, fixture, void_id, reason: str, voided_at):
    connection.execute(
        """
        insert into lending.collection_transaction_voids (
            id, transaction_id, voided_by_user_id, reason,
            transaction_snapshot, previous_covered_dates,
            state_before, state_after, voided_at
        )
        values (%s, %s, %s, %s, '{}'::jsonb, ARRAY[]::date[], '{}'::jsonb, '{}'::jsonb, %s)
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
                "select to_regclass(%s)", (relation,)
            ).fetchone()[0] is None:
                pytest.skip(f"Accounting prerequisite is not installed: {relation}")

        try:
            for migration in (SQL_0040, SQL_0041, SQL_0042, SQL_0043):
                connection.execute(_transaction_body(migration))

            fixture = _create_posted_set(
                connection, suffix=f"{suffix}a", token_char="a"
            )
            original_before = connection.execute(
                """
                select id, status, entry_number, source_event_key, posted_by_user_id, posted_at
                from accounting.journal_entries
                where id = any(%s)
                order by posting_date, id
                """,
                (list(fixture["original_ids"]),),
            ).fetchall()
            assert len(original_before) == 2
            assert all(row[1] == "posted" for row in original_before)

            # The generic General Journal reversal primitive may not bypass the
            # protected Regular collection-void path.
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
            voided_at = datetime.combine(
                fixture["collection_date"],
                datetime.min.time(),
                tzinfo=timezone.utc,
            ) + timedelta(hours=4)
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
                select id, posting_set_id, expected_entry_count, reversed_entry_count,
                       reversed_by_user_id, reason
                from accounting.regular_journal_reversal_sets
                where transaction_id = %s and collection_void_id = %s
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
                select re.original_journal_entry_id,
                       re.reversal_journal_entry_id,
                       re.original_entry_number,
                       re.reversal_entry_number,
                       re.original_source_event_key,
                       re.reversal_source_event_key,
                       journal.status,
                       journal.source_type,
                       journal.reversal_of_entry_id
                from accounting.regular_journal_reversal_entries re
                join accounting.journal_entries journal
                  on journal.id = re.reversal_journal_entry_id
                where re.reversal_set_id = %s
                order by re.sequence_order
                """,
                (reversal_set[0],),
            ).fetchall()
            assert len(reversal_rows) == 2
            assert all(row[6] == "posted" for row in reversal_rows)
            assert all(row[7] == "regular_collection_void_reversal" for row in reversal_rows)
            assert all(row[0] == row[8] for row in reversal_rows)

            # Every reversing line must be the exact debit/credit swap of the
            # immutable original line, with no amount drift.
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

            original_after = connection.execute(
                """
                select id, status, entry_number, source_event_key, posted_by_user_id, posted_at
                from accounting.journal_entries
                where id = any(%s)
                order by posting_date, id
                """,
                (list(fixture["original_ids"]),),
            ).fetchall()
            assert original_after == original_before

            # Reversal audit is append-only evidence.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.regular_journal_reversal_sets where id = %s",
                        (reversal_set[0],),
                    )

            # Build a second fully posted Regular source event, then force the
            # second reversing journal to fail. The surrounding operational void
            # transaction must roll back the void audit, is_voided flag, reversal
            # journals, and reversal audit as one unit.
            failed_fixture = _create_posted_set(
                connection, suffix=f"{suffix}b", token_char="c"
            )
            failed_original_before = connection.execute(
                """
                select id, status, entry_number, source_event_key
                from accounting.journal_entries
                where id = any(%s)
                order by posting_date, id
                """,
                (list(failed_fixture["original_ids"]),),
            ).fetchall()

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
            failed_voided_at = datetime.combine(
                failed_fixture["collection_date"],
                datetime.min.time(),
                tzinfo=timezone.utc,
            ) + timedelta(hours=4)

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
                "select is_voided, voided_at, voided_by_user_id, void_reason from lending.collection_transactions where id = %s",
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
                "select count(*) from accounting.journal_entries where source_reference = %s and source_type = 'regular_collection_void_reversal'",
                (str(failed_void_id),),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.journal_entries where reversal_of_entry_id = any(%s)",
                (list(failed_fixture["original_ids"]),),
            ).fetchone()[0] == 0
            failed_original_after = connection.execute(
                """
                select id, status, entry_number, source_event_key
                from accounting.journal_entries
                where id = any(%s)
                order by posting_date, id
                """,
                (list(failed_fixture["original_ids"]),),
            ).fetchall()
            assert failed_original_after == failed_original_before
        finally:
            connection.rollback()
