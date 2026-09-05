from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.management_api import (
    management_account_repository_dependency,
    management_auth_admin_dependency,
    management_auth_client_dependency,
    management_repository_dependency,
)
from gilbic_backend.management_repository import AccountAdminRecord


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TARGET_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
TARGET_AUTH_ID = UUID("44444444-4444-4444-8444-444444444444")
CLIENT_ID = UUID("77777777-7777-4777-8777-777777777777")
NOW = datetime(2026, 9, 5, 11, 45, tzinfo=UTC)
DEVICE_ID = "management-phone"


def _management_context(*, permissions: tuple[str, ...] = ("account.manage",)) -> AccountContext:
    return AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="manager.one",
        email="manager@example.com",
        full_name="Manager One",
        status="active",
        roles=("management",),
        permissions=permissions,
        device_registered=True,
    )


def _client_context() -> AccountContext:
    return AccountContext(
        user_id=TARGET_USER_ID,
        auth_user_id=TARGET_AUTH_ID,
        username="client.one",
        email="client@example.com",
        full_name="Maria Santos",
        status="pending",
        roles=("client",),
        permissions=("loan.self.view",),
        device_registered=False,
    )


class FakeAuthClient:
    def __init__(self) -> None:
        self.sign_up_calls = 0

    def sign_up(self, *, email: str, password: str) -> AuthSession:
        self.sign_up_calls += 1
        return AuthSession(
            auth_user_id=TARGET_AUTH_ID,
            email=email,
            access_token=None,
            refresh_token=None,
            expires_at=None,
            email_confirmed=False,
        )

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
        self.context = _management_context()
        self.public_profile_writes = 0

    def username_exists(self, username: str) -> bool:
        assert username.strip()
        return False

    def create_client_profile(
        self,
        *,
        auth_user_id: UUID,
        username: str,
        email: str,
        full_name: str,
        claimed_client_code: str,
        claimed_phone_number: str | None,
    ) -> AccountContext:
        self.public_profile_writes += 1
        return _client_context()

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == DEVICE_ID
        return self.context


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
        self.created_client: tuple[UUID, UUID, str, str, UUID] | None = None

    def create_client_account_profile(
        self,
        *,
        actor_user_id: UUID,
        auth_user_id: UUID,
        username: str,
        email: str,
        client_id: UUID,
    ) -> AccountAdminRecord:
        self.created_client = (
            actor_user_id,
            auth_user_id,
            username,
            email,
            client_id,
        )
        return AccountAdminRecord(
            id=TARGET_USER_ID,
            auth_user_id=auth_user_id,
            username=username,
            email=email,
            full_name="Maria Santos",
            status="pending",
            roles=("client",),
            device_count=0,
            created_at=NOW,
            updated_at=NOW,
        )


def _client_with_fakes():
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    admin = FakeAuthAdmin()
    management = FakeManagementRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_auth_client_dependency] = lambda: auth
    app.dependency_overrides[management_account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_auth_admin_dependency] = lambda: admin
    app.dependency_overrides[management_repository_dependency] = lambda: management
    return TestClient(app), auth, accounts, admin, management


def _management_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": DEVICE_ID,
    }


def test_public_client_self_registration_is_disabled_without_side_effects() -> None:
    client, auth, accounts, _, _ = _client_with_fakes()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "client.one",
            "email": "client@example.com",
            "full_name": "Maria Santos",
            "client_code": "C-001",
            "phone_number": "09171234567",
            "password": "borrower-chosen-password",
        },
    )

    assert response.status_code == 410
    assert "created by SPINA" in response.json()["detail"]
    assert auth.sign_up_calls == 0
    assert accounts.public_profile_writes == 0


def test_mobile_registration_alias_is_disabled_before_accepting_registration_data() -> None:
    client, auth, accounts, _, _ = _client_with_fakes()

    response = client.post("/api/mobile/v1/auth/register", json={})

    assert response.status_code == 410
    assert "created by SPINA" in response.json()["detail"]
    assert auth.sign_up_calls == 0
    assert accounts.public_profile_writes == 0


def test_management_can_invite_and_link_existing_client_without_password() -> None:
    client, _, _, admin, management = _client_with_fakes()

    response = client.post(
        "/api/v1/management/client-accounts/invite",
        headers=_management_headers(),
        json={
            "client_id": str(CLIENT_ID),
            "username": "client.one",
            "email": "client@example.com",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["invitation_sent"] is True
    assert data["account"]["roles"] == ["client"]
    assert data["account"]["full_name"] == "Maria Santos"
    assert admin.invited_email == "client@example.com"
    assert management.created_client == (
        ACTOR_USER_ID,
        TARGET_AUTH_ID,
        "client.one",
        "client@example.com",
        CLIENT_ID,
    )


def test_client_invitation_requires_account_manage_permission() -> None:
    client, _, accounts, admin, management = _client_with_fakes()
    accounts.context = _management_context(permissions=("management.dashboard.view",))

    response = client.post(
        "/api/v1/management/client-accounts/invite",
        headers=_management_headers(),
        json={
            "client_id": str(CLIENT_ID),
            "username": "client.one",
            "email": "client@example.com",
        },
    )

    assert response.status_code == 403
    assert admin.invited_email is None
    assert management.created_client is None
