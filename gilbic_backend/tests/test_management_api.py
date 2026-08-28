from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import gilbic_backend.management_repository as management_repository_module
import pytest
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import (
    AccountConflict,
    AccountContext,
    DeviceRevoked,
)
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.management_api import (
    _account_payload,
    management_account_repository_dependency,
    management_auth_admin_dependency,
    management_auth_client_dependency,
    management_repository_dependency,
)
from gilbic_backend.management_repository import (
    AccountAdminRecord,
    DeviceAdminRecord,
    PostgresManagementRepository,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TARGET_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
TARGET_AUTH_ID = UUID("44444444-4444-4444-8444-444444444444")
DEVICE_ID = UUID("55555555-5555-4555-8555-555555555555")
REASSIGNED_USER_ID = UUID("66666666-6666-4666-8666-666666666666")
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


def device_record(
    *,
    status: str = "active",
    user_id: UUID = TARGET_USER_ID,
) -> DeviceAdminRecord:
    return DeviceAdminRecord(
        id=DEVICE_ID,
        user_id=user_id,
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
        self.accounts = [account_record()]
        self.list_account_calls: list[dict[str, object]] = []
        self.selected_device = device_record()

    def list_accounts(
        self,
        *,
        query: str | None = None,
        role_code: str | None = None,
        account_status: str | None = None,
        staff_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ):
        self.list_account_calls.append(
            {
                "query": query,
                "role_code": role_code,
                "account_status": account_status,
                "staff_only": staff_only,
                "limit": limit,
                "offset": offset,
            }
        )
        return list(self.accounts)

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
        if actor_user_id == self.selected_device.user_id and device_status == "revoked":
            raise AccountConflict("You cannot revoke your own current account's device.")
        if device_status != self.selected_device.status:
            self.selected_device = replace(self.selected_device, status=device_status)
        return self.selected_device


class DeviceOwnerRaceCursor:
    def __init__(self, connection: DeviceOwnerRaceConnection) -> None:
        self.connection = connection
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, query: str, parameters=()) -> None:
        sql = " ".join(query.split())
        if sql.startswith("select user_id from core.devices where id"):
            self.row = {"user_id": TARGET_USER_ID}
        elif sql.startswith("select id from core.users where id"):
            self.row = (TARGET_USER_ID,)
        elif sql.endswith("from core.devices where id = %s for update"):
            self.row = self.connection.device_row()
        elif sql.startswith("select 1 from core.user_roles"):
            self.row = None
        elif sql.startswith("update core.devices set status = %s"):
            self.connection.status = parameters[0]
            self.connection.mutation_count += 1
            self.row = None
        elif sql.startswith("insert into core.audit_logs"):
            self.connection.audit_count += 1
            self.row = None
        elif sql.endswith("from core.devices where id = %s"):
            self.row = self.connection.device_row()
        else:
            raise AssertionError(f"Unexpected repository SQL: {sql}")

    def fetchone(self):
        return self.row


class DeviceOwnerRaceConnection:
    def __init__(self) -> None:
        self.status = "pending"
        self.mutation_count = 0
        self.audit_count = 0

    @contextmanager
    def transaction(self):
        yield

    def cursor(self, **kwargs) -> DeviceOwnerRaceCursor:
        return DeviceOwnerRaceCursor(self)

    def device_row(self) -> dict[str, object]:
        return {
            "id": DEVICE_ID,
            "user_id": REASSIGNED_USER_ID,
            "platform": "android",
            "app_version": "0.4.0+4",
            "status": self.status,
            "registered_at": NOW,
            "last_seen_at": NOW,
        }


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


def test_list_accounts_rejects_callers_without_account_or_device_permission() -> None:
    client, accounts, _, _ = client_with_fakes()
    accounts.context = management_context(permissions=("management.dashboard.view",))

    response = client.get("/api/v1/management/accounts", headers=headers())

    assert response.status_code == 403
    assert response.json()["detail"] == "This action is not permitted for your account."


def test_account_payload_omits_auth_user_id() -> None:
    assert "auth_user_id" not in _account_payload(account_record())


def test_list_accounts_allows_device_managers_and_forwards_filters() -> None:
    client, accounts, _, management = client_with_fakes()
    accounts.context = management_context(permissions=("device.manage",))

    response = client.get(
        "/api/v1/management/accounts",
        params={
            "q": "  Ana  ",
            "role": "collector",
            "status": "active",
            "staff_only": "true",
            "limit": 25,
            "offset": 50,
        },
        headers=headers(),
    )

    assert response.status_code == 200
    item = response.json()["data"]["accounts"][0]
    assert item.get("auth_user_id") is None
    assert item["username"] == "collector.one"
    assert item["roles"] == ["collector"]
    assert item["device_count"] == 1
    assert accounts.checked_device == INSTALLATION_ID
    assert management.list_account_calls == [{
        "query": "Ana",
        "role_code": "collector",
        "account_status": "active",
        "staff_only": True,
        "limit": 25,
        "offset": 50,
    }]


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


def test_management_can_list_devices() -> None:
    client, _, _, _ = client_with_fakes()

    list_response = client.get(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/devices",
        headers=headers(),
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["devices"][0]["platform"] == "android"


@pytest.mark.parametrize(
    ("previous_status", "requested_status"),
    [
        ("pending", "active"),
        ("active", "revoked"),
        ("revoked", "active"),
    ],
)
def test_device_status_transitions_require_only_device_manage(
    previous_status: str,
    requested_status: str,
) -> None:
    client, accounts, _, management = client_with_fakes()
    accounts.context = management_context(permissions=("device.manage",))
    management.selected_device = device_record(status=previous_status)

    response = client.patch(
        f"/api/v1/management/devices/{DEVICE_ID}/status",
        headers=headers(),
        json={"status": requested_status},
    )

    assert response.status_code == 200
    assert response.json()["data"]["device"]["status"] == requested_status
    assert management.device_change == (ACTOR_USER_ID, DEVICE_ID, requested_status)


@pytest.mark.parametrize("status", ["active", "revoked"])
def test_device_status_no_op_returns_selected_device(status: str) -> None:
    client, _, _, management = client_with_fakes()
    management.selected_device = device_record(status=status)

    response = client.patch(
        f"/api/v1/management/devices/{DEVICE_ID}/status",
        headers=headers(),
        json={"status": status},
    )

    assert response.status_code == 200
    assert response.json()["data"]["device"]["status"] == status
    assert management.device_change == (ACTOR_USER_ID, DEVICE_ID, status)


def test_device_status_rejects_account_manager_without_device_manage() -> None:
    client, accounts, _, management = client_with_fakes()
    accounts.context = management_context(permissions=("account.manage",))

    response = client.patch(
        f"/api/v1/management/devices/{DEVICE_ID}/status",
        headers=headers(),
        json={"status": "revoked"},
    )

    assert response.status_code == 403
    assert management.device_change is None


def test_management_cannot_revoke_own_device() -> None:
    client, _, _, management = client_with_fakes()
    management.selected_device = device_record(user_id=ACTOR_USER_ID)

    response = client.patch(
        f"/api/v1/management/devices/{DEVICE_ID}/status",
        headers=headers(),
        json={"status": "revoked"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "You cannot revoke your own current account's device."
    assert management.selected_device.status == "active"
    assert management.device_change == (ACTOR_USER_ID, DEVICE_ID, "revoked")


def test_repository_rejects_device_ownership_change_after_user_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = DeviceOwnerRaceConnection()

    @contextmanager
    def owner_race_connection():
        yield connection

    monkeypatch.setattr(
        management_repository_module,
        "open_connection",
        owner_race_connection,
    )

    try:
        outcome = PostgresManagementRepository().set_device_status(
            actor_user_id=ACTOR_USER_ID,
            device_id=DEVICE_ID,
            device_status="active",
        )
    except AccountConflict as error:
        outcome = error

    assert {
        "conflict": isinstance(outcome, AccountConflict),
        "detail": str(outcome),
        "status": connection.status,
        "mutation_count": connection.mutation_count,
        "audit_count": connection.audit_count,
    } == {
        "conflict": True,
        "detail": "Registered device ownership changed during this operation.",
        "status": "pending",
        "mutation_count": 0,
        "audit_count": 0,
    }
