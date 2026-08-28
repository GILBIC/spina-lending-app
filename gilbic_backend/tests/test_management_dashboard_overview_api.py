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
from gilbic_backend.management_dashboard_overview_api import (
    management_dashboard_overview_repository_dependency,
)
from gilbic_backend.management_dashboard_overview_repository import (
    ManagementDashboardMetric,
    ManagementDashboardOverview,
    ManagementDashboardOverviewError,
)

AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")

BASELINE_METRICS = (
    ManagementDashboardMetric(key="portfolio.active_clients", count=41),
    ManagementDashboardMetric(key="portfolio.active_loans", count=48),
    ManagementDashboardMetric(key="portfolio.overdue_loans", count=7),
    ManagementDashboardMetric(
        key="portfolio.outstanding_balance",
        amount=Decimal("987654.321"),
    ),
    ManagementDashboardMetric(
        key="collections.latest_day",
        count=32,
        amount=Decimal(18450),
        as_of_date=date(2026, 8, 28),
    ),
    ManagementDashboardMetric(
        key="collections.unremitted",
        count=6,
        amount=Decimal("3750.5"),
    ),
)

SPECIALIZED_METRICS = {
    "remittances": ManagementDashboardMetric(
        key="queues.remittances_assigned",
        count=2,
        amount=Decimal(1400),
    ),
    "renewals": ManagementDashboardMetric(
        key="queues.renewals_protected",
        count=5,
    ),
    "staff_accounts": ManagementDashboardMetric(
        key="queues.staff_registrations",
        count=3,
    ),
    "client_accounts": ManagementDashboardMetric(
        key="queues.client_registrations",
        count=4,
    ),
    "devices": ManagementDashboardMetric(
        key="queues.collector_mobile_devices",
        count=1,
    ),
    "support": ManagementDashboardMetric(
        key="queues.borrower_support",
        count=8,
    ),
}

ACTIVITY_METRIC = ManagementDashboardMetric(key="activity.unread", count=9)

EXPECTED_FILTERED_METRICS = [
    {"key": "portfolio.active_clients", "count": 41},
    {"key": "portfolio.active_loans", "count": 48},
    {"key": "portfolio.overdue_loans", "count": 7},
    {"key": "portfolio.outstanding_balance", "amount": "987654.32"},
    {
        "key": "collections.latest_day",
        "count": 32,
        "amount": "18450.00",
        "as_of_date": "2026-08-28",
    },
    {"key": "collections.unremitted", "count": 6, "amount": "3750.50"},
    {"key": "queues.remittances_assigned", "count": 2, "amount": "1400.00"},
    {"key": "queues.staff_registrations", "count": 3},
    {"key": "queues.client_registrations", "count": 4},
    {"key": "activity.unread", "count": 9},
]


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
class OverviewArguments:
    actor_user_id: UUID
    include_remittances: bool
    include_renewals: bool
    include_accounts: bool
    include_devices: bool
    include_support: bool


class FakeOverviewRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.arguments: OverviewArguments | None = None

    def load_overview(
        self,
        *,
        actor_user_id: UUID,
        include_remittances: bool,
        include_renewals: bool,
        include_accounts: bool,
        include_devices: bool,
        include_support: bool,
    ) -> ManagementDashboardOverview:
        self.arguments = OverviewArguments(
            actor_user_id=actor_user_id,
            include_remittances=include_remittances,
            include_renewals=include_renewals,
            include_accounts=include_accounts,
            include_devices=include_devices,
            include_support=include_support,
        )
        if self.fail:
            raise ManagementDashboardOverviewError("database detail must not leak")

        metrics = list(BASELINE_METRICS)
        if include_remittances:
            metrics.append(SPECIALIZED_METRICS["remittances"])
        if include_renewals:
            metrics.append(SPECIALIZED_METRICS["renewals"])
        if include_accounts:
            metrics.extend(
                (
                    SPECIALIZED_METRICS["staff_accounts"],
                    SPECIALIZED_METRICS["client_accounts"],
                )
            )
        if include_devices:
            metrics.append(SPECIALIZED_METRICS["devices"])
        if include_support:
            metrics.append(SPECIALIZED_METRICS["support"])
        metrics.append(ACTIVITY_METRIC)
        return ManagementDashboardOverview(
            generated_at=datetime(2026, 8, 29, 4, 15, 30, tzinfo=timezone.utc),
            metrics=tuple(metrics),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-phone",
    }


