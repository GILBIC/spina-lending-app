from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.management_loan_api import management_loan_repository_dependency
from gilbic_backend.management_loan_repository import (
    ManagementLoanPortfolio,
    ManagementLoanRecord,
    ManagementLoanSummary,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")


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
            username="manager" if is_management else "client",
            email="user@example.com",
            full_name="Management" if is_management else "Client",
            status="active",
            roles=(self.role,),
            permissions=(),
            device_registered=True,
        )


class FakeManagementLoans:
    def __init__(self) -> None:
        self.arguments: tuple[str, str, int, int] | None = None

    def list_portfolio(
        self,
        *,
        query: str,
        status: str,
        limit: int,
        offset: int,
    ) -> ManagementLoanPortfolio:
        self.arguments = (query, status, limit, offset)
        return ManagementLoanPortfolio(
            summary=ManagementLoanSummary(
                active_loan_count=2,
                active_client_count=1,
                active_principal_total=Decimal("8000.00"),
                active_remaining_total=Decimal("7900.00"),
                overdue_active_count=1,
                active_seven_by_seven_count=1,
                approved_renewal_count=1,
            ),
            loans=(
                ManagementLoanRecord(
                    loan_id=LOAN_ID,
                    loan_number="TEST-REG-20260802",
                    client_id=CLIENT_ID,
                    client_code="TEST-REG-001",
                    client_name="TEST CLIENT REGULAR",
                    client_area="GILBIC TEST AREA",
                    client_status="active",
                    loan_type_code="REG",
                    loan_type_name="Regular",
                    calculation_mode="fixed_daily",
                    principal=Decimal("5000.00"),
                    daily_amount=Decimal("50.00"),
                    interest_rate=Decimal("20.00"),
                    remaining_balance=Decimal("4900.00"),
                    date_released=date(2026, 8, 1),
                    due_date=date(2020, 1, 1),
                    loan_status="active",
                    last_payment_date=date(2026, 8, 6),
                    advance_until=date(2026, 8, 5),
                    pass_count=0,
                    payment_count=2,
                    state_version=3,
                    renewal_request_status="approved",
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(*, role: str = "management"):
    loans = FakeManagementLoans()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role
    )
    app.dependency_overrides[management_loan_repository_dependency] = lambda: loans
    return TestClient(app), loans


def test_management_can_view_searchable_loan_portfolio() -> None:
    client, loans = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/management/loans?q=TEST-REG&status=all&limit=50&offset=2",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["active_loan_count"] == 2
    assert data["summary"]["active_remaining_total"] == "7900.00"
    assert data["summary"]["approved_renewal_count"] == 1
    assert data["loans"][0]["client_code"] == "TEST-REG-001"
    assert data["loans"][0]["remaining_balance"] == "4900.00"
    assert data["loans"][0]["paid_percent"] == "2.0"
    assert data["loans"][0]["is_overdue"] is True
    assert data["loans"][0]["renewal_request_status"] == "approved"
    assert loans.arguments == ("TEST-REG", "all", 50, 2)


def test_non_management_role_is_denied() -> None:
    client, _ = client_with_fakes(role="client")

    response = client.get(
        "/api/v1/management/loans",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"


def test_management_loan_endpoint_has_no_write_route() -> None:
    client, _ = client_with_fakes()

    response = client.post(
        "/api/v1/management/loans",
        headers=headers(),
        json={"principal": "5000.00"},
    )

    assert response.status_code == 405
