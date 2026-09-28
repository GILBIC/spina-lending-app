"""Payroll audit regressions using the existing guarded disposable fixture."""

from datetime import date
from uuid import uuid4

import pytest
import test_employee_operations_postgres as employee_cases
from gilbic_backend.employee_authorization import EmployeeAccessDenied
from gilbic_backend.employee_operations import EmployeeConflict

database = employee_cases.database
pay_all = employee_cases.pay_all
pytestmark = employee_cases.pytestmark


def opening(case, **changes):
    fields = {
        "employee_id": case.users["one"].user_id,
        "year": 2026,
        "through_date": "2026-09-19",
        "basic_earned": "96000.00",
        "taxable_earned": "300000.00",
        "tax_withheld": "10000.00",
        "thirteenth_paid": "0.00",
        "other_benefits_paid": "0.00",
        "source": "Synthetic independently reviewed opening payslips",
    }
    fields.update(changes)
    return case.call("owner", "payroll_history_import", **fields)


def annual(case, *, kind="thirteenth_month", **changes):
    fields = {
        "employee_id": case.users["one"].user_id,
        "week_start": "2026-09-19",
        "payroll_kind": kind,
        "reason": "Synthetic reviewed annual reconciliation",
    }
    fields.update(changes)
    return case.call("manager", "payroll_prepare", **fields)


def enable_tax(case):
    employee = case.users["one"].user_id
    profile = case.record("profiles", employee)
    fields = dict(profile["payload"])
    fields.pop("full_name")
    fields["tax_exempt"] = False
    case.call(
        "owner",
        "profile_save",
        id=employee,
        employee_id=employee,
        expected_version=profile["version"],
        **fields,
    )


