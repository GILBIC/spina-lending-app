from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.client_payment_api import client_payment_repository_dependency
from gilbic_backend.client_payment_repository import (
    ClientPaymentBorrowerNotLinked,
    ClientPaymentRecord,
    ClientPaymentTimeline,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
POSTED_TRANSACTION_ID = UUID("55555555-5555-4555-8555-555555555555")
VOIDED_TRANSACTION_ID = UUID("66666666-6666-4666-8666-666666666666")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="client@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, role: str = "client") -> None:
        self.role = role

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "client-device"
        return AccountContext(
            user_id=CLIENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="testregular1",
            email="client@example.com",
            full_name="TEST CLIENT REGULAR",
            status="active",
            roles=(self.role,),
            permissions=(),
            device_registered=True,
        )


class FakePayments:
    def __init__(self) -> None:
        self.user_id: UUID | None = None
        self.error: Exception | None = None

    def list_for_user(self, *, user_id: UUID) -> ClientPaymentTimeline:
        self.user_id = user_id
        if self.error is not None:
            raise self.error
        return ClientPaymentTimeline(
            client_id=CLIENT_ID,
            client_code="TEST-REG-001",
            client_name="TEST CLIENT REGULAR",
            payments=(
                ClientPaymentRecord(
                    transaction_id=POSTED_TRANSACTION_ID,
                    receipt_number="GBC-20260806-00000010",
                    loan_id=LOAN_ID,
                    loan_number="TEST-REG-20260802",
                    loan_type_name="Regular",
                    collector_name="Test Collector",
                    collection_date=date(2026, 8, 6),
                    recorded_at=datetime(2026, 8, 5, 23, 3, tzinfo=timezone.utc),
                    entry_type="payment",
                    amount=Decimal("50.00"),
                    covered_dates=(date(2026, 8, 6),),
                    previous_balance=Decimal("4950.00"),
                    official_balance=Decimal("4900.00"),
                    note=None,
                    collection_origin="assigned_route",
                    is_voided=False,
                    voided_at=None,
                    void_reason=None,
                    edit_version=0,
                    remittance_number="REM-20260806-00000005",
                    remittance_status="received",
                    remittance_submitted_at=datetime(
                        2026, 8, 6, 0, 0, tzinfo=timezone.utc
                    ),
                    remittance_received_at=datetime(
                        2026, 8, 6, 0, 5, tzinfo=timezone.utc
                    ),
                ),
                ClientPaymentRecord(
                    transaction_id=VOIDED_TRANSACTION_ID,
                    receipt_number="GBC-20260805-00000008",
                    loan_id=LOAN_ID,
                    loan_number="TEST-REG-20260802",
                    loan_type_name="Regular",
                    collector_name="Test Collector",
                    collection_date=date(2026, 8, 5),
                    recorded_at=datetime(2026, 8, 5, 8, 30, tzinfo=timezone.utc),
                    entry_type="covered_payment",
                    amount=Decimal("50.00"),
                    covered_dates=(date(2026, 8, 6),),
                    previous_balance=Decimal("4950.00"),
                    official_balance=Decimal("4900.00"),
                    note=None,
                    collection_origin="assigned_route",
                    is_voided=True,
                    voided_at=datetime(2026, 8, 5, 9, 1, tzinfo=timezone.utc),
                    void_reason="Payment posted to the wrong borrower",
                    edit_version=0,
                    remittance_number=None,
                    remittance_status=None,
                    remittance_submitted_at=None,
                    remittance_received_at=None,
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer client-token",
        "X-Device-Id": "client-device",
    }


def client_with_fakes(*, role: str = "client") -> tuple[TestClient, FakePayments]:
    payments = FakePayments()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role
    )
    app.dependency_overrides[client_payment_repository_dependency] = lambda: payments
    return TestClient(app), payments


def test_linked_client_can_view_payment_timeline() -> None:
    client, payments = client_with_fakes()

    response = client.get("/api/mobile/v1/client/payments", headers=headers())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["client"]["client_code"] == "TEST-REG-001"
    assert len(data["payments"]) == 2
    assert data["payments"][0]["receipt_number"] == "GBC-20260806-00000010"
    assert data["payments"][0]["status"] == "accepted"
    assert data["payments"][0]["official_balance"] == "4900.00"
    assert data["payments"][1]["status"] == "voided"
    assert data["payments"][1]["covered_dates"] == ["2026-08-06"]
    assert data["payment_proof"]["upload_available"] is False
    assert payments.user_id == CLIENT_USER_ID


def test_non_client_role_cannot_open_client_payments() -> None:
    client, _ = client_with_fakes(role="management")

    response = client.get("/api/v1/client/payments", headers=headers())

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "client_role_required"


def test_unlinked_client_receives_clear_payment_error() -> None:
    client, payments = client_with_fakes()
    payments.error = ClientPaymentBorrowerNotLinked(
        "This client account is not linked to a borrower record."
    )

    response = client.get("/api/v1/client/payments", headers=headers())

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == (
        "client_payment_borrower_not_linked"
    )
