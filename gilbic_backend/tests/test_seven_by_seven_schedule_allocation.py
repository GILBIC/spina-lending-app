from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from gilbic_backend.seven_by_seven_schedule_allocation import (
    SevenBySevenExtraAllocationChoiceRequired,
    SevenBySevenScheduleAllocationConflict,
    SevenBySevenVerifiedScheduleNotFound,
    plan_verified_seven_by_seven_scheduled_payment,
    store_verified_seven_by_seven_scheduled_payment_allocations,
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
    operational_amount,
    principal_component,
    interest_component,
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


def test_scheduled_payment_clears_oldest_due_rows_without_spilling_future() -> None:
    cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(11, 1, date(2026, 8, 25), "50.00", "29.00", "21.00", "40.00"),
            _row(12, 2, date(2026, 8, 26), "50.00", "29.00", "21.00"),
            _row(13, 3, date(2026, 8, 27), "50.00", "29.00", "21.00"),
        ),
    )

    plan = plan_verified_seven_by_seven_scheduled_payment(
        cursor,
        loan_id=uuid4(),
        collection_date=date(2026, 8, 26),
        transaction_amount=Decimal("60.00"),
    )

    assert [(item.installment_id, item.amount_applied) for item in plan] == [
        (11, Decimal("10.00")),
        (12, Decimal("50.00")),
    ]
    assert all(item.installment_id != 13 for item in plan)


def test_scheduled_payment_requires_borrower_choice_for_true_extra() -> None:
    cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(11, 1, date(2026, 8, 25), "50.00", "29.00", "21.00", "40.00"),
            _row(12, 2, date(2026, 8, 26), "50.00", "29.00", "21.00"),
            _row(13, 3, date(2026, 8, 27), "50.00", "29.00", "21.00"),
        ),
    )

    with pytest.raises(SevenBySevenExtraAllocationChoiceRequired) as exc_info:
        plan_verified_seven_by_seven_scheduled_payment(
            cursor,
            loan_id=uuid4(),
            collection_date=date(2026, 8, 26),
            transaction_amount=Decimal("61.00"),
        )

    assert "1.00 beyond Past Due and Due Today" in str(exc_info.value)


def test_multiple_same_day_receipts_finish_the_same_contractual_row() -> None:
    cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(21, 1, date(2026, 8, 26), "50.00", "29.00", "21.00", "20.00"),
            _row(22, 2, date(2026, 8, 27), "50.00", "29.00", "21.00"),
        ),
    )

    plan = plan_verified_seven_by_seven_scheduled_payment(
        cursor,
        loan_id=uuid4(),
        collection_date=date(2026, 8, 26),
        transaction_amount=Decimal("30.00"),
    )

    assert len(plan) == 1
    assert plan[0].installment_id == 21
    assert plan[0].amount_applied == Decimal("30.00")


def test_verified_schedule_is_optional_only_for_legacy_transition_caller() -> None:
    cursor = FakeCursor(schedule=None)

    with pytest.raises(SevenBySevenVerifiedScheduleNotFound):
        plan_verified_seven_by_seven_scheduled_payment(
            cursor,
            loan_id=uuid4(),
            collection_date=date(2026, 8, 26),
            transaction_amount=Decimal("50.00"),
        )


def test_verified_7x7_operational_row_components_must_reconcile() -> None:
    cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(31, 1, date(2026, 8, 26), "50.00", "28.00", "21.00"),
        ),
    )

    with pytest.raises(SevenBySevenScheduleAllocationConflict):
        plan_verified_seven_by_seven_scheduled_payment(
            cursor,
            loan_id=uuid4(),
            collection_date=date(2026, 8, 26),
            transaction_amount=Decimal("50.00"),
        )


def test_store_schedule_allocations_keeps_receipt_and_rows_auditable() -> None:
    cursor = FakeCursor(schedule=(uuid4(), "daily"))
    actor_id = uuid4()
    transaction_id = uuid4()
    plan_cursor = FakeCursor(
        schedule=(uuid4(), "daily"),
        rows=(
            _row(41, 1, date(2026, 8, 25), "50.00", "29.00", "21.00", "40.00"),
            _row(42, 2, date(2026, 8, 26), "50.00", "29.00", "21.00"),
        ),
    )
    instructions = plan_verified_seven_by_seven_scheduled_payment(
        plan_cursor,
        loan_id=uuid4(),
        collection_date=date(2026, 8, 26),
        transaction_amount=Decimal("60.00"),
    )

    store_verified_seven_by_seven_scheduled_payment_allocations(
        cursor,
        transaction_id=transaction_id,
        actor_user_id=actor_id,
        instructions=instructions,
    )

    inserts = [item for item in cursor.executed if "loan_installment_payment_allocations" in item[0]]
    assert len(inserts) == 2
    assert inserts[0][1][0] == 41
    assert inserts[0][1][1] == transaction_id
    assert inserts[0][1][2] == Decimal("10.00")
    assert inserts[1][1][0] == 42
    assert inserts[1][1][2] == Decimal("50.00")
