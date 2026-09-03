from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.management_employee_activity import (
    EmployeeActivityCode,
    EmployeeActivityDomain,
    EmployeeActivityItem,
    EmployeeActivityNavigationCode,
    EmployeeActivityPage,
    EmployeeActivityRow,
    EmployeeActivityStatus,
    EmployeeActivityTimeline,
)
from gilbic_backend.management_employee_activity_api import (
    management_employee_activity_repository_dependency,
)
from gilbic_backend.management_employee_activity_repository import (
    EmployeeActivityNotFound,
    ManagementEmployeeActivityError,
)

AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
EMPLOYEE_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
RECORD_ID = UUID("44444444-4444-4444-8444-444444444444")
BUSINESS_DATE = date(2026, 8, 29)
GENERATED_AT = datetime(2026, 8, 29, 4, 15, 30, tzinfo=timezone.utc)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "test-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="manager@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(
        self,
        *,
        roles: tuple[str, ...],
        permissions: tuple[str, ...],
    ) -> None:
        self.roles = roles
        self.permissions = permissions

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "management-phone"
        return AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="manager",
            email="manager@example.com",
            full_name="Management User",
            status="active",
            roles=self.roles,
            permissions=self.permissions,
            device_registered=True,
        )


@dataclass(frozen=True)
class ListArguments:
    date_from: date
    date_to: date
    visible_domain_codes: tuple[EmployeeActivityDomain, ...]
    query: str | None
    status: EmployeeActivityStatus | None
    domain: EmployeeActivityDomain | None
    limit: int
    offset: int


class FakeEmployeeActivityRepository:
    def __init__(
        self,
        *,
        fail: bool = False,
        not_found: bool = False,
    ) -> None:
        self.fail = fail
        self.not_found = not_found
        self.list_arguments: ListArguments | None = None
        self.timeline_called = False

    def list_employees(
        self,
        *,
        date_from: date,
        date_to: date,
        visible_domains,
        query: str | None,
        status: EmployeeActivityStatus | None,
        domain: EmployeeActivityDomain | None,
        limit: int,
        offset: int,
    ) -> EmployeeActivityPage:
        visible_codes = tuple(item.code for item in visible_domains)
        self.list_arguments = ListArguments(
            date_from=date_from,
            date_to=date_to,
            visible_domain_codes=visible_codes,
            query=query,
            status=status,
            domain=domain,
            limit=limit,
            offset=offset,
        )
        if self.fail:
            raise ManagementEmployeeActivityError("private database detail")
        has_accounting = EmployeeActivityDomain.ACCOUNTING in visible_codes
        row = EmployeeActivityRow(
            employee_user_id=EMPLOYEE_USER_ID,
            employee_name="Employee Name",
            function_labels=(),
            completed_count=1 if has_accounting else 0,
            in_progress_count=0,
            awaiting_review_count=0,
            needs_attention_count=0,
            total_visible_count=1 if has_accounting else 0,
            last_activity_at=GENERATED_AT if has_accounting else None,
            last_activity_domain=(
                EmployeeActivityDomain.ACCOUNTING if has_accounting else None
            ),
            status=(
                EmployeeActivityStatus.COMPLETED
                if has_accounting
                else EmployeeActivityStatus.NO_ACTIVITY
            ),
            status_message=(
                "1 visible item completed."
                if has_accounting
                else "No permitted activity in this range."
            ),
        )
        return EmployeeActivityPage(
            date_from=date_from,
            date_to=date_to,
            generated_at=GENERATED_AT,
            available_domains=visible_codes,
            rows=(row,),
            total_count=1,
        )

    def load_timeline(
        self,
        *,
        employee_user_id: UUID,
        date_from: date,
        date_to: date,
        visible_domains,
        domain: EmployeeActivityDomain | None,
        limit: int,
        offset: int,
    ) -> EmployeeActivityTimeline:
        self.timeline_called = True
        if self.not_found:
            raise EmployeeActivityNotFound("private missing detail")
        if self.fail:
            raise ManagementEmployeeActivityError("private database detail")
        assert employee_user_id == EMPLOYEE_USER_ID
        assert (limit, offset) == (100, 0)
        visible_codes = tuple(item.code for item in visible_domains)
        item = EmployeeActivityItem(
            employee_user_id=EMPLOYEE_USER_ID,
            activity_code=EmployeeActivityCode.ACCOUNTING_JOURNAL_PREPARED,
            domain=EmployeeActivityDomain.ACCOUNTING,
            occurred_at=GENERATED_AT,
            business_date=BUSINESS_DATE,
            record_type="journal_entry",
            record_id=RECORD_ID,
            display_reference="Journal draft",
            summary="Prepared journal entry",
            workflow_state="draft",
            status=EmployeeActivityStatus.IN_PROGRESS,
            maker_name="Employee Name",
            checker_name=None,
            navigation_code=EmployeeActivityNavigationCode.GENERAL_JOURNALS,
        )
        return EmployeeActivityTimeline(
            employee_user_id=EMPLOYEE_USER_ID,
            employee_name="Employee Name",
            function_labels=(),
            date_from=date_from,
            date_to=date_to,
            generated_at=GENERATED_AT,
            available_domains=visible_codes,
            items=(item,),
            total_count=1,
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-phone",
    }


