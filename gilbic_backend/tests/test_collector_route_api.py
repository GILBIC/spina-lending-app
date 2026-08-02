from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import (
    AccountContext,
    DeviceRequired,
    DeviceRevoked,
)
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.collector_route_api import (
    PHILIPPINES_TIMEZONE,
    collector_route_repository_dependency,
)
from gilbic_backend.collector_route_repository import (
    CollectorRouteEntryRecord,
    CollectorRouteRecord,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")


def collector_context(*, permissions: tuple[str, ...] = ("route.view",)) -> AccountContext:
    return AccountContext(
        user_id=COLLECTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="collector.one",
        email="collector@example.com",
        full_name="Collector One",
        status="active",
        roles=("collector",),
        permissions=permissions,
        device_registered=True,
    )


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "collector-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="collector@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self) -> None:
        self.context = collector_context()
        self.device_error: Exception | None = None
        self.seen_device: str | None = None

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        self.seen_device = device_identifier
        if self.device_error is not None:
            raise self.device_error
        return self.context


class FakeRoutes:
    def __init__(self) -> None:
        self.request: tuple[UUID, str, date] | None = None

    def get_today_route(
        self,
        *,
        collector_user_id: UUID,
        collector_name: str,
        route_date: date,
    ) -> CollectorRouteRecord:
        self.request = (collector_user_id, collector_name, route_date)
        return CollectorRouteRecord(
            route_date=route_date,
            collector_name=collector_name,
            areas=("Cardona",),
            entries=(
                CollectorRouteEntryRecord(
                    route_entry_id=LOAN_ID,
                    client_id=CLIENT_ID,
                    loan_id=LOAN_ID,
                    client_name="Ana Client",
                    area="Cardona",
                    loan_type="Regular",
                    daily_amount=Decimal("200.00"),
                    remaining_balance=Decimal("4800.00"),
                    pass_count=1,
                    last_payment_date=date(2026, 7, 31),
                    advance_until=None,
                    status="Recorded today",
                    note="Call before visiting",
                    state_version=7,
                    is_reconciled=True,
                    mobile_collections_enabled=True,
                    mobile_balance_mode="direct_remaining_balance",
                    processed_today=True,
                    today_entry_type="payment",
                    today_collector_name="Collector Two",
                ),
            ),
        )


def client_with_fakes() -> tuple[TestClient, FakeAccounts, FakeRoutes]:
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    routes = FakeRoutes()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[collector_route_repository_dependency] = lambda: routes
    return TestClient(app), accounts, routes


def request_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer collector-token",
        "X-Device-Id": "gilbic-installation-one",
    }


def test_collector_receives_only_server_assigned_route() -> None:
    client, accounts, routes = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/collector/routes/today",
        headers=request_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["collector_name"] == "Collector One"
    assert data["areas"] == ["Cardona"]
    assert data["expected_total"] == "200.00"
    assert data["entries"] == [
        {
            "route_entry_id": str(LOAN_ID),
            "client_id": str(CLIENT_ID),
            "loan_id": str(LOAN_ID),
            "client_name": "Ana Client",
            "area": "Cardona",
            "loan_type": "Regular",
            "daily_amount": "200.00",
            "remaining_balance": "4800.00",
            "pass_count": 1,
            "last_payment_date": "2026-07-31",
            "advance_until": None,
            "status": "Recorded today",
            "note": "Call before visiting",
            "route_revision": f"loan:{LOAN_ID}:v7",
            "can_collect_mobile": True,
            "can_enter_payment": True,
            "collection_message": "Today's collection has already been recorded.",
            "processed_today": True,
            "today_entry_type": "payment",
            "today_collector_name": "Collector Two",
        }
    ]
    assert accounts.seen_device == "gilbic-installation-one"
    assert routes.request is not None
    assert routes.request[0] == COLLECTOR_USER_ID
    assert routes.request[1] == "Collector One"
    assert routes.request[2] == datetime.now(PHILIPPINES_TIMEZONE).date()


def test_collector_route_requires_device_header() -> None:
    client, accounts, _ = client_with_fakes()
    accounts.device_error = DeviceRequired("X-Device-Id is required.")

    response = client.get(
        "/api/v1/collector/routes/today",
        headers={"Authorization": "Bearer collector-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."


def test_revoked_device_cannot_use_existing_token_for_route() -> None:
    client, accounts, _ = client_with_fakes()
    accounts.device_error = DeviceRevoked("This device has been revoked.")

    response = client.get(
        "/api/mobile/v1/collector/routes/today",
        headers=request_headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "This device has been revoked."


def test_route_view_permission_is_required() -> None:
    client, accounts, _ = client_with_fakes()
    accounts.context = collector_context(permissions=("collection.create",))

    response = client.get(
        "/api/v1/collector/routes/today",
        headers=request_headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Collector route permission is required."