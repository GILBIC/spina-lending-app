from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.renewal_api import renewal_repository_dependency
from gilbic_backend.renewal_repository import (
    ClientRenewalPortal,
    RenewalConflict,
    RenewalLoanOption,
    RenewalRequestRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
MANAGEMENT_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
REQUEST_ID = UUID("66666666-6666-4666-8666-666666666666")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="user@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, role: str) -> None:
        self.role = role

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "test-device"
        is_management = self.role == "management"
        return AccountContext(
            user_id=MANAGEMENT_USER_ID if is_management else CLIENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="manager" if is_management else "testregular1",
            email="user@example.com",
            full_name="Management" if is_management else "TEST CLIENT REGULAR",
            status="active",
            roles=(self.role,),
            permissions=("renewal.manage",) if is_management else (),
            device_registered=True,
        )


def sample_request(*, status: str = "pending") -> RenewalRequestRecord:
    reviewed = status in {"approved", "rejected"}
    return RenewalRequestRecord(
        request_id=REQUEST_ID,
        client_id=CLIENT_ID,
        client_code="TEST-REG-001",
        client_name="TEST CLIENT REGULAR",
        loan_id=LOAN_ID,
        loan_number="TEST-REG-20260802",
        loan_type_name="Regular",
        current_principal=Decimal("5000.00"),
        remaining_balance=Decimal("4900.00"),
        requested_amount=Decimal("6000.00"),
        client_message="Requesting a higher renewal amount",
        status=status,
        submitted_at=datetime(2026, 8, 6, 12, 45, tzinfo=timezone.utc),
        reviewed_at=(
            datetime(2026, 8, 6, 13, 0, tzinfo=timezone.utc)
            if reviewed
            else None
        ),
        reviewed_by_name="Management" if reviewed else None,
        review_note="Approved for office processing" if reviewed else "",
        cancelled_at=None,
    )


class FakeRenewals:
    def __init__(self) -> None:
        self.portal_user_id: UUID | None = None
        self.submitted: tuple[UUID, UUID, Decimal, str] | None = None
        self.cancelled: tuple[UUID, UUID] | None = None
        self.management_status: str | None = None
        self.reviewed: tuple[UUID, UUID, str, str] | None = None
        self.error: Exception | None = None

    def portal_for_user(self, *, user_id: UUID) -> ClientRenewalPortal:
        self.portal_user_id = user_id
        if self.error:
            raise self.error
        return ClientRenewalPortal(
            client_id=CLIENT_ID,
            client_code="TEST-REG-001",
            client_name="TEST CLIENT REGULAR",
            loans=(
                RenewalLoanOption(
                    loan_id=LOAN_ID,
                    loan_number="TEST-REG-20260802",
                    loan_type_name="Regular",
                    calculation_mode="fixed_daily",
                    principal=Decimal("5000.00"),
                    contractual_total=Decimal("6000.00"),
                    remaining_balance=Decimal("4900.00"),
                    paid_amount=Decimal("100.00"),
                    daily_amount=Decimal("50.00"),
                    date_released=date(2026, 8, 1),
                    due_date=date(2026, 11, 29),
                    status="active",
                    eligible=True,
                    eligibility_message=(
                        "Management will review this request before office processing."
                    ),
                    pending_request_id=None,
                ),
            ),
            requests=(sample_request(),),
        )

    def submit_for_user(
        self,
        *,
        user_id: UUID,
        loan_id: UUID,
        requested_amount: Decimal,
        client_message: str,
    ) -> RenewalRequestRecord:
        if self.error:
            raise self.error
        self.submitted = (user_id, loan_id, requested_amount, client_message)
        return sample_request()

    def cancel_for_user(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
    ) -> RenewalRequestRecord:
        self.cancelled = (user_id, request_id)
        return sample_request(status="cancelled")

    def list_for_management(self, *, status: str, limit: int, offset: int):
        assert limit == 100
        assert offset == 0
        self.management_status = status
        return (sample_request(),)

    def review(
        self,
        *,
        actor_user_id: UUID,
        request_id: UUID,
        decision: str,
        review_note: str,
    ) -> RenewalRequestRecord:
        self.reviewed = (actor_user_id, request_id, decision, review_note)
        return sample_request(status=decision)


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(*, role: str = "client") -> tuple[TestClient, FakeRenewals]:
    renewals = FakeRenewals()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role
    )
    app.dependency_overrides[renewal_repository_dependency] = lambda: renewals
    return TestClient(app), renewals


def test_client_can_view_renewal_portal() -> None:
    client, renewals = client_with_fakes()

    response = client.get("/api/mobile/v1/client/renewals", headers=headers())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["client"]["client_code"] == "TEST-REG-001"
    assert data["loans"][0]["eligible"] is True
    assert data["loans"][0]["paid_percent"] == "1.7"
    assert data["requests"][0]["status"] == "pending"
    assert renewals.portal_user_id == CLIENT_USER_ID


def test_client_can_submit_renewal_request() -> None:
    client, renewals = client_with_fakes()

    response = client.post(
        "/api/mobile/v1/client/renewals",
        headers=headers(),
        json={
            "loan_id": str(LOAN_ID),
            "requested_amount": "6,000",
            "message": "  Requesting   a higher renewal amount  ",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["request"]["requested_amount"] == "6000.00"
    assert renewals.submitted == (
        CLIENT_USER_ID,
        LOAN_ID,
        Decimal("6000.00"),
        "Requesting a higher renewal amount",
    )


def test_duplicate_pending_renewal_returns_conflict() -> None:
    client, renewals = client_with_fakes()
    renewals.error = RenewalConflict(
        "A renewal request for this loan is already pending."
    )

    response = client.post(
        "/api/v1/client/renewals",
        headers=headers(),
        json={
            "loan_id": str(LOAN_ID),
            "requested_amount": "5000",
            "message": "",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "renewal_conflict"


def test_management_can_list_and_approve_pending_requests() -> None:
    client, renewals = client_with_fakes(role="management")

    list_response = client.get(
        "/api/mobile/v1/management/renewals?status=pending",
        headers=headers(),
    )
    review_response = client.post(
        f"/api/mobile/v1/management/renewals/{REQUEST_ID}/review",
        headers=headers(),
        json={
            "decision": "approved",
            "review_note": "Approved for office processing",
        },
    )

    assert list_response.status_code == 200
    assert len(list_response.json()["data"]["requests"]) == 1
    assert renewals.management_status == "pending"
    assert review_response.status_code == 200
    assert review_response.json()["data"]["request"]["status"] == "approved"
    assert renewals.reviewed == (
        MANAGEMENT_USER_ID,
        REQUEST_ID,
        "approved",
        "Approved for office processing",
    )


def test_rejection_requires_reason() -> None:
    client, _ = client_with_fakes(role="management")

    response = client.post(
        f"/api/v1/management/renewals/{REQUEST_ID}/review",
        headers=headers(),
        json={"decision": "rejected", "review_note": ""},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == (
        "renewal_review_note_required"
    )


def test_non_client_cannot_submit_client_renewal() -> None:
    client, _ = client_with_fakes(role="management")

    response = client.post(
        "/api/v1/client/renewals",
        headers=headers(),
        json={
            "loan_id": str(LOAN_ID),
            "requested_amount": "5000",
            "message": "",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "client_role_required"
