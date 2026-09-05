from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import gilbic_backend.management_api as management_api_module
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountConflict, AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.credential_mailer import CredentialDeliveryResult
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
NOW = datetime(2026, 9, 5, 13, 30, tzinfo=UTC)
DEVICE_ID = "management-phone"


def _actor_context(
    *,
    role: str = "management",
    permissions: tuple[str, ...] = ("account.manage",),
) -> AccountContext:
    return AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="manager.one",
        email="manager@example.com",
        full_name="Manager One",
        status="active",
        roles=(role,),
        permissions=permissions,
        device_registered=True,
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
        self.context = _actor_context()
        self.public_profile_writes = 0

    def create_client_profile(self, **kwargs) -> AccountContext:
        self.public_profile_writes += 1
        raise AssertionError("retired public registration must not create a profile")

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
        self.created: tuple[str, str, bool] | None = None
        self.deleted_user: UUID | None = None

    def create_user(
        self,
        *,
        email: str,
        password: str,
        email_confirm: bool = True,
    ) -> UUID:
        self.created = (email, password, email_confirm)
        return TARGET_AUTH_ID

    def delete_user(self, *, auth_user_id: UUID) -> None:
        self.deleted_user = auth_user_id


class FakeManagementRepository:
    def __init__(self) -> None:
        self.username = "spina.c.001"
        self.next_username_error: Exception | None = None
        self.create_error: Exception | None = None
        self.created_client: tuple[UUID, UUID, str, str, UUID] | None = None

    def next_client_username(self, *, client_id: UUID) -> str:
        assert client_id == CLIENT_ID
        if self.next_username_error is not None:
            raise self.next_username_error
        return self.username

    def create_client_account_profile(
        self,
        *,
        actor_user_id: UUID,
        auth_user_id: UUID,
        username: str,
        email: str,
        client_id: UUID,
    ) -> AccountAdminRecord:
        if self.create_error is not None:
            raise self.create_error
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
            status="active",
            roles=("client",),
            device_count=0,
            created_at=NOW,
            updated_at=NOW,
        )


class FakeMailer:
    def __init__(self, *, sent: bool = True) -> None:
        self.sent = sent
        self.calls: list[tuple[str, str, str, str]] = []

    def send_client_credentials(
        self,
        *,
        email: str,
        full_name: str,
        username: str,
        password: str,
    ) -> CredentialDeliveryResult:
        self.calls.append((email, full_name, username, password))
        return CredentialDeliveryResult(
            sent=self.sent,
            detail=(
                "SPINA account credentials were sent by email."
                if self.sent
                else "SPINA could not send the credential email."
            ),
        )


def _client_with_fakes(*, mail_sent: bool = True):
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    admin = FakeAuthAdmin()
    management = FakeManagementRepository()
    mailer = FakeMailer(sent=mail_sent)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_auth_client_dependency] = lambda: auth
    app.dependency_overrides[management_account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_auth_admin_dependency] = lambda: admin
    app.dependency_overrides[management_repository_dependency] = lambda: management
    mailer_dependency = getattr(
        management_api_module,
        "management_credential_mailer_dependency",
        None,
    )
    if mailer_dependency is not None:
        app.dependency_overrides[mailer_dependency] = lambda: mailer
    return TestClient(app), auth, accounts, admin, management, mailer


def _management_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": DEVICE_ID,
    }


def test_public_client_self_registration_is_disabled_without_side_effects() -> None:
    client, auth, accounts, _, _, _ = _client_with_fakes()

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
    client, auth, accounts, _, _, _ = _client_with_fakes()

    response = client.post("/api/mobile/v1/auth/register", json={})

    assert response.status_code == 410
    assert "created by SPINA" in response.json()["detail"]
    assert auth.sign_up_calls == 0
    assert accounts.public_profile_writes == 0


def test_management_creates_and_links_client_with_server_generated_credentials() -> None:
    client, _, _, admin, management, mailer = _client_with_fakes()

    response = client.post(
        "/api/v1/management/client-accounts",
        headers=_management_headers(),
        json={"client_id": str(CLIENT_ID), "email": "client@example.com"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    credentials = data["credentials"]
    assert credentials["username"] == "spina.c.001"
    assert len(credentials["password"]) == 16
    assert data["account"]["roles"] == ["client"]
    assert data["account"]["status"] == "active"
    assert data["delivery"]["sent"] is True
    assert admin.created == (
        "client@example.com",
        credentials["password"],
        True,
    )
    assert management.created_client == (
        ACTOR_USER_ID,
        TARGET_AUTH_ID,
        "spina.c.001",
        "client@example.com",
        CLIENT_ID,
    )
    assert mailer.calls == [
        (
            "client@example.com",
            "Maria Santos",
            "spina.c.001",
            credentials["password"],
        )
    ]


def test_client_account_creation_rejects_caller_supplied_username_or_password() -> None:
    client, _, _, admin, management, _ = _client_with_fakes()

    response = client.post(
        "/api/v1/management/client-accounts",
        headers=_management_headers(),
        json={
            "client_id": str(CLIENT_ID),
            "email": "client@example.com",
            "username": "caller.chosen",
            "password": "caller-chosen-password",
        },
    )

    assert response.status_code == 422
    assert admin.created is None
    assert management.created_client is None


def test_client_account_creation_requires_management_role_and_account_manage() -> None:
    client, _, accounts, admin, management, _ = _client_with_fakes()
    accounts.context = _actor_context(
        role="management",
        permissions=("management.dashboard.view",),
    )

    response = client.post(
        "/api/v1/management/client-accounts",
        headers=_management_headers(),
        json={"client_id": str(CLIENT_ID), "email": "client@example.com"},
    )

    assert response.status_code == 403
    assert admin.created is None
    assert management.created_client is None

    accounts.context = _actor_context(role="employee", permissions=("account.manage",))
    response = client.post(
        "/api/v1/management/client-accounts",
        headers=_management_headers(),
        json={"client_id": str(CLIENT_ID), "email": "client@example.com"},
    )

    assert response.status_code == 403
    assert admin.created is None
    assert management.created_client is None


def test_borrower_precheck_failure_happens_before_supabase_user_creation() -> None:
    client, _, _, admin, management, _ = _client_with_fakes()
    management.next_username_error = AccountConflict("Borrower record is already linked.")

    response = client.post(
        "/api/v1/management/client-accounts",
        headers=_management_headers(),
        json={"client_id": str(CLIENT_ID), "email": "client@example.com"},
    )

    assert response.status_code == 409
    assert admin.created is None
    assert management.created_client is None


def test_local_link_failure_compensates_new_supabase_user() -> None:
    client, _, _, admin, management, _ = _client_with_fakes()
    management.create_error = AccountConflict("Borrower record is already linked.")

    response = client.post(
        "/api/v1/management/client-accounts",
        headers=_management_headers(),
        json={"client_id": str(CLIENT_ID), "email": "client@example.com"},
    )

    assert response.status_code == 409
    assert admin.created is not None
    assert admin.deleted_user == TARGET_AUTH_ID


def test_email_failure_does_not_roll_back_valid_client_account_or_hide_one_time_credentials() -> None:
    client, _, _, admin, management, mailer = _client_with_fakes(mail_sent=False)

    response = client.post(
        "/api/v1/management/client-accounts",
        headers=_management_headers(),
        json={"client_id": str(CLIENT_ID), "email": "client@example.com"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["delivery"]["sent"] is False
    assert data["credentials"]["username"] == "spina.c.001"
    assert data["credentials"]["password"] == admin.created[1]
    assert management.created_client is not None
    assert admin.deleted_user is None
    assert mailer.calls
