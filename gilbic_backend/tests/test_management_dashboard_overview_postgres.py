from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import gilbic_backend.management_dashboard_overview_repository as overview_module
import psycopg
import pytest
from gilbic_backend.management_dashboard_overview_repository import (
    PostgresManagementDashboardOverviewRepository,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


@contextmanager
def _same_connection(connection):
    yield connection


def _insert_user(connection, *, suffix: str, role: str, status: str = "active") -> UUID:
    user_id = connection.execute(
        """
        insert into core.users (username, email, full_name, status)
        values (%s, %s, %s, %s)
        returning id
        """,
        (
            f"overview-{role}-{suffix}-{uuid4().hex[:6]}",
            f"overview-{role}-{suffix}-{uuid4().hex[:6]}@example.com",
            f"Overview {role.title()} {suffix}",
            status,
        ),
    ).fetchone()[0]
    connection.execute(
        """
        insert into core.user_roles (user_id, role_id)
        select %s, id from core.roles where code = %s
        """,
        (user_id, role),
    )
    return user_id


def _insert_device(
    connection,
    *,
    user_id: UUID,
    platform: str,
    status: str,
    suffix: str,
) -> UUID:
    return connection.execute(
        """
        insert into core.devices (
            user_id,
            device_identifier_hash,
            platform,
            app_version,
            status
        ) values (%s, %s, %s, 'overview-test', %s)
        returning id
        """,
        (user_id, f"overview-device-{suffix}-{uuid4().hex}", platform, status),
    ).fetchone()[0]


def _insert_collection(
    connection,
    *,
    loan_id: UUID,
    client_id: UUID,
    collector_id: UUID,
    device_id: UUID,
    sequence: int,
    collection_date: date,
    entry_type: str,
    amount: Decimal,
    balance: Decimal,
    suffix: str,
) -> UUID:
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
        ) values (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, '',
            %s, %s, 0, null, %s, '{}'::jsonb
        )
        returning id
        """,
        (
            uuid4(),
            loan_id,
            client_id,
            collector_id,
            device_id,
            loan_id,
            collection_date,
            entry_type,
            amount,
            sequence,
            balance,
            balance,
            f"OVERVIEW-{suffix}-{sequence:04d}",
        ),
    ).fetchone()[0]


def _table_counts(connection) -> tuple[int, ...]:
    return tuple(
        connection.execute(f"select count(*) from {table}").fetchone()[0]
        for table in (
            "lending.loans",
            "lending.collection_transactions",
            "lending.collection_remittances",
            "lending.client_renewal_requests",
            "core.client_registration_requests",
            "core.devices",
            "lending.client_support_requests",
            "core.activity_notifications",
            "core.audit_logs",
        )
    )


def _metric_map(overview):
    return {metric.key: metric for metric in overview.metrics}


def test_overview_counts_authoritative_rows_and_scopes_actor_queues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    connection = psycopg.connect(DATABASE_URL)
    try:
        required_tables = (
            "lending.collection_remittance_rejections",
            "lending.client_support_requests",
            "core.activity_notifications",
        )
        for table in required_tables:
            if (
                connection.execute("select to_regclass(%s)", (table,)).fetchone()[0]
                is None
            ):
                pytest.skip(f"{table} is not installed in the test database")

        monkeypatch.setattr(
            overview_module,
            "open_connection",
            lambda: _same_connection(connection),
        )
        repository = PostgresManagementDashboardOverviewRepository()
        suffix = uuid4().hex[:8]
        actor_id = uuid4()
        baseline = _metric_map(
            repository.load_overview(
                actor_user_id=actor_id,
                include_remittances=True,
                include_renewals=True,
                include_accounts=True,
                include_devices=True,
                include_support=True,
            )
        )

        actor_id = _insert_user(
            connection,
            suffix=suffix,
            role="management",
        )
        other_recipient_id = _insert_user(
            connection,
            suffix=suffix,
            role="management",
        )
        collector_id = _insert_user(
            connection,
            suffix=suffix,
            role="collector",
        )
        employee_id = _insert_user(
            connection,
            suffix=suffix,
            role="employee",
        )
        _insert_user(
            connection,
            suffix=suffix,
            role="collector",
            status="pending",
        )
        borrower_user_id = _insert_user(
            connection,
            suffix=suffix,
            role="client",
        )
        applicant_user_id = _insert_user(
            connection,
            suffix=suffix,
            role="client",
        )

        collector_device_id = _insert_device(
            connection,
            user_id=collector_id,
            platform="android",
            status="active",
            suffix=suffix,
        )
        _insert_device(
            connection,
            user_id=collector_id,
            platform="android",
            status="pending",
            suffix=suffix,
        )
        _insert_device(
            connection,
            user_id=collector_id,
            platform="ios",
            status="pending",
            suffix=suffix,
        )
        _insert_device(
            connection,
            user_id=collector_id,
            platform="web",
            status="pending",
            suffix=suffix,
        )
        _insert_device(
            connection,
            user_id=employee_id,
            platform="android",
            status="pending",
            suffix=suffix,
        )

        client_id = connection.execute(
            """
            insert into lending.clients (
                user_id,
                client_code,
                full_name,
                area,
                status
            ) values (%s, %s, %s, %s, 'active')
            returning id
            """,
            (
                borrower_user_id,
                f"OVERVIEW-C-{suffix}",
                f"Overview Client {suffix}",
                f"Overview Area {suffix}",
            ),
        ).fetchone()[0]
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code,
                name,
                term_days,
                calculation_mode,
                daily_interest_per_1000
            ) values (%s, %s, 120, 'fixed_daily', 0)
            returning id
            """,
            (f"OV-{suffix}", f"Overview Loan {suffix}"),
        ).fetchone()[0]
        overdue_loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number,
                client_id,
                loan_type_id,
                principal,
                daily_amount,
                date_released,
                due_date,
                status,
                created_by_user_id
            ) values (%s, %s, %s, 5000.00, 50.00, '2020-01-01',
                      '2020-05-01', 'active', %s)
            returning id
            """,
            (f"OVERVIEW-L1-{suffix}", client_id, loan_type_id, actor_id),
        ).fetchone()[0]
        current_loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number,
                client_id,
                loan_type_id,
                principal,
                daily_amount,
                date_released,
                due_date,
                status,
                created_by_user_id
            ) values (%s, %s, %s, 3000.00, 30.00, '2199-01-01',
                      '2199-12-31', 'active', %s)
            returning id
            """,
            (f"OVERVIEW-L2-{suffix}", client_id, loan_type_id, actor_id),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_collection_state (
                loan_id,
                remaining_balance,
                is_reconciled,
                state_version
            ) values (%s, 4900.00, true, 0), (%s, 3000.00, true, 0)
            """,
            (overdue_loan_id, current_loan_id),
        )

        latest_date = date(2199, 12, 31)
        _insert_collection(
            connection,
            loan_id=overdue_loan_id,
            client_id=client_id,
            collector_id=collector_id,
            device_id=collector_device_id,
            sequence=1,
            collection_date=latest_date,
            entry_type="payment",
            amount=Decimal("100.00"),
            balance=Decimal("4900.00"),
            suffix=suffix,
        )
        _insert_collection(
            connection,
            loan_id=current_loan_id,
            client_id=client_id,
            collector_id=collector_id,
            device_id=collector_device_id,
            sequence=2,
            collection_date=latest_date,
            entry_type="payment",
            amount=Decimal("50.00"),
            balance=Decimal("3000.00"),
            suffix=suffix,
        )
        _insert_collection(
            connection,
            loan_id=overdue_loan_id,
            client_id=client_id,
            collector_id=collector_id,
            device_id=collector_device_id,
            sequence=3,
            collection_date=latest_date,
            entry_type="pass",
            amount=Decimal("0.00"),
            balance=Decimal("4900.00"),
            suffix=suffix,
        )

        actionable_remittance_id = connection.execute(
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
                total_amount
            ) values (%s, %s, %s, %s, 'submitted', 1, 1, 0, 1, 1, 125.00)
            returning id
            """,
            (f"OVERVIEW-R1-{suffix}", collector_id, actor_id, latest_date),
        ).fetchone()[0]
        rejected_remittance_id = connection.execute(
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
                total_amount
            ) values (%s, %s, %s, %s, 'submitted', 1, 1, 0, 1, 1, 75.00)
            returning id
            """,
            (f"OVERVIEW-R2-{suffix}", collector_id, actor_id, latest_date),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.collection_remittance_rejections (
                remittance_id,
                rejected_by_user_id,
                reason
            ) values (%s, %s, 'Incorrect handover')
            """,
            (rejected_remittance_id, actor_id),
        )
        connection.execute(
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
                total_amount
            ) values (%s, %s, %s, %s, 'submitted', 1, 1, 0, 1, 1, 50.00)
            """,
            (
                f"OVERVIEW-R3-{suffix}",
                collector_id,
                other_recipient_id,
                latest_date,
            ),
        )
        assert actionable_remittance_id is not None

        pending_renewal_id = connection.execute(
            """
            insert into lending.client_renewal_requests (
                client_id,
                loan_id,
                requested_by_user_id,
                requested_amount,
                client_message,
                status
            ) values (%s, %s, %s, 5000.00, 'Please renew', 'pending')
            returning id
            """,
            (client_id, overdue_loan_id, borrower_user_id),
        ).fetchone()[0]
        assert pending_renewal_id is not None

        connection.execute(
            """
            insert into core.client_registration_requests (
                user_id,
                claimed_client_code,
                status
            ) values (%s, %s, 'pending')
            """,
            (applicant_user_id, f"CLAIM-{suffix}"),
        )

        connection.execute(
            """
            insert into lending.client_support_requests (
                client_id,
                created_by_user_id,
                category,
                subject,
                message,
                status
            ) values (%s, %s, 'loan', 'Loan help', 'Please review this loan', 'open')
            """,
            (client_id, borrower_user_id),
        )
        connection.execute(
            """
            insert into lending.client_support_requests (
                client_id,
                created_by_user_id,
                category,
                subject,
                message,
                status,
                managed_by_user_id,
                management_response,
                responded_at
            ) values (
                %s, %s, 'payment', 'Payment help', 'Please review payment',
                'answered', %s, 'Payment was reviewed', now()
            )
            """,
            (client_id, borrower_user_id, actor_id),
        )
        connection.execute(
            """
            insert into lending.client_support_requests (
                client_id,
                created_by_user_id,
                category,
                subject,
                message,
                status,
                managed_by_user_id,
                management_response,
                responded_at,
                resolved_at
            ) values (
                %s, %s, 'other', 'Closed help', 'This case is already closed',
                'resolved', %s, 'The case was resolved', now(), now()
            )
            """,
            (client_id, borrower_user_id, actor_id),
        )

        for recipient_id, is_read in (
            (actor_id, False),
            (actor_id, True),
            (other_recipient_id, False),
        ):
            connection.execute(
                """
                insert into core.activity_notifications (
                    recipient_user_id,
                    sender_user_id,
                    notification_type,
                    title,
                    message,
                    is_read,
                    read_at
                ) values (
                    %s, %s, 'client_payment_posted', 'Overview update',
                    'A safe overview test update', %s,
                    case when %s then now() else null end
                )
                """,
                (recipient_id, collector_id, is_read, is_read),
            )

        before_read_counts = _table_counts(connection)
        result = repository.load_overview(
            actor_user_id=actor_id,
            include_remittances=True,
            include_renewals=True,
            include_accounts=True,
            include_devices=True,
            include_support=True,
        )
        after_read_counts = _table_counts(connection)
        metrics = _metric_map(result)

        assert metrics["portfolio.active_clients"].count == (
            baseline["portfolio.active_clients"].count + 1
        )
        assert metrics["portfolio.active_loans"].count == (
            baseline["portfolio.active_loans"].count + 2
        )
        assert metrics["portfolio.overdue_loans"].count == (
            baseline["portfolio.overdue_loans"].count + 1
        )
        assert metrics["portfolio.outstanding_balance"].amount == (
            baseline["portfolio.outstanding_balance"].amount + Decimal("7900.00")
        )
        assert metrics["collections.latest_day"].count == 2
        assert metrics["collections.latest_day"].amount == Decimal("150.00")
        assert metrics["collections.latest_day"].as_of_date == latest_date
        assert metrics["collections.unremitted"].count == (
            baseline["collections.unremitted"].count + 3
        )
        assert metrics["collections.unremitted"].amount == (
            baseline["collections.unremitted"].amount + Decimal("150.00")
        )
        assert metrics["queues.remittances_assigned"].count == 1
        assert metrics["queues.remittances_assigned"].amount == Decimal("125.00")
        assert metrics["queues.renewals_protected"].count == (
            baseline["queues.renewals_protected"].count + 1
        )
        assert metrics["queues.staff_registrations"].count == (
            baseline["queues.staff_registrations"].count + 1
        )
        assert metrics["queues.client_registrations"].count == (
            baseline["queues.client_registrations"].count + 1
        )
        assert metrics["queues.collector_mobile_devices"].count == (
            baseline["queues.collector_mobile_devices"].count + 2
        )
        assert metrics["queues.borrower_support"].count == (
            baseline["queues.borrower_support"].count + 2
        )
        assert metrics["activity.unread"].count == 1
        assert after_read_counts == before_read_counts
    finally:
        connection.rollback()
        connection.close()
