from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.eir_cash_allocation import (
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
)
from gilbic_backend.eir_cash_allocation_repository import EirCashAllocationPack
from gilbic_backend.eir_period_journal_api import (
    build_regular_eir_period_journal_api_result,
    eir_period_journal_repository_dependency,
)
from gilbic_backend.main import create_app
from gilbic_backend.regular_accounting_sequence_preview import (
    build_regular_accounting_sequence_preview,
)
from gilbic_backend.regular_collection_journal_preview import (
    build_regular_collection_journal_preview,
)
from gilbic_backend.regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
    build_regular_eir_accrual_journal_preview,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
TX_ID = UUID("44444444-4444-4444-8444-444444444444")
JULY_ID = UUID("55555555-5555-4555-8555-555555555555")
AUGUST_ID = UUID("66666666-6666-4666-8666-666666666666")


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
    def __init__(self, pack, fiscal_periods) -> None:
        self.pack = pack
        self.fiscal_periods = fiscal_periods
        self.calls: list[UUID] = []

    def load_loan_context(self, *, loan_id: UUID):
        self.calls.append(loan_id)
        return self.pack, self.fiscal_periods


def _cross_period_context():
    state = EirCutoverState(
        loan_id=LOAN_ID,
        calculation_mode="fixed_daily",
        cutover_date=date(2026, 7, 30),
        due_date=date(2026, 12, 6),
        measurement_status="measured",
        daily_eir=Decimal("0.000025"),
        loan_component=Decimal("100.00"),
        accrued_interest_component=Decimal("0.00"),
        gross_carrying_amount=Decimal("100.00"),
    )
    event = EirCashSourceEvent(
        transaction_id=TX_ID,
        collection_date=date(2026, 8, 1),
        accepted_at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        entry_type="payment",
        amount=Decimal("1.00"),
    )
    allocation_result = allocate_event_date_eir_cash(state, (event,))
    allocation = allocation_result.allocations[0]
    july = AccountingFiscalPeriodReference(
        period_id=JULY_ID,
        label="July 2026",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        status="open",
    )
    august = AccountingFiscalPeriodReference(
        period_id=AUGUST_ID,
        label="August 2026",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        status="open",
    )
    fiscal_periods = (july, august)
    accrual_preview = build_regular_eir_accrual_journal_preview(
        allocation,
        allocation_result_status=allocation_result.status,
        accrual_start_date=state.cutover_date,
        fiscal_periods=fiscal_periods,
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )
    collection_preview = build_regular_collection_journal_preview(
        allocation,
        allocation_result_status=allocation_result.status,
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )
    sequence_preview = build_regular_accounting_sequence_preview(
        accrual_preview,
        collection_preview,
    )
    pack = EirCashAllocationPack(
        loan_id=LOAN_ID,
        loan_number="L-5D9-001",
        client_name="Synthetic Borrower",
        cutover_date=state.cutover_date,
        opening_balance_prepared=True,
        opening_balance_posted=True,
        opening_balance_entry_number="JE-202607-00000001",
        source_event_count=1,
        source_history_complete=True,
        blocker_code=None,
        blocker_message=None,
        allocation=allocation_result,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        account_configuration_ready=True,
        eir_accrual_account_configuration_ready=True,
        eir_accrual_previews=(accrual_preview,),
        collection_journal_previews=(collection_preview,),
        accounting_sequence_previews=(sequence_preview,),
    )
    return pack, fiscal_periods, accrual_preview, collection_preview


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-device",
    }


def _client(*, role: str = "management", can_view: bool = True):
    pack, fiscal_periods, _, _ = _cross_period_context()
    repository = FakeRepository(pack, fiscal_periods)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        can_view=can_view,
    )
    app.dependency_overrides[eir_period_journal_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_management_can_load_exact_cross_period_eir_journal_proposals() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"eir-period-journal-proposals/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.calls == [LOAN_ID]
    data = response.json()["data"]["eir_period_journal_proposals"]
    assert data["status"] == "eir_period_journal_preview_ready"
    assert data["blocker_code"] is None
    assert data["posting_eligible"] is False
    assert data["automatic_source_posting_enabled"] is False
    assert len(data["period_journal_previews"]) == 1

    preview = data["period_journal_previews"][0]
    assert preview["transaction_id"] == str(TX_ID)
    assert preview["related_collection_source_event_key"] == f"collection:{TX_ID}"
    assert preview["source_event_key"] == f"eir_accrual:collection:{TX_ID}"
    assert preview["amount"] == "0.01"
    assert preview["period_split_policy_version"] == "regular_eir_period_split_v1"
    assert preview["journal_preview_policy_version"] == (
        "regular_eir_period_journal_preview_v1"
    )
    assert preview["period_allocated_total"] == "0.01"
    assert preview["unallocated_residual"] == "0.00"
    assert preview["balanced"] is True
    assert preview["posting_eligible"] is False
    assert preview["automatic_source_posting_enabled"] is False

    july, august = preview["period_proposals"]
    assert july["fiscal_period_id"] == str(JULY_ID)
    assert july["allocated_amount"] == "0.00"
    assert july["proposed_lines"] == []
    assert july["balanced"] is True
    assert july["posting_eligible"] is False

    assert august["fiscal_period_id"] == str(AUGUST_ID)
    assert august["allocated_amount"] == "0.01"
    assert august["total_debit"] == august["total_credit"] == "0.01"
    assert august["proposed_lines"] == [
        {
            "account_system_key": "accrued_interest_receivable",
            "side": "debit",
            "amount": "0.01",
            "label": "Regular effective interest accrued",
        },
        {
            "account_system_key": "interest_income_regular",
            "side": "credit",
            "amount": "0.01",
            "label": "Regular effective interest income",
        },
    ]


def test_protected_fiscal_period_tampering_blocks_all_api_proposals() -> None:
    pack, fiscal_periods, _, _ = _cross_period_context()
    july, august = fiscal_periods
    tampered_periods = (july, replace(august, label="Tampered August"))

    result = build_regular_eir_period_journal_api_result(
        pack,
        protected_fiscal_periods=tampered_periods,
    )

    assert result.status == "eir_period_journal_preview_blocked"
    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.previews == ()
    assert result.posting_eligible is False
    assert result.automatic_source_posting_enabled is False


def test_unexpected_automatic_source_posting_blocks_api_proposals() -> None:
    pack, fiscal_periods, _, _ = _cross_period_context()
    pack = replace(pack, automatic_source_posting_enabled=True)

    result = build_regular_eir_period_journal_api_result(
        pack,
        protected_fiscal_periods=fiscal_periods,
    )

    assert result.status == "eir_period_journal_preview_blocked"
    assert result.blocker_code == (
        "eir_period_journal_automatic_posting_control_review"
    )
    assert result.previews == ()
    assert result.posting_eligible is False


def test_existing_cross_period_accounting_sequence_remains_fail_closed() -> None:
    _, _, accrual_preview, collection_preview = _cross_period_context()

    sequence = build_regular_accounting_sequence_preview(
        accrual_preview,
        collection_preview,
    )

    assert accrual_preview.disposition == "fiscal_period_split_allocation_preview_ready"
    assert sequence.disposition == "regular_accounting_sequence_preview_blocked"
    assert sequence.blocker_code == "fiscal_period_split_allocation_preview_ready"
    assert sequence.ordered_entries == ()
    assert sequence.posting_eligible is False


def test_period_journal_api_requires_accounting_view_permission() -> None:
    client, repository = _client(can_view=False)
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"eir-period-journal-proposals/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.calls == []


def test_period_journal_api_requires_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"eir-period-journal-proposals/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.calls == []
