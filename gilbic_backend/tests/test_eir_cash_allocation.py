from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.eir_cash_allocation import (
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
)


LOAN_ID = UUID("11111111-1111-4111-8111-111111111111")
TX1 = UUID("22222222-2222-4222-8222-222222222222")
TX2 = UUID("33333333-3333-4333-8333-333333333333")
TX3 = UUID("44444444-4444-4444-8444-444444444444")
CUTOVER = date(2026, 8, 8)
DUE_DATE = date(2026, 12, 6)


def state(**overrides: object) -> EirCutoverState:
    values: dict[str, object] = {
        "loan_id": LOAN_ID,
        "calculation_mode": "fixed_daily",
        "cutover_date": CUTOVER,
        "due_date": DUE_DATE,
        "measurement_status": "measured",
        "daily_eir": Decimal("0.01"),
        "loan_component": Decimal("100.00"),
        "accrued_interest_component": Decimal("10.00"),
        "gross_carrying_amount": Decimal("110.00"),
    }
    values.update(overrides)
    return EirCutoverState(**values)  # type: ignore[arg-type]


def event(
    transaction_id: UUID,
    *,
    collection_date: date = date(2026, 8, 9),
    accepted_hour: int = 1,
    amount: str = "15.00",
    entry_type: str = "payment",
    is_voided: bool = False,
) -> EirCashSourceEvent:
    return EirCashSourceEvent(
        transaction_id=transaction_id,
        collection_date=collection_date,
        accepted_at=datetime(
            collection_date.year,
            collection_date.month,
            collection_date.day,
            accepted_hour,
            tzinfo=timezone.utc,
        ),
        entry_type=entry_type,
        amount=Decimal(amount),
        is_voided=is_voided,
    )


def test_regular_cash_accrues_eir_before_cash_and_splits_interest_first() -> None:
    result = allocate_event_date_eir_cash(state(), (event(TX1),))

    assert result.status == "allocation_reference_ready"
    assert result.posting_eligible is False
    assert result.total_effective_interest_accrued == Decimal("1.10")
    allocation = result.allocations[0]
    assert allocation.gross_carrying_before == Decimal("111.10")
    assert allocation.accrued_interest_before == Decimal("11.10")
    assert allocation.loan_component_before == Decimal("100.00")
    assert allocation.cash_to_accrued_interest == Decimal("11.10")
    assert allocation.cash_to_loan_component == Decimal("3.90")
    assert allocation.gross_carrying_after == Decimal("96.10")
    assert allocation.accrued_interest_after == Decimal("0.00")
    assert allocation.loan_component_after == Decimal("96.10")
    assert allocation.source_event_key == f"collection:{TX1}"


def test_same_day_cash_events_accrue_interest_only_once_and_follow_acceptance_order() -> None:
    result = allocate_event_date_eir_cash(
        state(),
        (
            event(TX2, accepted_hour=2, amount="20.00"),
            event(TX1, accepted_hour=1, amount="5.00"),
        ),
    )

    assert [item.transaction_id for item in result.allocations] == [TX1, TX2]
    first, second = result.allocations
    assert first.effective_interest_accrued_since_prior_event == Decimal("1.10")
    assert first.cash_to_accrued_interest == Decimal("5.00")
    assert first.cash_to_loan_component == Decimal("0.00")
    assert second.effective_interest_accrued_since_prior_event == Decimal("0.00")
    assert second.accrued_interest_before == Decimal("6.10")
    assert second.cash_to_accrued_interest == Decimal("6.10")
    assert second.cash_to_loan_component == Decimal("13.90")
    assert result.closing_gross_carrying_amount == Decimal("86.10")


def test_next_day_interest_uses_reconciled_prior_cash_boundary() -> None:
    result = allocate_event_date_eir_cash(
        state(),
        (
            event(TX1, amount="15.00"),
            event(TX2, collection_date=date(2026, 8, 10), amount="1.00"),
        ),
    )

    first, second = result.allocations
    assert first.gross_carrying_after == Decimal("96.10")
    assert second.effective_interest_accrued_since_prior_event == Decimal("0.96")
    assert second.gross_carrying_before == Decimal("97.06")
    assert second.accrued_interest_before == Decimal("0.96")
    assert second.cash_to_accrued_interest == Decimal("0.96")
    assert second.cash_to_loan_component == Decimal("0.04")
    assert second.gross_carrying_after == Decimal("96.06")
    assert second.loan_component_after == Decimal("96.06")


def test_advance_is_cash_on_collection_date_not_covered_date() -> None:
    result = allocate_event_date_eir_cash(
        state(),
        (
            event(
                TX1,
                collection_date=date(2026, 8, 10),
                amount="30.00",
                entry_type="advance",
            ),
        ),
    )

    allocation = result.allocations[0]
    assert allocation.effective_interest_accrued_since_prior_event == Decimal("2.21")
    assert allocation.accrued_interest_before == Decimal("12.21")
    assert allocation.cash_to_accrued_interest == Decimal("12.21")
    assert allocation.cash_to_loan_component == Decimal("17.79")


