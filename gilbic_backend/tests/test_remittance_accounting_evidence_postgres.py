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
SQL_0057 = (SQL_ROOT / "0057_add_remittance_accounting_evidence.sql").read_text(
    encoding="utf-8"
)
MANILA = timezone(timedelta(hours=8))


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _create_user(connection, suffix: str):
    return connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"remit-accounting-{suffix}", f"Remittance Accounting {suffix}"),
    ).fetchone()[0]


def _create_received_remittance(
    connection,
    *,
    suffix: str,
    collector_id,
    recipient_id,
    business_date,
    amount="1500.00",
    received_at=None,
):
    exact_time = received_at or datetime(
        business_date.year,
        business_date.month,
        business_date.day,
        10,
        0,
        tzinfo=MANILA,
    )
    return connection.execute(
        """
        insert into lending.collection_remittances (
            remittance_number,
            collector_user_id,
            recipient_user_id,
            collection_date,
            status,
            transaction_count,
            payment_count,
            unable_to_pay_count,
            covered_payment_count,
            client_count,
            total_amount,
            note,
            submitted_at,
            received_at,
            received_by_user_id,
            custody_user_id,
            custody_transferred_at,
            created_at,
            updated_at
        ) values (
            %s, %s, %s, %s, 'received',
            1, 1, 0, 0, 1, %s, '',
            %s, %s, %s, %s, %s, %s, %s
        )
        returning id
        """,
        (
            f"REM-{suffix}",
            collector_id,
            recipient_id,
            business_date,
            amount,
            exact_time - timedelta(minutes=5),
            exact_time,
            recipient_id,
            recipient_id,
            exact_time,
            exact_time - timedelta(minutes=5),
            exact_time,
        ),
    ).fetchone()[0]


def _create_submitted_remittance(
    connection,
    *,
    suffix: str,
    collector_id,
    recipient_id,
    business_date,
):
    return connection.execute(
        """
        insert into lending.collection_remittances (
            remittance_number,
            collector_user_id,
            recipient_user_id,
            collection_date,
            status,
            transaction_count,
            payment_count,
            unable_to_pay_count,
            covered_payment_count,
            client_count,
            total_amount,
            note
        ) values (%s, %s, %s, %s, 'submitted', 1, 1, 0, 0, 1, 100.00, '')
        returning id
        """,
        (f"REM-{suffix}", collector_id, recipient_id, business_date),
    ).fetchone()[0]


