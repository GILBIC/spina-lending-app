from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0049 = (
    SQL_ROOT / "0049_add_controlled_new_loan_disbursement_reversals.sql"
).read_text(encoding="utf-8")
MANILA = timezone(timedelta(hours=8))


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _actor(connection, suffix: str):
    return connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"d23-{suffix}", f"Stage 5D.23 {suffix}"),
    ).fetchone()[0]


def _create_period(connection, *, suffix: str, posting_date):
    return connection.execute(
        """
        insert into accounting.fiscal_periods (
            label, start_date, end_date, status
        ) values (%s, %s, %s, 'open') returning id
        """,
        (f"D23 {suffix}", posting_date, posting_date),
    ).fetchone()[0]


def _loan(connection, *, suffix: str, actor_id, release_date, principal="5000.00"):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"D23-C-{suffix}", f"D23 Client {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) values (%s, %s, 120, 'fixed_daily', 0) returning id
        """,
        (f"D23-T-{suffix}", f"D23 Regular {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) values (%s, %s, %s, %s, 50.00, 20.0000, %s, %s, 'active', %s)
        returning id
        """,
        (
            f"D23-L-{suffix}",
            client_id,
            loan_type_id,
            principal,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]
    return client_id, loan_id


def _record_evidence(connection, *, loan_id, actor_id, business_date, reference):
    disbursed_at = datetime(
        business_date.year,
        business_date.month,
        business_date.day,
        10,
        0,
        tzinfo=MANILA,
    )
    return connection.execute(
        """
        select accounting.record_loan_disbursement_evidence(
            %s, %s, 'new_loan_release', %s, %s, 5000.00,
            0.00, 0.00, 'cash_office', %s, %s
        )
        """,
        (
            loan_id,
            actor_id,
            business_date,
            disbursed_at,
            reference,
            "Stage 5D.23 disposable reversal evidence",
        ),
    ).fetchone()[0]


def _prepare_and_post(
    connection,
    *,
    event_id,
    actor_id,
    draft_token,
    posting_token,
):
    coordinate = connection.execute(
        """
        select source_event_key, posting_date, fiscal_period_id,
               debit_account_id, credit_account_id, debit_amount
        from accounting.loan_disbursement_journal_coordinates
        where disbursement_event_id = %s
          and coordinate_status = 'coordinate_ready'
        """,
        (event_id,),
    ).fetchone()
    assert coordinate is not None

    preparation_id = connection.execute(
        """
        select accounting.create_new_loan_disbursement_journal_draft(
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            'new_loan_disbursement_coordinates_v1',
            'new_loan_disbursement_journal_draft_v1'
        )
        """,
        (
            event_id,
            actor_id,
            draft_token,
            coordinate[0],
            coordinate[1],
            coordinate[2],
            coordinate[3],
            coordinate[4],
            coordinate[5],
        ),
    ).fetchone()[0]

    prepared = connection.execute(
        """
        select preparation_id, journal_entry_id, source_event_key,
               draft_review_token, posting_date, fiscal_period_id,
               debit_account_id, credit_account_id, amount,
               total_debit, total_credit
        from accounting.loan_disbursement_journal_posting_status
        where preparation_id = %s
        """,
        (preparation_id,),
    ).fetchone()

    posting_id = connection.execute(
        """
        select accounting.post_new_loan_disbursement_journal(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            'new_loan_disbursement_journal_posting_v1'
        )
        """,
        (
            prepared[0], actor_id, posting_token, prepared[1], prepared[2],
            prepared[3], prepared[4], prepared[5], prepared[6], prepared[7],
            prepared[8], prepared[9], prepared[10],
        ),
    ).fetchone()[0]

    posted = connection.execute(
        """
        select journal_entry_id, entry_number, source_event_key,
               debit_account_id, credit_account_id, amount
        from accounting.loan_disbursement_journal_postings
        where id = %s
        """,
        (posting_id,),
    ).fetchone()
    return posting_id, posted


def _new_posted_source(connection, *, suffix: str, actor_id, release_date):
    client_id, loan_id = _loan(
        connection,
        suffix=suffix,
        actor_id=actor_id,
        release_date=release_date,
    )
    event_id = _record_evidence(
        connection,
        loan_id=loan_id,
        actor_id=actor_id,
        business_date=release_date,
        reference=f"D23-REL-{suffix}",
    )
    posting_id, posted = _prepare_and_post(
        connection,
        event_id=event_id,
        actor_id=actor_id,
        draft_token=(suffix[0].lower() if suffix else "a") * 64,
        posting_token=(suffix[-1].lower() if suffix else "b") * 64,
    )
    return client_id, loan_id, event_id, posting_id, posted


