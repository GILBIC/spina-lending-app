from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
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
from gilbic_backend.management_alerts_audit_api import (
    management_alerts_audit_repository_dependency,
)
from gilbic_backend.management_alerts_audit_repository import (
    ManagementAlert,
    ManagementAlertsAuditError,
    ManagementAlertsAuditSnapshot,
    ManagementAuditEvent,
)

AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
REMITTANCE_ID = UUID("33333333-3333-4333-8333-333333333333")
JOURNAL_ID = UUID("44444444-4444-4444-8444-444444444444")


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
class RepositoryArguments:
    actor_user_id: UUID
    include_accounts: bool
    include_devices: bool
    include_renewals: bool
    include_support: bool
    include_remittances: bool
    include_financial: bool
    window_days: int
    limit: int


class FakeRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.arguments: RepositoryArguments | None = None

    def load_snapshot(
        self,
        *,
        actor_user_id: UUID,
        include_accounts: bool,
        include_devices: bool,
        include_renewals: bool,
        include_support: bool,
        include_remittances: bool,
        include_financial: bool,
        window_days: int,
        limit: int,
    ) -> ManagementAlertsAuditSnapshot:
        self.arguments = RepositoryArguments(
            actor_user_id=actor_user_id,
            include_accounts=include_accounts,
            include_devices=include_devices,
            include_renewals=include_renewals,
            include_support=include_support,
            include_remittances=include_remittances,
            include_financial=include_financial,
            window_days=window_days,
            limit=limit,
        )
        if self.fail:
            raise ManagementAlertsAuditError("database detail must not leak")
        visible_domains = ["payment_updates"]
        alerts = [
            ManagementAlert.from_code("payment_updates_unread", count=4),
        ]
        events: list[ManagementAuditEvent] = []
        if include_accounts:
            visible_domains.append("approvals")
            alerts.append(ManagementAlert.from_code("staff_registrations", count=2))
        if include_remittances:
            visible_domains.append("remittance_custody")
            alerts.append(
                ManagementAlert.from_code(
                    "assigned_remittances",
                    count=3,
                    amount=Decimal("1450.00"),
                )
            )
            events.append(
                ManagementAuditEvent.from_row_values(
                    event_key="remittance-received:33333333-3333-4333-8333-333333333333",
                    action_code="remittance.received",
                    occurred_at=datetime(2026, 8, 30, 2, 15, tzinfo=timezone.utc),
                    business_date=date(2026, 8, 30),
                    record_id=REMITTANCE_ID,
                    reference="REM-20260830-0001",
                    current_state="received",
                    actor_name="Management User",
                    checker_name="Management User",
                    source_type=None,
                    reason=None,
                )
            )
        if include_financial:
            visible_domains.append("financial")
            events.append(
                ManagementAuditEvent.from_row_values(
                    event_key="financial:91",
                    action_code="financial.posted",
                    occurred_at=datetime(2026, 8, 30, 3, 0, tzinfo=timezone.utc),
                    business_date=date(2026, 8, 30),
                    record_id=JOURNAL_ID,
                    reference="GJ-2026-00000091",
                    current_state="posted",
                    actor_name="Accounting Manager",
                    checker_name="Accounting Manager",
                    source_type="v1_tax_recoverable_refund",
                    reason=None,
                )
            )
        return ManagementAlertsAuditSnapshot(
            generated_at=datetime(2026, 8, 30, 3, 5, tzinfo=timezone.utc),
            window_days=window_days,
            limit=limit,
            visible_domains=tuple(visible_domains),
            alerts=tuple(alerts),
            events=tuple(events),
            event_total_count=len(events),
        )


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-phone",
    }


