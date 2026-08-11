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
SQL_0046 = (
    SQL_ROOT / "0046_add_new_loan_disbursement_journal_coordinates.sql"
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
        (f"d20-{suffix}", f"Stage 5D.20 {suffix}"),
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
        (f"D20-C-{suffix}", f"D20 Client {suffix}"),
    ).fetchone()[0]
    daily_interest = "7.00" if calculation_mode == "seven_by_seven" else "0.00"
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) values (%s, %s, 120, %s, %s) returning id
        """,
        (
            f"D20-T-{suffix}",
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
            f"D20-L-{suffix}", client_id, loan_type_id, principal,
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
    event_kind: str = "new_loan_release",
    settlement: str = "0.00",
    deduction: str = "0.00",
    account: str = "cash_office",
    reference: str = "D20-RELEASE",
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
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            loan_id, actor_id, event_kind, business_date, disbursed_at,
            cash, settlement, deduction, account, reference,
            "Stage 5D.20 disposable coordinate evidence",
        ),
    ).fetchone()[0]


def test_new_regular_release_coordinates_are_exact_and_read_only() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            assert connection.execute(
                "select to_regclass('lending.loan_disbursement_events')"
            ).fetchone()[0] is not None
            assert connection.execute(
                "select to_regclass('accounting.loan_disbursement_journal_coordinates')"
            ).fetchone()[0] is None

            before_journals = connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0]
            connection.execute(_transaction_body(SQL_0046))
            assert connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0] == before_journals

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
                (f"D20 {suffix}", release_date, release_date),
            ).fetchone()[0]

            _, loan_id = _loan(
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

            row = connection.execute(
                """
                select coordinate_status, fiscal_period_id,
                       debit_account_system_key, debit_amount,
                       credit_account_system_key, credit_amount,
                       source_event_key, journal_draft_enabled,
                       automatic_source_posting, initial_measurement_basis
                from accounting.loan_disbursement_journal_coordinates
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert row == (
                "coordinate_ready",
                period_id,
                "loans_receivable_regular",
                Decimal("5000.00"),
                "cash_office",
                Decimal("5000.00"),
                f"loan_disbursement:{event_id}",
                False,
                False,
                "transaction_price_plain_cash_v1",
            )

            # Exact source history makes the coordinate fail closed instead of
            # presenting a duplicate candidate.
            connection.execute(
                """
                insert into accounting.journal_entries (
                    fiscal_period_id, posting_date, description, status,
                    source_type, source_reference, source_event_key,
                    created_by_user_id, updated_at
                ) values (
                    %s, %s, 'Synthetic existing disbursement journal', 'draft',
                    'loan_disbursement', %s, %s, %s, now()
                )
                """,
                (
                    period_id, release_date, str(event_id),
                    f"loan_disbursement:{event_id}", actor_id,
                ),
            )
            assert connection.execute(
                """
                select coordinate_status, debit_amount, credit_amount
                from accounting.loan_disbursement_journal_coordinates
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone() == ("journal_history_exists", None, None)

            # A new Regular release without an open fiscal period is blocked.
            no_period_date = release_date + timedelta(days=2)
            _, no_period_loan = _loan(
                connection,
                suffix=f"{suffix}p",
                actor_id=actor_id,
                release_date=no_period_date,
            )
            _record(
                connection,
                loan_id=no_period_loan,
                actor_id=actor_id,
                business_date=no_period_date,
                cash="5000.00",
                reference="D20-NO-PERIOD",
            )
            assert connection.execute(
                """
                select coordinate_status
                from accounting.loan_disbursement_journal_coordinates
                where loan_id = %s
                """,
                (no_period_loan,),
            ).fetchone() == ("fiscal_period_not_open",)

            # 7x7 may have valid Stage 5D.19 funding evidence, but Stage 5D.20
            # intentionally refuses to invent its accounting coordinates.
            _, seven_loan = _loan(
                connection,
                suffix=f"{suffix}7",
                actor_id=actor_id,
                release_date=release_date,
                calculation_mode="seven_by_seven",
            )
            _record(
                connection,
                loan_id=seven_loan,
                actor_id=actor_id,
                business_date=release_date,
                cash="5000.00",
                reference="D20-7X7",
            )
            assert connection.execute(
                """
                select coordinate_status, debit_account_system_key
                from accounting.loan_disbursement_journal_coordinates
                where loan_id = %s
                """,
                (seven_loan,),
            ).fetchone() == ("loan_type_policy_review", None)

            # Renewal/settlement and deduction cases preserve the upstream
            # policy block and never expose candidate debit/credit amounts.
            _, renewal_loan = _loan(
                connection,
                suffix=f"{suffix}r",
                actor_id=actor_id,
                release_date=release_date,
            )
            _record(
                connection,
                loan_id=renewal_loan,
                actor_id=actor_id,
                business_date=release_date,
                cash="2000.00",
                settlement="3000.00",
                event_kind="renewal_release",
                reference="D20-RENEW",
            )
            assert connection.execute(
                """
                select coordinate_status, debit_amount, credit_amount
                from accounting.loan_disbursement_journal_coordinates
                where loan_id = %s
                """,
                (renewal_loan,),
            ).fetchone() == (
                "renewal_or_restructure_policy_review", None, None
            )

            _, deduction_loan = _loan(
                connection,
                suffix=f"{suffix}d",
                actor_id=actor_id,
                release_date=release_date,
            )
            _record(
                connection,
                loan_id=deduction_loan,
                actor_id=actor_id,
                business_date=release_date,
                cash="4900.00",
                deduction="100.00",
                reference="D20-DEDUCT",
            )
            assert connection.execute(
                """
                select coordinate_status, debit_amount, credit_amount
                from accounting.loan_disbursement_journal_coordinates
                where loan_id = %s
                """,
                (deduction_loan,),
            ).fetchone() == (
                "deduction_or_settlement_policy_review", None, None
            )
        finally:
            connection.rollback()
