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
        (f"remit-journal-{suffix}", f"Remittance Journal {suffix}"),
    ).fetchone()[0]


def _create_received_remittance(
    connection,
    *,
    suffix: str,
    collector_id,
    recipient_id,
    business_date,
    amount="1500.00",
):
    received_at = datetime(
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
            f"RJL-{suffix}",
            collector_id,
            recipient_id,
            business_date,
            amount,
            received_at - timedelta(minutes=5),
            received_at,
            recipient_id,
            recipient_id,
            received_at,
            received_at - timedelta(minutes=5),
            received_at,
        ),
    ).fetchone()[0]


def _record_evidence(connection, *, remittance_id, actor_id, business_date):
    transferred_at = datetime(
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
            %s, %s, 'cash_office', %s, %s, %s, %s
        )
        """,
        (
            remittance_id,
            actor_id,
            business_date,
            transferred_at,
            f"OFFICE-{remittance_id}",
            "Protected remittance journal lifecycle test",
        ),
    ).fetchone()[0]


def test_protected_remittance_transfer_draft_post_reversal_and_reconciliation() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        required = (
            "core.users",
            "lending.collection_remittances",
            "accounting.accounts",
            "accounting.fiscal_periods",
            "accounting.journal_entries",
            "accounting.remittance_transfer_evidence",
            "accounting.remittance_transfer_readiness",
        )
        for relation in required:
            if connection.execute(
                "select to_regclass(%s)", (relation,)
            ).fetchone()[0] is None:
                pytest.skip(f"Accounting prerequisite is not installed: {relation}")

        try:
            assert connection.execute(
                "select to_regclass('accounting.remittance_transfer_journal_preparations')"
            ).fetchone()[0] is None
            before_journals = connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0]
            before_lines = connection.execute(
                "select count(*) from accounting.journal_lines"
            ).fetchone()[0]

            connection.execute(_transaction_body(SQL_0058))

            assert connection.execute(
                "select count(*) from accounting.remittance_transfer_journal_preparations"
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.remittance_transfer_journal_postings"
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.remittance_transfer_journal_reversals"
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0] == before_journals
            assert connection.execute(
                "select count(*) from accounting.journal_lines"
            ).fetchone()[0] == before_lines

            actor_id = _create_user(connection, f"{suffix}-actor")
            collector_id = _create_user(connection, f"{suffix}-collector")
            recipient_id = _create_user(connection, f"{suffix}-recipient")

            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            business_date = max_end + timedelta(days=7)
            period_id = connection.execute(
                """
                insert into accounting.fiscal_periods (label, start_date, end_date, status)
                values (%s, %s, %s, 'open')
                returning id
                """,
                (f"Remittance journal {suffix}", business_date, business_date),
            ).fetchone()[0]

            remittance_id = _create_received_remittance(
                connection,
                suffix=suffix,
                collector_id=collector_id,
                recipient_id=recipient_id,
                business_date=business_date,
            )
            evidence_id = _record_evidence(
                connection,
                remittance_id=remittance_id,
                actor_id=actor_id,
                business_date=business_date,
            )
            source_key = f"remittance_transfer:{remittance_id}"
            draft_token = "a" * 64
            posting_token = "b" * 64

            preparation_id = connection.execute(
                """
                select accounting.create_remittance_transfer_journal_draft(
                    %s, %s, %s, %s, %s, %s,
                    'cash_office', 'cash_collector_custody', 1500.00,
                    'remittance_transfer_coordinates_v1',
                    'remittance_transfer_journal_draft_v1'
                )
                """,
                (
                    remittance_id,
                    actor_id,
                    draft_token,
                    evidence_id,
                    source_key,
                    business_date,
                ),
            ).fetchone()[0]

            status = connection.execute(
                """
                select journal_entry_id, posting_ready, posted_audit_exact,
                       reversal_audit_exact, lifecycle_status,
                       debit_account_system_key, credit_account_system_key,
                       amount, income_recognition, explicit_management_posting,
                       automatic_source_posting
                from accounting.remittance_transfer_journal_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone()
            journal_id = status[0]
            assert status[1:] == (
                True,
                False,
                False,
                "draft",
                "cash_office",
                "cash_collector_custody",
                Decimal("1500.00"),
                False,
                True,
                False,
            )

            lines = connection.execute(
                """
                select account.system_key, line.debit, line.credit
                from accounting.journal_lines line
                join accounting.accounts account on account.id = line.account_id
                where line.journal_entry_id = %s
                order by line.line_number
                """,
                (journal_id,),
            ).fetchall()
            assert lines == [
                ("cash_office", Decimal("1500.00"), Decimal("0.00")),
                ("cash_collector_custody", Decimal("0.00"), Decimal("1500.00")),
            ]

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "update accounting.journal_lines set description = 'tampered' where journal_entry_id = %s",
                        (journal_id,),
                    )

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.post_journal_entry(%s, %s)",
                        (journal_id, actor_id),
                    )

            repeated_preparation = connection.execute(
                """
                select accounting.create_remittance_transfer_journal_draft(
                    %s, %s, %s, %s, %s, %s,
                    'cash_office', 'cash_collector_custody', 1500.00,
                    'remittance_transfer_coordinates_v1',
                    'remittance_transfer_journal_draft_v1'
                )
                """,
                (
                    remittance_id,
                    actor_id,
                    draft_token,
                    evidence_id,
                    source_key,
                    business_date,
                ),
            ).fetchone()[0]
            assert repeated_preparation == preparation_id

            posting_id = connection.execute(
                """
                select accounting.post_remittance_transfer_journal(
                    %s, %s, %s, %s, %s, %s, 1500.00,
                    'remittance_transfer_journal_posting_v1'
                )
                """,
                (
                    preparation_id,
                    actor_id,
                    posting_token,
                    journal_id,
                    source_key,
                    draft_token,
                ),
            ).fetchone()[0]

            posted = connection.execute(
                """
                select journal_status, posting_id, posting_ready,
                       posted_audit_exact, reversal_audit_exact, lifecycle_status
                from accounting.remittance_transfer_journal_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone()
            assert posted == (
                "posted",
                posting_id,
                False,
                True,
                False,
                "posted",
            )

            repeated_post = connection.execute(
                """
                select accounting.post_remittance_transfer_journal(
                    %s, %s, %s, %s, %s, %s, 1500.00,
                    'remittance_transfer_journal_posting_v1'
                )
                """,
                (
                    preparation_id,
                    actor_id,
                    posting_token,
                    journal_id,
                    source_key,
                    draft_token,
                ),
            ).fetchone()[0]
            assert repeated_post == posting_id

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.create_reversal_draft(%s, %s, %s, %s)",
                        (
                            journal_id,
                            actor_id,
                            business_date,
                            "Generic reversal must be blocked",
                        ),
                    )

            reversal_id = connection.execute(
                "select accounting.reverse_posted_remittance_transfer(%s, %s, %s, %s)",
                (posting_id, actor_id, business_date, "Destination transfer corrected"),
            ).fetchone()[0]

            reversed_status = connection.execute(
                """
                select reversal_id, posted_audit_exact, reversal_audit_exact,
                       lifecycle_status, reversal_journal_entry_id
                from accounting.remittance_transfer_journal_status
                where preparation_id = %s
                """,
                (preparation_id,),
            ).fetchone()
            assert reversed_status[0] == reversal_id
            assert reversed_status[1:4] == (True, True, "reversed")
            reversal_journal_id = reversed_status[4]

            reversal_lines = connection.execute(
                """
                select account.system_key, line.debit, line.credit
                from accounting.journal_lines line
                join accounting.accounts account on account.id = line.account_id
                where line.journal_entry_id = %s
                order by line.line_number
                """,
                (reversal_journal_id,),
            ).fetchall()
            assert reversal_lines == [
                ("cash_collector_custody", Decimal("1500.00"), Decimal("0.00")),
                ("cash_office", Decimal("0.00"), Decimal("1500.00")),
            ]

            repeated_reversal = connection.execute(
                "select accounting.reverse_posted_remittance_transfer(%s, %s, %s, %s)",
                (posting_id, actor_id, business_date, "Destination transfer corrected"),
            ).fetchone()[0]
            assert repeated_reversal == reversal_id

            net = connection.execute(
                """
                select account.system_key,
                       sum(line.debit - line.credit)::numeric(18,2)
                from accounting.journal_lines line
                join accounting.accounts account on account.id = line.account_id
                where line.journal_entry_id in (%s, %s)
                  and account.system_key in ('cash_office', 'cash_collector_custody')
                group by account.system_key
                order by account.system_key
                """,
                (journal_id, reversal_journal_id),
            ).fetchall()
            assert net == [
                ("cash_collector_custody", Decimal("0.00")),
                ("cash_office", Decimal("0.00")),
            ]

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.void_remittance_transfer_evidence(%s, %s, %s)",
                        (evidence_id, actor_id, "Cannot void posted history"),
                    )

            assert period_id is not None
        finally:
            connection.rollback()
