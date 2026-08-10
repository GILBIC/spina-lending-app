from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.cross_period_accounting_sequence_api import (
    build_regular_cross_period_accounting_sequence_api_result,
)
from gilbic_backend.eir_cash_allocation import (
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
)
from gilbic_backend.eir_cash_allocation_repository import EirCashAllocationPack
from gilbic_backend.eir_period_journal_api import eir_period_journal_repository_dependency
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


def _cross_period_context(*, daily_eir: Decimal = Decimal("0.0001")):
    state = EirCutoverState(
        loan_id=LOAN_ID,
        calculation_mode="fixed_daily",
        cutover_date=date(2026, 7, 30),
        due_date=date(2026, 12, 6),
        measurement_status="measured",
        daily_eir=daily_eir,
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
    assert allocation_result.status == "allocation_reference_ready"
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
    legacy_sequence = build_regular_accounting_sequence_preview(
        accrual_preview,
        collection_preview,
    )
    assert legacy_sequence.disposition == "regular_accounting_sequence_preview_blocked"
    assert legacy_sequence.blocker_code == "fiscal_period_split_allocation_preview_ready"

    pack = EirCashAllocationPack(
        loan_id=LOAN_ID,
        loan_number="L-5D11-001",
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
        accounting_sequence_previews=(legacy_sequence,),
    )
    return pack, fiscal_periods


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-device",
    }


def _client(
    *,
    role: str = "management",
    can_view: bool = True,
    daily_eir: Decimal = Decimal("0.0001"),
):
    pack, fiscal_periods = _cross_period_context(daily_eir=daily_eir)
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


def test_management_can_load_exact_cross_period_sequence_without_posting_semantics() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"cross-period-accounting-sequences/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.calls == [LOAN_ID]
    data = response.json()["data"]["cross_period_accounting_sequences"]
    assert data["status"] == "cross_period_accounting_sequence_preview_ready"
    assert data["blocker_code"] is None
    assert data["posting_eligible"] is False
    assert data["automatic_source_posting_enabled"] is False
    assert len(data["sequence_previews"]) == 1

    preview = data["sequence_previews"][0]
    assert preview["transaction_id"] == str(TX_ID)
    assert preview["sequence_policy_version"] == (
        "regular_cross_period_accounting_sequence_preview_v1"
    )
    assert preview["collection_source_event_key"] == f"collection:{TX_ID}"
    assert preview["collection_date"] == "2026-08-01"
    assert preview["required_eir_accrual_before_collection"] == "0.02"
    assert preview["posting_eligible"] is False
    assert preview["automatic_source_posting_enabled"] is False
    assert preview["zero_cent_fiscal_period_ids"] == []
    assert "posting_date" not in preview

    july, august, collection = preview["ordered_entries"]
    assert [july["sequence_order"], august["sequence_order"], collection["sequence_order"]] == [1, 2, 3]
    assert [july["entry_type"], august["entry_type"], collection["entry_type"]] == [
        "eir_accrual_period",
        "eir_accrual_period",
        "collection",
    ]
    assert july["recognition_date"] == "2026-07-31"
    assert august["recognition_date"] == "2026-08-01"
    assert collection["recognition_date"] == "2026-08-01"
    assert august["sequence_order"] < collection["sequence_order"]
    assert july["fiscal_period_id"] == str(JULY_ID)
    assert august["fiscal_period_id"] == str(AUGUST_ID)
    assert collection["fiscal_period_id"] is None
    assert all("posting_date" not in entry for entry in preview["ordered_entries"])
    assert all(entry["posting_eligible"] is False for entry in preview["ordered_entries"])


def test_zero_cent_period_is_evidence_not_fake_api_sequence_entry() -> None:
    client, _ = _client(daily_eir=Decimal("0.000025"))
    response = client.get(
        f"/api/v1/management/financial-accounting/"
        f"cross-period-accounting-sequences/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    preview = response.json()["data"]["cross_period_accounting_sequences"][
        "sequence_previews"
    ][0]
    assert preview["zero_cent_fiscal_period_ids"] == [str(JULY_ID)]
    assert [entry["entry_type"] for entry in preview["ordered_entries"]] == [
        "eir_accrual_period",
        "collection",
    ]
    assert preview["ordered_entries"][0]["fiscal_period_id"] == str(AUGUST_ID)


def test_incomplete_collection_preview_set_fails_closed() -> None:
    pack, fiscal_periods = _cross_period_context()
    pack = replace(pack, collection_journal_previews=())

    result = build_regular_cross_period_accounting_sequence_api_result(
        pack,
        protected_fiscal_periods=fiscal_periods,
    )

    assert result.status == "cross_period_accounting_sequence_preview_blocked"
    assert result.blocker_code == "cross_period_sequence_source_preview_set_not_exact"
    assert result.previews == ()
    assert result.posting_eligible is False


def test_existing_cross_period_sequence_path_must_remain_fail_closed() -> None:
    pack, fiscal_periods = _cross_period_context()
    legacy = pack.accounting_sequence_previews[0]
    tampered_legacy = replace(
        legacy,
        disposition="regular_accounting_sequence_preview_ready",
        blocker_code=None,
    )
    pack = replace(pack, accounting_sequence_previews=(tampered_legacy,))

    result = build_regular_cross_period_accounting_sequence_api_result(
        pack,
        protected_fiscal_periods=fiscal_periods,
    )

    assert result.blocker_code == "cross_period_sequence_legacy_boundary_not_closed"
    assert result.previews == ()


def test_tampered_collection_preview_fails_closed_through_stage5d10() -> None:
    pack, fiscal_periods = _cross_period_context()
    collection = pack.collection_journal_previews[0]
    pack = replace(
        pack,
        collection_journal_previews=(replace(collection, total_credit=Decimal("0.99")),),
    )

    result = build_regular_cross_period_accounting_sequence_api_result(
        pack,
        protected_fiscal_periods=fiscal_periods,
    )

    assert result.blocker_code == "cross_period_collection_preview_not_exact"
    assert result.previews == ()


def test_protected_period_tampering_propagates_stage5d8_blocker() -> None:
    pack, fiscal_periods = _cross_period_context()
    july, august = fiscal_periods
    tampered_periods = (july, replace(august, label="Tampered August"))

    result = build_regular_cross_period_accounting_sequence_api_result(
        pack,
        protected_fiscal_periods=tampered_periods,
    )

    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.previews == ()


def test_automatic_source_posting_remains_blocked() -> None:
    pack, fiscal_periods = _cross_period_context()
    pack = replace(pack, automatic_source_posting_enabled=True)

    result = build_regular_cross_period_accounting_sequence_api_result(
        pack,
        protected_fiscal_periods=fiscal_periods,
    )

    assert result.blocker_code == "eir_period_journal_automatic_posting_control_review"
    assert result.previews == ()
    assert result.automatic_source_posting_enabled is False


def test_cross_period_sequence_api_requires_accounting_view_permission() -> None:
    client, repository = _client(can_view=False)
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"cross-period-accounting-sequences/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.calls == []


def test_cross_period_sequence_api_requires_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"cross-period-accounting-sequences/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.calls == []
