from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import gilbic_backend.management_api as management_api_module
import pytest
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
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


ACTOR_AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TARGET_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
TARGET_AUTH_ID = UUID("44444444-4444-4444-8444-444444444444")
DEVICE_ID = "priority3-password-device"
NOW = datetime(2026, 9, 5, 13, 40, tzinfo=UTC)


def _actor_context(
    role: str,
    *,
    permissions: tuple[str, ...] | None = None,
) -> AccountContext:
    defaults = {
        "client": ("loan.self.view",),
        "collector": ("route.view",),
        "employee": ("employee.portal.view", "client.credential.manage"),
        "management": ("management.dashboard.view", "account.manage", "client.credential.manage"),
    }
    return AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=ACTOR_AUTH_ID,
        username=f"{role}.one",
        email=f"{role}@example.com",
        full_name=f"{role.title()} One",
        status="active",
        roles=(role,),
        permissions=permissions if permissions is not None else defaults[role],
        device_registered=True,
    )


def _target_record(role: str) -> AccountAdminRecord:
    return AccountAdminRecord(
        id=TARGET_USER_ID,
        auth_user_id=TARGET_AUTH_ID,
        username=f"target.{role}",
        email=f"target-{role}@example.com",
        full_name=f"Target {role.title()}",
        status="active",
        roles=(role,),
        device_count=0,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeAuthClient:
    def __init__(self) -> None:
        self.updated_password: tuple[str, str] | None = None

    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "access-token"
        return AuthSession(
            auth_user_id=ACTOR_AUTH_ID,
            email="actor@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )

    def update_password(self, *, access_token: str, password: str) -> None:
        self.updated_password = (access_token, password)


class FakeAccounts:
    def __init__(self, actor: AccountContext) -> None:
        self.context = actor

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == ACTOR_AUTH_ID
        assert device_identifier == DEVICE_ID
        return self.context


class FakeAuthAdmin:
    def __init__(self) -> None:
        self.updated: tuple[UUID, str] | None = None

    def update_user_password(self, *, auth_user_id: UUID, password: str) -> None:
        self.updated = (auth_user_id, password)


class FakeManagementRepository:
    def __init__(self, target_role: str) -> None:
        self.target = _target_record(target_role)
        self.audit: tuple[UUID, UUID, bool] | None = None

    def get_account(self, *, target_user_id: UUID) -> AccountAdminRecord:
        assert target_user_id == TARGET_USER_ID
        return self.target

    def record_password_reset(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        delivery_sent: bool,
    ) -> None:
        self.audit = (actor_user_id, target_user_id, delivery_sent)


class FakeMailer:
    def __init__(self) -> None:
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
        return CredentialDeliveryResult(sent=True, detail="sent")


def _client_for(
    *,
    actor_role: str,
    target_role: str = "client",
    permissions: tuple[str, ...] | None = None,
):
    auth = FakeAuthClient()
    accounts = FakeAccounts(_actor_context(actor_role, permissions=permissions))
    admin = FakeAuthAdmin()
    management = FakeManagementRepository(target_role)
    mailer = FakeMailer()
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
    return TestClient(app), auth, admin, management, mailer


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer access-token",
        "X-Device-Id": DEVICE_ID,
    }


def test_client_cannot_change_own_password() -> None:
    client, auth, _, _, _ = _client_for(actor_role="client")

    response = client.patch(
        "/api/v1/auth/password",
        headers=_headers(),
        json={"password": "user-chosen-password-2"},
    )

    assert response.status_code == 403
    assert auth.updated_password is None


@pytest.mark.parametrize("role", ["collector", "employee", "management"])
def test_non_client_staff_can_change_only_their_own_password(role: str) -> None:
    client, auth, _, _, _ = _client_for(actor_role=role)

    response = client.patch(
        "/api/v1/auth/password",
        headers=_headers(),
        json={"password": "user-chosen-password-2"},
    )

    assert response.status_code == 200
    assert auth.updated_password == ("access-token", "user-chosen-password-2")


def test_employee_can_generate_new_password_for_client_account_only() -> None:
    client, _, admin, management, mailer = _client_for(actor_role="employee", target_role="client")

    response = client.post(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/password/reset",
        headers=_headers(),
    )

    assert response.status_code == 200
    password = response.json()["data"]["credentials"]["password"]
    assert len(password) == 16
    assert admin.updated == (TARGET_AUTH_ID, password)
    assert management.audit == (ACTOR_USER_ID, TARGET_USER_ID, True)
    assert mailer.calls[0][3] == password

    client, _, admin, management, _ = _client_for(actor_role="employee", target_role="collector")
    response = client.post(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/password/reset",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert admin.updated is None
    assert management.audit is None


def test_collector_cannot_reset_another_users_password() -> None:
    client, _, admin, management, _ = _client_for(actor_role="collector", target_role="client")

    response = client.post(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/password/reset",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert admin.updated is None
    assert management.audit is None


@pytest.mark.parametrize("target_role", ["client", "collector", "employee", "management"])
def test_management_can_generate_new_password_for_any_user(target_role: str) -> None:
    client, _, admin, management, mailer = _client_for(
        actor_role="management",
        target_role=target_role,
    )

    response = client.post(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/password/reset",
        headers=_headers(),
    )

    assert response.status_code == 200
    password = response.json()["data"]["credentials"]["password"]
    assert admin.updated == (TARGET_AUTH_ID, password)
    assert management.audit is not None
    if target_role == "client":
        assert mailer.calls and mailer.calls[0][3] == password
    else:
        assert mailer.calls == []
