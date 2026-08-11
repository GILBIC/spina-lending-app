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
SQL_0047 = (
    SQL_ROOT / "0047_add_protected_new_loan_disbursement_journal_drafts.sql"
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
        (f"d21-{suffix}", f"Stage 5D.21 {suffix}"),
    ).fetchone()[0]


def _loan(
    connection,
    *,
    suffix: str,
    actor_id,
    release_date,
    calculation_mode: str = "fixed_daily",
    principal: str = "5000.00",
):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"D21-C-{suffix}", f"D21 Client {suffix}"),
    ).fetchone()[0]
    daily_interest = "7.00" if calculation_mode == "seven_by_seven" else "0.00"
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) values (%s, %s, 120, %s, %s) returning id
        """,
        (
            f"D21-T-{suffix}",
            "7x7" if calculation_mode == "seven_by_seven" else "Regular",
            calculation_mode,
            daily_interest,
        ),
    ).fetchone()[0]
    daily_amount = "35.00" if calculation_mode == "seven_by_seven" else "50.00"
    interest_rate = None if calculation_mode == "seven_by_seven" else "20.0000"
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) values (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)
        returning id
        """,
        (
            f"D21-L-{suffix}", client_id, loan_type_id, principal,
            daily_amount, interest_rate, release_date,
            release_date + timedelta(days=120), actor_id,
        ),
    ).fetchone()[0]
    return client_id, loan_id


