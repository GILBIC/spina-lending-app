from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.client_account_api import (
    client_account_repository_dependency,
    client_credential_mailer_dependency,
)
from gilbic_backend.main import create_app
from gilbic_backend.management_api import (
    management_account_repository_dependency,
    management_auth_admin_dependency,
    management_auth_client_dependency,
)


ACTOR_AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TARGET_AUTH_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
DEVICE_ID = "priority3-compensation-device"


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "management-token"
        return AuthSession(
            auth_user_id=ACTOR_AUTH_ID,
            email="manager@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == ACTOR_AUTH_ID
        assert device_identifier == DEVICE_ID
        return AccountContext(
            user_id=ACTOR_USER_ID,
            auth_user_id=ACTOR_AUTH_ID,
            username="manager.one",
            email="manager@example.com",
            full_name="Manager One",
            status="active",
            roles=("management",),
            permissions=("account.manage",),
            device_registered=True,
        )


class FakeAuthAdmin:
    def __init__(self) -> None:
        self.created = False
        self.deleted_user: UUID | None = None

    def create_user(
        self,
        *,
        email: str,
        password: str,
        email_confirm: bool = True,
    ) -> UUID:
        assert email == "client@example.com"
        assert password
        assert email_confirm is True
        self.created = True
        return TARGET_AUTH_ID

    def delete_user(self, *, auth_user_id: UUID) -> None:
        self.deleted_user = auth_user_id


class FailingClientAccountRepository:
    def next_client_username(self, *, client_id: UUID) -> str:
        assert client_id == CLIENT_ID
        return "spina.c.001"

    def create_client_account_profile(self, **kwargs):
        raise RuntimeError("database unavailable")


class UnusedMailer:
    def send_client_credentials(self, **kwargs):
        raise AssertionError("mail must not run when local account linking fails")


def test_unexpected_local_link_failure_compensates_created_auth_user() -> None:
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    admin = FakeAuthAdmin()
    repository = FailingClientAccountRepository()
    app = create_app()
    app.dependency_overrides[management_auth_client_dependency] = lambda: auth
    app.dependency_overrides[management_account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_auth_admin_dependency] = lambda: admin
    app.dependency_overrides[client_account_repository_dependency] = lambda: repository
    app.dependency_overrides[client_credential_mailer_dependency] = lambda: UnusedMailer()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/api/v1/management/client-accounts",
        headers={
            "Authorization": "Bearer management-token",
            "X-Device-Id": DEVICE_ID,
        },
        json={"client_id": str(CLIENT_ID), "email": "client@example.com"},
    )

    assert admin.created is True
    assert admin.deleted_user == TARGET_AUTH_ID
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Client account could not be saved. No active SPINA account was created."
    )
