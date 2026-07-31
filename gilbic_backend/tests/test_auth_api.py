from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext, AccountNotFound
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
GILBIC_USER_ID = UUID("22222222-2222-4222-8222-222222222222")


def session(*, signed_in: bool = True) -> AuthSession:
    return AuthSession(
        auth_user_id=AUTH_USER_ID,
        email="collector@example.com",
        access_token="access-token" if signed_in else None,
        refresh_token="refresh-token" if signed_in else None,
        expires_at=datetime.now(UTC) + timedelta(hours=1) if signed_in else None,
        email_confirmed=signed_in,
    )


def context(
    *,
    role: str = "collector",
    status: str = "active",
    device_registered: bool = False,
) -> AccountContext:
    permissions = {
        "client": ("loan.self.view",),
        "collector": ("collection.create", "route.view"),
        "employee": ("employee.portal.view",),
        "management": ("management.dashboard.view",),
    }[role]
    return AccountContext(
        user_id=GILBIC_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="collector.one",
        email="collector@example.com",
        full_name="Collector One",
        status=status,
        roles=(role,),
        permissions=permissions,
        device_registered=device_registered,
    )


class FakeAuthClient:
    def __init__(self) -> None:
        self.logout_token: str | None = None

    def sign_up(self, *, email: str, password: str) -> AuthSession:
        assert email == "client@example.com"
        assert password == "strong-pass-123"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email=email,
            access_token=None,
            refresh_token=None,
            expires_at=None,
            email_confirmed=False,
        )

    def sign_in(self, *, email: str, password: str) -> AuthSession:
        assert email == "collector@example.com"
        assert password == "correct-password"
        return session()

    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "access-token"
        return session()

    def refresh(self, *, refresh_token: str) -> AuthSession:
        assert refresh_token == "refresh-token-12345"
        return session()

    def sign_out(self, *, access_token: str) -> None:
        self.logout_token = access_token


class FakeAccounts:
    def __init__(self) -> None:
        self.username_taken = False
        self.login_context = context()
        self.registered_device: tuple[str | None, str | None, str | None] | None = None

    def username_exists(self, username: str) -> bool:
        assert username
        return self.username_taken

    def resolve_email(self, identifier: str) -> str:
        if identifier == "missing":
            raise AccountNotFound("missing")
        if "@" in identifier:
            return identifier.lower()
        return "collector@example.com"

    def create_client_profile(
        self,
        *,
        auth_user_id: UUID,
        username: str,
        email: str,
        full_name: str,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert username == "client.one"
        assert email == "client@example.com"
        assert full_name == "Client One"
        return AccountContext(
            user_id=GILBIC_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username=username,
            email=email,
            full_name=full_name,
            status="pending",
            roles=("client",),
            permissions=("loan.self.view",),
        )

    def activate_and_register_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
        platform: str | None,
        app_version: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        self.registered_device = (device_identifier, platform, app_version)
        value = self.login_context
        return AccountContext(
            user_id=value.user_id,
            auth_user_id=value.auth_user_id,
            username=value.username,
            email=value.email,
            full_name=value.full_name,
            status=value.status,
            roles=value.roles,
            permissions=value.permissions,
            device_registered=device_identifier is not None,
        )

    def get_context(self, auth_user_id: UUID) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        return self.login_context


def client_with_fakes() -> tuple[TestClient, FakeAuthClient, FakeAccounts]:
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    return TestClient(app), auth, accounts


def test_public_registration_is_client_only() -> None:
    client, _, _ = client_with_fakes()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "client.one",
            "email": "client@example.com",
            "full_name": "Client One",
            "password": "strong-pass-123",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["requires_email_confirmation"] is True
    assert data["user"]["role"] == "Client"
    assert data["user"]["roles"] == ["client"]
    assert data["user"]["permissions"] == ["loan.self.view"]


def test_registration_rejects_role_injection() -> None:
    client, _, _ = client_with_fakes()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "client.one",
            "email": "client@example.com",
            "full_name": "Client One",
            "password": "strong-pass-123",
            "role": "Management",
        },
    )

    assert response.status_code == 422


def test_existing_mobile_login_contract_returns_server_role() -> None:
    client, _, accounts = client_with_fakes()

    response = client.post(
        "/api/mobile/v1/auth/login",
        json={"username": "collector.one", "password": "correct-password"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["access_token"] == "access-token"
    assert data["refresh_token"] == "refresh-token"
    assert data["user"]["role"] == "Collector"
    assert data["user"]["permissions"] == ["collection.create", "route.view"]
    assert data["user"]["device_registered"] is False
    assert accounts.registered_device == (None, None, None)


def test_login_registers_device_when_mobile_sends_identity() -> None:
    client, _, accounts = client_with_fakes()

    response = client.post(
        "/api/mobile/v1/auth/login",
        json={
            "username": "collector.one",
            "password": "correct-password",
            "device_id": "install-123",
            "platform": "android",
            "app_version": "0.3.0+3",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["device_registered"] is True
    assert accounts.registered_device == ("install-123", "android", "0.3.0+3")


def test_unknown_username_returns_generic_credential_error() -> None:
    client, _, _ = client_with_fakes()

    response = client.post(
        "/api/mobile/v1/auth/login",
        json={"username": "missing", "password": "anything"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_me_uses_bearer_identity_then_gilbic_permissions() -> None:
    client, _, _ = client_with_fakes()

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 200
    user = response.json()["data"]["user"]
    assert user["role"] == "Collector"
    assert "collection.create" in user["permissions"]


def test_refresh_returns_new_session_with_server_permissions() -> None:
    client, _, _ = client_with_fakes()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "refresh-token-12345"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["access_token"] == "access-token"
    assert response.json()["data"]["user"]["role"] == "Collector"


def test_logout_revokes_supabase_session() -> None:
    client, auth, _ = client_with_fakes()

    response = client.post(
        "/api/mobile/v1/auth/logout",
        headers={"Authorization": "Bearer access-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert auth.logout_token == "access-token"
