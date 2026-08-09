from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from inspect import getsource
from uuid import UUID

from gilbic_backend.eir_cash_allocation import (
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
)
from gilbic_backend.eir_cash_allocation_repository import (
    PostgresEirCashAllocationRepository,
)


LOAN_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TX1 = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
TX2 = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
TX3 = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


def _event(transaction_id: UUID, day: int) -> EirCashSourceEvent:
    return EirCashSourceEvent(
        transaction_id=transaction_id,
        collection_date=date(2026, 8, day),
        accepted_at=datetime(2026, 8, day, 1, tzinfo=timezone.utc),
        entry_type="payment",
        amount=Decimal("0.01"),
    )


def test_subcent_interest_discarded_at_each_boundary_does_not_reappear_in_total() -> None:
    state = EirCutoverState(
        loan_id=LOAN_ID,
        calculation_mode="fixed_daily",
        cutover_date=date(2026, 8, 8),
        due_date=date(2026, 12, 6),
        measurement_status="measured",
        daily_eir=Decimal("0.004"),
        loan_component=Decimal("1.00"),
        accrued_interest_component=Decimal("0.00"),
        gross_carrying_amount=Decimal("1.00"),
    )

    result = allocate_event_date_eir_cash(
        state,
        (_event(TX1, 9), _event(TX2, 10), _event(TX3, 11)),
    )

    assert [
        item.effective_interest_accrued_since_prior_event
        for item in result.allocations
    ] == [Decimal("0.00"), Decimal("0.00"), Decimal("0.00")]
    assert result.total_effective_interest_accrued == Decimal("0.00")
    assert result.closing_gross_carrying_amount == Decimal("0.97")
    assert result.closing_accrued_interest_component == Decimal("0.00")
    assert result.closing_loan_component == Decimal("0.97")


def test_repository_blocks_mutable_remeasurement_after_opening_journal_preparation() -> None:
    source = getsource(PostgresEirCashAllocationRepository)

    assert "opening_balance_journal_preparations" in source
    assert "opening_balance_prepared" in source
    assert "protected_cutover_snapshot_required" in source
    assert "if opening_balance_prepared" in source
    assert source.index("if opening_balance_prepared") < source.index(
        "measurement = self._load_measurement"
    )