def test_pass_and_voided_cash_do_not_change_eir_cash_rollforward() -> None:
    pass_event = event(TX1, amount="0.00", entry_type="pass")
    voided = event(TX2, amount="50.00", is_voided=True)
    active = event(TX3, amount="15.00")

    result = allocate_event_date_eir_cash(state(), (pass_event, voided, active))

    assert [item.transaction_id for item in result.allocations] == [TX3]
    assert result.allocations[0].gross_carrying_before == Decimal("111.10")


def test_cent_reconciliation_keeps_gross_equal_to_components_after_each_cash_event() -> None:
    reconciled = state(
        daily_eir=Decimal("0.003333333333"),
        loan_component=Decimal("99.99"),
        accrued_interest_component=Decimal("0.02"),
        gross_carrying_amount=Decimal("100.01"),
    )
    result = allocate_event_date_eir_cash(
        reconciled,
        (
            event(TX1, amount="10.01"),
            event(TX2, collection_date=date(2026, 8, 10), amount="10.00"),
        ),
    )

    for item in result.allocations:
        assert item.gross_carrying_before == (
            item.accrued_interest_before + item.loan_component_before
        )
        assert item.gross_carrying_after == (
            item.accrued_interest_after + item.loan_component_after
        )
    assert result.closing_gross_carrying_amount == (
        result.closing_accrued_interest_component + result.closing_loan_component
    )


def test_cash_exceeding_eir_carrying_amount_blocks_this_and_later_allocations() -> None:
    result = allocate_event_date_eir_cash(
        state(),
        (
            event(TX1, amount="200.00"),
            event(TX2, collection_date=date(2026, 8, 10), amount="1.00"),
        ),
    )

    assert result.status == "cash_exceeds_carrying_review"
    assert len(result.allocations) == 1
    assert result.allocations[0].disposition == "cash_exceeds_carrying_review"
    assert result.allocations[0].cash_to_accrued_interest == Decimal("0.00")
    assert result.allocations[0].cash_to_loan_component == Decimal("0.00")


def test_cutover_or_same_day_cash_is_not_replayed_into_post_cutover_allocation() -> None:
    for cash_date in (date(2026, 8, 7), CUTOVER):
        result = allocate_event_date_eir_cash(
            state(),
            (event(TX1, collection_date=cash_date),),
        )
        assert result.status == "cutover_boundary_review"
        assert result.allocations == ()


def test_unmeasured_or_unreconciled_cutover_blocks_rollforward() -> None:
    unmeasured = allocate_event_date_eir_cash(
        state(measurement_status="7x7_cash_flow_review_required"),
        (event(TX1),),
    )
    unreconciled = allocate_event_date_eir_cash(
        state(
            loan_component=Decimal("100.00"),
            accrued_interest_component=Decimal("10.00"),
            gross_carrying_amount=Decimal("109.99"),
        ),
        (event(TX1),),
    )
    assert unmeasured.status == "cutover_measurement_required"
    assert unreconciled.status == "cutover_measurement_not_reconciled"


def test_7x7_remains_policy_blocked_instead_of_guessing_prepayment_allocation() -> None:
    result = allocate_event_date_eir_cash(
        state(calculation_mode="seven_by_seven"),
        (event(TX1, amount="50.00"),),
    )

    assert result.status == "seven_by_seven_policy_review"
    assert result.allocations == ()
    assert result.posting_eligible is False


def test_post_maturity_cash_is_blocked_without_extrapolating_original_eir() -> None:
    result = allocate_event_date_eir_cash(
        state(due_date=date(2026, 8, 9)),
        (
            event(TX1, collection_date=date(2026, 8, 9), amount="15.00"),
            event(TX2, collection_date=date(2026, 8, 10), amount="1.00"),
        ),
    )

    assert result.status == "post_maturity_review_required"
    assert len(result.allocations) == 1
    assert result.allocations[0].transaction_id == TX1
    assert result.total_effective_interest_accrued == Decimal("1.10")
    assert result.closing_gross_carrying_amount == Decimal("96.10")


def test_cutover_after_maturity_is_blocked_before_rollforward() -> None:
    result = allocate_event_date_eir_cash(
        state(due_date=date(2026, 8, 7)),
        (event(TX1),),
    )
    assert result.status == "post_maturity_review_required"
    assert result.allocations == ()


def test_no_cash_events_preserve_cutover_components_without_creating_entries() -> None:
    result = allocate_event_date_eir_cash(state(), ())

    assert result.status == "allocation_reference_ready"
    assert result.total_effective_interest_accrued == Decimal("0.00")
    assert result.allocations == ()
    assert result.closing_gross_carrying_amount == Decimal("110.00")
    assert result.closing_accrued_interest_component == Decimal("10.00")
    assert result.closing_loan_component == Decimal("100.00")


@pytest.mark.parametrize("mode", ["custom", "unknown"])
def test_unknown_modes_are_policy_blocked(mode: str) -> None:
    result = allocate_event_date_eir_cash(
        state(calculation_mode=mode),
        (event(TX1),),
    )
    assert result.status == "unsupported_calculation_mode"
    assert result.allocations == ()