def _client(
    *,
    roles: tuple[str, ...] = ("management",),
    permissions: tuple[str, ...] = ("management.dashboard.view",),
    fail: bool = False,
) -> tuple[TestClient, FakeRepository]:
    repository = FakeRepository(fail=fail)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        roles=roles,
        permissions=permissions,
    )
    app.dependency_overrides[management_alerts_audit_repository_dependency] = lambda: (
        repository
    )
    return TestClient(app), repository


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/management/alerts-audit",
        "/api/mobile/v1/management/alerts-audit",
    ],
)
def test_aliases_return_the_same_permission_reduced_contract(path: str) -> None:
    client, repository = _client(
        permissions=(
            "management.dashboard.view",
            "account.manage",
            "remittance.view",
            "accounting.view",
        )
    )

    response = client.get(path, headers=_headers())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["generated_at"] == "2026-08-30T03:05:00+00:00"
    assert data["window_days"] == 30
    assert data["limit"] == 100
    assert data["visible_domains"] == [
        "payment_updates",
        "approvals",
        "remittance_custody",
        "financial",
    ]
    assert [alert["code"] for alert in data["alerts"]] == [
        "payment_updates_unread",
        "staff_registrations",
        "assigned_remittances",
    ]
    assert data["alerts"][2]["amount"] == "1450.00"
    assert [event["action_code"] for event in data["events"]] == [
        "remittance.received",
        "financial.posted",
    ]
    assert data["events"][1]["source_type"] == "v1_tax_recoverable_refund"
    assert data["events"][1]["source_label"] == "Tax Recoverable refund"
    assert data["notice"].startswith("Read-only")
    assert repository.arguments == RepositoryArguments(
        actor_user_id=MANAGEMENT_USER_ID,
        include_accounts=True,
        include_devices=False,
        include_renewals=False,
        include_support=False,
        include_remittances=True,
        include_financial=True,
        window_days=30,
        limit=100,
    )


def test_specialized_domains_are_forwarded_independently() -> None:
    client, repository = _client(
        permissions=(
            "management.dashboard.view",
            "device.manage",
            "renewal.manage",
            "support.manage",
            "remittance.view",
            "remittance.receive",
        )
    )

    response = client.get(
        "/api/v1/management/alerts-audit?window_days=14&limit=25",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.arguments == RepositoryArguments(
        actor_user_id=MANAGEMENT_USER_ID,
        include_accounts=False,
        include_devices=True,
        include_renewals=True,
        include_support=True,
        include_remittances=True,
        include_financial=False,
        window_days=14,
        limit=25,
    )


def test_remittance_receive_without_view_does_not_expose_remittance_activity() -> None:
    client, repository = _client(
        permissions=(
            "management.dashboard.view",
            "remittance.receive",
        )
    )

    response = client.get(
        "/api/v1/management/alerts-audit",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.arguments is not None
    assert repository.arguments.include_remittances is False


def test_role_base_permission_and_device_are_required_before_repository_access() -> (
    None
):
    client, repository = _client(
        roles=("employee",),
        permissions=("management.dashboard.view",),
    )
    response = client.get("/api/v1/management/alerts-audit", headers=_headers())
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.arguments is None

    client, repository = _client(permissions=("accounting.view",))
    response = client.get("/api/v1/management/alerts-audit", headers=_headers())
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == (
        "management_dashboard_permission_required"
    )
    assert repository.arguments is None

    client, repository = _client()
    response = client.get(
        "/api/v1/management/alerts-audit",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."
    assert repository.arguments is None


def test_repository_failure_is_a_safe_503() -> None:
    client, _ = _client(fail=True)

    response = client.get("/api/v1/management/alerts-audit", headers=_headers())

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "management_alerts_audit_unavailable",
            "message": "Management alerts and audit activity are temporarily unavailable.",
        }
    }
    assert "database detail" not in response.text


def test_alerts_audit_has_no_write_endpoint() -> None:
    client, _ = _client()

    response = client.post(
        "/api/v1/management/alerts-audit",
        headers=_headers(),
        json={"approve": True},
    )

    assert response.status_code == 405
