from __future__ import annotations

import os
from datetime import timedelta
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
        (f"regular-post-{suffix}", f"Regular Posting {suffix}"),
    ).fetchone()[0]
    device_id = connection.execute(
        """
        insert into core.devices (
            user_id, device_identifier_hash, platform, status
        )
        values (%s, %s, 'desktop', 'active')
        returning id
        """,
        (actor_id, f"regular-post-device-{suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        )
        values (%s, %s, 120, 'fixed_daily', 0)
        returning id
        """,
        (f"RP-{suffix}", f"Regular Posting {suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"RP-C-{suffix}", f"Regular Posting Client {suffix}"),
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
            f"RP-L-{suffix}",
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
    amount: str = "100.00",
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
            %s, %s, %s, %s, %s, %s, %s, 'payment', %s, now(), %s,
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
            amount,
            sequence,
            f"RP-R-{suffix}-{sequence}",
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
            fiscal_period_id,
            posting_date,
            description,
            status,
            source_type,
            source_reference,
            source_event_key,
            created_by_user_id,
            updated_at
        )
        values (
            %s, %s, %s, 'draft', 'regular_eir_accrual', %s, %s, %s, now()
        )
        returning id
        """,
        (
            eir_period_id,
            eir_date,
            "Synthetic protected Regular EIR draft",
            f"{transaction_id}:fiscal_period:{eir_period_id}",
            f"eir_accrual:collection:{transaction_id}:fiscal_period:{eir_period_id}",
            actor_id,
        ),
    ).fetchone()[0]
    collection_entry_id = connection.execute(
        """
        insert into accounting.journal_entries (
            fiscal_period_id,
            posting_date,
            description,
            status,
            source_type,
            source_reference,
            source_event_key,
            created_by_user_id,
            updated_at
        )
        values (
            %s, %s, %s, 'draft', 'collection', %s, %s, %s, now()
        )
        returning id
        """,
        (
            collection_period_id,
            collection_date,
            "Synthetic protected Regular collection draft",
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
            accounts["accrued_interest_receivable"],
            client_id,
            loan_id,
            eir_entry_id,
            accounts["interest_income_regular"],
            client_id,
            loan_id,
            collection_entry_id,
            accounts["cash_collector_custody"],
            client_id,
            loan_id,
            collection_entry_id,
            accounts["accrued_interest_receivable"],
            client_id,
            loan_id,
            collection_entry_id,
            accounts["loans_receivable_regular"],
            client_id,
            loan_id,
        ),
    )

    connection.execute(
        "select set_config('accounting.regular_journal_prepare_allowed', 'on', true)"
    )
    preparation_id = connection.execute(
        """
        insert into accounting.regular_journal_draft_preparations (
            loan_id,
            transaction_id,
            review_set_fingerprint,
            bundle_fingerprint,
            evidence_policy_version,
            draft_policy_version,
            expected_set_transaction_count,
            expected_entry_count,
            prepared_by_user_id
        )
        values (
            %s, %s, %s, %s,
            'regular_cross_period_posting_ready_evidence_v1',
            'regular_journal_draft_v1',
            1, 2, %s
        )
        returning id
        """,
        (loan_id, transaction_id, review_token, bundle_token, actor_id),
    ).fetchone()[0]
    connection.execute(
        """
        insert into accounting.regular_journal_draft_preparation_entries (
            preparation_id,
            sequence_order,
            entry_type,
            journal_entry_id,
            bundle_entry_key,
            source_event_key
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


def test_protected_regular_posting_is_atomic_idempotent_and_ledger_guarded() -> None:
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
            connection.execute(_transaction_body(SQL_0040))
            connection.execute(_transaction_body(SQL_0041))
            connection.execute(_transaction_body(SQL_0042))

            actor_id, device_id, client_id, loan_id, base_date = _create_fixture(
                connection, suffix
            )
            accounts = _account_ids(connection)

            eir_date = base_date
            collection_date = base_date + timedelta(days=1)
            eir_period_id = _create_period(
                connection,
                suffix=suffix,
                label="Synthetic Regular EIR",
                period_date=eir_date,
            )
            collection_period_id = _create_period(
                connection,
                suffix=suffix,
                label="Synthetic Regular collection",
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
            review_token = "a" * 64
            eir_entry_id, collection_entry_id = _create_protected_review_set(
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
                bundle_token="b" * 64,
            )

            # The ordinary General Journal wrapper cannot post protected Regular
            # source-event drafts by UUID.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.post_manual_journal_entry(%s, %s)",
                        (eir_entry_id, actor_id),
                    )
            assert connection.execute(
                "select status, entry_number from accounting.journal_entries where id = %s",
                (eir_entry_id,),
            ).fetchone() == ("draft", None)

            posting_set_id = connection.execute(
                "select accounting.post_regular_journal_review_set(%s, %s, %s)",
                (loan_id, review_token, actor_id),
            ).fetchone()[0]

            posted = connection.execute(
                """
                select id, status, entry_number, posted_by_user_id
                from accounting.journal_entries
                where id in (%s, %s)
                order by posting_date, id
                """,
                (eir_entry_id, collection_entry_id),
            ).fetchall()
            assert len(posted) == 2
            assert all(row[1] == "posted" for row in posted)
            assert all(str(row[2]).startswith("JE-") for row in posted)
            assert all(row[3] == actor_id for row in posted)

            audit = connection.execute(
                """
                select expected_transaction_count, expected_entry_count, posted_by_user_id
                from accounting.regular_journal_posting_sets
                where id = %s
                """,
                (posting_set_id,),
            ).fetchone()
            assert audit == (1, 2, actor_id)
            assert connection.execute(
                """
                select count(*)
                from accounting.regular_journal_posting_entries
                where posting_set_id = %s
                """,
                (posting_set_id,),
            ).fetchone()[0] == 2
            assert connection.execute(
                """
                select count(*)
                from accounting.journal_events
                where journal_entry_id in (%s, %s)
                  and event_type = 'posted'
                  and details ->> 'protected_posting' = 'true'
                  and details ->> 'automatic_source_posting' = 'false'
                """,
                (eir_entry_id, collection_entry_id),
            ).fetchone()[0] == 2

            # Exact retry returns the same immutable posting set and adds nothing.
            repeated_id = connection.execute(
                "select accounting.post_regular_journal_review_set(%s, %s, %s)",
                (loan_id, review_token, actor_id),
            ).fetchone()[0]
            assert repeated_id == posting_set_id
            assert connection.execute(
                "select count(*) from accounting.regular_journal_posting_sets where id = %s",
                (posting_set_id,),
            ).fetchone()[0] == 1
            assert connection.execute(
                """
                select count(*)
                from accounting.journal_events
                where journal_entry_id in (%s, %s)
                  and event_type = 'posted'
                  and details ->> 'protected_posting' = 'true'
                """,
                (eir_entry_id, collection_entry_id),
            ).fetchone()[0] == 2

            # Posting audit rows themselves are immutable outside the protected
            # function even after a successful post.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.regular_journal_posting_sets where id = %s",
                        (posting_set_id,),
                    )

            # Build a second review set and force the second journal update to
            # fail after the first has posted inside a nested transaction. The
            # savepoint must restore the first journal to draft and remove all
            # posting audit/event rows for this failed set.
            eir_date_2 = base_date + timedelta(days=2)
            collection_date_2 = base_date + timedelta(days=3)
            eir_period_id_2 = _create_period(
                connection,
                suffix=suffix,
                label="Synthetic rollback EIR",
                period_date=eir_date_2,
            )
            collection_period_id_2 = _create_period(
                connection,
                suffix=suffix,
                label="Synthetic rollback collection",
                period_date=collection_date_2,
            )
            transaction_id_2 = _create_collection(
                connection,
                suffix=suffix,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                sequence=2,
                collection_date=collection_date_2,
            )
            rollback_token = "c" * 64
            eir_entry_id_2, collection_entry_id_2 = _create_protected_review_set(
                connection,
                actor_id=actor_id,
                client_id=client_id,
                loan_id=loan_id,
                transaction_id=transaction_id_2,
                eir_period_id=eir_period_id_2,
                eir_date=eir_date_2,
                collection_period_id=collection_period_id_2,
                collection_date=collection_date_2,
                accounts=accounts,
                review_token=rollback_token,
                bundle_token="d" * 64,
            )

            connection.execute(
                sql.SQL(
                    """
                    create or replace function pg_temp.stage5d17_force_second_failure()
                    returns trigger
                    language plpgsql
                    as $$
                    begin
                        if new.id = {}::uuid
                           and old.status = 'draft'
                           and new.status = 'posted' then
                            raise exception 'Synthetic Stage 5D.17 second-entry failure.';
                        end if;
                        return new;
                    end;
                    $$
                    """
                ).format(sql.Literal(str(collection_entry_id_2)))
            )
            trigger_name = f"zz_stage5d17_force_failure_{suffix}"
            connection.execute(
                sql.SQL(
                    """
                    create trigger {}
                    before update on accounting.journal_entries
                    for each row execute function pg_temp.stage5d17_force_second_failure()
                    """
                ).format(sql.Identifier(trigger_name))
            )

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.post_regular_journal_review_set(%s, %s, %s)",
                        (loan_id, rollback_token, actor_id),
                    )

            failed_statuses = connection.execute(
                """
                select id, status, entry_number
                from accounting.journal_entries
                where id in (%s, %s)
                order by posting_date, id
                """,
                (eir_entry_id_2, collection_entry_id_2),
            ).fetchall()
            assert len(failed_statuses) == 2
            assert all(row[1:] == ("draft", None) for row in failed_statuses)
            assert connection.execute(
                """
                select count(*)
                from accounting.regular_journal_posting_sets
                where loan_id = %s and review_set_fingerprint = %s
                """,
                (loan_id, rollback_token),
            ).fetchone()[0] == 0
            assert connection.execute(
                """
                select count(*)
                from accounting.journal_events
                where journal_entry_id in (%s, %s)
                  and event_type = 'posted'
                """,
                (eir_entry_id_2, collection_entry_id_2),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
