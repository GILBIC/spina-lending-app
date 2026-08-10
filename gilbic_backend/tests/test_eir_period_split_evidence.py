from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from gilbic_backend.eir_cash_allocation import (
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
    money,
)
from gilbic_backend.regular_eir_accrual_journal_preview import (
    REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION,
    AccountingFiscalPeriodReference,
    RegularEirAccrualJournalPreview,
    RegularEirAccrualPeriodEvidence,
    allocate_regular_eir_period_split,
    build_regular_eir_accrual_journal_preview,
)


LOAN_ID = UUID("11111111-1111-4111-8111-111111111111")
TX_ID = UUID("22222222-2222-4222-8222-222222222222")
JULY_ID = UUID("33333333-3333-4333-8333-333333333333")
AUGUST_ID = UUID("44444444-4444-4444-8444-444444444444")
CUTOVER_DATE = date(2026, 7, 30)
COLLECTION_DATE = date(2026, 8, 1)


def _period(
    *,
    period_id: UUID,
    label: str,
    start_date: date,
    end_date: date,
) -> AccountingFiscalPeriodReference:
    return AccountingFiscalPeriodReference(
        period_id=period_id,
        label=label,
        start_date=start_date,
        end_date=end_date,
        status="open",
    )


def _allocation_preview(
    *,
    daily_eir: str = "0.000025",
) -> RegularEirAccrualJournalPreview:
    state = EirCutoverState(
        loan_id=LOAN_ID,
        calculation_mode="fixed_daily",
        cutover_date=CUTOVER_DATE,
        due_date=date(2026, 12, 6),
        measurement_status="measured",
        daily_eir=Decimal(daily_eir),
        loan_component=Decimal("100.00"),
        accrued_interest_component=Decimal("0.00"),
        gross_carrying_amount=Decimal("100.00"),
    )
    event = EirCashSourceEvent(
        transaction_id=TX_ID,
        collection_date=COLLECTION_DATE,
        accepted_at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        entry_type="payment",
        amount=Decimal("1.00"),
    )
    allocation_result = allocate_event_date_eir_cash(state, (event,))
    assert allocation_result.status == "allocation_reference_ready"
    allocation = allocation_result.allocations[0]
    assert allocation.effective_interest_accrued_since_prior_event == Decimal(
        "0.01"
    )

    july = _period(
        period_id=JULY_ID,
        label="July 2026",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )
    august = _period(
        period_id=AUGUST_ID,
        label="August 2026",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )
    return build_regular_eir_accrual_journal_preview(
        allocation,
        allocation_result_status=allocation_result.status,
        accrual_start_date=CUTOVER_DATE,
        fiscal_periods=(july, august),
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )


def test_allocator_preserves_exact_daily_eir_for_period_evidence() -> None:
    state = EirCutoverState(
        loan_id=LOAN_ID,
        calculation_mode="fixed_daily",
        cutover_date=CUTOVER_DATE,
        due_date=date(2026, 12, 6),
        measurement_status="measured",
        daily_eir=Decimal("0.000025"),
        loan_component=Decimal("100.00"),
        accrued_interest_component=Decimal("0.00"),
        gross_carrying_amount=Decimal("100.00"),
    )
    event = EirCashSourceEvent(
        transaction_id=TX_ID,
        collection_date=COLLECTION_DATE,
        accepted_at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        entry_type="payment",
        amount=Decimal("1.00"),
    )

    allocation = allocate_event_date_eir_cash(state, (event,)).allocations[0]

    assert [item.accrual_date for item in allocation.daily_accruals] == [
        date(2026, 7, 31),
        date(2026, 8, 1),
    ]
    for previous, current in zip(
        allocation.daily_accruals,
        allocation.daily_accruals[1:],
    ):
        assert (
            previous.closing_gross_carrying_raw
            == current.opening_gross_carrying_raw
        )
    raw_total = sum(
        (item.effective_interest_raw for item in allocation.daily_accruals),
        Decimal("0"),
    )
    assert money(raw_total) == allocation.effective_interest_accrued_since_prior_event


