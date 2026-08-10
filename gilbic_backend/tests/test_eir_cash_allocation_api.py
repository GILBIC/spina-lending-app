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
    _eir_accrual_preview_payload,
    eir_cash_allocation_repository_dependency,
)
from gilbic_backend.eir_cash_allocation_repository import EirCashAllocationPack
from gilbic_backend.regular_collection_journal_preview import (
    build_regular_collection_journal_preview,
)
from gilbic_backend.regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
    RegularEirAccrualJournalPreview,
    RegularEirAccrualPeriodEvidence,
    build_regular_eir_accrual_journal_preview,
)
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
        preview = build_regular_collection_journal_preview(
            item,
            allocation_result_status=result.status,
            opening_balance_posted=True,
            protected_snapshot_available=True,
            protected_snapshot_reconciled=True,
            source_history_complete=True,
            account_configuration_ready=True,
        )
        period = AccountingFiscalPeriodReference(
            period_id=UUID("55555555-5555-4555-8555-555555555555"),
            label="August 2026",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
            status="open",
        )
        accrual_preview = build_regular_eir_accrual_journal_preview(
            item,
            allocation_result_status=result.status,
            accrual_start_date=date(2026, 8, 8),
            fiscal_periods=(period,),
            opening_balance_posted=True,
            protected_snapshot_available=True,
            protected_snapshot_reconciled=True,
            source_history_complete=True,
            account_configuration_ready=True,
        )
        return EirCashAllocationPack(
            loan_id=loan_id,
            loan_number="L-001",
            client_name="Synthetic Borrower",
            cutover_date=date(2026, 8, 8),
            opening_balance_prepared=True,
            opening_balance_posted=True,
            opening_balance_entry_number="JE-202608-00000001",
            source_event_count=1,
            source_history_complete=True,
            blocker_code=None,
            blocker_message=None,
            allocation=result,
            protected_snapshot_available=True,
            protected_snapshot_reconciled=True,
            account_configuration_ready=True,
            eir_accrual_account_configuration_ready=True,
            eir_accrual_previews=(accrual_preview,),
            collection_journal_previews=(preview,),
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
    assert data["opening_balance_prepared"] is True
    assert data["opening_balance_posted"] is True
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
    assert data["account_configuration_ready"] is True
    assert data["eir_accrual_account_configuration_ready"] is True
    accrual = data["eir_accrual_previews"][0]
    assert accrual["related_collection_source_event_key"] == f"collection:{TX_ID}"
    assert accrual["source_event_key"] == f"eir_accrual:collection:{TX_ID}"
    assert accrual["accrual_start_date_exclusive"] == "2026-08-08"
    assert accrual["accrual_end_date_inclusive"] == "2026-08-09"
    assert accrual["posting_date"] == "2026-08-09"
    assert accrual["fiscal_period_label"] == "August 2026"
    assert accrual["fiscal_period_status"] == "open"
    assert accrual["amount"] == "1.10"
    assert accrual["posting_eligible"] is False
    assert accrual["balanced"] is True
    assert accrual["total_debit"] == accrual["total_credit"] == "1.10"
    assert accrual["period_split_evidence"] == []
    assert accrual["period_rounded_total"] == "0.00"
    assert accrual["rounding_residual"] == "0.00"
    assert accrual["split_policy_required"] is False
    assert accrual["proposed_lines"] == [
        {
            "account_system_key": "accrued_interest_receivable",
            "side": "debit",
            "amount": "1.10",
            "label": "Regular effective interest accrued",
        },
        {
            "account_system_key": "interest_income_regular",
            "side": "credit",
            "amount": "1.10",
            "label": "Regular effective interest income",
        },
    ]
    preview = data["collection_journal_previews"][0]
    assert preview["source_event_key"] == f"collection:{TX_ID}"
    assert preview["posting_eligible"] is False
    assert preview["balanced"] is True
    assert preview["required_eir_accrual_before_collection"] == "1.10"
    assert preview["total_debit"] == "15.00"
    assert preview["total_credit"] == "15.00"
    assert preview["proposed_lines"] == [
        {
            "account_system_key": "cash_collector_custody",
            "side": "debit",
            "amount": "15.00",
            "label": "Accepted collection cash",
        },
        {
            "account_system_key": "accrued_interest_receivable",
            "side": "credit",
            "amount": "11.10",
            "label": "Cash applied to accrued effective interest",
        },
        {
            "account_system_key": "loans_receivable_regular",
            "side": "credit",
            "amount": "3.90",
            "label": "Cash applied to Regular loan component",
        },
    ]


def test_eir_cash_allocation_requires_accounting_view_permission() -> None:
    client, repository = _client(can_view=False)
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/eir-cash-allocation/{LOAN_ID}",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert repository.calls == []


def test_cross_period_eir_evidence_serializes_raw_and_cent_values_separately() -> None:
    july = RegularEirAccrualPeriodEvidence(
        period_id=UUID("55555555-5555-4555-8555-555555555555"),
        label="July 2026",
        period_start_date=date(2026, 7, 1),
        period_end_date=date(2026, 7, 31),
        status="open",
        accrual_start_date_inclusive=date(2026, 7, 31),
        accrual_end_date_inclusive=date(2026, 7, 31),
        day_count=1,
        effective_interest_raw=Decimal("0.00250000"),
        effective_interest_rounded=Decimal("0.00"),
    )
    august = RegularEirAccrualPeriodEvidence(
        period_id=UUID("66666666-6666-4666-8666-666666666666"),
        label="August 2026",
        period_start_date=date(2026, 8, 1),
        period_end_date=date(2026, 8, 31),
        status="open",
        accrual_start_date_inclusive=date(2026, 8, 1),
        accrual_end_date_inclusive=date(2026, 8, 1),
        day_count=1,
        effective_interest_raw=Decimal("0.00250006250000"),
        effective_interest_rounded=Decimal("0.00"),
    )
    preview = RegularEirAccrualJournalPreview(
        transaction_id=TX_ID,
        related_collection_source_event_key=f"collection:{TX_ID}",
        source_event_key=f"eir_accrual:collection:{TX_ID}",
        accrual_start_date_exclusive=date(2026, 7, 30),
        accrual_end_date_inclusive=date(2026, 8, 1),
        posting_date=date(2026, 8, 1),
        fiscal_period_id=None,
        fiscal_period_label=None,
        fiscal_period_status=None,
        amount=Decimal("0.01"),
        disposition="fiscal_period_split_required",
        posting_eligible=False,
        message="Management-approved residual policy required.",
        proposed_lines=(),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        balanced=False,
        period_split_evidence=(july, august),
        period_rounded_total=Decimal("0.00"),
        rounding_residual=Decimal("0.01"),
        split_policy_required=True,
    )

    payload = _eir_accrual_preview_payload(preview)

    assert payload["split_policy_required"] is True
    assert payload["period_rounded_total"] == "0.00"
    assert payload["rounding_residual"] == "0.01"
    assert payload["proposed_lines"] == []
    evidence = payload["period_split_evidence"]
    assert isinstance(evidence, list)
    assert [item["effective_interest_raw"] for item in evidence] == [
        "0.00250000",
        "0.00250006250000",
    ]
    assert [item["effective_interest_rounded"] for item in evidence] == [
        "0.00",
        "0.00",
    ]


def test_eir_cash_allocation_requires_management_role() -> None:
    client, repository = _client(role="collector")
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/eir-cash-allocation/{LOAN_ID}",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.calls == []