def _record(
    connection,
    *,
    loan_id,
    actor_id,
    business_date,
    cash: str,
    account: str = "cash_office",
    reference: str = "D21-RELEASE",
):
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
            %s, %s, 'new_loan_release', %s, %s, %s,
            0.00, 0.00, %s, %s, %s
        )
        """,
        (
            loan_id,
            actor_id,
            business_date,
            disbursed_at,
            cash,
            account,
            reference,
            "Stage 5D.21 disposable draft evidence",
        ),
    ).fetchone()[0]


def _coordinates(connection, event_id):
    return connection.execute(
        """
        select
            coordinate_status,
            source_event_key,
            posting_date,
            fiscal_period_id,
            debit_account_id,
            credit_account_id,
            debit_amount,
            credit_amount
        from accounting.loan_disbursement_journal_coordinates
        where disbursement_event_id = %s
        """,
        (event_id,),
    ).fetchone()


def _prepare(connection, *, event_id, actor_id, review_token, coordinate):
    return connection.execute(
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
            review_token,
            coordinate[1],
            coordinate[2],
            coordinate[3],
            coordinate[4],
            coordinate[5],
            coordinate[6],
        ),
    ).fetchone()[0]


def test_new_regular_disbursement_draft_is_confirmed_immutable_and_not_posted() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    review_token = "a" * 64

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            assert connection.execute(
                "select to_regclass('accounting.loan_disbursement_journal_coordinates')"
            ).fetchone()[0] is not None
            assert connection.execute(
                "select to_regclass('accounting.loan_disbursement_journal_draft_preparations')"
            ).fetchone()[0] is None

            before_journals = connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0]
            before_lines = connection.execute(
                "select count(*) from accounting.journal_lines"
            ).fetchone()[0]
            connection.execute(_transaction_body(SQL_0047))
            assert connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0] == before_journals
            assert connection.execute(
                "select count(*) from accounting.journal_lines"
            ).fetchone()[0] == before_lines
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_draft_preparations"
            ).fetchone()[0] == 0

            actor_id = _actor(connection, suffix)
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            release_date = max_end + timedelta(days=7)
            period_id = connection.execute(
                """
                insert into accounting.fiscal_periods (
                    label, start_date, end_date, status
                ) values (%s, %s, %s, 'open') returning id
                """,
                (f"D21 {suffix}", release_date, release_date),
            ).fetchone()[0]

            client_id, loan_id = _loan(
                connection,
                suffix=f"{suffix}a",
                actor_id=actor_id,
                release_date=release_date,
            )
            event_id = _record(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                business_date=release_date,
                cash="5000.00",
            )
            coordinate = _coordinates(connection, event_id)
            assert coordinate[0] == "coordinate_ready"
            assert coordinate[3] == period_id
            assert coordinate[6:] == (Decimal("5000.00"), Decimal("5000.00"))

            # A mismatched Management confirmation fails before any journal is created.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    bad = list(coordinate)
                    bad[6] = Decimal("4999.00")
                    _prepare(
                        connection,
                        event_id=event_id,
                        actor_id=actor_id,
                        review_token=review_token,
                        coordinate=bad,
                    )
            assert connection.execute(
                "select count(*) from accounting.journal_entries where source_event_key = %s",
                (f"loan_disbursement:{event_id}",),
            ).fetchone()[0] == 0

            preparation_id = _prepare(
                connection,
                event_id=event_id,
                actor_id=actor_id,
                review_token=review_token,
                coordinate=coordinate,
            )
            status_row = connection.execute(
                """
                select journal_entry_id, journal_status, entry_number,
                       source_event_key, amount,
                       debit_account_system_key, credit_account_system_key,
                       line_count, total_debit, total_credit,
                       draft_integrity_ready, posting_enabled,
                       automatic_source_posting
                from accounting.loan_disbursement_journal_draft_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone()
            journal_id = status_row[0]
            assert status_row[1:] == (
                "draft",
                None,
                f"loan_disbursement:{event_id}",
                Decimal("5000.00"),
                "loans_receivable_regular",
                "cash_office",
                2,
                Decimal("5000.00"),
                Decimal("5000.00"),
                True,
                False,
                False,
            )

            lines = connection.execute(
                """
                select account.system_key, line.debit, line.credit,
                       line.client_id, line.loan_id
                from accounting.journal_lines line
                join accounting.accounts account on account.id = line.account_id
                where line.journal_entry_id = %s
                order by line.line_number
                """,
                (journal_id,),
            ).fetchall()
            assert lines == [
                ("loans_receivable_regular", Decimal("5000.00"), Decimal("0.00"), client_id, loan_id),
                ("cash_office", Decimal("0.00"), Decimal("5000.00"), client_id, loan_id),
            ]

            # Exact retry returns the same immutable preparation and journal.
            assert _prepare(
                connection,
                event_id=event_id,
                actor_id=actor_id,
                review_token=review_token,
                coordinate=coordinate,
            ) == preparation_id
            assert connection.execute(
                "select count(*) from accounting.journal_entries where source_event_key = %s",
                (f"loan_disbursement:{event_id}",),
            ).fetchone()[0] == 1

            # The normal General Journal and generic posting function cannot edit,
            # delete, mutate lines or post this protected source-event draft.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "update accounting.journal_entries set description = 'tampered' where id = %s",
                        (journal_id,),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "update accounting.journal_lines set debit = debit + 1 where journal_entry_id = %s and line_number = 1",
                        (journal_id,),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.journal_entries where id = %s",
                        (journal_id,),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.post_manual_journal_entry(%s, %s)",
                        (journal_id, actor_id),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.post_journal_entry(%s, %s)",
                        (journal_id, actor_id),
                    )
            assert connection.execute(
                "select status, entry_number from accounting.journal_entries where id = %s",
                (journal_id,),
            ).fetchone() == ("draft", None)

            # Once draft history exists, Stage 5D.19 evidence cannot be voided.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.void_loan_disbursement_evidence(%s, %s, %s)",
                        (event_id, actor_id, "Cannot erase protected draft source"),
                    )

            # 7x7 evidence remains policy-blocked and cannot be forced into the
            # Regular draft function even when callers supply plausible accounts.
            _, seven_loan = _loan(
                connection,
                suffix=f"{suffix}7",
                actor_id=actor_id,
                release_date=release_date,
                calculation_mode="seven_by_seven",
            )
            seven_event = _record(
                connection,
                loan_id=seven_loan,
                actor_id=actor_id,
                business_date=release_date,
                cash="5000.00",
                reference="D21-7X7",
            )
            assert _coordinates(connection, seven_event)[0] == "loan_type_policy_review"
            debit_id = connection.execute(
                "select id from accounting.accounts where system_key = 'loans_receivable_regular'"
            ).fetchone()[0]
            credit_id = connection.execute(
                "select id from accounting.accounts where system_key = 'cash_office'"
            ).fetchone()[0]
            fake_coordinate = (
                "loan_type_policy_review",
                f"loan_disbursement:{seven_event}",
                release_date,
                period_id,
                debit_id,
                credit_id,
                Decimal("5000.00"),
                Decimal("5000.00"),
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _prepare(
                        connection,
                        event_id=seven_event,
                        actor_id=actor_id,
                        review_token="b" * 64,
                        coordinate=fake_coordinate,
                    )
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_draft_preparations where disbursement_event_id = %s",
                (seven_event,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
