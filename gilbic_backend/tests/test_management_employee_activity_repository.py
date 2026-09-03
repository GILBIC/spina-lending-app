from __future__ import annotations

from datetime import date, datetime, timezone
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import gilbic_backend.management_employee_activity_repository as repository_module
import pytest
from gilbic_backend.management_employee_activity import (
    EmployeeActivityDomain,
    EmployeeActivityStatus,
)
from gilbic_backend.management_employee_activity_registry import (
    visible_employee_activity_domains,
)
from gilbic_backend.management_employee_activity_repository import (
    EmployeeActivityDomainForbidden,
    ManagementEmployeeActivityError,
    PostgresManagementEmployeeActivityRepository,
)

EMPLOYEE_ID = UUID("11111111-1111-4111-8111-111111111111")
JOURNAL_ID = UUID("22222222-2222-4222-8222-222222222222")


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.execute_count = 0
        self.query = ""
        self.parameters: tuple[object, ...] = ()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def execute(self, query: str, parameters: tuple[object, ...]) -> None:
        self.execute_count += 1
        self.query = query
        self.parameters = parameters

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def cursor(self, *, row_factory: object) -> FakeCursor:
        assert row_factory is not None
        return self._cursor


def _employee_row() -> dict[str, Any]:
    return {
        "employee_user_id": EMPLOYEE_ID,
        "employee_name": "Employee Name",
        "function_labels": [],
        "completed_count": 1,
        "in_progress_count": 0,
        "awaiting_review_count": 0,
        "needs_attention_count": 0,
        "total_visible_count": 1,
        "last_activity_at": datetime(2026, 8, 29, 2, 42, tzinfo=timezone.utc),
        "last_activity_domain": "accounting",
        "status": "completed",
        "generated_at": datetime(2026, 8, 29, 2, 45, tzinfo=timezone.utc),
        "total_count": 1,
    }


def _timeline_row() -> dict[str, Any]:
    return {
        "employee_user_id": EMPLOYEE_ID,
        "employee_name": "Employee Name",
        "function_labels": [],
        "activity_code": "accounting.journal.prepared",
        "domain": "accounting",
        "occurred_at": datetime(2026, 8, 29, 2, 42, tzinfo=timezone.utc),
        "business_date": date(2026, 8, 29),
        "record_type": "journal_entry",
        "record_id": JOURNAL_ID,
        "display_reference": "Journal draft",
        "summary": "Prepared journal entry",
        "workflow_state": "draft",
        "status": "in_progress",
        "maker_name": "Employee Name",
        "checker_name": None,
        "navigation_code": "management.general_journals",
        "generated_at": datetime(2026, 8, 29, 2, 45, tzinfo=timezone.utc),
        "total_count": 1,
    }


def _install_fake_connection(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, Any]],
) -> FakeCursor:
    cursor = FakeCursor(rows)
    monkeypatch.setattr(
        repository_module,
        "open_connection",
        lambda: FakeConnection(cursor),
    )
    return cursor


def test_registry_exposes_only_domains_with_an_owning_view_permission() -> None:
    visible = visible_employee_activity_domains(
        frozenset(
            {
                "employee.activity.review",
                "accounting.view",
                "remittance.view",
            }
        )
    )

    assert [domain.code for domain in visible] == [
        EmployeeActivityDomain.ACCOUNTING,
        EmployeeActivityDomain.REMITTANCE_OPERATIONS,
    ]
    assert all(
        domain.required_permission != "employee.activity.review" for domain in visible
    )


def test_registry_does_not_advertise_unimplemented_sensitive_domains() -> None:
    visible = visible_employee_activity_domains(
        frozenset(
            {
                "employee.activity.review",
                "accounting.view",
                "support.manage",
                "remittance.view",
                "account.manage",
            }
        )
    )

    codes = {domain.code for domain in visible}
    assert EmployeeActivityDomain.HR not in codes
    assert EmployeeActivityDomain.PAYROLL not in codes
    assert EmployeeActivityDomain.ADMINISTRATION not in codes


def test_registry_requires_the_exact_domain_permission() -> None:
    visible = visible_employee_activity_domains(
        frozenset(
            {
                "employee.activity.review",
                "accounting.journal.manage",
                "support.view",
                "remittance.receive",
            }
        )
    )

    assert visible == ()


