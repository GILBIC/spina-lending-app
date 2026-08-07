from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.financial_accounting_api import (
    financial_accounting_repository_dependency,
)
from gilbic_backend.financial_accounting_repository import (
    FinancialAccountingOverview,
    FinancialAccountingSummary,
    LoanAccountingPolicy,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_USER_ID = UUID("33333333-3333-4333-8333-333333333333")


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


class FakeAccounting:
    def load_overview(self) -> FinancialAccountingOverview:
        return FinancialAccountingOverview(
            summary=FinancialAccountingSummary(
                active_loan_count=7,
                active_principal=Decimal("29000.00"),
                operational_outstanding=Decimal("28550.00"),
                regular_outstanding=Decimal("19550.00"),
                seven_by_seven_outstanding=Decimal("9000.00"),
                unremitted_cash=Decimal("200.00"),
                received_remittance_total=Decimal("250.00"),
                valid_collection_count=9,
                correction_count=1,
                void_count=1,
            ),
            policies=(
                LoanAccountingPolicy(
                    code="regular_mobile_test",
                    name="Regular",
                    term_days=120,
                    calculation_mode="fixed_daily",
                    daily_interest_per_1000=Decimal("0.00"),
                    mobile_collections_enabled=True,
                    operational_rule="Fixed contractual interest and daily collection.",
                    accounting_rule="Use an effective-interest schedule.",
                    renewal_rule="Close the old loan and create a new loan.",
                ),
                LoanAccountingPolicy(
                    code="seven_by_seven_mobile_test",
                    name="7x7",
                    term_days=120,
                    calculation_mode="seven_by_seven",
                    daily_interest_per_1000=Decimal("7.00"),
                    mobile_collections_enabled=False,
                    operational_rule="PHP 7 per PHP 1,000 of original principal per day.",
                    accounting_rule="Track principal and accrued interest separately.",
                    renewal_rule="Deduct old principal and accrued unpaid interest.",
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(*, role: str = "management") -> TestClient:
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role
    )
    app.dependency_overrides[financial_accounting_repository_dependency] = (
        lambda: FakeAccounting()
    )
    return TestClient(app)


def test_management_can_view_financial_accounting_control_center() -> None:
    client = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/management/financial-accounting",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["active_loan_count"] == 7
    assert data["summary"]["operational_outstanding"] == "28550.00"
    assert data["summary"]["unremitted_cash"] == "200.00"
    assert data["journal_status"] == "not_started"
    assert data["trial_balance_status"] == "unavailable"
    assert data["policies"][0]["name"] == "Regular"
    assert data["policies"][1]["daily_interest_per_1000"] == "7.00"
    assert data["policies"][1]["mobile_collections_enabled"] is False


def test_non_management_role_is_denied() -> None:
    client = client_with_fakes(role="client")

    response = client.get(
        "/api/v1/management/financial-accounting",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"


def test_financial_accounting_control_center_has_no_write_endpoint() -> None:
    client = client_with_fakes()

    response = client.post(
        "/api/v1/management/financial-accounting",
        headers=headers(),
        json={"debit": "100.00", "credit": "100.00"},
    )

    assert response.status_code == 405
