from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.client_account_api import (
    client_account_repository_dependency,
    client_credential_mailer_dependency,
)
from gilbic_backend.credential_mailer import CredentialDeliveryResult
from gilbic_backend.main import create_app
from gilbic_backend.management_api import (
    management_account_repository_dependency,
    management_auth_admin_dependency,
    management_auth_client_dependency,
)
from gilbic_backend.management_repository import AccountAdminRecord


ACTOR_AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TARGET_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
TARGET_AUTH_ID = UUID("44444444-4444-4444-8444-444444444444")
DEVICE_ID = "priority3-audit-guard-device"
NOW = datetime(2026, 9, 6, 2, tzinfo=UTC)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "access-token"
        return AuthSession(
            auth_user_id=ACTOR_AUTH_ID,
            email="employee@example.com",
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
            username="employee.one",
            email="employee@example.com",
            full_name="Employee One",
            status="active",
            roles=("employee",),
            permissions=("client.credential.manage",),
            device_registered=True,
        )


class FakeAuthAdmin:
    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.updated = False

    def update_user_password(self, *, auth_user_id: UUID, password: str) -> None:
        assert auth_user_id == TARGET_AUTH_ID
        assert password
        self.order.append("auth_update")
        self.updated = True


class FakeRepository:
    def __init__(self, order: list[str], *, fail_requested_audit: bool = False) -> None:
        self.order = order
        self.fail_requested_audit = fail_requested_audit

    def get_account(self, *, target_user_id: UUID) -> AccountAdminRecord:
        assert target_user_id == TARGET_USER_ID
        return AccountAdminRecord(
            id=TARGET_USER_ID,
            auth_user_id=TARGET_AUTH_ID,
            username="spina.c.001",
            email="client@example.com",
            full_name="Maria Santos",
            status="active",
            roles=("client",),
            device_count=0,
            created_at=NOW,
            updated_at=NOW,
        )

    def record_password_reset_requested(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
    ) -> None:
        assert actor_user_id == ACTOR_USER_ID
        assert target_user_id == TARGET_USER_ID
        self.order.append("audit_requested")
        if self.fail_requested_audit:
            raise RuntimeError("audit unavailable")

    def record_password_reset(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        delivery_sent: bool,
    ) -> None:
        assert actor_user_id == ACTOR_USER_ID
        assert target_user_id == TARGET_USER_ID
        assert delivery_sent is True
        self.order.append("audit_completed")


class FakeMailer:
    def __init__(self, order: list[str]) -> None:
        self.order = order

    def send_client_credentials(
        self,
        *,
        email: str,
        full_name: str,
        username: str,
        password: str,
    ) -> CredentialDeliveryResult:
        assert email == "client@example.com"
        assert full_name == "Maria Santos"
        assert username == "spina.c.001"
        assert password
        self.order.append("mail")
        return CredentialDeliveryResult(sent=True, detail="sent")


def _client(*, fail_requested_audit: bool = False):
    order: list[str] = []
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    admin = FakeAuthAdmin(order)
    repository = FakeRepository(order, fail_requested_audit=fail_requested_audit)
    mailer = FakeMailer(order)
    app = create_app()
    app.dependency_overrides[management_auth_client_dependency] = lambda: auth
    app.dependency_overrides[management_account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_auth_admin_dependency] = lambda: admin
    app.dependency_overrides[client_account_repository_dependency] = lambda: repository
    app.dependency_overrides[client_credential_mailer_dependency] = lambda: mailer
    return TestClient(app), admin, order


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer access-token",
        "X-Device-Id": DEVICE_ID,
    }


def test_audit_intent_failure_blocks_password_change() -> None:
    client, admin, order = _client(fail_requested_audit=True)

    response = client.post(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/password/reset",
        headers=_headers(),
    )

    assert response.status_code == 503
    assert admin.updated is False
    assert order == ["audit_requested"]


def test_successful_reset_audits_before_and_after_external_change() -> None:
    client, admin, order = _client()

    response = client.post(
        f"/api/v1/management/accounts/{TARGET_USER_ID}/password/reset",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert admin.updated is True
    assert order == ["audit_requested", "auth_update", "mail", "audit_completed"]
