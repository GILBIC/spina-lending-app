from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.eir_cash_allocation import EirAllocationResult, EirCashAllocation
from gilbic_backend.eir_cash_allocation_api import (
    eir_cash_allocation_repository_dependency,
)
from gilbic_backend.eir_cash_allocation_repository import EirCashAllocationPack
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
TX_ID = UUID("44444444-4444-4444-8444-444444444444")


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


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[UUID] = []

    def load_loan_allocation(self, *, loan_id: UUID) -> EirCashAllocationPack:
        self.calls.append(loan_id)
        item = EirCashAllocation(
            transaction_id=TX_ID,
            source_event_key=f"collection:{TX_ID}",
            collection_date=date(2026, 8, 9),
            amount=Decimal("15.00"),
            effective_interest_accrued_since_prior_event=Decimal("1.10"),
            gross_carrying_before=Decimal("111.10"),
            accrued_interest_before=Decimal("11.10"),
            loan_component_before=Decimal("100.00"),
            cash_to_accrued_interest=Decimal("11.10"),
            cash_to_loan_component=Decimal("3.90"),
            gross_carrying_after=Decimal("96.10"),
            accrued_interest_after=Decimal("0.00"),
            loan_component_after=Decimal("96.10"),
            posting_eligible=False,
            disposition="allocation_reference_ready",
            message="Read-only allocation reference.",
        )
        result = EirAllocationResult(
            status="allocation_reference_ready",
            message="Read-only Regular allocation reference.",
            calculation_mode="fixed_daily",
            cutover_date=date(2026, 8, 8),
            due_date=date(2026, 12, 6),
            daily_eir=Decimal("0.010000000000"),
            opening_gross_carrying_amount=Decimal("110.00"),
            opening_accrued_interest_component=Decimal("10.00"),
            opening_loan_component=Decimal("100.00"),
            total_effective_interest_accrued=Decimal("1.10"),
            closing_gross_carrying_amount=Decimal("96.10"),
            closing_accrued_interest_component=Decimal("0.00"),
            closing_loan_component=Decimal("96.10"),
            allocations=(item,),
            posting_eligible=False,
        )
        return EirCashAllocationPack(
            loan_id=loan_id,
            loan_number="L-001",
            client_name="Synthetic Borrower",
            cutover_date=date(2026, 8, 8),
            opening_balance_posted=False,
            opening_balance_entry_number=None,
            source_event_count=1,
            source_history_complete=True,
            blocker_code=None,
            blocker_message=None,
            allocation=result,
        )


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-device",
    }


def _client(*, role: str = "management", can_view: bool = True):
    app = create_app()
    repository = FakeRepository()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        can_view=can_view,
    )
    app.dependency_overrides[eir_cash_allocation_repository_dependency] = lambda: repository
    return TestClient(app), repository


def test_management_can_load_exact_decimal_eir_cash_allocation_reference() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/eir-cash-allocation/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.calls == [LOAN_ID]
    data = response.json()["data"]["eir_cash_allocation"]
    assert data["automatic_source_posting_enabled"] is False
    assert data["opening_balance_posted"] is False
    assert data["source_history_complete"] is True
    allocation = data["allocation"]
    assert allocation["posting_eligible"] is False
    assert allocation["daily_eir"] == "0.010000000000"
    assert allocation["opening_gross_carrying_amount"] == "110.00"
    item = allocation["allocations"][0]
    assert item["amount"] == "15.00"
    assert item["cash_to_accrued_interest"] == "11.10"
    assert item["cash_to_loan_component"] == "3.90"
    assert item["source_event_key"] == f"collection:{TX_ID}"


def test_eir_cash_allocation_requires_accounting_view_permission() -> None:
    client, repository = _client(can_view=False)
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/eir-cash-allocation/{LOAN_ID}",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert repository.calls == []


def test_eir_cash_allocation_requires_management_role() -> None:
    client, repository = _client(role="collector")
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/eir-cash-allocation/{LOAN_ID}",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.calls == []
