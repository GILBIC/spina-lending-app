from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.cross_collection_status_repository import CrossCollectionStatusRecord
from gilbic_backend.cross_remittance_api import (
    cross_collection_status_repository_dependency,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
ASSIGNED_COLLECTOR_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
TRANSACTION_ID = UUID("66666666-6666-4666-8666-666666666666")
REMITTANCE_ID = UUID("77777777-7777-4777-8777-777777777777")
COLLECTION_DATE = date(2026, 8, 18)
ACCEPTED_AT = datetime(2026, 8, 18, 2, 15, tzinfo=timezone.utc)


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


class FakeStatuses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list_for_collector(self, **kwargs):
        self.calls.append(kwargs)
        return (
            CrossCollectionStatusRecord(
                transaction_id=TRANSACTION_ID,
                receipt_number="GBC-20260818-00000018",
                client_id=CLIENT_ID,
                client_name="Ana Client",
                loan_id=LOAN_ID,
                loan_type="Regular",
                area="CARDONA › LOOC",
                assigned_collector_user_id=ASSIGNED_COLLECTOR_ID,
                assigned_collector_name="Collector Two",
                collection_date=COLLECTION_DATE,
                entry_type="payment",
                amount=Decimal("50.00"),
                accepted_at=ACCEPTED_AT,
                is_locked=True,
                remittance_id=REMITTANCE_ID,
                remittance_number="REM-20260818-00000006",
                custody_status="awaiting_acceptance",
                remittance_recipient_user_id=ASSIGNED_COLLECTOR_ID,
                remittance_recipient_name="Collector Two",
                submitted_at=ACCEPTED_AT,
                received_at=None,
            ),
        )


def _client(
    *,
    roles: tuple[str, ...] = ("collector",),
    permissions: tuple[str, ...] = ("remittance.view",),
) -> tuple[TestClient, FakeStatuses]:
    statuses = FakeStatuses()
    accounts = FakeAccounts(roles=roles, permissions=permissions)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[cross_collection_status_repository_dependency] = (
        lambda: statuses
    )
    return TestClient(app), statuses


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer actor-token",
        "X-Device-Id": "device-one",
    }


def test_collector_sees_authoritative_other_area_remittance_status() -> None:
    client, statuses = _client()

    response = client.get(
        "/api/mobile/v1/collector/cross-remittances/history",
        params={"collection_date": COLLECTION_DATE.isoformat(), "limit": 100},
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["receipt_number"] == "GBC-20260818-00000018"
    assert data[0]["area"] == "CARDONA › LOOC"
    assert data[0]["assigned_collector_name"] == "Collector Two"
    assert data[0]["custody_status"] == "awaiting_acceptance"
    assert data[0]["remittance_number"] == "REM-20260818-00000006"
    assert data[0]["remittance_recipient_name"] == "Collector Two"
    assert statuses.calls == [
        {
            "collector_user_id": ACTOR_USER_ID,
            "collection_date": COLLECTION_DATE,
            "limit": 100,
        }
    ]


def test_other_area_collection_history_requires_remittance_view() -> None:
    client, statuses = _client(permissions=())

    response = client.get(
        "/api/mobile/v1/collector/cross-remittances/history",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert statuses.calls == []


def test_other_area_collection_history_is_collector_only() -> None:
    client, statuses = _client(
        roles=("management",),
        permissions=("remittance.view",),
    )

    response = client.get(
        "/api/mobile/v1/collector/cross-remittances/history",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert statuses.calls == []
