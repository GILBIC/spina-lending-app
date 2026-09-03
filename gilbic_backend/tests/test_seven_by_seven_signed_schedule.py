from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.seven_by_seven_signed_schedule import (
    SevenBySevenSignedScheduleError,
    generate_signed_seven_by_seven_schedule,
)


def test_signed_7x7_schedule_uses_agreed_daily_payment_not_interest_only() -> None:
    rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("3000.00"),
        agreed_daily_payment=Decimal("50.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=date(2026, 8, 27),
    )

    assert len(rows) == 104
    assert rows[0].installment_number == 1
    assert rows[0].due_date == date(2026, 8, 27)
    assert rows[0].contractual_amount == Decimal("50.00")
    assert rows[0].interest_component == Decimal("21.00")
    assert rows[0].principal_component == Decimal("29.00")
    assert rows[-1].installment_number == 104
    assert rows[-1].due_date == date(2026, 12, 8)
    assert rows[-1].contractual_amount == Decimal("34.00")
    assert rows[-1].interest_component == Decimal("21.00")
    assert rows[-1].principal_component == Decimal("13.00")
    assert sum(row.principal_component for row in rows) == Decimal("3000.00")


def test_signed_7x7_schedule_uses_canonical_started_thousand_interest_rule() -> None:
    rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("3500.00"),
        agreed_daily_payment=Decimal("60.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=date(2026, 9, 1),
    )

    assert rows[0].interest_component == Decimal("28.00")
    assert rows[0].principal_component == Decimal("32.00")
    assert rows[0].contractual_amount == Decimal("60.00")
    assert sum(row.principal_component for row in rows) == Decimal("3500.00")


def test_signed_7x7_schedule_reduces_only_the_final_row_for_exact_principal() -> None:
    rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("5000.00"),
        agreed_daily_payment=Decimal("100.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=date(2026, 10, 1),
    )

    assert len(rows) == 77
    assert all(row.contractual_amount == Decimal("100.00") for row in rows[:-1])
    assert rows[-1].principal_component == Decimal("60.00")
    assert rows[-1].interest_component == Decimal("35.00")
    assert rows[-1].contractual_amount == Decimal("95.00")
    assert sum(row.principal_component for row in rows) == Decimal("5000.00")


def test_signed_7x7_schedule_rejects_interest_only_or_lower_daily_amount() -> None:
    with pytest.raises(SevenBySevenSignedScheduleError):
        generate_signed_seven_by_seven_schedule(
            original_principal=Decimal("3000.00"),
            agreed_daily_payment=Decimal("21.00"),
            daily_interest_per_1000=Decimal("7.00"),
            first_due_date=date(2026, 8, 27),
        )

    with pytest.raises(SevenBySevenSignedScheduleError):
        generate_signed_seven_by_seven_schedule(
            original_principal=Decimal("3000.00"),
            agreed_daily_payment=Decimal("20.00"),
            daily_interest_per_1000=Decimal("7.00"),
            first_due_date=date(2026, 8, 27),
        )