def _record(
    connection,
    *,
    remittance_id,
    actor_id,
    business_date,
    destination="cash_office",
    reference="OFFICE-CASH-001",
    transferred_at=None,
):
    exact_time = transferred_at or datetime(
        business_date.year,
        business_date.month,
        business_date.day,
        10,
        5,
        tzinfo=MANILA,
    )
    return connection.execute(
        """
        select accounting.record_remittance_transfer_evidence(
            %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            remittance_id,
            actor_id,
            destination,
            business_date,
            exact_time,
            reference,
            "Disposable remittance accounting evidence",
        ),
    ).fetchone()[0]


def test_remittance_destination_evidence_is_explicit_immutable_and_never_income() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        required = (
            "core.users",
            "lending.collection_remittances",
            "accounting.accounts",
            "accounting.fiscal_periods",
            "accounting.journal_entries",
        )
        for relation in required:
            if connection.execute(
                "select to_regclass(%s)", (relation,)
            ).fetchone()[0] is None:
                pytest.skip(f"Accounting prerequisite is not installed: {relation}")

        try:
            assert connection.execute(
                "select to_regclass('accounting.remittance_transfer_evidence')"
            ).fetchone()[0] is None
            before_journals = connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0]

            connection.execute(_transaction_body(SQL_0057))

            assert connection.execute(
                "select count(*) from accounting.remittance_transfer_evidence"
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0] == before_journals

            actor_id = _create_user(connection, f"{suffix}-actor")
            collector_id = _create_user(connection, f"{suffix}-collector")
            recipient_id = _create_user(connection, f"{suffix}-recipient")
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            business_date = max_end + timedelta(days=7)

            remittance_id = _create_received_remittance(
                connection,
                suffix=f"{suffix}-ready",
                collector_id=collector_id,
                recipient_id=recipient_id,
                business_date=business_date,
            )
            evidence_id = _record(
                connection,
                remittance_id=remittance_id,
                actor_id=actor_id,
                business_date=business_date,
            )

            readiness = connection.execute(
                """
                select readiness_status, source_event_key,
                       debit_account_system_key, credit_account_system_key,
                       debit_amount, credit_amount, income_recognition,
                       journal_lines_enabled, automatic_source_posting
                from accounting.remittance_transfer_readiness
                where remittance_id = %s
                """,
                (remittance_id,),
            ).fetchone()
            assert readiness == (
                "transfer_coordinate_ready",
                f"remittance_transfer:{remittance_id}",
                "cash_office",
                "cash_collector_custody",
                Decimal("1500.00"),
                Decimal("1500.00"),
                False,
                False,
                False,
            )

            repeated_id = _record(
                connection,
                remittance_id=remittance_id,
                actor_id=actor_id,
                business_date=business_date,
            )
            assert repeated_id == evidence_id

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "update accounting.remittance_transfer_evidence set evidence_note = 'tampered' where id = %s",
                        (evidence_id,),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.remittance_transfer_evidence where id = %s",
                        (evidence_id,),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record(
                        connection,
                        remittance_id=remittance_id,
                        actor_id=actor_id,
                        business_date=business_date,
                        destination="cash_bank_gcash",
                        reference="BANK-001",
                    )

            submitted_id = _create_submitted_remittance(
                connection,
                suffix=f"{suffix}-submitted",
                collector_id=collector_id,
                recipient_id=recipient_id,
                business_date=business_date,
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record(
                        connection,
                        remittance_id=submitted_id,
                        actor_id=actor_id,
                        business_date=business_date,
                    )

            invalid_destination_id = _create_received_remittance(
                connection,
                suffix=f"{suffix}-invalid",
                collector_id=collector_id,
                recipient_id=recipient_id,
                business_date=business_date,
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record(
                        connection,
                        remittance_id=invalid_destination_id,
                        actor_id=actor_id,
                        business_date=business_date,
                        destination="interest_income_regular",
                    )

            before_custody_id = _create_received_remittance(
                connection,
                suffix=f"{suffix}-early",
                collector_id=collector_id,
                recipient_id=recipient_id,
                business_date=business_date,
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record(
                        connection,
                        remittance_id=before_custody_id,
                        actor_id=actor_id,
                        business_date=business_date,
                        transferred_at=datetime(
                            business_date.year,
                            business_date.month,
                            business_date.day,
                            9,
                            59,
                            tzinfo=MANILA,
                        ),
                    )

            connection.execute(
                "select accounting.void_remittance_transfer_evidence(%s, %s, %s)",
                (evidence_id, actor_id, "Correct destination reference"),
            )
            corrected_id = _record(
                connection,
                remittance_id=remittance_id,
                actor_id=actor_id,
                business_date=business_date,
                destination="cash_bank_gcash",
                reference="BANK-DEP-001",
            )
            assert corrected_id != evidence_id

            period_id = connection.execute(
                """
                insert into accounting.fiscal_periods (label, start_date, end_date, status)
                values (%s, %s, %s, 'open')
                returning id
                """,
                (f"Remittance disposable {suffix}", business_date, business_date),
            ).fetchone()[0]
            connection.execute(
                """
                insert into accounting.journal_entries (
                    fiscal_period_id, posting_date, description, status,
                    source_type, source_reference, source_event_key,
                    created_by_user_id
                ) values (%s, %s, 'Disposable remittance history guard', 'draft',
                          'remittance_transfer', %s, %s, %s)
                """,
                (
                    period_id,
                    business_date,
                    f"REM-{suffix}-ready",
                    f"remittance_transfer:{remittance_id}",
                    actor_id,
                ),
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.void_remittance_transfer_evidence(%s, %s, %s)",
                        (corrected_id, actor_id, "Cannot void journalled evidence"),
                    )

            assert connection.execute(
                "select count(*) from accounting.journal_entries where source_event_key = %s",
                (f"remittance_transfer:{remittance_id}",),
            ).fetchone()[0] == 1
        finally:
            connection.rollback()
