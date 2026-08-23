from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.other_area_api import other_area_repository_dependency
from gilbic_backend.other_area_repository import OtherAreaLoanRecord


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
ASSIGNED_COLLECTOR_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
WORK_DATE = date(2026, 8, 18)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "actor-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="actor@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, roles: tuple[str, ...], permissions: tuple[str, ...]) -> None:
        self.roles = roles
        self.permissions = permissions

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "device-one"
        return AccountContext(
            user_id=ACTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="actor.one",
            email="actor@example.com",
            full_name="Actor One",
            status="active",
            roles=self.roles,
            permissions=self.permissions,
            device_registered=True,
        )


def _record(*, processed_today: bool = False) -> OtherAreaLoanRecord:
    return OtherAreaLoanRecord(
        route_entry_id=LOAN_ID,
        client_id=CLIENT_ID,
        loan_id=LOAN_ID,
        client_name="Ana Client",
        client_code="C-1001",
        phone_number="09170000000",
        area="CARDONA › LOOC",
        loan_type="Regular",
        daily_amount=Decimal("200.00"),
        remaining_balance=Decimal("4800.00"),
        pass_count=0,
        status="Recorded today" if processed_today else "Other area",
        route_revision=f"loan:{LOAN_ID}:v3",
        can_collect_mobile=True,
        can_enter_payment=not processed_today,
        collection_message=(
            "Already recorded today by Collector Three."
            if processed_today
            else (
                "Cross-route collection. The assigned collector and linked client "
                "will be notified after posting."
            )
        ),
        assigned_collector_user_id=ASSIGNED_COLLECTOR_ID,
        assigned_collector_name="Collector Two",
        processed_today=processed_today,
        today_entry_type="payment" if processed_today else "",
        today_collector_user_id=(ACTOR_USER_ID if processed_today else None),
        today_collector_name="Collector Three" if processed_today else "",
        today_amount=Decimal("200.00") if processed_today else Decimal("0.00"),
        today_is_locked=processed_today,
    )


class FakeOtherAreas:
    def __init__(self) -> None:
        self.collector_search_calls: list[dict[str, object]] = []
        self.management_search_calls: list[dict[str, object]] = []
        self.work_calls: list[dict[str, object]] = []

    def search(self, **kwargs):
        self.collector_search_calls.append(kwargs)
        return (_record(),)

    def search_management_direct(self, **kwargs):
        self.management_search_calls.append(kwargs)
        return (_record(),)

    def list_work(self, **kwargs):
        self.work_calls.append(kwargs)
        return (_record(processed_today=True),)


def _client(
    *,
    roles: tuple[str, ...],
    permissions: tuple[str, ...],
) -> tuple[TestClient, FakeOtherAreas]:
    repository = FakeOtherAreas()
    accounts = FakeAccounts(roles=roles, permissions=permissions)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[other_area_repository_dependency] = lambda: repository
    return TestClient(app), repository


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer actor-token",
        "X-Device-Id": "device-one",
    }


def test_collector_can_list_granted_other_area_work_and_see_today_recorder() -> None:
    client, repository = _client(
        roles=("collector",),
        permissions=("collection.create", "delegated_area.view"),
    )

    response = client.get(
        "/api/mobile/v1/collector/delegated-area/work",
        params={
            "date": WORK_DATE.isoformat(),
            "assigned_collector_user_id": str(ASSIGNED_COLLECTOR_ID),
        },
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["client_name"] == "Ana Client"
    assert data[0]["area"] == "CARDONA › LOOC"
    assert data[0]["assigned_collector_name"] == "Collector Two"
    assert data[0]["processed_today"] is True
    assert data[0]["today_entry_type"] == "payment"
    assert data[0]["today_collector_name"] == "Collector Three"
    assert data[0]["today_amount"] == "200.00"
    assert data[0]["today_is_locked"] is True
    assert data[0]["can_enter_payment"] is False
    assert repository.work_calls == [
        {
            "collector_user_id": ACTOR_USER_ID,
            "collection_date": WORK_DATE,
            "assigned_collector_user_id": ASSIGNED_COLLECTOR_ID,
            "limit": 500,
        }
    ]


def test_collector_search_needs_collection_permission_not_delegated_view() -> None:
    client, repository = _client(
        roles=("collector",),
        permissions=("collection.create",),
    )

    response = client.get(
        "/api/mobile/v1/collector/other-area-clients/search",
        params={"q": "Ana", "limit": 10},
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["client_name"] == "Ana Client"
    assert data[0]["is_other_area"] is True
    assert data[0]["assigned_collector_name"] == "Collector Two"
    assert repository.collector_search_calls == [
        {
            "collector_user_id": ACTOR_USER_ID,
            "query": "Ana",
            "limit": 10,
        }
    ]
    assert repository.management_search_calls == []


def test_collector_without_collection_permission_cannot_search_cross_route() -> None:
    client, repository = _client(
        roles=("collector",),
        permissions=("delegated_area.view",),
    )

    response = client.get(
        "/api/mobile/v1/collector/other-area-clients/search",
        params={"q": "Ana"},
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.collector_search_calls == []
    assert repository.management_search_calls == []


def test_management_direct_search_does_not_require_delegated_permission() -> None:
    client, repository = _client(
        roles=("management",),
        permissions=("collection.create",),
    )

    response = client.get(
        "/api/mobile/v1/collector/other-area-clients/search",
        params={"q": "Ana"},
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.collector_search_calls == []
    assert repository.management_search_calls == [
        {
            "management_user_id": ACTOR_USER_ID,
            "query": "Ana",
            "limit": 25,
        }
    ]


def test_non_collector_non_management_cannot_use_payment_search() -> None:
    client, repository = _client(
        roles=("employee",),
        permissions=("collection.create",),
    )

    response = client.get(
        "/api/mobile/v1/collector/other-area-clients/search",
        params={"q": "Ana"},
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.collector_search_calls == []
    assert repository.management_search_calls == []


def test_delegated_work_endpoint_still_requires_delegated_view_permission() -> None:
    client, repository = _client(
        roles=("collector",),
        permissions=("collection.create",),
    )

    response = client.get(
        "/api/mobile/v1/collector/delegated-area/work",
        params={"date": WORK_DATE.isoformat()},
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.work_calls == []


def test_delegated_work_endpoint_is_collector_only_even_with_permission() -> None:
    client, repository = _client(
        roles=("management",),
        permissions=("delegated_area.view",),
    )

    response = client.get(
        "/api/mobile/v1/collector/delegated-area/work",
        params={"date": WORK_DATE.isoformat()},
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.work_calls == []
