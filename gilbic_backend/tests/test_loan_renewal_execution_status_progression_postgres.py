from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_0050 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0050_add_authoritative_renewal_execution_evidence.sql"
).read_text(encoding="utf-8")
MANILA = timezone(timedelta(hours=8))


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;") and body.endswith("COMMIT;")
    return body[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def test_normal_status_progression_does_not_rewrite_or_invalidate_renewal_evidence() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "select to_regclass('lending.loan_disbursement_events')"
        ).fetchone()[0] is None:
            pytest.skip("Stage 5D.19 disbursement evidence prerequisite is not installed")
        try:
            connection.execute(_transaction_body(SQL_0050))
            actor_id = connection.execute(
                """
                insert into core.users (username, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"renew-status-{suffix}", f"Renewal Status {suffix}"),
            ).fetchone()[0]
            client_id = connection.execute(
                """
                insert into lending.clients (client_code, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"RS-C-{suffix}", f"Renewal Status Client {suffix}"),
            ).fetchone()[0]
            loan_type_id = connection.execute(
                """
                insert into lending.loan_types (
                    code, name, term_days, calculation_mode, daily_interest_per_1000
                ) values (%s, %s, 120, 'fixed_daily', 0) returning id
                """,
                (f"RS-{suffix}", f"Renewal Status Type {suffix}"),
            ).fetchone()[0]
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            old_date = max_end + timedelta(days=7)
            new_date = old_date + timedelta(days=30)

            def create_loan(number: str, release_date):
                return connection.execute(
                    """
                    insert into lending.loans (
                        loan_number, client_id, loan_type_id, principal, daily_amount,
                        date_released, due_date, status, created_by_user_id
                    ) values (%s, %s, %s, 5000.00, 50.00, %s, %s, 'active', %s)
                    returning id
                    """,
                    (
                        number,
                        client_id,
                        loan_type_id,
                        release_date,
                        release_date + timedelta(days=120),
                        actor_id,
                    ),
                ).fetchone()[0]

            old_loan_id = create_loan(f"RS-OLD-{suffix}", old_date)
            new_loan_id = create_loan(f"RS-NEW-{suffix}", new_date)
            disbursed_at = datetime(
                new_date.year, new_date.month, new_date.day, 9, 0, tzinfo=MANILA
            )
            release_event_id = connection.execute(
                """
                select accounting.record_loan_disbursement_evidence(
                    %s, %s, 'renewal_release', %s, %s,
                    2000.00, 3000.00, 0.00, 'cash_office', %s, ''
                )
                """,
                (
                    new_loan_id,
                    actor_id,
                    new_date,
                    disbursed_at,
                    f"RS-RELEASE-{suffix}",
                ),
            ).fetchone()[0]
            executed_at = datetime(
                new_date.year, new_date.month, new_date.day, 9, 5, tzinfo=MANILA
            )
            execution_id = connection.execute(
                """
                select accounting.record_loan_renewal_execution_evidence(
                    %s, %s, %s, %s, %s, %s,
                    3000.00, %s, '', null
                )
                """,
                (
                    old_loan_id,
                    new_loan_id,
                    release_event_id,
                    actor_id,
                    new_date,
                    executed_at,
                    f"RS-EXEC-{suffix}",
                ),
            ).fetchone()[0]
            original_status_snapshots = connection.execute(
                """
                select old_loan_status_snapshot, new_loan_status_snapshot
                from lending.loan_renewal_execution_events where id = %s
                """,
                (execution_id,),
            ).fetchone()
            assert original_status_snapshots == ("active", "active")

            # Closing the settled old loan and later paying the new loan are normal
            # lifecycle changes. They must not rewrite historical evidence or make
            # the exact original evidence request non-idempotent.
            connection.execute(
                "update lending.loans set status = 'closed' where id = %s",
                (old_loan_id,),
            )
            connection.execute(
                "update lending.loans set status = 'paid' where id = %s",
                (new_loan_id,),
            )
            assert connection.execute(
                """
                select readiness_status
                from accounting.loan_renewal_execution_source_readiness
                where disbursement_event_id = %s
                """,
                (release_event_id,),
            ).fetchone() == ("renewal_execution_evidence_ready",)

            repeated_id = connection.execute(
                """
                select accounting.record_loan_renewal_execution_evidence(
                    %s, %s, %s, %s, %s, %s,
                    3000.00, %s, '', null
                )
                """,
                (
                    old_loan_id,
                    new_loan_id,
                    release_event_id,
                    actor_id,
                    new_date,
                    executed_at,
                    f"RS-EXEC-{suffix}",
                ),
            ).fetchone()[0]
            assert repeated_id == execution_id
            assert connection.execute(
                """
                select old_loan_status_snapshot, new_loan_status_snapshot
                from lending.loan_renewal_execution_events where id = %s
                """,
                (execution_id,),
            ).fetchone() == original_status_snapshots
        finally:
            connection.rollback()