def client_with_fakes(
    *,
    roles: tuple[str, ...] = ("management",),
    permissions: tuple[str, ...] = ("management.dashboard.view",),
    fail: bool = False,
) -> tuple[TestClient, FakeOverviewRepository]:
    repository = FakeOverviewRepository(fail=fail)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        roles=roles,
        permissions=permissions,
    )
    app.dependency_overrides[management_dashboard_overview_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/management/dashboard-overview",
        "/api/mobile/v1/management/dashboard-overview",
    ],
)
def test_management_overview_aliases_return_the_same_filtered_shape(path: str) -> None:
    client, repository = client_with_fakes(
        permissions=(
            "management.dashboard.view",
            "remittance.receive",
            "account.manage",
        )
    )

    response = client.get(path, headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "generated_at": "2026-08-29T04:15:30+00:00",
            "currency": "PHP",
            "metrics": EXPECTED_FILTERED_METRICS,
        },
    }
    assert repository.arguments == OverviewArguments(
        actor_user_id=MANAGEMENT_USER_ID,
        include_remittances=True,
        include_renewals=False,
        include_accounts=True,
        include_devices=False,
        include_support=False,
    )


def test_non_management_with_dashboard_permission_is_denied_by_role() -> None:
    client, repository = client_with_fakes(
        roles=("employee",),
        permissions=("management.dashboard.view",),
    )

    response = client.get(
        "/api/v1/management/dashboard-overview",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.arguments is None


def test_management_without_dashboard_permission_is_denied() -> None:
    client, repository = client_with_fakes(permissions=("remittance.receive",))

    response = client.get(
        "/api/v1/management/dashboard-overview",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == (
        "management_dashboard_permission_required"
    )
    assert repository.arguments is None


def test_management_overview_requires_an_active_device_header() -> None:
    client, repository = client_with_fakes()

    response = client.get(
        "/api/v1/management/dashboard-overview",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."
    assert repository.arguments is None


def test_unauthorized_specialized_metrics_are_omitted() -> None:
    client, repository = client_with_fakes()

    response = client.get(
        "/api/v1/management/dashboard-overview",
        headers=headers(),
    )

    assert response.status_code == 200
    metric_keys = [metric["key"] for metric in response.json()["data"]["metrics"]]
    assert metric_keys == [
        "portfolio.active_clients",
        "portfolio.active_loans",
        "portfolio.overdue_loans",
        "portfolio.outstanding_balance",
        "collections.latest_day",
        "collections.unremitted",
        "activity.unread",
    ]
    assert repository.arguments == OverviewArguments(
        actor_user_id=MANAGEMENT_USER_ID,
        include_remittances=False,
        include_renewals=False,
        include_accounts=False,
        include_devices=False,
        include_support=False,
    )


def test_all_specialized_permissions_are_forwarded_independently() -> None:
    client, repository = client_with_fakes(
        permissions=(
            "management.dashboard.view",
            "remittance.receive",
            "renewal.manage",
            "account.manage",
            "device.manage",
            "support.manage",
        )
    )

    response = client.get(
        "/api/v1/management/dashboard-overview",
        headers=headers(),
    )

    assert response.status_code == 200
    assert repository.arguments == OverviewArguments(
        actor_user_id=MANAGEMENT_USER_ID,
        include_remittances=True,
        include_renewals=True,
        include_accounts=True,
        include_devices=True,
        include_support=True,
    )


def test_repository_failure_returns_safe_503() -> None:
    client, _ = client_with_fakes(fail=True)

    response = client.get(
        "/api/v1/management/dashboard-overview",
        headers=headers(),
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "management_overview_unavailable",
            "message": "The live Management overview is temporarily unavailable.",
        }
    }
    assert "database detail" not in response.text


def test_management_overview_has_no_write_endpoint() -> None:
    client, _ = client_with_fakes()

    response = client.post(
        "/api/v1/management/dashboard-overview",
        headers=headers(),
        json={"count": 999},
    )

    assert response.status_code == 405
