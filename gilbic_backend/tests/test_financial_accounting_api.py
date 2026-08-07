from __future__ import annotations

from datetime import date
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
    AccountingAccount,
    AccountingFiscalPeriod,
    AccountingFoundationSummary,
    FinancialAccountingOverview,
    FinancialAccountingSummary,
    LoanAccountingPolicy,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
PERIOD_ID = UUID("44444444-4444-4444-8444-444444444444")


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
    def __init__(self, *, role: str, can_manage_periods: bool) -> None:
        self.role = role
        self.can_manage_periods = can_manage_periods

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "test-device"
        is_management = self.role == "management"
        permissions: tuple[str, ...] = ()
        if is_management:
            permissions = ("accounting.view",)
            if self.can_manage_periods:
                permissions += ("accounting.period.manage",)
        return AccountContext(
            user_id=MANAGEMENT_USER_ID if is_management else CLIENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="manager" if is_management else "client",
            email="user@example.com",
            full_name="Management" if is_management else "Client",
            status="active",
            roles=(self.role,),
            permissions=permissions,
            device_registered=True,
        )


class FakeAccounting:
    def __init__(self) -> None:
        self.created: tuple[str, date, date, UUID] | None = None
        self.status_change: tuple[UUID, str, UUID] | None = None

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
            foundation=AccountingFoundationSummary(
                account_count=23,
                posting_account_count=23,
                fiscal_period_count=1,
                open_period_count=1,
                journal_entry_count=0,
                draft_journal_count=0,
                posted_journal_count=0,
                reversal_draft_count=0,
            ),
            accounts=(
                AccountingAccount(
                    code="1010",
                    system_key="cash_office",
                    name="Cash - Office",
                    account_type="asset",
                    normal_balance="debit",
                    is_posting=True,
                    is_active=True,
                ),
                AccountingAccount(
                    code="4000",
                    system_key="interest_income_regular",
                    name="Interest Income - Regular",
                    account_type="income",
                    normal_balance="credit",
                    is_posting=True,
                    is_active=True,
                ),
            ),
            fiscal_periods=(self._period("open"),),
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

    def create_fiscal_period(
        self,
        *,
        actor_user_id: UUID,
        label: str,
        start_date: date,
        end_date: date,
    ) -> AccountingFiscalPeriod:
        self.created = (label, start_date, end_date, actor_user_id)
        return self._period("open", label=label, start_date=start_date, end_date=end_date)

    def set_fiscal_period_status(
        self,
        *,
        actor_user_id: UUID,
        period_id: UUID,
        status: str,
    ) -> AccountingFiscalPeriod:
        self.status_change = (period_id, status, actor_user_id)
        return self._period(status)

    @staticmethod
    def _period(
        status: str,
        *,
        label: str = "August 2026",
        start_date: date = date(2026, 8, 1),
        end_date: date = date(2026, 8, 31),
    ) -> AccountingFiscalPeriod:
        return AccountingFiscalPeriod(
            period_id=PERIOD_ID,
            label=label,
            start_date=start_date,
            end_date=end_date,
            status=status,
            journal_count=0,
            draft_journal_count=0,
            posted_journal_count=0,
            closed_by_name="Management" if status == "closed" else None,
            closed_at=None,
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(
    *,
    role: str = "management",
    can_manage_periods: bool = True,
) -> tuple[TestClient, FakeAccounting]:
    app = create_app()
    fake_accounting = FakeAccounting()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        can_manage_periods=can_manage_periods,
    )
    app.dependency_overrides[financial_accounting_repository_dependency] = (
        lambda: fake_accounting
    )
    return TestClient(app), fake_accounting


def test_management_can_view_financial_accounting_foundation_and_periods() -> None:
    client, _ = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/management/financial-accounting",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["active_loan_count"] == 7
    assert data["summary"]["operational_outstanding"] == "28550.00"
    assert data["summary"]["unremitted_cash"] == "200.00"
    assert data["foundation_status"] == "ready"
    assert data["foundation"]["account_count"] == 23
    assert data["foundation"]["posted_journal_count"] == 0
    assert data["fiscal_period_status"] == "open"
    assert data["period_management_enabled"] is True
    assert data["fiscal_periods"][0]["label"] == "August 2026"
    assert data["fiscal_periods"][0]["status"] == "open"
    assert data["journal_status"] == "manual_ready"
    assert data["trial_balance_status"] == "available"
    assert data["accounts"][0]["code"] == "1010"
    assert data["accounts"][1]["normal_balance"] == "credit"
    assert data["policies"][0]["name"] == "Regular"
    assert data["policies"][1]["daily_interest_per_1000"] == "7.00"
    assert data["policies"][1]["mobile_collections_enabled"] is False


def test_management_can_create_fiscal_period() -> None:
    client, accounting = client_with_fakes()

    response = client.post(
        "/api/mobile/v1/management/financial-accounting/fiscal-periods",
        headers=headers(),
        json={
            "label": "September 2026",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["period"]["label"] == "September 2026"
    assert accounting.created == (
        "September 2026",
        date(2026, 9, 1),
        date(2026, 9, 30),
        MANAGEMENT_USER_ID,
    )


def test_period_close_requires_confirmation() -> None:
    client, accounting = client_with_fakes()

    response = client.post(
        f"/api/v1/management/financial-accounting/fiscal-periods/{PERIOD_ID}/status",
        headers=headers(),
        json={"status": "closed", "confirm_close": False},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "accounting_period_close_confirmation_required"
    )
    assert accounting.status_change is None


def test_management_can_move_period_to_review() -> None:
    client, accounting = client_with_fakes()

    response = client.post(
        f"/api/v1/management/financial-accounting/fiscal-periods/{PERIOD_ID}/status",
        headers=headers(),
        json={"status": "review"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["period"]["status"] == "review"
    assert accounting.status_change == (PERIOD_ID, "review", MANAGEMENT_USER_ID)


def test_period_management_permission_is_required_for_writes() -> None:
    client, accounting = client_with_fakes(can_manage_periods=False)

    response = client.post(
        "/api/v1/management/financial-accounting/fiscal-periods",
        headers=headers(),
        json={
            "label": "September 2026",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
        },
    )

    assert response.status_code == 403
    assert accounting.created is None


def test_non_management_role_is_denied() -> None:
    client, _ = client_with_fakes(role="client", can_manage_periods=False)

    response = client.get(
        "/api/v1/management/financial-accounting",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"


def test_general_financial_accounting_write_endpoint_remains_disabled() -> None:
    client, _ = client_with_fakes()

    response = client.post(
        "/api/v1/management/financial-accounting",
        headers=headers(),
        json={"debit": "100.00", "credit": "100.00"},
    )

    assert response.status_code == 405
