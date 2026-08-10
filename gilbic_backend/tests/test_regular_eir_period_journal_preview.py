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
OTHER_TX_ID = UUID("55555555-5555-4555-8555-555555555555")
JULY_ID = UUID("33333333-3333-4333-8333-333333333333")
AUGUST_ID = UUID("44444444-4444-4444-8444-444444444444")
OVERLAP_ID = UUID("66666666-6666-4666-8666-666666666666")


def _cross_period_source(*, cutover_date: date = date(2026, 7, 30)):
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
    preview = build_regular_eir_accrual_journal_preview(
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
    return preview, allocation, (july, august)


def _build(source, allocation, fiscal_periods):
    return build_regular_eir_period_journal_proposal_preview(
        source,
        protected_allocation=allocation,
        protected_fiscal_periods=fiscal_periods,
    )


def test_reconciled_split_maps_to_balanced_per_period_lines() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    result = _build(source, allocation, fiscal_periods)

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
    source, allocation, fiscal_periods = _cross_period_source()

    first = _build(source, allocation, fiscal_periods)
    second = _build(source, allocation, fiscal_periods)

    assert first == second


def test_non_reconciled_split_fails_closed_without_lines() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    source = replace(source, period_allocation_reconciled=False)

    result = _build(source, allocation, fiscal_periods)

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_split_allocation_not_reconciled"
    assert result.period_proposals == ()
    assert result.total_debit == result.total_credit == Decimal("0.00")
    assert result.balanced is False
    assert result.posting_eligible is False


def test_policy_mismatch_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    source = replace(source, period_split_policy_version="unexpected_policy")

    result = _build(source, allocation, fiscal_periods)

    assert result.blocker_code == "eir_period_split_policy_mismatch"
    assert result.period_proposals == ()
    assert result.posting_eligible is False


def test_unexpected_source_posting_eligibility_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    source = replace(source, posting_eligible=True)

    result = _build(source, allocation, fiscal_periods)

    assert result.blocker_code == "eir_period_journal_posting_control_review"
    assert result.period_proposals == ()
    assert result.automatic_source_posting_enabled is False


def test_replayed_transaction_identity_fails_closed_against_protected_allocation() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    replayed = replace(
        source,
        transaction_id=OTHER_TX_ID,
        related_collection_source_event_key=f"collection:{OTHER_TX_ID}",
        source_event_key=f"eir_accrual:collection:{OTHER_TX_ID}",
    )

    result = _build(replayed, allocation, fiscal_periods)

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_source_allocation_not_exact"
    assert result.period_proposals == ()
    assert result.posting_eligible is False


def test_non_deterministic_protected_source_key_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    source_key = f"manual:{TX_ID}"
    allocation = replace(allocation, source_event_key=source_key)
    source = replace(
        source,
        related_collection_source_event_key=source_key,
        source_event_key=f"eir_accrual:{source_key}",
    )

    result = _build(source, allocation, fiscal_periods)

    assert result.blocker_code == "eir_period_source_allocation_not_exact"
    assert result.period_proposals == ()


def test_tampered_residual_cent_recipient_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    july, august = source.period_split_evidence
    tampered_evidence = (
        replace(
            july,
            residual_cent_adjustment=Decimal("0.01"),
            effective_interest_allocated=Decimal("0.01"),
            received_residual_cent=True,
        ),
        replace(
            august,
            residual_cent_adjustment=Decimal("0.00"),
            effective_interest_allocated=Decimal("0.00"),
            received_residual_cent=False,
        ),
    )
    tampered = replace(source, period_split_evidence=tampered_evidence)

    result = _build(tampered, allocation, fiscal_periods)

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()
    assert result.posting_eligible is False


def test_shifted_source_accrual_coverage_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    july, august = source.period_split_evidence
    shifted_july = replace(
        july,
        accrual_start_date_inclusive=date(2026, 7, 30),
        accrual_end_date_inclusive=date(2026, 7, 30),
    )
    tampered = replace(source, period_split_evidence=(shifted_july, august))

    result = _build(tampered, allocation, fiscal_periods)

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()


def test_day_count_or_gap_in_coverage_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    july, august = source.period_split_evidence
    bad_day_count = replace(july, day_count=2)
    gap_in_coverage = replace(
        august,
        accrual_start_date_inclusive=date(2026, 8, 2),
        accrual_end_date_inclusive=date(2026, 8, 2),
    )

    bad_count_result = _build(
        replace(source, period_split_evidence=(bad_day_count, august)),
        allocation,
        fiscal_periods,
    )
    gap_result = _build(
        replace(source, period_split_evidence=(july, gap_in_coverage)),
        allocation,
        fiscal_periods,
    )

    assert bad_count_result.blocker_code == "eir_period_split_evidence_not_exact"
    assert bad_count_result.period_proposals == ()
    assert gap_result.blocker_code == "eir_period_split_evidence_not_exact"
    assert gap_result.period_proposals == ()


def test_swapped_period_raw_amounts_fail_closed_against_daily_evidence() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    july, august = source.period_split_evidence
    tampered_evidence = (
        replace(
            july,
            effective_interest_raw=august.effective_interest_raw,
            effective_interest_rounded=august.effective_interest_rounded,
            effective_interest_floor=august.effective_interest_floor,
            fractional_cent_remainder=august.fractional_cent_remainder,
            allocation_rank=august.allocation_rank,
            residual_cent_adjustment=august.residual_cent_adjustment,
            effective_interest_allocated=august.effective_interest_allocated,
            received_residual_cent=august.received_residual_cent,
        ),
        replace(
            august,
            effective_interest_raw=july.effective_interest_raw,
            effective_interest_rounded=july.effective_interest_rounded,
            effective_interest_floor=july.effective_interest_floor,
            fractional_cent_remainder=july.fractional_cent_remainder,
            allocation_rank=july.allocation_rank,
            residual_cent_adjustment=july.residual_cent_adjustment,
            effective_interest_allocated=july.effective_interest_allocated,
            received_residual_cent=july.received_residual_cent,
        ),
    )
    tampered = replace(source, period_split_evidence=tampered_evidence)

    result = _build(tampered, allocation, fiscal_periods)

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()
    assert result.posting_eligible is False


def test_swapped_period_identity_fails_closed_against_protected_references() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    july, august = source.period_split_evidence
    tampered_evidence = (
        replace(july, period_id=AUGUST_ID, label="August 2026"),
        replace(august, period_id=JULY_ID, label="July 2026"),
    )
    tampered = replace(source, period_split_evidence=tampered_evidence)

    result = _build(tampered, allocation, fiscal_periods)

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()
    assert result.posting_eligible is False


def test_partial_protected_period_overlap_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source(
        cutover_date=date(2026, 7, 29)
    )
    overlap = AccountingFiscalPeriodReference(
        period_id=OVERLAP_ID,
        label="Overlap July 31",
        start_date=date(2026, 7, 31),
        end_date=date(2026, 7, 31),
        status="open",
    )

    result = _build(
        source,
        allocation,
        fiscal_periods + (overlap,),
    )

    assert source.disposition == "fiscal_period_split_allocation_preview_ready"
    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()


def test_source_preview_control_envelope_tamper_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    tampered = replace(source, balanced=True, split_policy_required=True)

    result = _build(tampered, allocation, fiscal_periods)

    assert result.blocker_code == "eir_period_source_preview_not_exact"
    assert result.period_proposals == ()


def test_rounding_audit_totals_tamper_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    tampered = replace(
        source,
        period_rounded_total=source.period_rounded_total + Decimal("0.01"),
        rounding_residual=source.rounding_residual - Decimal("0.01"),
    )

    result = _build(tampered, allocation, fiscal_periods)

    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()


def test_daily_chain_must_reconcile_to_source_gross_before() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    allocation = replace(
        allocation,
        gross_carrying_before=allocation.gross_carrying_before + Decimal("0.01"),
    )

    result = _build(source, allocation, fiscal_periods)

    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()


def test_missing_protected_daily_evidence_fails_closed() -> None:
    source, allocation, fiscal_periods = _cross_period_source()
    allocation = replace(allocation, daily_accruals=())

    result = _build(source, allocation, fiscal_periods)

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()
    assert result.posting_eligible is False


def test_missing_protected_fiscal_period_references_fail_closed() -> None:
    source, allocation, _ = _cross_period_source()

    result = _build(source, allocation, ())

    assert result.disposition == "eir_period_journal_lines_preview_blocked"
    assert result.blocker_code == "eir_period_split_evidence_not_exact"
    assert result.period_proposals == ()
    assert result.posting_eligible is False
