from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from gilbic_backend.eir_cash_allocation import (
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
)
from gilbic_backend.regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
    build_regular_eir_accrual_journal_preview,
)
from gilbic_backend.regular_eir_period_journal_preview import (
    REGULAR_EIR_PERIOD_JOURNAL_PREVIEW_POLICY_VERSION,
    build_regular_eir_period_journal_proposal_preview,
)


LOAN_ID = UUID("11111111-1111-4111-8111-111111111111")
TX_ID = UUID("22222222-2222-4222-8222-222222222222")
JULY_ID = UUID("33333333-3333-4333-8333-333333333333")
AUGUST_ID = UUID("44444444-4444-4444-8444-444444444444")


def _cross_period_preview():
    cutover_date = date(2026, 7, 30)
    state = EirCutoverState(
        loan_id=LOAN_ID,
        calculation_mode="fixed_daily",
        cutover_date=cutover_date,
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
    return build_regular_eir_accrual_journal_preview(
        allocation,
        allocation_result_status=allocation_result.status,
        accrual_start_date=cutover_date,
        fiscal_periods=(july, august),
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )


def test_reconciled_split_maps_to_balanced_per_period_lines() -> None:
    source = _cross_period_preview()
    result = build_regular_eir_period_journal_proposal_preview(source)

    assert source.disposition == "fiscal_period_split_allocation_preview_ready"
    assert result.disposition == "eir_period_journal_lines_preview_ready"
    assert result.blocker_code is None
    assert result.journal_preview_policy_version == (
        REGULAR_EIR_PERIOD_JOURNAL_PREVIEW_POLICY_VERSION
    )
    assert result.amount == Decimal("0.01")
    assert result.period_allocated_total == Decimal("0.01")
    assert result.unallocated_residual == Decimal("0.00")
    assert result.total_debit == result.total_credit == Decimal("0.01")
    assert result.balanced is True
    assert result.posting_eligible is False
    assert result.automatic_source_posting_enabled is False
    assert [proposal.fiscal_period_id for proposal in result.period_proposals] == [
        JULY_ID,
        AUGUST_ID,
    ]

    july, august = result.period_proposals
    assert july.allocated_amount == Decimal("0.00")
    assert july.proposed_lines == ()
    assert july.balanced is True
    assert july.posting_eligible is False

    assert august.allocated_amount == Decimal("0.01")
    assert august.balanced is True
    assert august.posting_eligible is False
    assert [
        (line.account_system_key, line.side, line.amount)
        for line in august.proposed_lines
    ] == [
        ("accrued_interest_receivable", "debit", Decimal("0.01")),
        ("interest_income_regular", "credit", Decimal("0.01")),
    ]


def test_period_journal_preview_is_deterministic() -> None:
    source = _cross_period_preview()

    first = build_regular_eir_period_journal_proposal_preview(source)
    second = build_regular_eir_period_journal_proposal_preview(source)

    assert first == second


def test_non_reconciled_split_fails_closed_without_lines() -> None:
    source = replace(
        _cross_period_preview(),
        period_allocation_reconciled=False,
    )

    result = build_regular_eir_period_journal_proposal_preview(source)

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_split_allocation_not_reconciled"
    assert result.period_proposals == ()
    assert result.total_debit == result.total_credit == Decimal("0.00")
    assert result.balanced is False
    assert result.posting_eligible is False


def test_policy_mismatch_fails_closed() -> None:
    source = replace(
        _cross_period_preview(),
        period_split_policy_version="unexpected_policy",
    )

    result = build_regular_eir_period_journal_proposal_preview(source)

    assert result.blocker_code == "eir_period_split_policy_mismatch"
    assert result.period_proposals == ()
    assert result.posting_eligible is False


def test_unexpected_source_posting_eligibility_fails_closed() -> None:
    source = replace(_cross_period_preview(), posting_eligible=True)

    result = build_regular_eir_period_journal_proposal_preview(source)

    assert result.blocker_code == "eir_period_journal_posting_control_review"
    assert result.period_proposals == ()
    assert result.automatic_source_posting_enabled is False
