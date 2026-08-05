from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.client_loan_api import client_loan_repository_dependency
from gilbic_backend.client_loan_repository import (
    ClientBorrowerNotLinked,
    ClientLoanPortfolio,
    ClientLoanRecord,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
REGULAR_LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
SEVEN_BY_SEVEN_LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")


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


class FakeLoans:
    def __init__(self) -> None:
        self.user_id: UUID | None = None
        self.error: Exception | None = None

    def list_for_user(self, *, user_id: UUID) -> ClientLoanPortfolio:
        self.user_id = user_id
        if self.error is not None:
            raise self.error
        return ClientLoanPortfolio(
            client_id=CLIENT_ID,
            client_code="TEST-REG-001",
            client_name="TEST CLIENT REGULAR",
            area="TEST AREA",
            client_status="active",
            loans=(
                ClientLoanRecord(
                    loan_id=REGULAR_LOAN_ID,
                    loan_number="TEST-REG-20260802",
                    loan_type_code="regular_mobile_test",
                    loan_type_name="Regular",
                    principal=Decimal("5000.00"),
                    daily_amount=Decimal("50.00"),
                    interest_rate=Decimal("20.0000"),
                    date_released=date(2026, 8, 1),
                    due_date=date(2026, 11, 29),
                    status="active",
                    remaining_balance=Decimal("4950.00"),
                    pass_count=0,
                    last_payment_date=date(2026, 8, 2),
                    advance_until=date(2026, 8, 5),
                    state_version=3,
                    payment_count=1,
                ),
                ClientLoanRecord(
                    loan_id=SEVEN_BY_SEVEN_LOAN_ID,
                    loan_number="TEST-REG-7X7-20260802",
                    loan_type_code="seven_by_seven_mobile_test",
                    loan_type_name="7x7",
                    principal=Decimal("3000.00"),
                    daily_amount=Decimal("21.00"),
                    interest_rate=None,
                    date_released=date(2026, 8, 2),
                    due_date=date(2026, 11, 30),
                    status="active",
                    remaining_balance=Decimal("3000.00"),
                    pass_count=0,
                    last_payment_date=None,
                    advance_until=None,
                    state_version=0,
                    payment_count=0,
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer client-token",
        "X-Device-Id": "client-device",
    }


def client_with_fakes(*, role: str = "client") -> tuple[TestClient, FakeLoans]:
    loans = FakeLoans()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role
    )
    app.dependency_overrides[client_loan_repository_dependency] = lambda: loans
    return TestClient(app), loans


def test_linked_client_can_view_own_loans() -> None:
    client, loans = client_with_fakes()

    response = client.get("/api/mobile/v1/client/loans", headers=headers())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["client"]["client_code"] == "TEST-REG-001"
    assert len(data["loans"]) == 2
    assert data["loans"][0]["remaining_balance"] == "4950.00"
    assert data["loans"][0]["paid_amount"] == "50.00"
    assert data["loans"][1]["loan_type_name"] == "7x7"
    assert loans.user_id == CLIENT_USER_ID


def test_non_client_role_cannot_open_client_loans() -> None:
    client, _ = client_with_fakes(role="management")

    response = client.get("/api/v1/client/loans", headers=headers())

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "client_role_required"


def test_unlinked_client_receives_clear_error() -> None:
    client, loans = client_with_fakes()
    loans.error = ClientBorrowerNotLinked(
        "This client account is not linked to a borrower record."
    )

    response = client.get("/api/v1/client/loans", headers=headers())

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "client_borrower_not_linked"
