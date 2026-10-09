"""Receipt-time clock anomalies survive reads until an approved correction."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from gilbic_backend.employee_operations import EmployeeConflict
from test_employee_workflow_transitions import (
    DEVICE,
    EMPLOYEE,
    MemoryTransaction,
    approve,
    pay,
)

from gilbic_backend import employee_operations as domain
from gilbic_backend import employee_operations_payroll as payroll
from gilbic_backend import employee_operations_repository as repository


class Clock(datetime):
    instant = datetime(2026, 10, 9, 21, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return (
            cls.instant.astimezone(tz)
            if tz is not None
            else cls.instant.replace(tzinfo=None)
        )


@pytest.fixture
def tx(monkeypatch):
    monkeypatch.setattr(Clock, "instant", datetime(2026, 10, 9, 21, tzinfo=UTC))
    for module in (domain, repository, payroll):
        monkeypatch.setattr(module, "datetime", Clock)
    transaction = MemoryTransaction(monkeypatch)
    transaction.today = date(2026, 10, 10)
    transaction.rows["profiles"][str(EMPLOYEE)]["payload"].update(
        premium_pay_covered=True,
        holiday_pay_covered=True,
        gp_partial_day_policy="prorated",
        tax_exempt=True,
    )
    transaction.seed(
        "schedules",
        uuid4(),
        {
            "effective_from": "2026-01-01",
            "work_days": [6],
            "start_time": "06:00",
            "end_time": "15:00",
            "meal_minutes": 60,
        },
        status="active",
    )
    for offset in range(7):
        day = date(2026, 10, 4) + timedelta(days=offset)
        transaction.seed(
            "calendar",
            uuid4(),
            {"work_date": day.isoformat(), "day_kind": "ordinary"},
            status="reviewed",
        )
    transaction.seed(
        "statutory_months",
        uuid4(),
        {
            "month": "2026-10-01",
            "sss_employee": "0.00",
            "philhealth_employee": "0.00",
            "pagibig_employee": "0.00",
            "prior_employee_deductions": "0.00",
            "source": "Synthetic reviewed inputs",
        },
        status="reviewed",
    )
    return transaction


def record_shift(tx, *, order=(0, 1, 2, 3)):
    ids = [uuid4() for _ in range(4)]
    events = [
        ("clock_in", "06:00"),
        ("break_start", "12:00"),
        ("break_end", "13:00"),
        ("clock_out", "15:00"),
    ]
    return [
        tx.call(
            "attendance_record",
            actor=EMPLOYEE,
            id=ids[index],
            event_type=events[index][0],
            captured_at=f"2026-10-10T{events[index][1]}:00+08:00",
            device_id=DEVICE,
            previous_event_id=ids[index - 1] if index else None,
            sequence=index + 1,
            offline=True,
        )
        for index in order
    ]


def prepare_week(tx):
    return tx.call(
        "payroll_prepare", week_start="2026-10-04", reason="Synthetic reviewed week"
    )


def test_future_captured_shift_still_blocks_payroll_after_wall_clock_passes(tx):
    records = record_shift(tx)
    assert all(row["status"] == "pending_review" for row in records)
    with pytest.raises(EmployeeConflict, match="incomplete or conflicting"):
        prepare_week(tx)
    Clock.instant = datetime(2026, 10, 10, 8, tzinfo=UTC)
    later = tx.attendance(EMPLOYEE, tx.today)
    assert later["status"] == "pending_review"
    assert "Capture time needs review" in later["issues"]
    with pytest.raises(EmployeeConflict, match="incomplete or conflicting"):
        prepare_week(tx)
    assert tx.all("payroll") == []
    assert tx.all("payments") == []


def test_only_approved_correction_resolves_future_capture(tx):
    record_shift(tx)
    Clock.instant = datetime(2026, 10, 10, 8, tzinfo=UTC)
    correction = tx.call(
        "correction_request",
        actor=EMPLOYEE,
        work_date="2026-10-10",
        clock_in="2026-10-10T06:00:00+08:00",
        clock_out="2026-10-10T15:00:00+08:00",
        unpaid_break_minutes=60,
        reason="Synthetic independently verified completed shift",
    )
    assert tx.attendance(EMPLOYEE, tx.today)["status"] == "pending_review"
    tx.call(
        "request_decide",
        id=correction["id"],
        expected_version=correction["version"],
        decision="approved",
        reason="Reviewed actual working time",
    )
    accepted = tx.attendance(EMPLOYEE, tx.today)
    assert accepted["status"] == "accepted"
    assert accepted["working_minutes"] == 480
    paid = pay(
        tx,
        approve(tx, prepare_week(tx)),
        amount="600.00",
        occurred_at="2026-10-10T16:00:00+08:00",
    )
    assert paid["status"] == "paid"
    assert all(row["status"] == "pending_review" for row in tx.all("attendance"))


def test_out_of_order_offline_shift_resolves_when_missing_events_arrive(tx):
    Clock.instant = datetime(2026, 10, 10, 8, tzinfo=UTC)
    records = record_shift(tx, order=(3, 1, 0, 2))
    assert records[0]["status"] == "pending_review"
    accepted = tx.attendance(EMPLOYEE, tx.today)
    assert accepted["status"] == "accepted"
    assert accepted["working_minutes"] == 480
    assert prepare_week(tx)["payload"]["net_pay"] == "600.00"
