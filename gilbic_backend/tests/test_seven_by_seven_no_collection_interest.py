from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from gilbic_backend.seven_by_seven_advance_activation import (
    replay_verified_seven_by_seven_financial_state,
)


class _Cursor:
    def __init__(self) -> None:
        self.query = ""

    def execute(self, query: str, params) -> None:
        self.query = query

    def fetchall(self):
        if "from lending.collection_transactions transaction" in self.query:
            return [
                {
                    "id": UUID("11111111-1111-4111-8111-111111111111"),
                    "collection_date": date(2026, 8, 1),
                    "entry_type": "payment",
                    "receipt_amount": Decimal("21.00"),
                    "deferred_amount": Decimal("0.00"),
                    "accepted_at": datetime(2026, 8, 1, 1, tzinfo=timezone.utc),
                },
                {
                    "id": UUID("22222222-2222-4222-8222-222222222222"),
                    "collection_date": date(2026, 8, 3),
                    "entry_type": "payment",
                    "receipt_amount": Decimal("21.00"),
                    "deferred_amount": Decimal("0.00"),
                    "accepted_at": datetime(2026, 8, 3, 1, tzinfo=timezone.utc),
                },
            ]
        if "join lending.loan_installment_active_advance active_advance" in self.query:
            return []
        if "from lending.loan_installment_payment_allocations allocation" in self.query:
            return []
        if "from lending.loan_schedule_adjustments adjustment" in self.query:
            return [{"no_collection_date": date(2026, 8, 2)}]
        raise AssertionError(self.query)


def test_verified_replay_uses_active_no_collection_as_zero_interest_holiday() -> None:
    replay = replay_verified_seven_by_seven_financial_state(
        _Cursor(),
        loan_id=UUID("33333333-3333-4333-8333-333333333333"),
        original_principal=Decimal("3000.00"),
        daily_interest_per_1000=Decimal("7.00"),
        payment_start=date(2026, 8, 1),
        through_date=date(2026, 8, 3),
    )

    assert replay.interest_holiday_dates == (date(2026, 8, 2),)
    assert replay.result.closing_interest_arrears == Decimal("0.00")
    assert replay.result.closing_remaining_principal == Decimal("3000.00")
    first, after_holiday = replay.result.allocations
    assert first.interest_due == Decimal("21.00")
    assert after_holiday.gap_days == 2
    assert after_holiday.interest_days == 1
    assert after_holiday.interest_holiday_days == 1
    assert after_holiday.interest_due == Decimal("21.00")
