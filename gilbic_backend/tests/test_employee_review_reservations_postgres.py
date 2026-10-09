"""Durable review and settlement proofs on the guarded disposable database."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import test_employee_operations_postgres as employee_cases
from gilbic_backend.employee_operations import EmployeeConflict
from gilbic_backend.employee_operations_repository import EmployeeTransaction

database = employee_cases.database
pytestmark = employee_cases.pytestmark


def transaction(case):
    return EmployeeTransaction(case.connection.cursor(), case.users["one"])


def approve(case, payroll):
    return case.call(
        "owner",
        "payroll_approve",
        id=payroll["id"],
        employee_id=case.users["one"].user_id,
        expected_version=payroll["version"],
        decision="approved",
        reason="Synthetic reviewed payroll",
    )


def payment(case, payroll, amount, *, occurred_at="2026-09-20T09:00:00+08:00"):
    return {
        "action": "payroll_payment",
        "request_id": str(uuid4()),
        "id": payroll["id"],
        "employee_id": str(case.users["one"].user_id),
        "expected_version": payroll["version"],
        "amount": amount,
        "occurred_at": occurred_at,
        "payment_method": "cash",
        "employee_acknowledgment": "Synthetic employee acknowledgment",
        "result": "completed",
    }


def test_partial_separation_reserves_leave_and_final_payment_replays_once(database):
    case = database
    employee = case.users["one"].user_id
    day = date(2026, 9, 20)
    available = transaction(case).leave_balance(employee, day)["available_minutes"]
    case.call(
        "owner",
        "leave_balance_adjust",
        employee_id=employee,
        as_of=day.isoformat(),
        minutes=2400 - available,
        kind="correction",
        reason="Synthetic reviewed balance of exactly five unused days",
    )
    case.call(
        "owner",
        "payroll_history_import",
        employee_id=employee,
        year=2026,
        through_date=day.isoformat(),
        basic_earned="0.00",
        taxable_earned="0.00",
        tax_withheld="0.00",
        thirteenth_paid="0.00",
        other_benefits_paid="0.00",
        source="Synthetic reviewed zero opening payroll facts",
    )
    prepared = case.call(
        "manager",
        "payroll_prepare",
        employee_id=employee,
        week_start=day.isoformat(),
        payroll_kind="separation",
        withholding_override="0.00",
        withholding_basis="Synthetic reviewed zero withholding",
        reason="Synthetic separation settlement",
    )
    assert case.record("payroll", prepared["id"])["payload"]["net_pay"] == "4000.00"
    approved = approve(case, prepared)
    assert transaction(case).leave_balance(employee, day)["reserved_minutes"] == 2400
    first_command = payment(case, approved, "1500.00")
    partial = case.run("owner", first_command)
    assert case.run("owner", first_command)["replayed"]
    assert case.record("payroll", partial["id"])["status"] == "partially_paid"
    balance = transaction(case).leave_balance(employee, day)
    assert balance["reserved_minutes"] == 2400
    assert balance["available_minutes"] == 0

    request = case.call(
        "one",
        "leave_conversion_request",
        employee_id=employee,
        as_of=day.isoformat(),
        minutes=2400,
        reason="Synthetic competing conversion",
    )
    decision_request = str(uuid4())
    with pytest.raises(EmployeeConflict, match="Insufficient eligible"):
        case.call(
            "manager",
            "request_decide",
            request_id=decision_request,
            id=request["id"],
            employee_id=employee,
            expected_version=request["version"],
            decision="approved",
            reason="Synthetic competing approval must conflict",
        )
    assert case.record("requests", request["id"])["status"] == "pending"
    assert (
        case.connection.execute(
            "select count(*) as count from core.employee_action_receipts where request_id=%s",
            (decision_request,),
        ).fetchone()["count"]
        == 0
    )

    final_command = payment(case, partial, "2500.00")
    paid = case.run("owner", final_command)
    assert case.run("owner", final_command)["replayed"]
    assert case.record("payroll", paid["id"])["status"] == "paid"
    tx = transaction(case)
    balance = tx.leave_balance(employee, day)
    assert balance["reserved_minutes"] == 0
    assert balance["available_minutes"] == 0
    debits = [
        r
        for r in tx.all("leave_ledger", employee)
        if r["payload"]["kind"] == "conversion"
    ]
    assert [r["payload"]["minutes"] for r in debits] == [-2400]
    assert debits[0]["payload"]["linked_payroll_id"] == prepared["id"]
    assert [r["payload"]["amount"] for r in tx.all("payments", employee)] == [
        "1500.00",
        "2500.00",
    ]


def test_future_capture_receipt_needs_approved_correction_after_time_passes(
    database, monkeypatch
):
    case = database
    employee = case.users["one"].user_id

    class Clock(datetime):
        instant = datetime(2026, 9, 18, 21, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return (
                cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)
            )

    for module in (
        "employee_operations",
        "employee_operations_repository",
        "employee_operations_payroll",
    ):
        monkeypatch.setattr(f"gilbic_backend.{module}.datetime", Clock)
    case.call(
        "owner",
        "schedule_save",
        employee_id=employee,
        effective_from="2026-09-13",
        work_days=[6],
        start_time="06:00",
        end_time="15:00",
        meal_minutes=60,
        reason="Synthetic Saturday-only schedule",
    )
    for offset in range(7):
        case.call(
            "owner",
            "calendar_save",
            work_date=(date(2026, 9, 13) + timedelta(days=offset)).isoformat(),
            day_kind="ordinary",
            source="Synthetic reviewed calendar",
        )
    case.call(
        "owner",
        "statutory_month_save",
        employee_id=employee,
        month="2026-09-01",
        sss_employee="0.00",
        sss_employer="0.00",
        philhealth_employee="0.00",
        philhealth_employer="0.00",
        pagibig_employee="0.00",
        pagibig_employer="0.00",
        employer_other="0.00",
        prior_employee_deductions="0.00",
        compensation_basis="Explicit synthetic zero fixture",
        source="Synthetic reviewed monthly totals",
    )
    previous = None
    events = []
    for sequence, (kind, hour) in enumerate(
        (
            ("clock_in", "06:00"),
            ("break_start", "12:00"),
            ("break_end", "13:00"),
            ("clock_out", "15:00"),
        ),
        start=1,
    ):
        command = {
            "action": "attendance_record",
            "request_id": str(uuid4()),
            "id": str(uuid4()),
            "employee_id": str(employee),
            "expected_version": 0,
            "event_type": kind,
            "captured_at": f"2026-09-19T{hour}:00+08:00",
            "device_id": str(case.users["one"].registered_device_id),
            "previous_event_id": previous,
            "sequence": sequence,
            "offline": False,
        }
        result = case.run("one", command)
        assert result["status"] == "pending_review"
        previous = result["id"]
        events.append((command, case.record("attendance", previous)))

    Clock.instant = datetime(2026, 9, 19, 8, tzinfo=UTC)
    later = transaction(case).attendance(employee, date(2026, 9, 19))
    assert later["status"] == "pending_review"
    assert "Capture time needs review" in later["issues"]
    for command, original in events:
        replayed = case.run("one", command)
        assert replayed["replayed"] and replayed["status"] == "pending_review"
        assert case.record("attendance", original["id"]) == original
    with pytest.raises(EmployeeConflict, match="incomplete or conflicting"):
        case.payroll()
    assert transaction(case).all("payroll", employee) == []

    correction = case.call(
        "one",
        "correction_request",
        employee_id=employee,
        work_date="2026-09-19",
        clock_in="2026-09-19T06:00:00+08:00",
        clock_out="2026-09-19T15:00:00+08:00",
        unpaid_break_minutes=60,
        reason="Synthetic independently verified completed work",
    )
    assert (
        transaction(case).attendance(employee, date(2026, 9, 19))["status"]
        == "pending_review"
    )
    with pytest.raises(EmployeeConflict, match="still need review"):
        case.payroll()
    case.call(
        "manager",
        "request_decide",
        id=correction["id"],
        employee_id=employee,
        expected_version=correction["version"],
        decision="approved",
        reason="Synthetic approved actual working time",
    )
    accepted = transaction(case).attendance(employee, date(2026, 9, 19))
    assert accepted["status"] == "accepted" and accepted["working_minutes"] == 480
    approved = approve(case, case.payroll())
    case.run(
        "owner",
        payment(case, approved, "900.00", occurred_at="2026-09-19T16:00:00+08:00"),
    )
    assert case.record("payroll", approved["id"])["status"] == "paid"
    assert all(
        case.record("attendance", original["id"]) == original for _, original in events
    )
