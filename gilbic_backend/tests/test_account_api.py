from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_api import (
    account_auth_client_dependency,
    account_repository_dependency,
    self_account_repository_dependency,
)
from gilbic_backend.account_repository import AccountContext, AccountNotFound
from gilbic_backend.account_self_repository import AccountDeviceRecord
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CURRENT_DEVICE_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_DEVICE_ID = UUID("44444444-4444-4444-8444-444444444444")


def _context() -> AccountContext:
    return AccountContext(
        user_id=USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="collector.one",
        email="collector@example.com",
        full_name="Collector One",
        status="active",
        roles=("collector",),
        permissions=("collection.create", "route.view"),
        device_registered=True,
        registered_device_id=CURRENT_DEVICE_ID,
    )


def _device(device_id: UUID, *, status: str = "active") -> AccountDeviceRecord:
    return AccountDeviceRecord(
        id=device_id,
        user_id=USER_ID,
        platform="android" if device_id == CURRENT_DEVICE_ID else "ios",
        app_version="0.4.0+4",
        status=status,
        registered_at=datetime(2026, 8, 15, 1, 0, tzinfo=UTC),
        last_seen_at=datetime(2026, 8, 15, 2, 0, tzinfo=UTC),
    )


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "access-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="collector@example.com",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            email_confirmed=True,
        )


class FakeAccounts:
    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "install-current"
        return _context()


class FakeSelfAccountRepository:
    def __init__(self) -> None:
        self.devices = [_device(CURRENT_DEVICE_ID), _device(OTHER_DEVICE_ID)]
        self.revoked: UUID | None = None
        self.missing = False

    def list_devices(self, *, user_id: UUID) -> list[AccountDeviceRecord]:
        assert user_id == USER_ID
        return list(self.devices)

    def revoke_device(
        self,
        *,
        user_id: UUID,
        device_id: UUID,
    ) -> AccountDeviceRecord:
        assert user_id == USER_ID
        if self.missing:
            raise AccountNotFound("That device is not registered to this account.")
        self.revoked = device_id
        return _device(device_id, status="revoked")


def _client() -> tuple[TestClient, FakeSelfAccountRepository]:
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    self_account = FakeSelfAccountRepository()
    app = create_app()
    app.dependency_overrides[account_auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[self_account_repository_dependency] = lambda: self_account
    return TestClient(app), self_account


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer access-token",
        "X-Device-Id": "install-current",
    }


def test_mobile_account_returns_own_profile_and_privacy_safe_device_state() -> None:
    client, _ = _client()

    response = client.get("/api/mobile/v1/account", headers=_headers())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["profile"] == {
        "id": str(USER_ID),
        "username": "collector.one",
        "email": "collector@example.com",
        "full_name": "Collector One",
        "role": "Collector",
        "roles": ["collector"],
        "permissions": ["collection.create", "route.view"],
        "status": "active",
    }
    assert len(data["devices"]) == 2
    assert data["devices"][0]["id"] == str(CURRENT_DEVICE_ID)
    assert data["devices"][0]["is_current"] is True
    assert data["devices"][1]["id"] == str(OTHER_DEVICE_ID)
    assert data["devices"][1]["is_current"] is False
    assert "device_identifier_hash" not in data["devices"][0]


def test_account_can_revoke_only_another_owned_device() -> None:
    client, account_state = _client()

    response = client.post(
        f"/api/mobile/v1/account/devices/{OTHER_DEVICE_ID}/revoke",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["data"]["device"]["status"] == "revoked"
    assert response.json()["data"]["device"]["is_current"] is False
    assert account_state.revoked == OTHER_DEVICE_ID


def test_account_rejects_revoking_the_current_device() -> None:
    client, account_state = _client()

    response = client.post(
        f"/api/mobile/v1/account/devices/{CURRENT_DEVICE_ID}/revoke",
        headers=_headers(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Use Sign out to end the session on this device."
    assert account_state.revoked is None


def test_account_cannot_revoke_a_device_outside_its_ownership_scope() -> None:
    client, account_state = _client()
    account_state.missing = True

    response = client.post(
        f"/api/mobile/v1/account/devices/{OTHER_DEVICE_ID}/revoke",
        headers=_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "That device is not registered to this account."