def test_cross_period_evidence_allocates_residual_without_proposing_lines() -> None:
    preview = _allocation_preview()

    assert preview.disposition == "fiscal_period_split_allocation_preview_ready"
    assert preview.split_policy_required is False
    assert (
        preview.period_split_policy_version
        == REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION
    )
    assert preview.posting_eligible is False
    assert preview.balanced is False
    assert preview.proposed_lines == ()
    assert preview.period_rounded_total == Decimal("0.00")
    assert preview.rounding_residual == Decimal("0.01")
    assert preview.period_allocated_total == Decimal("0.01")
    assert preview.unallocated_residual == Decimal("0.00")
    assert preview.period_allocation_reconciled is True
    assert [item.period_id for item in preview.period_split_evidence] == [
        JULY_ID,
        AUGUST_ID,
    ]
    assert [item.day_count for item in preview.period_split_evidence] == [1, 1]
    assert [
        item.effective_interest_rounded
        for item in preview.period_split_evidence
    ] == [Decimal("0.00"), Decimal("0.00")]
    assert [
        item.effective_interest_allocated
        for item in preview.period_split_evidence
    ] == [Decimal("0.00"), Decimal("0.01")]
    assert [
        item.received_residual_cent
        for item in preview.period_split_evidence
    ] == [False, True]
    assert [item.allocation_rank for item in preview.period_split_evidence] == [2, 1]
    assert money(
        sum(
            (
                item.effective_interest_raw
                for item in preview.period_split_evidence
            ),
            Decimal("0"),
        )
    ) == preview.amount


def test_cross_period_evidence_is_deterministic() -> None:
    first = _allocation_preview()
    second = _allocation_preview()

    assert first == second


def test_policy_reconciles_negative_independent_rounding_residual() -> None:
    preview = _allocation_preview(daily_eir="0.00005")

    assert preview.amount == Decimal("0.01")
    assert preview.period_rounded_total == Decimal("0.02")
    assert preview.rounding_residual == Decimal("-0.01")
    assert preview.period_allocated_total == Decimal("0.01")
    assert preview.unallocated_residual == Decimal("0.00")
    assert preview.period_allocation_reconciled is True
    assert preview.split_policy_required is False
    assert [
        item.effective_interest_allocated
        for item in preview.period_split_evidence
    ] == [Decimal("0.00"), Decimal("0.01")]
    assert preview.proposed_lines == ()
    assert preview.posting_eligible is False


def _evidence(
    *,
    period_id: UUID,
    label: str,
    start: date,
    raw: str,
    status: str = "open",
) -> RegularEirAccrualPeriodEvidence:
    raw_amount = Decimal(raw)
    return RegularEirAccrualPeriodEvidence(
        period_id=period_id,
        label=label,
        period_start_date=start,
        period_end_date=start,
        status=status,
        accrual_start_date_inclusive=start,
        accrual_end_date_inclusive=start,
        day_count=1,
        effective_interest_raw=raw_amount,
        effective_interest_rounded=money(raw_amount),
    )


def test_largest_remainder_tie_prefers_larger_exact_period_amount() -> None:
    larger = _evidence(
        period_id=JULY_ID,
        label="Larger",
        start=date(2026, 7, 31),
        raw="10.004",
    )
    smaller = _evidence(
        period_id=AUGUST_ID,
        label="Smaller",
        start=date(2026, 8, 1),
        raw="5.004",
    )

    allocated = allocate_regular_eir_period_split(
        (smaller, larger),
        target_amount=Decimal("15.01"),
    )

    assert allocated is not None
    assert [item.period_id for item in allocated] == [JULY_ID, AUGUST_ID]
    assert [item.allocation_rank for item in allocated] == [1, 2]
    assert [item.effective_interest_allocated for item in allocated] == [
        Decimal("10.01"),
        Decimal("5.00"),
    ]


