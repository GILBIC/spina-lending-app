from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.client_loan_api import client_loan_repository_dependency
from gilbic_backend.client_loan_repository import ClientLoanPortfolio, ClientLoanRecord
from gilbic_backend.client_payment_api import client_payment_repository_dependency
from gilbic_backend.client_payment_repository import ClientPaymentRecord, ClientPaymentTimeline
from gilbic_backend.main import create_app

AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
TX_ID = UUID("55555555-5555-4555-8555-555555555555")


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
    def __init__(self, role: str = "client") -> None:
        self.role = role

    def get_context_for_device(self, *, auth_user_id: UUID, device_identifier: str | None) -> AccountContext:
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


class FakeLoans:
    def list_for_user(self, *, user_id: UUID) -> ClientLoanPortfolio:
        assert user_id == CLIENT_USER_ID
        return ClientLoanPortfolio(
            client_id=CLIENT_ID,
            client_code="TEST-REG-001",
            client_name="TEST CLIENT REGULAR",
            area="Cardona",
            client_status="active",
            loans=(
                ClientLoanRecord(
                    loan_id=LOAN_ID,
                    loan_number="TEST-REG-20260802",
                    loan_type_code="regular",
                    loan_type_name="Regular",
                    principal=Decimal("5000.00"),
                    daily_amount=Decimal("200.00"),
                    interest_rate=Decimal("0.00"),
                    date_released=date(2026, 8, 2),
                    due_date=date(2026, 11, 30),
                    status="active",
                    remaining_balance=Decimal("4900.00"),
                    pass_count=0,
                    last_payment_date=date(2026, 8, 6),
                    advance_until=None,
                    state_version=2,
                    payment_count=2,
                ),
            ),
        )


class FakePayments:
    def list_for_user(self, *, user_id: UUID) -> ClientPaymentTimeline:
        assert user_id == CLIENT_USER_ID
        return ClientPaymentTimeline(
            client_id=CLIENT_ID,
            client_code="TEST-REG-001",
            client_name="TEST CLIENT REGULAR",
            payments=(
                ClientPaymentRecord(
                    transaction_id=TX_ID,
                    receipt_number="GBC-20260806-00000010",
                    loan_id=LOAN_ID,
                    loan_number="TEST-REG-20260802",
                    loan_type_name="Regular",
                    collector_name="Test Collector",
                    collection_date=date(2026, 8, 6),
                    recorded_at=datetime(2026, 8, 6, 1, 0, tzinfo=timezone.utc),
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
                    remittance_number=None,
                    remittance_status=None,
                    remittance_submitted_at=None,
                    remittance_received_at=None,
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer client-token", "X-Device-Id": "client-device"}


def client_with_fakes(*, role: str = "client") -> TestClient:
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(role)
    app.dependency_overrides[client_loan_repository_dependency] = lambda: FakeLoans()
    app.dependency_overrides[client_payment_repository_dependency] = lambda: FakePayments()
    return TestClient(app)


def test_linked_client_can_view_authoritative_statement() -> None:
    response = client_with_fakes().get("/api/mobile/v1/client/statement", headers=headers())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["client"] == {
        "client_id": str(CLIENT_ID),
        "client_code": "TEST-REG-001",
        "client_name": "TEST CLIENT REGULAR",
        "area": "Cardona",
        "status": "active",
    }
    assert data["loans"][0]["principal"] == "5000.00"
    assert data["loans"][0]["remaining_balance"] == "4900.00"
    assert data["loans"][0]["daily_amount"] == "200.00"
    assert data["payments"][0]["amount"] == "50.00"
    assert data["payments"][0]["official_balance"] == "4900.00"
    assert data["payments"][0]["receipt_number"] == "GBC-20260806-00000010"
    assert "paid_amount" not in data["loans"][0]
    assert "progress" not in data["loans"][0]
    assert "past_due_amount" not in data["loans"][0]
    assert "next_payment_date" not in data["loans"][0]
    assert "download_url" not in data


def test_non_client_role_cannot_view_statement() -> None:
    response = client_with_fakes(role="management").get(
        "/api/v1/client/statement", headers=headers()
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "client_role_required"
