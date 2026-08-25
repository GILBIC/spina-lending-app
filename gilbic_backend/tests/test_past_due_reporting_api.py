from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.past_due_reporting_api import (
    past_due_reporting_repository_dependency,
)
from gilbic_backend.past_due_reporting_repository import (
    PastDueReasonReport,
    PastDueReasonReportRow,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
COLLECTOR_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
DEVICE_ID = "past-due-report-device"


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "management-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="manager@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, permissions: tuple[str, ...] = ("management.dashboard.view",)) -> None:
        self.context = AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="manager.one",
            email="manager@example.com",
            full_name="Manager One",
            status="active",
            roles=("management",),
            permissions=permissions,
            device_registered=True,
        )

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == DEVICE_ID
        return self.context


class FakeReports:
    def __init__(self, *, schema_available: bool = True) -> None:
        self.schema_available = schema_available
        self.call: dict[str, object] | None = None

    def report_reason_summary(self, **kwargs) -> PastDueReasonReport:
        self.call = kwargs
        if not self.schema_available:
            return PastDueReasonReport(schema_available=False, rows=())
        return PastDueReasonReport(
            schema_available=True,
            rows=(
                PastDueReasonReportRow(
                    client_id=CLIENT_ID,
                    client_name="Ana Client",
                    collector_user_id=COLLECTOR_USER_ID,
                    collector_name="Collector One",
                    area="Cardona",
                    reason_code="no_cash",
                    event_kind="unable_to_pay",
                    event_count=2,
                    total_past_due_amount=Decimal("300.00"),
                    remaining_past_due_amount=Decimal("100.00"),
                ),
                PastDueReasonReportRow(
                    client_id=CLIENT_ID,
                    client_name="Ana Client",
                    collector_user_id=COLLECTOR_USER_ID,
                    collector_name="Collector One",
                    area="Cardona",
                    reason_code="business_slow",
                    event_kind="partial_payment",
                    event_count=1,
                    total_past_due_amount=Decimal("50.00"),
                    remaining_past_due_amount=Decimal("50.00"),
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": DEVICE_ID,
    }


def client_with_fakes(*, permissions: tuple[str, ...] = ("management.dashboard.view",), schema_available: bool = True):
    reports = FakeReports(schema_available=schema_available)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        permissions=permissions
    )
    app.dependency_overrides[past_due_reporting_repository_dependency] = lambda: reports
    return TestClient(app), reports


def test_management_past_due_reason_report_supports_approved_filters() -> None:
    client, reports = client_with_fakes()

    response = client.get(
        "/api/v1/management/past-due/reasons",
        headers=headers(),
        params={
            "start_date": "2026-08-01",
            "end_date": "2026-08-25",
            "client_id": str(CLIENT_ID),
            "collector_user_id": str(COLLECTOR_USER_ID),
            "area": "Cardona",
            "reason_code": "no_cash",
            "event_kind": "unable_to_pay",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["schema_available"] is True
    assert data["summary"] == {
        "event_count": 3,
        "total_past_due_amount": "350.00",
        "remaining_past_due_amount": "150.00",
    }
    assert data["rows"][0]["reason_label"] == "No cash"
    assert data["rows"][0]["event_kind_label"] == "Full Unable to Pay"
    assert data["rows"][1]["event_kind_label"] == "Partial-payment Past Due"
    assert reports.call is not None
    assert reports.call["start_date"] == date(2026, 8, 1)
    assert reports.call["end_date"] == date(2026, 8, 25)
    assert reports.call["client_id"] == CLIENT_ID
    assert reports.call["collector_user_id"] == COLLECTOR_USER_ID
    assert reports.call["area"] == "Cardona"
    assert reports.call["reason_code"] == "no_cash"
    assert reports.call["event_kind"] == "unable_to_pay"


def test_past_due_report_requires_management_dashboard_permission() -> None:
    client, _ = client_with_fakes(permissions=("route.view",))

    response = client.get(
        "/api/v1/management/past-due/reasons",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Management permission is required."


def test_past_due_report_is_schema_safe_before_migration_0103() -> None:
    client, _ = client_with_fakes(schema_available=False)

    response = client.get(
        "/api/v1/management/past-due/reasons",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "schema_available": False,
        "summary": {
            "event_count": 0,
            "total_past_due_amount": "0.00",
            "remaining_past_due_amount": "0.00",
        },
        "rows": [],
    }
