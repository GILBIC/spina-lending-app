from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.refund_due_api import refund_due_repository_dependency
from gilbic_backend.refund_due_repository import (
    RefundDueApprovalRecord,
    RefundDueReleaseRecord,
)

AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
COLLECTOR_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
ADJUSTMENT_ID = UUID("66666666-6666-4666-8666-666666666666")
APPROVAL_ID = UUID("77777777-7777-4777-8777-777777777777")
RELEASE_ID = UUID("88888888-8888-4888-8888-888888888888")
APPROVAL_KEY = UUID("99999999-9999-4999-8999-999999999999")
RELEASE_KEY = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
APPROVED_AT = datetime(2026, 8, 28, 8, tzinfo=timezone.utc)
RELEASED_AT = datetime(2026, 8, 28, 9, tzinfo=timezone.utc)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "session-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="user@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(
        self,
        *,
        user_id: UUID,
        roles: tuple[str, ...],
        permissions: tuple[str, ...],
    ) -> None:
        self.user_id = user_id
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
            user_id=self.user_id,
            auth_user_id=AUTH_USER_ID,
            username="test.user",
            email="user@example.com",
            full_name="Test User",
            status="active",
            roles=self.roles,
            permissions=self.permissions,
            device_registered=True,
        )


class FakeRefundDues:
    def __init__(self) -> None:
        self.approve_request: dict[str, object] | None = None
        self.release_request: dict[str, object] | None = None

    def approve(self, **kwargs) -> RefundDueApprovalRecord:
        self.approve_request = kwargs
        return RefundDueApprovalRecord(
            approval_id=APPROVAL_ID,
            idempotency_key=APPROVAL_KEY,
            adjustment_id=ADJUSTMENT_ID,
            loan_id=LOAN_ID,
            client_id=CLIENT_ID,
            approved_amount=Decimal("200.00"),
            released_amount=Decimal("0.00"),
            remaining_approved_amount=Decimal("200.00"),
            approved_by_user_id=MANAGEMENT_USER_ID,
            reason="Client requested cash return",
            authority_reference="MGT-2026-0088",
            approved_at=APPROVED_AT,
        )

    def release(self, **kwargs) -> RefundDueReleaseRecord:
        self.release_request = kwargs
        return RefundDueReleaseRecord(
            release_id=RELEASE_ID,
            idempotency_key=RELEASE_KEY,
            approval_id=APPROVAL_ID,
            adjustment_id=ADJUSTMENT_ID,
            loan_id=LOAN_ID,
            client_id=CLIENT_ID,
            assigned_collector_user_id=COLLECTOR_USER_ID,
            released_amount=Decimal("200.00"),
            approval_released_amount=Decimal("200.00"),
            approval_remaining_amount=Decimal("0.00"),
            adjustment_outstanding_refund_due=Decimal("0.00"),
            released_by_user_id=COLLECTOR_USER_ID,
            released_at=RELEASED_AT,
            evidence_reference="SIGNED-RF-2026-0042",
            evidence_digest="a" * 64,
        )


def _client(
    *,
    user_id: UUID,
    roles: tuple[str, ...],
    permissions: tuple[str, ...],
) -> tuple[TestClient, FakeRefundDues]:
    refunds = FakeRefundDues()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        user_id=user_id,
        roles=roles,
        permissions=permissions,
    )
    app.dependency_overrides[refund_due_repository_dependency] = lambda: refunds
    return TestClient(app), refunds


def _headers(idempotency_key: UUID) -> dict[str, str]:
    return {
        "Authorization": "Bearer session-token",
        "X-Device-Id": "device-one",
        "Idempotency-Key": str(idempotency_key),
    }


def test_management_can_approve_refund_due_without_release_fields() -> None:
    client, refunds = _client(
        user_id=MANAGEMENT_USER_ID,
        roles=("management",),
        permissions=("lending.refund_due.approve",),
    )

    response = client.post(
        f"/api/v1/management/refund-dues/{ADJUSTMENT_ID}/approve",
        headers=_headers(APPROVAL_KEY),
        json={
            "approved_amount": "200.00",
            "reason": "Client requested cash return",
            "authority_reference": "MGT-2026-0088",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["approval_id"] == str(APPROVAL_ID)
    assert data["approved_amount"] == "200.00"
    assert data["released_amount"] == "0.00"
    assert data["remaining_approved_amount"] == "200.00"
    assert refunds.approve_request == {
        "idempotency_key": APPROVAL_KEY,
        "actor_user_id": MANAGEMENT_USER_ID,
        "adjustment_id": ADJUSTMENT_ID,
        "approved_amount": Decimal("200.00"),
        "reason": "Client requested cash return",
        "authority_reference": "MGT-2026-0088",
    }


def test_assigned_collector_can_record_physical_release_evidence() -> None:
    client, refunds = _client(
        user_id=COLLECTOR_USER_ID,
        roles=("collector",),
        permissions=("lending.refund_due.release",),
    )

    response = client.post(
        f"/api/v1/collector/refund-due-approvals/{APPROVAL_ID}/release",
        headers=_headers(RELEASE_KEY),
        json={
            "released_amount": "200.00",
            "released_at": RELEASED_AT.isoformat(),
            "evidence_reference": "SIGNED-RF-2026-0042",
            "evidence_digest": "a" * 64,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["release_id"] == str(RELEASE_ID)
    assert data["released_amount"] == "200.00"
    assert data["approval_remaining_amount"] == "0.00"
    assert data["adjustment_outstanding_refund_due"] == "0.00"
    assert refunds.release_request == {
        "idempotency_key": RELEASE_KEY,
        "actor_user_id": COLLECTOR_USER_ID,
        "approval_id": APPROVAL_ID,
        "released_amount": Decimal("200.00"),
        "released_at": RELEASED_AT,
        "evidence_reference": "SIGNED-RF-2026-0042",
        "evidence_digest": "a" * 64,
    }


def test_approval_requires_management_permission() -> None:
    client, refunds = _client(
        user_id=COLLECTOR_USER_ID,
        roles=("collector",),
        permissions=("lending.refund_due.release",),
    )

    response = client.post(
        f"/api/v1/management/refund-dues/{ADJUSTMENT_ID}/approve",
        headers=_headers(APPROVAL_KEY),
        json={
            "approved_amount": "200.00",
            "reason": "Client requested cash return",
            "authority_reference": "MGT-2026-0088",
        },
    )

    assert response.status_code == 403
    assert refunds.approve_request is None


def test_release_rejects_non_sha256_evidence_digest() -> None:
    client, refunds = _client(
        user_id=COLLECTOR_USER_ID,
        roles=("collector",),
        permissions=("lending.refund_due.release",),
    )

    response = client.post(
        f"/api/v1/collector/refund-due-approvals/{APPROVAL_ID}/release",
        headers=_headers(RELEASE_KEY),
        json={
            "released_amount": "200.00",
            "released_at": RELEASED_AT.isoformat(),
            "evidence_reference": "SIGNED-RF-2026-0042",
            "evidence_digest": "not-a-digest",
        },
    )

    assert response.status_code == 422
    assert refunds.release_request is None