def test_posted_new_regular_disbursement_cancellation_is_exact_immutable_and_atomic() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            assert connection.execute(
                "select to_regclass('accounting.loan_disbursement_journal_postings')"
            ).fetchone()[0] is not None
            assert connection.execute(
                "select to_regclass('lending.loan_disbursement_cancellations')"
            ).fetchone()[0] is None

            before = (
                connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
                connection.execute("select count(*) from lending.loan_disbursement_events").fetchone()[0],
                connection.execute("select count(*) from core.audit_logs").fetchone()[0],
            )
            connection.execute(_transaction_body(SQL_0049))
            after_install = (
                connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
                connection.execute("select count(*) from lending.loan_disbursement_events").fetchone()[0],
                connection.execute("select count(*) from core.audit_logs").fetchone()[0],
            )
            assert after_install == before
            assert connection.execute(
                "select count(*) from lending.loan_disbursement_cancellations"
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_reversals"
            ).fetchone()[0] == 0

            actor_id = _actor(connection, suffix)
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            release_date = max_end + timedelta(days=7)
            reversal_date = release_date + timedelta(days=1)
            _create_period(connection, suffix=f"{suffix}-release", posting_date=release_date)
            _create_period(connection, suffix=f"{suffix}-reversal", posting_date=reversal_date)

            client_id, loan_id, event_id, posting_id, posted = _new_posted_source(
                connection,
                suffix=f"a{suffix}",
                actor_id=actor_id,
                release_date=release_date,
            )
            original_journal_id, original_entry_number, original_source_key = posted[:3]
            debit_account_id, credit_account_id, amount = posted[3:]

            original_snapshot = connection.execute(
                """
                select status, entry_number, source_event_key, posted_by_user_id, posted_at
                from accounting.journal_entries where id = %s
                """,
                (original_journal_id,),
            ).fetchone()
            posting_snapshot = connection.execute(
                "select * from accounting.loan_disbursement_journal_postings where id = %s",
                (posting_id,),
            ).fetchone()

            # Generic/manual reversal creation cannot bypass Stage 5D.23.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.create_reversal_draft(%s, %s, %s, %s)",
                        (
                            original_journal_id,
                            actor_id,
                            reversal_date,
                            "Generic reversal must be blocked",
                        ),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        """
                        insert into accounting.journal_entries (
                            fiscal_period_id, posting_date, description, source_type,
                            source_reference, source_event_key, reversal_of_entry_id,
                            created_by_user_id
                        )
                        select fiscal_period_id, %s, 'Bypass reversal', 'reversal',
                               entry_number, %s, id, %s
                        from accounting.journal_entries where id = %s
                        """,
                        (
                            reversal_date,
                            f"bypass-d23:{uuid4()}",
                            actor_id,
                            original_journal_id,
                        ),
                    )

            reason = "Release cancelled before borrower received funds"
            cancellation_id = connection.execute(
                "select accounting.reverse_posted_new_loan_disbursement(%s, %s, %s, %s)",
                (posting_id, actor_id, reversal_date, reason),
            ).fetchone()[0]

            status = connection.execute(
                """
                select cancellation_id, cancellation_reason, reversal_posting_date,
                       reversal_id, reversal_journal_entry_id,
                       reversal_entry_number, reversal_journal_status,
                       cancellation_ready, cancelled_reversal_audit_exact,
                       protected_reversal_enabled, automatic_source_posting
                from accounting.loan_disbursement_cancellation_status
                where posting_id = %s
                """,
                (posting_id,),
            ).fetchone()
            assert status[0] == cancellation_id
            assert status[1] == reason
            assert status[2] == reversal_date
            assert status[3] is not None
            reversal_journal_id = status[4]
            assert reversal_journal_id is not None
            assert status[5].startswith(f"JE-{reversal_date:%Y%m}-")
            assert status[6:] == ("posted", False, True, True, False)

            # Original journal and Stage 5D.22 posting audit remain byte-for-byte
            # equivalent at the database-row level after cancellation.
            assert connection.execute(
                """
                select status, entry_number, source_event_key, posted_by_user_id, posted_at
                from accounting.journal_entries where id = %s
                """,
                (original_journal_id,),
            ).fetchone() == original_snapshot
            assert connection.execute(
                "select * from accounting.loan_disbursement_journal_postings where id = %s",
                (posting_id,),
            ).fetchone() == posting_snapshot
            assert connection.execute(
                "select is_voided from lending.loan_disbursement_events where id = %s",
                (event_id,),
            ).fetchone() == (False,)

            reversal_lines = connection.execute(
                """
                select line.account_id, line.debit, line.credit,
                       line.client_id, line.loan_id
                from accounting.journal_lines line
                where line.journal_entry_id = %s
                order by line.line_number
                """,
                (reversal_journal_id,),
            ).fetchall()
            # Original line order is preserved while debit/credit are swapped:
            # original Dr 1100 becomes Cr 1100; original Cr Cash becomes Dr Cash.
            assert reversal_lines == [
                (debit_account_id, Decimal("0.00"), amount, client_id, loan_id),
                (credit_account_id, amount, Decimal("0.00"), client_id, loan_id),
            ]

            reversal_audit = connection.execute(
                """
                select cancellation_id, posting_id, disbursement_event_id,
                       original_journal_entry_id, reversal_journal_entry_id,
                       original_entry_number, original_source_event_key,
                       original_debit_account_id, original_credit_account_id, amount
                from accounting.loan_disbursement_journal_reversals
                where cancellation_id = %s
                """,
                (cancellation_id,),
            ).fetchone()
            assert reversal_audit == (
                cancellation_id,
                posting_id,
                event_id,
                original_journal_id,
                reversal_journal_id,
                original_entry_number,
                original_source_key,
                debit_account_id,
                credit_account_id,
                amount,
            )

            # Exact retry is idempotent. Different actor/reason/date is not.
            assert connection.execute(
                "select accounting.reverse_posted_new_loan_disbursement(%s, %s, %s, %s)",
                (posting_id, actor_id, reversal_date, reason),
            ).fetchone()[0] == cancellation_id
            assert connection.execute(
                "select count(*) from lending.loan_disbursement_cancellations where posting_id = %s",
                (posting_id,),
            ).fetchone()[0] == 1
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_reversals where posting_id = %s",
                (posting_id,),
            ).fetchone()[0] == 1

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.reverse_posted_new_loan_disbursement(%s, %s, %s, %s)",
                        (posting_id, actor_id, reversal_date, "Different retry reason"),
                    )
            other_actor = _actor(connection, f"{suffix}-other")
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.reverse_posted_new_loan_disbursement(%s, %s, %s, %s)",
                        (posting_id, other_actor, reversal_date, reason),
                    )

            # Immutable cancellation/reversal evidence cannot be mutated/deleted.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "update lending.loan_disbursement_cancellations set reason = 'tampered' where id = %s",
                        (cancellation_id,),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.loan_disbursement_journal_reversals where cancellation_id = %s",
                        (cancellation_id,),
                    )

            # Evidence-only void remains forbidden even after the controlled
            # cancellation; history is represented by cancellation + reversal.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.void_loan_disbursement_evidence(%s, %s, %s)",
                        (event_id, actor_id, "Original evidence remains immutable"),
                    )

            # Atomic rollback proof: fail the final immutable reversal audit after
            # cancellation creation and reversing-journal posting have begun.
            rollback_client, rollback_loan, rollback_event, rollback_posting, rollback_posted = (
                _new_posted_source(
                    connection,
                    suffix=f"b{suffix}",
                    actor_id=actor_id,
                    release_date=release_date,
                )
            )
            rollback_original_journal = rollback_posted[0]
            rollback_original_snapshot = connection.execute(
                "select status, entry_number, posted_by_user_id, posted_at from accounting.journal_entries where id = %s",
                (rollback_original_journal,),
            ).fetchone()
            before_journal_count = connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0]

            connection.execute(
                """
                create or replace function accounting.test_fail_d23_reversal_audit()
                returns trigger language plpgsql as $$
                begin
                    raise exception 'forced Stage 5D.23 reversal audit failure';
                end;
                $$
                """
            )
            connection.execute(
                """
                create trigger zzz_test_fail_d23_reversal_audit
                before insert on accounting.loan_disbursement_journal_reversals
                for each row execute function accounting.test_fail_d23_reversal_audit()
                """
            )

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.reverse_posted_new_loan_disbursement(%s, %s, %s, %s)",
                        (
                            rollback_posting,
                            actor_id,
                            reversal_date,
                            "Forced audit failure must roll back everything",
                        ),
                    )

            assert connection.execute(
                "select count(*) from lending.loan_disbursement_cancellations where posting_id = %s",
                (rollback_posting,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_reversals where posting_id = %s",
                (rollback_posting,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0] == before_journal_count
            assert connection.execute(
                "select status, entry_number, posted_by_user_id, posted_at from accounting.journal_entries where id = %s",
                (rollback_original_journal,),
            ).fetchone() == rollback_original_snapshot
            assert connection.execute(
                "select is_voided from lending.loan_disbursement_events where id = %s",
                (rollback_event,),
            ).fetchone() == (False,)

            connection.execute(
                "drop trigger zzz_test_fail_d23_reversal_audit on accounting.loan_disbursement_journal_reversals"
            )
            connection.execute(
                "drop function accounting.test_fail_d23_reversal_audit()"
            )
        finally:
            connection.rollback()