def client_with_fakes(
    *,
    roles: tuple[str, ...] = ("management",),
    permissions: tuple[str, ...] = (
        "employee.activity.review",
        "accounting.view",
    ),
    fail: bool = False,
    not_found: bool = False,
) -> tuple[TestClient, FakeEmployeeActivityRepository]:
    repository = FakeEmployeeActivityRepository(fail=fail, not_found=not_found)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        roles=roles,
        permissions=permissions,
    )
    app.dependency_overrides[management_employee_activity_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/management/employee-activity",
        "/api/mobile/v1/management/employee-activity",
    ],
)
def test_employee_activity_aliases_return_the_same_permission_filtered_shape(
    path: str,
) -> None:
    client, repository = client_with_fakes()

    response = client.get(
        path,
        params={"date_from": "2026-08-29", "date_to": "2026-08-29"},
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "date_from": "2026-08-29",
            "date_to": "2026-08-29",
            "generated_at": "2026-08-29T04:15:30+00:00",
            "available_domains": ["accounting"],
            "total_count": 1,
            "rows": [
                {
                    "employee_user_id": str(EMPLOYEE_USER_ID),
                    "employee_name": "Employee Name",
                    "function_labels": [],
                    "completed_count": 1,
                    "in_progress_count": 0,
                    "awaiting_review_count": 0,
                    "needs_attention_count": 0,
                    "total_visible_count": 1,
                    "last_activity_at": "2026-08-29T04:15:30+00:00",
                    "last_activity_domain": "accounting",
                    "status": "completed",
                    "status_message": "1 visible item completed.",
                }
            ],
        },
    }
    assert repository.list_arguments == ListArguments(
        date_from=BUSINESS_DATE,
        date_to=BUSINESS_DATE,
        visible_domain_codes=(EmployeeActivityDomain.ACCOUNTING,),
        query=None,
        status=None,
        domain=None,
        limit=50,
        offset=0,
    )


