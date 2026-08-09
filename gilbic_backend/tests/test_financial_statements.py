from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.financial_statements_api import (
    financial_statements_repository_dependency,
)
from gilbic_backend.financial_statements_repository import (
    AccountMovement,
    AccountingStatementPeriod,
    FinancialStatementPack,
    StatementPeriodNotFound,
    build_financial_statement_pack,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
PERIOD_ID = UUID("33333333-3333-4333-8333-333333333333")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="manager@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, role: str = "management", can_view: bool = True) -> None:
        self.role = role
        self.can_view = can_view

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        return AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=auth_user_id,
            username="manager",
            email="manager@example.com",
            full_name="Management User",
            status="active",
            roles=(self.role,),
            permissions=("accounting.view",) if self.can_view else (),
            device_registered=True,
        )


class FakeStatementsRepository:
    def __init__(self, *, missing: bool = False) -> None:
        self.missing = missing
        self.requested_period_id: UUID | None = None

    def load_statement_pack(self, *, period_id: UUID | None = None) -> FinancialStatementPack:
        self.requested_period_id = period_id
        if self.missing:
            raise StatementPeriodNotFound("Accounting period was not found.")
        return sample_pack()


def movement(
    code: str,
    name: str,
    account_type: str,
    *,
    debit: str = "0.00",
    credit: str = "0.00",
    normal_balance: str | None = None,
) -> AccountMovement:
    return AccountMovement(
        account_code=code,
        account_name=name,
        account_type=account_type,
        normal_balance=normal_balance
        or ("debit" if account_type in {"asset", "expense"} else "credit"),
        total_debit=Decimal(debit),
        total_credit=Decimal(credit),
    )


def sample_pack() -> FinancialStatementPack:
    period = AccountingStatementPeriod(
        period_id=PERIOD_ID,
        label="August 2026",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        status="open",
    )
    period_movements = (
        movement("4000", "Interest Income - Regular", "income", credit="1200.00"),
        movement("4010", "Interest Income - 7x7", "income", credit="300.00"),
        movement("5100", "Salaries and Wages Expense", "expense", debit="500.00"),
    )
    cumulative_movements = (
        movement("1010", "Cash - Office", "asset", debit="2000.00"),
        movement("1100", "Loans Receivable - Regular", "asset", debit="5000.00"),
        movement(
            "1190",
            "Allowance for Expected Credit Loss",
            "asset",
            credit="200.00",
            normal_balance="credit",
        ),
        movement("2000", "Accounts Payable", "liability", credit="1000.00"),
        movement("3000", "Capital", "equity", credit="4000.00"),
        movement("3100", "Retained Earnings", "equity", credit="800.00"),
        movement("4000", "Interest Income - Regular", "income", credit="1800.00"),
        movement("5100", "Salaries and Wages Expense", "expense", debit="800.00"),
    )
    return build_financial_statement_pack(
        period=period,
        period_movements=period_movements,
        cumulative_movements=cumulative_movements,
    )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(
    *,
    role: str = "management",
    can_view: bool = True,
    missing: bool = False,
):
    app = create_app()
    fake = FakeStatementsRepository(missing=missing)
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        can_view=can_view,
    )
    app.dependency_overrides[financial_statements_repository_dependency] = lambda: fake
    return TestClient(app), fake


def test_statement_builder_uses_period_profit_and_cumulative_position() -> None:
    pack = sample_pack()

    assert pack.total_income == Decimal("1500.00")
    assert pack.total_expenses == Decimal("500.00")
    assert pack.net_income == Decimal("1000.00")

    assert pack.total_assets == Decimal("6800.00")
    assert pack.total_liabilities == Decimal("1000.00")
    assert pack.recorded_equity == Decimal("4800.00")
    assert pack.unclosed_earnings_to_date == Decimal("1000.00")
    assert pack.total_equity == Decimal("5800.00")
    assert pack.total_liabilities_and_equity == Decimal("6800.00")
    assert pack.balanced is True

    allowance = next(line for line in pack.asset_lines if line.account_code == "1190")
    assert allowance.amount == Decimal("-200.00")


def test_management_can_view_posted_ledger_financial_statements() -> None:
    client, fake = client_with_fakes()
    response = client.get(
        "/api/mobile/v1/management/financial-accounting/statements",
        headers=headers(),
        params={"period_id": str(PERIOD_ID)},
    )

    assert response.status_code == 200
    assert fake.requested_period_id == PERIOD_ID
    statements = response.json()["data"]["statements"]
    assert statements["source"] == "posted_general_ledger_only"
    assert statements["profit_or_loss"]["net_income"] == "1000.00"
    assert statements["financial_position"]["total_assets"] == "6800.00"
    assert statements["financial_position"]["balanced"] is True


def test_financial_statements_require_management_role() -> None:
    client, _ = client_with_fakes(role="collector")
    response = client.get(
        "/api/mobile/v1/management/financial-accounting/statements",
        headers=headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"


def test_financial_statements_return_not_found_for_unknown_period() -> None:
    client, _ = client_with_fakes(missing=True)
    response = client.get(
        "/api/mobile/v1/management/financial-accounting/statements",
        headers=headers(),
        params={"period_id": str(PERIOD_ID)},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "financial_statement_period_not_found"