def test_exact_tie_prefers_earlier_period_and_replay_ignores_input_order() -> None:
    earlier = _evidence(
        period_id=JULY_ID,
        label="Earlier",
        start=date(2026, 7, 31),
        raw="1.005",
    )
    later = _evidence(
        period_id=AUGUST_ID,
        label="Later",
        start=date(2026, 8, 1),
        raw="1.005",
    )

    forward = allocate_regular_eir_period_split(
        (earlier, later),
        target_amount=Decimal("2.01"),
    )
    reverse = allocate_regular_eir_period_split(
        (later, earlier),
        target_amount=Decimal("2.01"),
    )

    assert forward == reverse
    assert forward is not None
    assert [item.received_residual_cent for item in forward] == [True, False]
    assert sum(
        (item.effective_interest_allocated for item in forward),
        Decimal("0.00"),
    ) == Decimal("2.01")


def test_final_exact_tie_uses_stable_period_uuid() -> None:
    lower_uuid = _evidence(
        period_id=JULY_ID,
        label="Lower UUID",
        start=date(2026, 7, 31),
        raw="1.005",
    )
    higher_uuid = _evidence(
        period_id=AUGUST_ID,
        label="Higher UUID",
        start=date(2026, 7, 31),
        raw="1.005",
    )

    allocated = allocate_regular_eir_period_split(
        (higher_uuid, lower_uuid),
        target_amount=Decimal("2.01"),
    )

    assert allocated is not None
    by_id = {item.period_id: item for item in allocated}
    assert by_id[JULY_ID].allocation_rank == 1
    assert by_id[JULY_ID].received_residual_cent is True
    assert by_id[AUGUST_ID].allocation_rank == 2
    assert by_id[AUGUST_ID].received_residual_cent is False


def test_allocator_rejects_closed_period_and_target_mismatch() -> None:
    closed = _evidence(
        period_id=JULY_ID,
        label="Closed",
        start=date(2026, 7, 31),
        raw="0.006",
        status="closed",
    )
    open_period = _evidence(
        period_id=AUGUST_ID,
        label="Open",
        start=date(2026, 8, 1),
        raw="0.004",
    )

    assert (
        allocate_regular_eir_period_split(
            (closed, open_period),
            target_amount=Decimal("0.01"),
        )
        is None
    )
    assert (
        allocate_regular_eir_period_split(
            (open_period,),
            target_amount=Decimal("0.02"),
        )
        is None
    )


def test_cross_period_closed_period_remains_fail_closed() -> None:
    state = EirCutoverState(
        loan_id=LOAN_ID,
        calculation_mode="fixed_daily",
        cutover_date=CUTOVER_DATE,
        due_date=date(2026, 12, 6),
        measurement_status="measured",
        daily_eir=Decimal("0.000025"),
        loan_component=Decimal("100.00"),
        accrued_interest_component=Decimal("0.00"),
        gross_carrying_amount=Decimal("100.00"),
    )
    event = EirCashSourceEvent(
        transaction_id=TX_ID,
        collection_date=COLLECTION_DATE,
        accepted_at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        entry_type="payment",
        amount=Decimal("1.00"),
    )
    allocation_result = allocate_event_date_eir_cash(state, (event,))
    july = AccountingFiscalPeriodReference(
        period_id=JULY_ID,
        label="July 2026",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        status="closed",
    )
    august = _period(
        period_id=AUGUST_ID,
        label="August 2026",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
    )

    preview = build_regular_eir_accrual_journal_preview(
        allocation_result.allocations[0],
        allocation_result_status=allocation_result.status,
        accrual_start_date=CUTOVER_DATE,
        fiscal_periods=(july, august),
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )

    assert preview.disposition == "fiscal_period_split_period_not_open"
    assert preview.period_allocation_reconciled is False
    assert preview.period_allocated_total == Decimal("0.00")
    assert preview.proposed_lines == ()
