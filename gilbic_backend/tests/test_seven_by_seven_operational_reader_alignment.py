from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from gilbic_backend.seven_by_seven_advance_activation import (
    replay_verified_seven_by_seven_financial_state,
)
from gilbic_backend.seven_by_seven_advance_schedule_allocation import (
    SevenBySevenAdvanceCapacityExceeded,
    plan_verified_seven_by_seven_advance,
)
from gilbic_backend.seven_by_seven_schedule_allocation import (
    plan_verified_seven_by_seven_scheduled_payment,
)


class PlannerCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self._result = None
        self.executed = []
        self.schedule_id = uuid4()

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if "from lending.loan_contract_schedules schedule" in normalized:
            self._result = (self.schedule_id, "daily")
        elif "from lending.loan_contract_installments_operational installment" in normalized:
            self._result = list(self.rows)
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}")

    def fetchone(self):
        return self._result

    def fetchall(self):
        return list(self._result or [])


def _operational_row(
    installment_id: int,
    installment_number: int,
    due_date: date,
    operational_amount: str,
    operational_principal: str,
    operational_interest: str,
    allocated_amount: str,
    removed: bool = False,
):
    return (
        installment_id,
        installment_number,
        due_date,
        Decimal(operational_amount),
        Decimal(operational_principal),
        Decimal(operational_interest),
        Decimal(allocated_amount),
        removed,
    )


def test_normal_payment_uses_shortened_operational_amount_and_ignores_removed_tail() -> None:
    cursor = PlannerCursor(
        (
            _operational_row(
                11,
                1,
                date(2026, 8, 28),
                "30.00",
                "9.00",
                "21.00",
                "20.00",
            ),
            _operational_row(
                12,
                2,
                date(2026, 8, 29),
                "0.00",
                "0.00",
                "0.00",
                "0.00",
                True,
            ),
        )
    )

    plan = plan_verified_seven_by_seven_scheduled_payment(
        cursor,
        loan_id=uuid4(),
        collection_date=date(2026, 8, 28),
        transaction_amount=Decimal("10.00"),
    )

    assert [(item.installment_id, item.amount_applied) for item in plan] == [
        (11, Decimal("10.00"))
    ]
    reader_sql = next(
        sql for sql, _params in cursor.executed if "loan_contract_installments_operational" in sql
    )
    assert "installment.operational_amount" in reader_sql
    assert "loan_installment_active_advance" in reader_sql
    assert "installment.removed_from_operational_schedule" in reader_sql


def test_new_advance_uses_only_remaining_operational_capacity() -> None:
    cursor = PlannerCursor(
        (
            _operational_row(
                21,
                1,
                date(2026, 8, 28),
                "30.00",
                "9.00",
                "21.00",
                "30.00",
            ),
            _operational_row(
                22,
                2,
                date(2026, 8, 29),
                "25.00",
                "4.00",
                "21.00",
                "20.00",
            ),
            _operational_row(
                23,
                3,
                date(2026, 8, 30),
                "0.00",
                "0.00",
                "0.00",
                "0.00",
                True,
            ),
        )
    )

    plan = plan_verified_seven_by_seven_advance(
        cursor,
        loan_id=uuid4(),
        collection_date=date(2026, 8, 28),
        transaction_amount=Decimal("5.00"),
    )
    assert [(item.installment_id, item.amount_applied) for item in plan] == [
        (22, Decimal("5.00"))
    ]

    with pytest.raises(SevenBySevenAdvanceCapacityExceeded):
        plan_verified_seven_by_seven_advance(
            PlannerCursor(cursor.rows),
            loan_id=uuid4(),
            collection_date=date(2026, 8, 28),
            transaction_amount=Decimal("6.00"),
        )


class ReplayCursor:
    def __init__(self):
        self._result = None
        self.executed = []
        self.installment_id = 31
        self.accepted_at = datetime(2026, 8, 27, tzinfo=timezone.utc)

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if "transaction.amount as receipt_amount" in normalized:
            self._result = []
        elif "active_advance.active_advance_allocated as amount_applied" in normalized:
            self._result = [
                (
                    self.installment_id,
                    1,
                    date(2026, 8, 28),
                    Decimal("30.00"),
                    self.accepted_at,
                )
            ]
        elif "select distinct adjustment.no_collection_date" in normalized:
            self._result = []
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}")

    def fetchall(self):
        return list(self._result or [])


def test_advance_activation_replays_active_advance_not_gross_historical_advance() -> None:
    cursor = ReplayCursor()

    replay = replay_verified_seven_by_seven_financial_state(
        cursor,
        loan_id=uuid4(),
        original_principal=Decimal("3000.00"),
        daily_interest_per_1000=Decimal("7.00"),
        payment_start=date(2026, 8, 28),
        through_date=date(2026, 8, 28),
    )

    assert replay.matured_advance_row_count == 1
    assert replay.historical_events[0].amount == Decimal("30.00")
    assert replay.result.closing_remaining_principal == Decimal("2991.00")
    matured_sql = next(
        sql
        for sql, _params in cursor.executed
        if "active_advance.active_advance_allocated as amount_applied" in sql
    )
    assert "loan_installment_active_advance" in matured_sql
    assert "removed_from_operational_schedule = false" in matured_sql
