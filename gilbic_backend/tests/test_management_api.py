from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import (
    AccountConflict,
    AccountContext,
    DeviceRevoked,
)
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.management_api import (
    management_account_repository_dependency,
    management_auth_admin_dependency,
    management_auth_client_dependency,
    management_repository_dependency,
)
from gilbic_backend.management_repository import AccountAdminRecord, DeviceAdminRecord


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TARGET_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
TARGET_AUTH_ID = UUID("44444444-4444-4444-8444-444444444444")
DEVICE_ID = UUID("55555555-5555-4555-8555-555555555555")
INSTALLATION_ID = "gilbic-management-device"
NOW = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)


def management_context(*, permissions: tuple[str, ...] | None = None) -> AccountContext:
    return AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="manager.one",
        email="manager@example.com",
        full_name="Manager One",
        status="active",
        roles=("management",),
        permissions=permissions
        if permissions is not None
        else ("account.manage", "device.manage", "management.dashboard.view"),
        device_registered=True,
    )


def account_record(*, role: str = "collector", status: str = "pending") -> AccountAdminRecord:
    return AccountAdminRecord(
        id=TARGET_USER_ID,
        auth_user_id=TARGET_AUTH_ID,
        username="collector.one",
        email="collector@example.com",
        full_name="Collector One",
        status=status,
        roles=(role,),
        device_count=1,
        created_at=NOW,
        updated_at=NOW,
    )


def device_record(*, status: str = "active") -> DeviceAdminRecord:
    return DeviceAdminRecord(
        id=DEVICE_ID,
        user_id=TARGET_USER_ID,
        platform="android",
        app_version="0.4.0+4",
        status=status,
        registered_at=NOW,
        last_seen_at=NOW,
    )


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
    def __init__(self) -> None:
        self.context = management_context()
        self.username_taken = False
        self.checked_device: str | None = None
        self.device_error: Exception | None = None

    def get_context(self, auth_user_id: UUID) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        return self.context

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        self.checked_device = device_identifier
        if self.device_error is not None:
            raise self.device_error
        return self.context

    def username_exists(self, username: str) -> bool:
        assert username
        return self.username_taken


class FakeAuthAdmin:
    def __init__(self) -> None:
        self.invited_email: str | None = None
        self.deleted_user: UUID | None = None

    def invite_user(self, *, email: str) -> UUID:
        self.invited_email = email
        return TARGET_AUTH_ID

    def delete_user(self, *, auth_user_id: UUID) -> None:
        self.deleted_user = auth_user_id


class FakeManagementRepository:
    def __init__(self) -> None:
        self.role_change: tuple[UUID, UUID, str] | None = None
        self.status_change: tuple[UUID, UUID, str] | None = None
        self.device_change: tuple[UUID, UUID, str] | None = None
        self.created_role: str | None = None

    def list_accounts(self, *, limit: int = 100, offset: int = 0):
        assert limit == 100
        assert offset == 0
        return [account_record()]

    def create_staff_profile(
        self,
        *,
        actor_user_id: UUID,
        auth_user_id: UUID,
        username: str,
        email: str,
        full_name: str,
        role_code: str,
    ) -> AccountAdminRecord:
        assert actor_user_id == ACTOR_USER_ID
        assert auth_user_id == TARGET_AUTH_ID
        assert username == "collector.one"
        assert email == "collector@example.com"
        assert full_name == "Collector One"
        self.created_role = role_code
        return account_record(role=role_code)

    def set_role(self, *, actor_user_id: UUID, target_user_id: UUID, role_code: str):
        self.role_change = (actor_user_id, target_user_id, role_code)
        if actor_user_id == target_user_id:
            raise AccountConflict("You cannot change your own management role.")
        return account_record(role=role_code, status="active")

    def set_status(self, *, actor_user_id: UUID, target_user_id: UUID, account_status: str):
        self.status_change = (actor_user_id, target_user_id, account_status)
        if actor_user_id == target_user_id and account_status != "active":
            raise AccountConflict("You cannot lock or disable your own management account.")
        return account_record(status=account_status)

    def list_devices(self, *, target_user_id: UUID):
        assert target_user_id == TARGET_USER_ID
        return [device_record()]

    def set_device_status(self, *, actor_user_id: UUID, device_id: UUID, device_status: str):
        self.device_change = (actor_user_id, device_id, device_status)
        return device_record(status=device_status)


