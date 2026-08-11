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
from gilbic_backend.eir_period_journal_api import eir_period_journal_repository_dependency
from gilbic_backend.main import create_app
from gilbic_backend.posting_ready_evidence_review_api import (
    build_regular_posting_ready_evidence_review_api_result,
)
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
        loan_number="L-5D15-001",
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


def test_management_can_review_exact_posting_ready_bundle_without_write_semantics() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"posting-ready-evidence/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.calls == [LOAN_ID]
    data = response.json()["data"]["posting_ready_evidence_review"]
    assert data["status"] == "regular_posting_ready_evidence_review_ready"
    assert data["blocker_code"] is None
    assert data["posting_eligible"] is False
    assert data["automatic_source_posting_enabled"] is False
    assert data["review_only"] is True
    assert len(data["posting_ready_evidence_bundles"]) == 1

    bundle = data["posting_ready_evidence_bundles"][0]
    assert bundle["transaction_id"] == str(TX_ID)
    assert bundle["bundle_policy_version"] == (
        "regular_cross_period_posting_ready_evidence_v1"
    )
    assert bundle["posting_coordinate_ready"] is True
    assert bundle["posting_identity_ready"] is True
    assert bundle["posting_ready_evidence_complete"] is True
    assert bundle["posting_eligible"] is False
    assert bundle["automatic_source_posting_enabled"] is False
    assert bundle["zero_cent_fiscal_period_ids"] == []

    july, august, cash = bundle["ordered_entries"]
    assert [july["sequence_order"], august["sequence_order"], cash["sequence_order"]] == [
        1,
        2,
        3,
    ]
    assert [july["entry_type"], august["entry_type"], cash["entry_type"]] == [
        "eir_accrual_period",
        "eir_accrual_period",
        "collection",
    ]
    assert july["recognition_date"] == "2026-07-31"
    assert july["proposed_posting_date"] == "2026-07-31"
    assert july["fiscal_period_id"] == str(JULY_ID)
    assert july["fiscal_period_status"] == "open"
    assert july["source_type"] == "regular_eir_accrual"
    assert july["source_event_key"] == (
        f"eir_accrual:collection:{TX_ID}:fiscal_period:{JULY_ID}"
    )
    assert august["proposed_posting_date"] == "2026-08-01"
    assert august["fiscal_period_id"] == str(AUGUST_ID)
    assert cash["proposed_posting_date"] == "2026-08-01"
    assert cash["source_type"] == "collection"
    assert cash["source_event_key"] == f"collection:{TX_ID}"
    assert cash["sequence_order"] > august["sequence_order"]

    for entry in bundle["ordered_entries"]:
        assert entry["balanced"] is True
        assert entry["posting_eligible"] is False
        assert entry["total_debit"] == entry["amount"]
        assert entry["total_credit"] == entry["amount"]
        assert [line["line_order"] for line in entry["journal_lines"]] == list(
            range(1, len(entry["journal_lines"]) + 1)
        )
        assert "journal_entry_id" not in entry
        assert "entry_number" not in entry
        assert "journal_status" not in entry
        assert "posted_at" not in entry

    assert [
        (line["account_system_key"], line["side"], line["amount"])
        for line in july["journal_lines"]
    ] == [
        ("accrued_interest_receivable", "debit", "0.01"),
        ("interest_income_regular", "credit", "0.01"),
    ]


def test_zero_cent_period_is_review_evidence_without_fake_journal_candidate() -> None:
    client, _ = _client(daily_eir=Decimal("0.000025"))
    response = client.get(
        f"/api/v1/management/financial-accounting/"
        f"posting-ready-evidence/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    bundle = response.json()["data"]["posting_ready_evidence_review"][
        "posting_ready_evidence_bundles"
    ][0]
    assert bundle["zero_cent_fiscal_period_ids"] == [str(JULY_ID)]
    assert [entry["entry_type"] for entry in bundle["ordered_entries"]] == [
        "eir_accrual_period",
        "collection",
    ]
    assert bundle["ordered_entries"][0]["fiscal_period_id"] == str(AUGUST_ID)
    assert all(
        entry["fiscal_period_id"] != str(JULY_ID)
        for entry in bundle["ordered_entries"]
    )


def test_tampered_collection_line_evidence_fails_closed_all_or_none() -> None:
    pack, fiscal_periods = _cross_period_context()
    collection = pack.collection_journal_previews[0]
    pack = replace(
        pack,
        collection_journal_previews=(
            replace(collection, total_credit=Decimal("0.99")),
        ),
    )

    result = build_regular_posting_ready_evidence_review_api_result(
        pack,
        protected_fiscal_periods=fiscal_periods,
    )

    assert result.status == "regular_posting_ready_evidence_review_blocked"
    assert result.blocker_code is not None
    assert result.bundles == ()
    assert result.posting_eligible is False
    assert result.automatic_source_posting_enabled is False
    assert result.review_only is True


def test_closed_affected_fiscal_period_fails_closed() -> None:
    pack, fiscal_periods = _cross_period_context()
    july, august = fiscal_periods

    result = build_regular_posting_ready_evidence_review_api_result(
        pack,
        protected_fiscal_periods=(replace(july, status="closed"), august),
    )

    assert result.status == "regular_posting_ready_evidence_review_blocked"
    assert result.blocker_code is not None
    assert result.bundles == ()


def test_automatic_source_posting_remains_blocked() -> None:
    pack, fiscal_periods = _cross_period_context()
    pack = replace(pack, automatic_source_posting_enabled=True)

    result = build_regular_posting_ready_evidence_review_api_result(
        pack,
        protected_fiscal_periods=fiscal_periods,
    )

    assert result.status == "regular_posting_ready_evidence_review_blocked"
    assert result.blocker_code == "eir_period_journal_automatic_posting_control_review"
    assert result.bundles == ()
    assert result.automatic_source_posting_enabled is False


def test_posting_ready_review_api_requires_accounting_view_permission() -> None:
    client, repository = _client(can_view=False)
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"posting-ready-evidence/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.calls == []


def test_posting_ready_review_api_requires_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/"
        f"posting-ready-evidence/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.calls == []
