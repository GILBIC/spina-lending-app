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
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
ASSIGNED_COLLECTOR_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
WORK_DATE = date(2026, 8, 17)


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
    permissions = ("collection.create", "delegated_area.view")

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "device-one"
        return AccountContext(
            user_id=COLLECTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="collector.one",
            email="collector@example.com",
            full_name="Collector One",
            status="active",
            roles=("collector",),
            permissions=self.permissions,
            device_registered=True,
        )


class FakeAccountsWithoutDelegatedView(FakeAccounts):
    permissions = ("collection.create",)


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
                "Delegated other-area work. The assigned collector and linked "
                "client will be notified after posting."
            )
        ),
        assigned_collector_user_id=ASSIGNED_COLLECTOR_ID,
        assigned_collector_name="Collector Two",
        processed_today=processed_today,
        today_entry_type="payment" if processed_today else "",
        today_collector_user_id=(COLLECTOR_USER_ID if processed_today else None),
        today_collector_name="Collector Three" if processed_today else "",
        today_amount=Decimal("200.00") if processed_today else Decimal("0.00"),
        today_is_locked=processed_today,
    )


class FakeOtherAreas:
    def search(self, *, collector_user_id: UUID, query: str, limit: int):
        assert collector_user_id == COLLECTOR_USER_ID
        assert query == "Ana"
        assert limit == 10
        return (_record(),)

    def list_work(
        self,
        *,
        collector_user_id: UUID,
        collection_date: date,
        assigned_collector_user_id: UUID | None,
        limit: int,
    ):
        assert collector_user_id == COLLECTOR_USER_ID
        assert collection_date == WORK_DATE
        assert assigned_collector_user_id == ASSIGNED_COLLECTOR_ID
        assert limit == 500
        return (_record(processed_today=True),)


def _client(accounts) -> TestClient:
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[other_area_repository_dependency] = lambda: FakeOtherAreas()
    return TestClient(app)


def test_collector_can_list_granted_other_area_work_and_see_today_recorder() -> None:
    client = _client(FakeAccounts())

    response = client.get(
        "/api/mobile/v1/collector/delegated-area/work"
        f"?date={WORK_DATE.isoformat()}"
        f"&assigned_collector_user_id={ASSIGNED_COLLECTOR_ID}",
        headers={
            "Authorization": "Bearer collector-token",
            "X-Device-Id": "device-one",
        },
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


def test_collector_can_search_a_granted_other_area_client() -> None:
    client = _client(FakeAccounts())

    response = client.get(
        "/api/mobile/v1/collector/other-area-clients/search?q=Ana&limit=10",
        headers={
            "Authorization": "Bearer collector-token",
            "X-Device-Id": "device-one",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["client_name"] == "Ana Client"
    assert data[0]["is_other_area"] is True
    assert data[0]["assigned_collector_name"] == "Collector Two"
    assert data[0]["can_enter_payment"] is True
    assert data[0]["route_revision"] == f"loan:{LOAN_ID}:v3"


def test_other_area_surfaces_require_delegated_view_permission() -> None:
    client = _client(FakeAccountsWithoutDelegatedView())
    headers = {
        "Authorization": "Bearer collector-token",
        "X-Device-Id": "device-one",
    }

    search = client.get(
        "/api/mobile/v1/collector/other-area-clients/search?q=Ana&limit=10",
        headers=headers,
    )
    work = client.get(
        f"/api/mobile/v1/collector/delegated-area/work?date={WORK_DATE.isoformat()}",
        headers=headers,
    )

    assert search.status_code == 403
    assert work.status_code == 403