def test_list_employees_uses_one_permission_filtered_statement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = _install_fake_connection(monkeypatch, [_employee_row()])
    visible = visible_employee_activity_domains(frozenset({"accounting.view"}))

    page = PostgresManagementEmployeeActivityRepository().list_employees(
        date_from=date(2026, 8, 29),
        date_to=date(2026, 8, 29),
        visible_domains=visible,
        query=None,
        status=None,
        domain=None,
        limit=50,
        offset=0,
    )

    assert cursor.execute_count == 1
    assert "accounting.journal_entries" in cursor.query
    assert "support.answered" in cursor.query
    assert "remittance.submitted" in cursor.query
    assert page.available_domains == (EmployeeActivityDomain.ACCOUNTING,)
    assert page.total_count == 1
    assert page.rows[0].employee_user_id == EMPLOYEE_ID
    assert page.rows[0].status is EmployeeActivityStatus.COMPLETED
    assert page.rows[0].total_visible_count == 1


def test_list_employees_rejects_inconsistent_authoritative_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _employee_row()
    row["completed_count"] = 2
    _install_fake_connection(monkeypatch, [row])

    with pytest.raises(ManagementEmployeeActivityError) as captured:
        PostgresManagementEmployeeActivityRepository().list_employees(
            date_from=date(2026, 8, 29),
            date_to=date(2026, 8, 29),
            visible_domains=visible_employee_activity_domains(
                frozenset({"accounting.view"})
            ),
            query=None,
            status=None,
            domain=None,
            limit=50,
            offset=0,
        )

    assert str(captured.value) == "The Employee Activity data is invalid."


def test_list_employees_rejects_a_hidden_domain_filter_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = _install_fake_connection(monkeypatch, [])

    with pytest.raises(EmployeeActivityDomainForbidden):
        PostgresManagementEmployeeActivityRepository().list_employees(
            date_from=date(2026, 8, 29),
            date_to=date(2026, 8, 29),
            visible_domains=visible_employee_activity_domains(
                frozenset({"accounting.view"})
            ),
            query=None,
            status=None,
            domain=EmployeeActivityDomain.CRM_SUPPORT,
            limit=50,
            offset=0,
        )

    assert cursor.execute_count == 0


def test_timeline_preserves_authoritative_identity_and_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = _install_fake_connection(monkeypatch, [_timeline_row()])

    timeline = PostgresManagementEmployeeActivityRepository().load_timeline(
        employee_user_id=EMPLOYEE_ID,
        date_from=date(2026, 8, 29),
        date_to=date(2026, 8, 29),
        visible_domains=visible_employee_activity_domains(
            frozenset({"accounting.view"})
        ),
        domain=EmployeeActivityDomain.ACCOUNTING,
        limit=100,
        offset=0,
    )

    assert cursor.execute_count == 1
    assert timeline.employee_user_id == EMPLOYEE_ID
    assert timeline.items[0].record_id == JOURNAL_ID
    assert timeline.items[0].maker_name == "Employee Name"
    assert timeline.items[0].checker_name is None
    assert timeline.items[0].activity_code.value == "accounting.journal.prepared"
    assert timeline.items[0].navigation_code is not None
    assert timeline.items[0].navigation_code.value == "management.general_journals"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("completed_count", True),
        ("total_visible_count", -1),
        ("status", "ranked_high_performer"),
        ("employee_user_id", "not-a-uuid"),
        ("employee_name", "x" * 201),
        (
            "last_activity_at",
            datetime(2026, 8, 29, 2, 42, tzinfo=timezone.utc).replace(tzinfo=None),
        ),
    ],
)
def test_list_employees_rejects_malformed_or_unapproved_values(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    row = _employee_row()
    row[field] = value
    _install_fake_connection(monkeypatch, [row])

    with pytest.raises(ManagementEmployeeActivityError) as captured:
        PostgresManagementEmployeeActivityRepository().list_employees(
            date_from=date(2026, 8, 29),
            date_to=date(2026, 8, 29),
            visible_domains=visible_employee_activity_domains(
                frozenset({"accounting.view"})
            ),
            query=None,
            status=None,
            domain=None,
            limit=50,
            offset=0,
        )

    assert str(captured.value) == "The Employee Activity data is invalid."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("activity_code", "employee.keystroke.captured"),
        ("domain", "payroll_private_amount"),
        ("status", "productivity_score"),
        ("navigation_code", "management.impersonate_employee"),
    ],
)
def test_timeline_rejects_unknown_sensitive_contract_values(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    row = _timeline_row()
    row[field] = value
    _install_fake_connection(monkeypatch, [row])

    with pytest.raises(ManagementEmployeeActivityError) as captured:
        PostgresManagementEmployeeActivityRepository().load_timeline(
            employee_user_id=EMPLOYEE_ID,
            date_from=date(2026, 8, 29),
            date_to=date(2026, 8, 29),
            visible_domains=visible_employee_activity_domains(
                frozenset({"accounting.view"})
            ),
            domain=None,
            limit=100,
            offset=0,
        )

    assert str(captured.value) == "The Employee Activity data is invalid."