def client_with_fakes():
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    admin = FakeAuthAdmin()
    management = FakeManagementRepository()
    app = create_app()
    app.dependency_overrides[management_auth_client_dependency] = lambda: auth
    app.dependency_overrides[management_account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_auth_admin_dependency] = lambda: admin
    app.dependency_overrides[management_repository_dependency] = lambda: management
    return TestClient(app), accounts, admin, management


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": INSTALLATION_ID,
    }


def test_management_device_header_is_required() -> None:
    client, _, _, _ = client_with_fakes()

    response = client.get(
        "/api/v1/management/accounts",
        headers={"Authorization": "Bearer management-token"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."


def test_management_rejects_revoked_device_with_existing_token() -> None:
    client, accounts, _, _ = client_with_fakes()
    accounts.device_error = DeviceRevoked("This device has been revoked.")

    response = client.get("/api/v1/management/accounts", headers=headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "This device has been revoked."


def test_management_permission_is_required() -> None:
    client, accounts, _, _ = client_with_fakes()
    accounts.context = management_context(permissions=("management.dashboard.view",))

    response = client.get("/api/v1/management/accounts", headers=headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "Management permission is required."


def test_management_can_list_accounts() -> None:
    client, accounts, _, _ = client_with_fakes()

    response = client.get("/api/v1/management/accounts", headers=headers())

    assert response.status_code == 200
    item = response.json()["data"]["accounts"][0]
    assert item["username"] == "collector.one"
    assert item["roles"] == ["collector"]
    assert item["device_count"] == 1
    assert accounts.checked_device == INSTALLATION_ID


def test_management_can_invite_collector_without_password() -> None:
    client, _, admin, management = client_with_fakes()

    response = client.post(
        "/api/v1/management/accounts/invite",
        headers=headers(),
        json={
            "username": "collector.one",
            "email": "collector@example.com",
            "full_name": "Collector One",
            "role": "collector",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["invitation_sent"] is True
    assert admin.invited_email == "collector@example.com"
    assert management.created_role == "collector"


def test_invite_rejects_client_or_unknown_role() -> None:
    client, _, _, _ = client_with_fakes()

    response = client.post(
        "/api/v1/management/accounts/invite",
        headers=headers(),
        json={
            "username": "staff.one",
            "email": "staff@example.com",
            "full_name": "Staff One",
            "role": "client",
        },
    )

    assert response.status_code == 422


def test_management_can_change_another_staff_role() -> None:
    client, _, _, management = client_with_fakes()

    response = client.patch(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/role",
        headers=headers(),
        json={"role": "employee"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["account"]["roles"] == ["employee"]
    assert management.role_change == (ACTOR_USER_ID, TARGET_USER_ID, "employee")


def test_management_cannot_demote_itself() -> None:
    client, _, _, _ = client_with_fakes()

    response = client.patch(
        f"/api/v1/management/accounts/{ACTOR_USER_ID}/role",
        headers=headers(),
        json={"role": "employee"},
    )

    assert response.status_code == 409


def test_management_can_lock_another_account() -> None:
    client, _, _, management = client_with_fakes()

    response = client.patch(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/status",
        headers=headers(),
        json={"status": "locked"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["account"]["status"] == "locked"
    assert management.status_change == (ACTOR_USER_ID, TARGET_USER_ID, "locked")


def test_management_cannot_lock_itself() -> None:
    client, _, _, _ = client_with_fakes()

    response = client.patch(
        f"/api/v1/management/accounts/{ACTOR_USER_ID}/status",
        headers=headers(),
        json={"status": "locked"},
    )

    assert response.status_code == 409


def test_management_can_list_and_revoke_devices() -> None:
    client, _, _, management = client_with_fakes()

    list_response = client.get(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/devices",
        headers=headers(),
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["devices"][0]["platform"] == "android"

    revoke_response = client.patch(
        f"/api/v1/management/devices/{DEVICE_ID}/status",
        headers=headers(),
        json={"status": "revoked"},
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["data"]["device"]["status"] == "revoked"
    assert management.device_change == (ACTOR_USER_ID, DEVICE_ID, "revoked")