def conversion(case, *, tax="500.00"):
    employee = case.users["one"].user_id
    request = case.call(
        "one",
        "leave_conversion_request",
        employee_id=employee,
        as_of="2026-09-19",
        minutes=480,
        reason="Synthetic conversion of earned leave",
    )
    case.call(
        "manager",
        "request_decide",
        id=request["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Synthetic reviewed credits",
    )
    return case.call(
        "manager",
        "payroll_prepare",
        employee_id=employee,
        week_start="2026-09-19",
        payroll_kind="leave_conversion",
        leave_conversion_request_id=request["id"],
        withholding_override=tax,
        withholding_basis="Synthetic reviewed tax amount",
        reason="Synthetic leave conversion settlement",
    )


def test_paid_annual_refund_is_not_refunded_again_on_separation(database):
    case = database
    employee = case.users["one"].user_id
    enable_tax(case)
    opening(case)
    leave = case.workspace("one")["leave_balances"][0]["available_minutes"]
    case.call(
        "owner",
        "leave_balance_adjust",
        employee_id=employee,
        as_of="2026-09-19",
        minutes=-leave,
        kind="correction",
        reason="Synthetic no remaining conversion credits",
    )
    original = annual(case)
    assert case.record("payroll", original["id"])["payload"]["net_pay"] == "10500.00"
    pay_all(case, original, employee)
    following = annual(case, kind="separation")
    payload = case.record("payroll", following["id"])["payload"]
    assert payload["annual_facts"]["withheld"] == "7500.00"
    assert payload["net_pay"] == "0.00"


def test_paid_leave_conversion_withholding_is_in_next_annual_facts(database):
    case = database
    enable_tax(case)
    opening(case)
    payroll = conversion(case)
    pay_all(case, payroll, case.users["one"].user_id)
    with pytest.raises(EmployeeConflict, match="taxable/exempt"):
        annual(case)
    result = annual(
        case,
        withholding_override="120.00",
        withholding_basis="Synthetic reviewed annual reconciliation including conversion treatment",
    )
    assert (
        case.record("payroll", result["id"])["payload"]["annual_facts"]["withheld"]
        == "10500.00"
    )


def test_zero_withholding_on_paid_conversion_is_not_inferred_to_mean_exempt(database):
    case = database
    enable_tax(case)
    opening(case)
    payroll = conversion(case, tax="0.00")
    pay_all(case, payroll, case.users["one"].user_id)
    original = case.record("payroll", payroll["id"])
    with pytest.raises(EmployeeConflict, match="taxable/exempt"):
        annual(case)
    assert case.record("payroll", payroll["id"]) == original


def test_partial_annual_refund_blocks_next_run_until_fully_settled(database):
    case = database
    employee = case.users["one"].user_id
    enable_tax(case)
    opening(case)
    original = annual(case)
    case.call(
        "owner",
        "payroll_approve",
        id=original["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Synthetic reviewed amount",
    )
    payment = {
        "id": original["id"],
        "employee_id": employee,
        "occurred_at": "2026-09-19T18:00:00+08:00",
        "payment_method": "cash",
        "employee_acknowledgment": "Synthetic receipt acknowledgment",
        "result": "completed",
    }
    case.call(
        "owner", "payroll_payment", expected_version=2, amount="100.00", **payment
    )
    with pytest.raises(EmployeeConflict, match="[Ss]ettle.*tax"):
        annual(case, kind="separation")
    case.call(
        "owner", "payroll_payment", expected_version=3, amount="10400.00", **payment
    )
    following = annual(
        case,
        kind="separation",
        withholding_override="0.00",
        withholding_basis="Synthetic explicitly reviewed new tax delta",
    )
    assert (
        case.record("payroll", following["id"])["payload"]["annual_facts"]["withheld"]
        == "7500.00"
    )


@pytest.mark.parametrize(
    "start,through,year",
    [
        ("2026-09-13", "2026-09-15", 2026),
        ("2025-12-28", "2025-12-31", 2025),
        ("2025-12-28", "2026-01-01", 2026),
    ],
)
@pytest.mark.parametrize("history_first", [True, False])
def test_opening_history_and_week_cannot_overlap_in_either_order(
    database, start, through, year, history_first
):
    case = database
    start_date = date.fromisoformat(start)
    case.week(start=start_date)
    if history_first:
        opening(case, year=year, through_date=through)
        with pytest.raises(EmployeeConflict, match="overlap"):
            case.payroll(start=start_date)
    else:
        case.payroll(start=start_date)
        with pytest.raises(EmployeeConflict, match="overlap"):
            opening(case, year=year, through_date=through)


def test_settled_zero_net_conversion_cannot_replace_snapshot_or_consume_leave_twice(
    database,
):
    case = database
    employee = case.users["one"].user_id
    opening(case)
    payroll = conversion(case, tax="800.00")
    pay_all(case, payroll, employee)
    original = case.record("payroll", payroll["id"])
    assert original["status"] == "paid" and original["payload"]["paid_amount"] == "0.00"
    before = case.workspace("one")
    with pytest.raises(EmployeeConflict, match="cannot be overwritten"):
        annual(case, id=payroll["id"], expected_version=original["version"])
    assert case.record("payroll", payroll["id"]) == original
    after = case.workspace("one")
    assert after["leave_balances"] == before["leave_balances"]
    assert after["payments"] == before["payments"]


def correction_fields(case, original, **changes):
    fields = dict(original["payload"])
    fields.update(
        employee_id=case.users["one"].user_id,
        original_history_id=original["id"],
        original_expected_version=original["version"],
        reason="Synthetic corrected source document",
    )
    fields.update(changes)
    return fields


def test_reviewed_year_opening_then_full_week_has_nonoverlapping_annual_totals(
    database,
):
    case = database
    opening(case, through_date="2026-01-03")
    case.week(start=date(2026, 1, 4))
    weekly = case.payroll(start=date(2026, 1, 4))
    pay_all(case, weekly, case.users["one"].user_id)
    result = annual(case, week_start="2026-01-10")
    facts = case.record("payroll", result["id"])["payload"]["annual_facts"]
    assert facts["basic"] == "100800.00"
    assert facts["taxable"] == "305400.00"


def test_corrected_opening_cutoff_can_release_a_nonoverlapping_full_week(database):
    case = database
    result = opening(case, through_date="2026-09-15")
    original = case.record("payroll_history", result["id"])
    case.call(
        "owner",
        "payroll_history_correct",
        **correction_fields(case, original, through_date="2026-09-12"),
    )
    case.week()
    weekly = case.payroll()
    pay_all(case, weekly, case.users["one"].user_id)
    result = annual(case)
    assert (
        case.record("payroll", result["id"])["payload"]["annual_facts"]["basic"]
        == "100800.00"
    )


def test_history_correction_keeps_original_and_uses_only_latest_facts_and_invalidates_approval(
    database,
):
    case = database
    employee = case.users["one"].user_id
    opening_result = opening(case)
    original = case.record("payroll_history", opening_result["id"])
    assert case.workspace("owner")["payroll_history"][0]["allowed_actions"] == [
        "payroll_history_correct"
    ]
    assert case.workspace("manager")["payroll_history"][0]["allowed_actions"] == []
    first = annual(case)
    case.call(
        "owner",
        "payroll_approve",
        id=first["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Synthetic original review",
    )
    request = dict(
        action="payroll_history_correct",
        id=str(uuid4()),
        request_id=str(uuid4()),
        expected_version=0,
        **correction_fields(case, original, basic_earned="120000.00"),
    )
    result = case.run("owner", request)
    assert case.run("owner", request)["replayed"]
    assert case.record("payroll_history", original["id"]) == original
    visible = {r["id"]: r for r in case.workspace("owner")["payroll_history"]}
    assert visible[original["id"]]["allowed_actions"] == []
    assert visible[result["id"]]["allowed_actions"] == ["payroll_history_correct"]
    assert case.record("payroll", first["id"])["status"] == "stale"
    next_run = annual(
        case,
        kind="separation",
        withholding_override="0.00",
        withholding_basis="Synthetic reviewed tax delta",
    )
    assert (
        case.record("payroll", next_run["id"])["payload"]["annual_facts"]["basic"]
        == "120000.00"
    )
    with pytest.raises(EmployeeConflict, match="current|superseded"):
        case.call(
            "owner", "payroll_history_correct", **correction_fields(case, original)
        )
    corrected = case.record("payroll_history", result["id"])
    case.call(
        "owner",
        "payroll_history_correct",
        **correction_fields(case, corrected, basic_earned="144000.00"),
    )
    revised = annual(
        case,
        id=next_run["id"],
        expected_version=1,
        kind="separation",
        withholding_override="0.00",
        withholding_basis="Synthetic reviewed tax delta",
    )
    assert (
        case.record("payroll", revised["id"])["payload"]["annual_facts"]["basic"]
        == "144000.00"
    )


def test_history_correction_requires_owner_matching_employee_current_version_and_no_overlap(
    database,
):
    case = database
    result = opening(case, through_date="2026-09-12")
    original = case.record("payroll_history", result["id"])
    fields = correction_fields(case, original)
    with pytest.raises(EmployeeAccessDenied):
        case.call("manager", "payroll_history_correct", **fields)
    with pytest.raises(EmployeeAccessDenied):
        case.call(
            "owner",
            "payroll_history_correct",
            **dict(fields, employee_id=case.users["two"].user_id),
        )
    with pytest.raises(EmployeeConflict, match="version|changed"):
        case.call(
            "owner",
            "payroll_history_correct",
            **dict(fields, original_expected_version=2),
        )
    case.week()
    case.payroll()
    with pytest.raises(EmployeeConflict, match="overlap"):
        case.call(
            "owner",
            "payroll_history_correct",
            **dict(fields, through_date="2026-09-15"),
        )
    assert case.record("payroll_history", original["id"]) == original
