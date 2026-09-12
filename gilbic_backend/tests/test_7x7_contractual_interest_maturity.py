from datetime import date
from decimal import Decimal

from gilbic_backend.seven_by_seven_operational_allocator import (
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
)


def test_contractual_interest_stops_at_signed_maturity_but_arrears_remain_collectible() -> None:
    result = allocate_seven_by_seven_payments(
        original_principal=Decimal("3000.00"),
        daily_interest_per_1000=Decimal("7.00"),
        payment_start=date(2026, 8, 1),
        contractual_maturity=date(2026, 8, 2),
        events=(
            SevenBySevenCashEvent(
                event_id="short-before-maturity",
                collection_date=date(2026, 8, 1),
                amount=Decimal("10.00"),
            ),
            SevenBySevenCashEvent(
                event_id="cash-after-maturity",
                collection_date=date(2026, 8, 4),
                amount=Decimal("80.00"),
            ),
        ),
    )

    first, after_maturity = result.allocations
    assert first.interest_due == Decimal("21.00")
    assert first.interest_paid == Decimal("10.00")
    assert first.closing_interest_arrears == Decimal("11.00")

    assert after_maturity.gap_days == 3
    assert after_maturity.interest_days == 1
    assert after_maturity.interest_holiday_days == 0
    assert after_maturity.opening_interest_arrears == Decimal("11.00")
    assert after_maturity.interest_due == Decimal("32.00")
    assert after_maturity.interest_paid == Decimal("32.00")
    assert after_maturity.principal_paid == Decimal("48.00")
    assert after_maturity.closing_interest_arrears == Decimal("0.00")
