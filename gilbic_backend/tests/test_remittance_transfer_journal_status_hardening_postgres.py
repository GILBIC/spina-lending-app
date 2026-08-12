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
SQL_0058 = (
    SQL_ROOT / "0058_add_protected_remittance_transfer_journal_lifecycle.sql"
).read_text(encoding="utf-8")
SQL_0059 = (
    SQL_ROOT / "0059_harden_remittance_transfer_journal_status.sql"
).read_text(encoding="utf-8")
MANILA = timezone(timedelta(hours=8))


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _user(connection, suffix: str):
    return connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"remit-status-{suffix}", f"Remittance Status {suffix}"),
    ).fetchone()[0]


def test_status_posting_ready_fails_closed_when_current_controls_change() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0058))
            connection.execute(_transaction_body(SQL_0059))

            actor_id = _user(connection, f"{suffix}-actor")
            collector_id = _user(connection, f"{suffix}-collector")
            recipient_id = _user(connection, f"{suffix}-recipient")
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            business_date = max_end + timedelta(days=7)
            period_id = connection.execute(
                """
                insert into accounting.fiscal_periods (label, start_date, end_date, status)
                values (%s, %s, %s, 'open') returning id
                """,
                (f"Remittance status {suffix}", business_date, business_date),
            ).fetchone()[0]
            received_at = datetime(
                business_date.year,
                business_date.month,
                business_date.day,
                10,
                0,
                tzinfo=MANILA,
            )
            remittance_id = connection.execute(
                """
                insert into lending.collection_remittances (
                    remittance_number, collector_user_id, recipient_user_id,
                    collection_date, status, transaction_count, payment_count,
                    unable_to_pay_count, covered_payment_count, client_count,
                    total_amount, note, submitted_at, received_at,
                    received_by_user_id, custody_user_id, custody_transferred_at,
                    created_at, updated_at
                ) values (
                    %s, %s, %s, %s, 'received', 1, 1, 0, 0, 1,
                    750.00, '', %s, %s, %s, %s, %s, %s, %s
                ) returning id
                """,
                (
                    f"RSH-{suffix}",
                    collector_id,
                    recipient_id,
                    business_date,
                    received_at - timedelta(minutes=5),
                    received_at,
                    recipient_id,
                    recipient_id,
                    received_at,
                    received_at - timedelta(minutes=5),
                    received_at,
                ),
            ).fetchone()[0]
            evidence_id = connection.execute(
                """
                select accounting.record_remittance_transfer_evidence(
                    %s, %s, 'cash_office', %s, %s, %s, %s
                )
                """,
                (
                    remittance_id,
                    actor_id,
                    business_date,
                    received_at + timedelta(minutes=5),
                    f"STATUS-{suffix}",
                    "Status hardening proof",
                ),
            ).fetchone()[0]
            source_key = f"remittance_transfer:{remittance_id}"
            preparation_id = connection.execute(
                """
                select accounting.create_remittance_transfer_journal_draft(
                    %s, %s, %s, %s, %s, %s,
                    'cash_office', 'cash_collector_custody', 750.00,
                    'remittance_transfer_coordinates_v1',
                    'remittance_transfer_journal_draft_v1'
                )
                """,
                (
                    remittance_id,
                    actor_id,
                    "c" * 64,
                    evidence_id,
                    source_key,
                    business_date,
                ),
            ).fetchone()[0]

            assert connection.execute(
                """
                select posting_ready
                from accounting.remittance_transfer_journal_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone() == (True,)

            connection.execute(
                "update accounting.accounts set is_active = false where system_key = 'cash_office'"
            )
            assert connection.execute(
                """
                select posting_ready
                from accounting.remittance_transfer_journal_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone() == (False,)

            connection.execute(
                "update accounting.accounts set is_active = true where system_key = 'cash_office'"
            )
            assert connection.execute(
                """
                select posting_ready
                from accounting.remittance_transfer_journal_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone() == (True,)

            connection.execute(
                "update accounting.fiscal_periods set status = 'review' where id = %s",
                (period_id,),
            )
            assert connection.execute(
                """
                select posting_ready
                from accounting.remittance_transfer_journal_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone() == (False,)

            assert connection.execute(
                """
                select debit_account_system_key, credit_account_system_key, amount,
                       income_recognition, explicit_management_posting,
                       automatic_source_posting
                from accounting.remittance_transfer_journal_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone() == (
                "cash_office",
                "cash_collector_custody",
                Decimal("750.00"),
                False,
                True,
                False,
            )
        finally:
            connection.rollback()