def test_shell_permission_without_domain_permissions_leaks_no_domain_facts() -> None:
    client, _ = client_with_fakes(permissions=("employee.activity.review",))

    response = client.get(
        "/api/v1/management/employee-activity",
        params={"date_from": "2026-08-29", "date_to": "2026-08-29"},
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["available_domains"] == []
    assert data["rows"][0]["total_visible_count"] == 0
    assert data["rows"][0]["last_activity_at"] is None
    assert data["rows"][0]["last_activity_domain"] is None
    assert "payroll" not in response.text.lower()
    assert "support" not in response.text.lower()


def test_non_management_with_shell_permission_is_denied_by_role() -> None:
    client, repository = client_with_fakes(roles=("employee",))

    response = client.get(
        "/api/v1/management/employee-activity",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.list_arguments is None


def test_management_without_shell_permission_is_denied() -> None:
    client, repository = client_with_fakes(permissions=("accounting.view",))

    response = client.get(
        "/api/v1/management/employee-activity",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == (
        "employee_activity_permission_required"
    )
    assert repository.list_arguments is None


def test_hidden_domain_filter_is_denied_before_repository_access() -> None:
    client, repository = client_with_fakes()

    response = client.get(
        "/api/v1/management/employee-activity",
        params={"domain": "payroll"},
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == ("employee_activity_domain_forbidden")
    assert repository.list_arguments is None


def test_list_filters_are_normalized_and_forwarded() -> None:
    permissions = (
        "employee.activity.review",
        "accounting.view",
        "support.manage",
        "remittance.view",
    )
    client, repository = client_with_fakes(permissions=permissions)

    response = client.get(
        "/api/v1/management/employee-activity",
        params={
            "date_from": "2026-08-01",
            "date_to": "2026-08-29",
            "q": "  Employee   Name  ",
            "domain": "crm_support",
            "status": "completed",
            "limit": 25,
            "offset": 5,
        },
        headers=headers(),
    )

    assert response.status_code == 200
    assert repository.list_arguments == ListArguments(
        date_from=date(2026, 8, 1),
        date_to=BUSINESS_DATE,
        visible_domain_codes=(
            EmployeeActivityDomain.ACCOUNTING,
            EmployeeActivityDomain.CRM_SUPPORT,
            EmployeeActivityDomain.REMITTANCE_OPERATIONS,
        ),
        query="Employee Name",
        status=EmployeeActivityStatus.COMPLETED,
        domain=EmployeeActivityDomain.CRM_SUPPORT,
        limit=25,
        offset=5,
    )


def test_date_range_over_31_days_is_rejected_without_database_access() -> None:
    client, repository = client_with_fakes()

    response = client.get(
        "/api/v1/management/employee-activity",
        params={"date_from": "2026-07-01", "date_to": "2026-08-29"},
        headers=headers(),
    )

    assert response.status_code == 422
    assert repository.list_arguments is None


def test_timeline_serializes_safe_authoritative_fields_only() -> None:
    client, repository = client_with_fakes()

    response = client.get(
        f"/api/v1/management/employee-activity/{EMPLOYEE_USER_ID}",
        params={"date_from": "2026-08-29", "date_to": "2026-08-29"},
        headers=headers(),
    )

    assert response.status_code == 200
    assert repository.timeline_called
    data = response.json()["data"]
    assert data["employee_user_id"] == str(EMPLOYEE_USER_ID)
    assert data["items"][0] == {
        "activity_code": "accounting.journal.prepared",
        "domain": "accounting",
        "occurred_at": "2026-08-29T04:15:30+00:00",
        "business_date": "2026-08-29",
        "record_type": "journal_entry",
        "record_id": str(RECORD_ID),
        "display_reference": "Journal draft",
        "summary": "Prepared journal entry",
        "workflow_state": "draft",
        "status": "in_progress",
        "maker_name": "Employee Name",
        "checker_name": None,
        "navigation_code": "management.general_journals",
    }
    prohibited = (
        "password",
        "token",
        "device_identifier",
        "government_id",
        "payroll_amount",
        "management_response",
    )
    assert not any(field in response.text.lower() for field in prohibited)


def test_missing_employee_is_safe_404() -> None:
    client, _ = client_with_fakes(not_found=True)

    response = client.get(
        f"/api/v1/management/employee-activity/{EMPLOYEE_USER_ID}",
        headers=headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "employee_activity_not_found"
    assert "private" not in response.text.lower()


def test_repository_failure_is_safe_503() -> None:
    client, _ = client_with_fakes(fail=True)

    response = client.get(
        "/api/v1/management/employee-activity",
        headers=headers(),
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == (
        "management_employee_activity_unavailable"
    )
    assert "private database detail" not in response.text.lower()


def test_employee_activity_requires_an_active_device_header() -> None:
    client, repository = client_with_fakes()

    response = client.get(
        "/api/v1/management/employee-activity",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."
    assert repository.list_arguments is None
