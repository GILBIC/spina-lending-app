from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from gilbic_backend.seven_by_seven_advance_schedule_allocation import (
    SevenBySevenAdvanceCapacityExceeded,
    SevenBySevenAdvanceRequiresCurrentSchedule,
    plan_verified_seven_by_seven_advance,
    store_verified_seven_by_seven_advance_allocations,
)


class FakeCursor:
    def __init__(self, *, schedule=None, rows=()):
        self.schedule = schedule
        self.rows = list(rows)
        self._result = None
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        normalized = " ".join(sql.split())
        if "from lending.loan_contract_schedules schedule" in normalized:
            self._result = self.schedule
        elif "from lending.loan_contract_installments_operational installment" in normalized:
            self._result = list(self.rows)
        elif "insert into lending.loan_installment_payment_allocations" in normalized:
            self._result = None
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}")

    def fetchone(self):
        return self._result

    def fetchall(self):
        return list(self._result or [])


def _row(
    installment_id,
    installment_number,
    due_date,
    operational_amount="50.00",
    principal_component="29.00",
    interest_component="21.00",
    allocated_amount="0.00",
    removed=False,
):
    return (
        installment_id,
        installment_number,
        due_date,
        Decimal(operational_amount),
        Decimal(principal_component),
        Decimal(interest_component),
        Decimal(allocated_amount),
        removed,
    )


def test_advance_allocates_future_rows_oldest_first_with_partial_final() -> None:
    cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(11, 1, date(2026, 8, 26), allocated_amount="50.00"),
            _row(12, 2, date(2026, 8, 27)),
            _row(13, 3, date(2026, 8, 28)),
            _row(14, 4, date(2026, 8, 29)),
        ),
    )

    plan = plan_verified_seven_by_seven_advance(
        cursor,
        loan_id=uuid4(),
        collection_date=date(2026, 8, 26),
        transaction_amount=Decimal("120.00"),
    )

    assert [
        (item.installment_id, item.effective_due_date, item.amount_applied)
        for item in plan
    ] == [
        (12, date(2026, 8, 27), Decimal("50.00")),
        (13, date(2026, 8, 28), Decimal("50.00")),
        (14, date(2026, 8, 29), Decimal("20.00")),
    ]


def test_advance_requires_all_past_due_and_today_to_be_cleared_first() -> None:
    cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(21, 1, date(2026, 8, 25), allocated_amount="40.00"),
            _row(22, 2, date(2026, 8, 26), allocated_amount="50.00"),
            _row(23, 3, date(2026, 8, 27)),
        ),
    )

    with pytest.raises(SevenBySevenAdvanceRequiresCurrentSchedule) as exc_info:
        plan_verified_seven_by_seven_advance(
            cursor,
            loan_id=uuid4(),
            collection_date=date(2026, 8, 26),
            transaction_amount=Decimal("20.00"),
        )

    assert "10.00 of Past Due and Due Today" in str(exc_info.value)


def test_second_partial_advance_continues_same_oldest_future_row() -> None:
    cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(31, 1, date(2026, 8, 26), allocated_amount="50.00"),
            _row(32, 2, date(2026, 8, 27), allocated_amount="20.00"),
            _row(33, 3, date(2026, 8, 28)),
        ),
    )

    plan = plan_verified_seven_by_seven_advance(
        cursor,
        loan_id=uuid4(),
        collection_date=date(2026, 8, 26),
        transaction_amount=Decimal("30.00"),
    )

    assert len(plan) == 1
    assert plan[0].installment_id == 32
    assert plan[0].amount_applied == Decimal("30.00")


def test_advance_rejects_amount_above_remaining_future_capacity() -> None:
    cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(41, 1, date(2026, 8, 26), allocated_amount="50.00"),
            _row(42, 2, date(2026, 8, 27), allocated_amount="25.00"),
        ),
    )

    with pytest.raises(SevenBySevenAdvanceCapacityExceeded) as exc_info:
        plan_verified_seven_by_seven_advance(
            cursor,
            loan_id=uuid4(),
            collection_date=date(2026, 8, 26),
            transaction_amount=Decimal("30.00"),
        )

    assert "exceeds remaining future 7x7 capacity by 5.00" in str(exc_info.value)


def test_store_advance_allocations_uses_future_oldest_first_basis() -> None:
    plan_cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(51, 1, date(2026, 8, 26), allocated_amount="50.00"),
            _row(52, 2, date(2026, 8, 27)),
            _row(53, 3, date(2026, 8, 28)),
        ),
    )
    instructions = plan_verified_seven_by_seven_advance(
        plan_cursor,
        loan_id=uuid4(),
        collection_date=date(2026, 8, 26),
        transaction_amount=Decimal("70.00"),
    )
    cursor = FakeCursor(schedule=(uuid4(), "daily"))
    transaction_id = uuid4()
    actor_id = uuid4()

    store_verified_seven_by_seven_advance_allocations(
        cursor,
        transaction_id=transaction_id,
        actor_user_id=actor_id,
        instructions=instructions,
    )

    inserts = [
        item
        for item in cursor.executed
        if "insert into lending.loan_installment_payment_allocations" in item[0]
    ]
    assert len(inserts) == 2
    assert "'future_advance_oldest_first'" in inserts[0][0]
    assert inserts[0][1][0] == 52
    assert inserts[0][1][2] == Decimal("50.00")
    assert inserts[0][1][3] == f"seven-by-seven-advance:{transaction_id}"
    assert inserts[1][1][0] == 53
    assert inserts[1][1][2] == Decimal("20.00")
