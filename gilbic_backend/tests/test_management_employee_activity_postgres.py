from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date
from uuid import UUID, uuid4

import gilbic_backend.management_employee_activity_repository as repository_module
import psycopg
import pytest
from gilbic_backend.management_employee_activity import (
    EmployeeActivityDomain,
    EmployeeActivityStatus,
)
from gilbic_backend.management_employee_activity_registry import (
    visible_employee_activity_domains,
)
from gilbic_backend.management_employee_activity_repository import (
    PostgresManagementEmployeeActivityRepository,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
BUSINESS_DATE = date(2098, 8, 29)
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


@contextmanager
def _same_connection(connection):
    yield connection


def _insert_user(connection, *, suffix: str, role: str) -> UUID:
    user_id = connection.execute(
        """
        insert into core.users (username, email, full_name, status)
        values (%s, %s, %s, 'active')
        returning id
        """,
        (
            f"employee-activity-{role}-{suffix}-{uuid4().hex[:6]}",
            f"employee-activity-{role}-{suffix}-{uuid4().hex[:6]}@example.com",
            f"Employee Activity {role.title()} {suffix}",
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


def _fiscal_period(connection) -> UUID:
    existing = connection.execute(
        """
        select id
        from accounting.fiscal_periods
        where %s between start_date and end_date
        order by start_date desc
        limit 1
        """,
        (BUSINESS_DATE,),
    ).fetchone()
    if existing:
        return existing[0]
    return connection.execute(
        """
        insert into accounting.fiscal_periods (
            label,
            start_date,
            end_date,
            status
        ) values (%s, %s, %s, 'open')
        returning id
        """,
        (f"Employee Activity {uuid4().hex[:8]}", BUSINESS_DATE, BUSINESS_DATE),
    ).fetchone()[0]


def _source_counts(connection) -> tuple[int, ...]:
    return tuple(
        connection.execute(f"select count(*) from {table}").fetchone()[0]
        for table in (
            "accounting.journal_entries",
            "lending.client_support_requests",
            "lending.collection_remittances",
            "core.audit_logs",
        )
    )


def test_employee_activity_reads_registered_sources_without_hidden_domain_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    connection = psycopg.connect(DATABASE_URL)
    try:
        required_tables = (
            "accounting.journal_entries",
            "lending.client_support_requests",
            "lending.collection_remittances",
            "lending.collection_remittance_rejections",
            "core.audit_logs",
        )
        for table in required_tables:
            if (
                connection.execute("select to_regclass(%s)", (table,)).fetchone()[0]
                is None
            ):
                pytest.skip(f"{table} is not installed in the test database")

        suffix = uuid4().hex[:8]
        employee_id = _insert_user(connection, suffix=suffix, role="employee")
        quiet_employee_id = _insert_user(
            connection,
            suffix=f"quiet-{suffix}",
            role="employee",
        )
        management_id = _insert_user(connection, suffix=suffix, role="management")
        client_user_id = _insert_user(connection, suffix=suffix, role="client")
        client_id = connection.execute(
            """
            insert into lending.clients (
                user_id,
                client_code,
                full_name,
                status
            ) values (%s, %s, %s, 'active')
            returning id
            """,
            (client_user_id, f"EA-{suffix}", f"Employee Activity Client {suffix}"),
        ).fetchone()[0]

        journal_id = connection.execute(
            """
            insert into accounting.journal_entries (
                fiscal_period_id,
                posting_date,
                description,
                created_by_user_id
            ) values (%s, %s, %s, %s)
            returning id
            """,
            (
                _fiscal_period(connection),
                BUSINESS_DATE,
                "Employee Activity journal evidence",
                employee_id,
            ),
        ).fetchone()[0]

        support_id = connection.execute(
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
                updated_at
            ) values (
                %s, %s, 'account', %s, %s, 'answered', %s, %s,
                %s::date + time '10:00', %s::date + time '10:00'
            )
            returning id
            """,
            (
                client_id,
                client_user_id,
                "Private account question",
                "PRIVATE-SUPPORT-MESSAGE",
                employee_id,
                "PRIVATE-SUPPORT-RESPONSE",
                BUSINESS_DATE,
                BUSINESS_DATE,
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into core.audit_logs (
                actor_user_id,
                action,
                target_type,
                target_id,
                details,
                created_at
            ) values (
                %s,
                'support.answered',
                'client_support_request',
                %s,
                jsonb_build_object('response', 'PRIVATE-AUDIT-DETAIL'),
                %s::date + time '10:00'
            )
            """,
            (employee_id, support_id, BUSINESS_DATE),
        )

        remittance_id = connection.execute(
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
                submitted_at
            ) values (
                %s, %s, %s, %s, 'submitted', 1, 1, 0, 1, 1, 100.00,
                %s::date + time '11:00'
            )
            returning id
            """,
            (
                f"EA-REM-{suffix}",
                employee_id,
                management_id,
                BUSINESS_DATE,
                BUSINESS_DATE,
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into core.audit_logs (
                actor_user_id,
                action,
                target_type,
                target_id,
                details,
                created_at
            ) values (
                %s,
                'remittance.submitted',
                'collection_remittance',
                %s,
                jsonb_build_object('private_note', 'PRIVATE-REMITTANCE-DETAIL'),
                %s::date + time '11:00'
            )
            """,
            (employee_id, remittance_id, BUSINESS_DATE),
        )

        connection.execute(
            """
            update accounting.journal_entries
            set created_at = %s::date + time '09:00'
            where id = %s
            """,
            (BUSINESS_DATE, journal_id),
        )
        baseline_counts = _source_counts(connection)

        monkeypatch.setattr(
            repository_module,
            "open_connection",
            lambda: _same_connection(connection),
        )
        repository = PostgresManagementEmployeeActivityRepository()

        full_page = repository.list_employees(
            date_from=BUSINESS_DATE,
            date_to=BUSINESS_DATE,
            visible_domains=visible_employee_activity_domains(
                frozenset({"accounting.view", "support.manage", "remittance.view"})
            ),
            query=f"{suffix}",
            status=None,
            domain=None,
            limit=50,
            offset=0,
        )
        row = next(
            item for item in full_page.rows if item.employee_user_id == employee_id
        )
        quiet_row = next(
            item
            for item in full_page.rows
            if item.employee_user_id == quiet_employee_id
        )
        assert row.total_visible_count == 3
        assert row.completed_count == 1
        assert row.in_progress_count == 1
        assert row.awaiting_review_count == 1
        assert row.status is EmployeeActivityStatus.AWAITING_REVIEW
        assert quiet_row.total_visible_count == 0
        assert quiet_row.status is EmployeeActivityStatus.NO_ACTIVITY

        accounting_only = repository.list_employees(
            date_from=BUSINESS_DATE,
            date_to=BUSINESS_DATE,
            visible_domains=visible_employee_activity_domains(
                frozenset({"accounting.view"})
            ),
            query=f"{suffix}",
            status=None,
            domain=None,
            limit=50,
            offset=0,
        )
        accounting_row = next(
            item
            for item in accounting_only.rows
            if item.employee_user_id == employee_id
        )
        assert accounting_only.available_domains == (EmployeeActivityDomain.ACCOUNTING,)
        assert accounting_row.total_visible_count == 1
        assert accounting_row.last_activity_domain is EmployeeActivityDomain.ACCOUNTING

        timeline = repository.load_timeline(
            employee_user_id=employee_id,
            date_from=BUSINESS_DATE,
            date_to=BUSINESS_DATE,
            visible_domains=visible_employee_activity_domains(
                frozenset({"accounting.view", "support.manage", "remittance.view"})
            ),
            domain=None,
            limit=100,
            offset=0,
        )
        serialized_safe_text = " ".join(
            f"{item.display_reference} {item.summary}" for item in timeline.items
        )
        assert len(timeline.items) == 3
        assert "PRIVATE-SUPPORT-MESSAGE" not in serialized_safe_text
        assert "PRIVATE-SUPPORT-RESPONSE" not in serialized_safe_text
        assert "PRIVATE-AUDIT-DETAIL" not in serialized_safe_text
        assert "PRIVATE-REMITTANCE-DETAIL" not in serialized_safe_text
        assert _source_counts(connection) == baseline_counts
    finally:
        connection.rollback()
        connection.close()
