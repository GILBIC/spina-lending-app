from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _fixture(connection, *, suffix: str, two_periods: bool = False):
    actor_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"rb-{suffix}", f"Renewal Boundary {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        )
        values (%s, %s, 120, 'fixed_daily', 0)
        returning id
        """,
        (f"RB-{suffix}", f"Renewal Boundary {suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"RB-C-{suffix}", f"Boundary Client {suffix}"),
    ).fetchone()[0]
    max_end = connection.execute(
        "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
    ).fetchone()[0]
    target_date = max_end + timedelta(days=20)
    old_release = target_date - timedelta(days=30)
    old_loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status
        )
        values (%s, %s, %s, 5000.00, 50.00, %s, %s, 'active')
        returning id
        """,
        (
            f"RB-OLD-{suffix}",
            client_id,
            loan_type_id,
            old_release,
            old_release + timedelta(days=120),
        ),
    ).fetchone()[0]
    new_loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status
        )
        values (%s, %s, %s, 6000.00, 60.00, %s, %s, 'active')
        returning id
        """,
        (
            f"RB-NEW-{suffix}",
            client_id,
            loan_type_id,
            target_date,
            target_date + timedelta(days=120),
        ),
    ).fetchone()[0]

    connection.execute(
        "select set_config('lending.loan_disbursement_evidence_insert_allowed', 'on', true)"
    )
    disbursement_event_id = connection.execute(
        """
        insert into lending.loan_disbursement_events (
            loan_id, client_id, event_kind, business_date, disbursed_at,
            cash_disbursed_amount, settlement_amount, other_deduction_amount,
            funding_account_system_key, external_reference, evidence_note,
            principal_snapshot, date_released_snapshot, loan_status_snapshot,
            recorded_by_user_id
        )
        values (
            %s, %s, 'renewal_release', %s,
            (%s::date + time '09:00') at time zone 'Asia/Manila',
            3000.00, 3000.00, 0.00,
            'cash_bank', %s, '', 6000.00, %s, 'active', %s
        )
        returning id
        """,
        (
            new_loan_id,
            client_id,
            target_date,
            target_date,
            f"RB-DISB-{suffix}",
            target_date,
            actor_id,
        ),
    ).fetchone()[0]

    connection.execute(
        "select set_config('lending.loan_renewal_execution_insert_allowed', 'on', true)"
    )
    execution_id = connection.execute(
        """
        insert into lending.loan_renewal_execution_events (
            old_loan_id, new_loan_id, disbursement_event_id, client_id,
            business_date, executed_at, old_loan_settlement_amount,
            external_reference, evidence_note,
            old_loan_principal_snapshot, old_loan_date_released_snapshot,
            old_loan_status_snapshot, new_loan_principal_snapshot,
            new_loan_date_released_snapshot, new_loan_status_snapshot,
            recorded_by_user_id
        )
        values (
            %s, %s, %s, %s, %s,
            (%s::date + time '09:05') at time zone 'Asia/Manila',
            3000.00, %s, '', 5000.00, %s, 'active',
            6000.00, %s, 'active', %s
        )
        returning id
        """,
        (
            old_loan_id,
            new_loan_id,
            disbursement_event_id,
            client_id,
            target_date,
            target_date,
            f"RB-EXEC-{suffix}",
            old_release,
            target_date,
            actor_id,
        ),
    ).fetchone()[0]

    period_dates = (
        (target_date - timedelta(days=1), target_date)
        if two_periods
        else (target_date,)
    )
    periods = []
    for index, period_date in enumerate(period_dates, start=1):
        period_id = connection.execute(
            """
            insert into accounting.fiscal_periods (
                label, start_date, end_date, status
            ) values (%s, %s, %s, 'open')
            returning id
            """,
            (f"RB Period {suffix}-{index}", period_date, period_date),
        ).fetchone()[0]
        periods.append((period_id, period_date))

    return actor_id, client_id, old_loan_id, execution_id, periods, target_date


def _entries(execution_id, periods, amounts):
    result = []
    for sequence, ((period_id, period_date), amount) in enumerate(
        zip(periods, amounts, strict=True), start=1
    ):
        result.append(
            {
                "sequence_order": sequence,
                "fiscal_period_id": str(period_id),
                "posting_date": period_date.isoformat(),
                "amount": amount,
                "source_type": "regular_renewal_eir_accrual",
                "source_reference": f"{execution_id}:fiscal_period:{period_id}",
                "source_event_key": (
                    f"renewal_eir_accrual:{execution_id}:fiscal_period:{period_id}"
                ),
                "debit_account_system_key": "accrued_interest_receivable",
                "credit_account_system_key": "interest_income_regular",
            }
        )
    return result


def _prepare(connection, *, execution_id, actor_id, token, entries, total):
    return connection.execute(
        """
        select accounting.create_renewal_boundary_eir_journal_draft_batch(
            %s, %s, %s,
            'greenfield_regular_renewal_boundary_eir_v1',
            'renewal_boundary_eir_journal_draft_v1',
            %s, %s::jsonb
        )
        """,
        (execution_id, actor_id, token, total, psycopg.types.json.Jsonb(entries)),
    ).fetchone()[0]


def _post(connection, *, execution_id, actor_id, token, count, total):
    return connection.execute(
        """
        select accounting.post_renewal_boundary_eir_journal_review_set(
            %s, %s, %s, %s, %s, %s,
            'renewal_boundary_eir_journal_posting_v1'
        )
        """,
        (execution_id, actor_id, token, count, total, total),
    ).fetchone()[0]


def test_protected_renewal_boundary_eir_posting_is_atomic_immutable_and_idempotent():
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        actor_id, client_id, old_loan_id, execution_id, periods, _ = _fixture(
            connection, suffix=suffix
        )
        token = "a" * 64
        entries = _entries(execution_id, periods, ["10.00"])
        preparation_id = _prepare(
            connection,
            execution_id=execution_id,
            actor_id=actor_id,
            token=token,
            entries=entries,
            total="10.00",
        )

        status = connection.execute(
            """
            select expected_entry_count, actual_entry_count, draft_entry_count,
                   posted_entry_count, total_debit, total_credit, integrity_ready,
                   protected_posting_complete, automatic_source_posting
            from accounting.renewal_boundary_eir_journal_status
            where renewal_execution_event_id = %s
            """,
            (execution_id,),
        ).fetchone()
        assert status == (1, 1, 1, 0, Decimal("10.00"), Decimal("10.00"), True, False, False)

        repeated_preparation = _prepare(
            connection,
            execution_id=execution_id,
            actor_id=actor_id,
            token=token,
            entries=entries,
            total="10.00",
        )
        assert repeated_preparation == preparation_id
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                _prepare(
                    connection,
                    execution_id=execution_id,
                    actor_id=actor_id,
                    token="b" * 64,
                    entries=entries,
                    total="10.00",
                )

        journal_id = connection.execute(
            """
            select journal_entry_id
            from accounting.renewal_boundary_eir_journal_preparation_entries
            where preparation_id = %s
            """,
            (preparation_id,),
        ).fetchone()[0]
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "update accounting.journal_lines set debit = 9.99 where journal_entry_id = %s and line_number = 1",
                    (journal_id,),
                )
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "select accounting.post_manual_journal_entry(%s, %s)",
                    (journal_id, actor_id),
                )

        posting_set_id = _post(
            connection,
            execution_id=execution_id,
            actor_id=actor_id,
            token=token,
            count=1,
            total="10.00",
        )
        posted = connection.execute(
            "select status, entry_number, posted_by_user_id from accounting.journal_entries where id = %s",
            (journal_id,),
        ).fetchone()
        assert posted[0] == "posted"
        assert str(posted[1]).startswith("JE-")
        assert posted[2] == actor_id
        audit = connection.execute(
            """
            select expected_entry_count, posted_entry_count, total_debit, total_credit,
                   posted_by_user_id
            from accounting.renewal_boundary_eir_journal_posting_sets
            where id = %s
            """,
            (posting_set_id,),
        ).fetchone()
        assert audit == (1, 1, Decimal("10.00"), Decimal("10.00"), actor_id)
        assert connection.execute(
            "select count(*) from accounting.renewal_boundary_eir_journal_posting_entries where posting_set_id = %s",
            (posting_set_id,),
        ).fetchone()[0] == 1

        repeated_post = _post(
            connection,
            execution_id=execution_id,
            actor_id=actor_id,
            token=token,
            count=1,
            total="10.00",
        )
        assert repeated_post == posting_set_id
        assert connection.execute(
            "select count(*) from accounting.renewal_boundary_eir_journal_posting_sets where renewal_execution_event_id = %s",
            (execution_id,),
        ).fetchone()[0] == 1

        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "update accounting.renewal_boundary_eir_journal_posting_sets set total_debit = 9.99 where id = %s",
                    (posting_set_id,),
                )
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "select accounting.create_manual_reversal_draft(%s, %s, current_date, 'not allowed')",
                    (journal_id, actor_id),
                )
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "select set_config('lending.loan_renewal_execution_void_allowed', 'on', true)"
                )
                connection.execute(
                    """
                    update lending.loan_renewal_execution_events
                    set is_voided = true,
                        voided_by_user_id = %s,
                        voided_at = now(),
                        void_reason = 'test protected history guard'
                    where id = %s
                    """,
                    (actor_id, execution_id),
                )
        assert connection.execute(
            "select is_voided from lending.loan_renewal_execution_events where id = %s",
            (execution_id,),
        ).fetchone()[0] is False


def test_forced_second_post_failure_rolls_back_entire_boundary_posting_set():
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        actor_id, _, _, execution_id, periods, _ = _fixture(
            connection, suffix=suffix, two_periods=True
        )
        token = "c" * 64
        entries = _entries(execution_id, periods, ["4.00", "6.00"])
        preparation_id = _prepare(
            connection,
            execution_id=execution_id,
            actor_id=actor_id,
            token=token,
            entries=entries,
            total="10.00",
        )
        journal_ids = [
            row[0]
            for row in connection.execute(
                """
                select journal_entry_id
                from accounting.renewal_boundary_eir_journal_preparation_entries
                where preparation_id = %s
                order by sequence_order
                """,
                (preparation_id,),
            ).fetchall()
        ]
        second_id = journal_ids[1]
        trigger_suffix = suffix.replace("-", "")
        function_name = f"test_fail_boundary_post_{trigger_suffix}"
        trigger_name = f"zz_test_fail_boundary_post_{trigger_suffix}"
        connection.execute(
            f"""
            create function accounting.{function_name}()
            returns trigger language plpgsql as $$
            begin
                if OLD.status = 'draft' and NEW.status = 'posted'
                   and NEW.id = '{second_id}'::uuid then
                    raise exception 'forced second boundary post failure';
                end if;
                return NEW;
            end;
            $$
            """
        )
        connection.execute(
            f"""
            create trigger {trigger_name}
            before update on accounting.journal_entries
            for each row execute function accounting.{function_name}()
            """
        )

        with pytest.raises(psycopg.Error, match="forced second boundary post failure"):
            with connection.transaction():
                _post(
                    connection,
                    execution_id=execution_id,
                    actor_id=actor_id,
                    token=token,
                    count=2,
                    total="10.00",
                )

        states = connection.execute(
            """
            select status, entry_number
            from accounting.journal_entries
            where id = any(%s)
            order by id
            """,
            (journal_ids,),
        ).fetchall()
        assert states == [("draft", None), ("draft", None)]
        assert connection.execute(
            "select count(*) from accounting.renewal_boundary_eir_journal_posting_sets where renewal_execution_event_id = %s",
            (execution_id,),
        ).fetchone()[0] == 0
        assert connection.execute(
            """
            select count(*)
            from accounting.renewal_boundary_eir_journal_posting_entries entry
            join accounting.renewal_boundary_eir_journal_posting_sets posting
              on posting.id = entry.posting_set_id
            where posting.renewal_execution_event_id = %s
            """,
            (execution_id,),
        ).fetchone()[0] == 0