"""Separation reserves unused leave until its single final ledger debit."""

import pytest
from gilbic_backend.employee_operations import EmployeeConflict
from test_employee_workflow_transitions import (
    EMPLOYEE,
    MemoryTransaction,
    approve,
    conversion_request,
    pay,
)


def prepare_separation(tx, **changes):
    return tx.call(
        "payroll_prepare",
        week_start="2026-10-09",
        payroll_kind="separation",
        withholding_override="0.00",
        withholding_basis="Synthetic reviewed zero tax",
        reason="Separation settlement",
        **changes,
    )


@pytest.fixture
def tx(monkeypatch):
    transaction = MemoryTransaction(monkeypatch)
    transaction.call(
        "payroll_history_import",
        year=2026,
        through_date="2026-10-09",
        basic_earned="0.00",
        taxable_earned="0.00",
        tax_withheld="0.00",
        thirteenth_paid="0.00",
        other_benefits_paid="0.00",
        source="Synthetic reviewed opening facts",
    )
    return transaction


@pytest.mark.parametrize("partial", [False, True])
def test_approved_separation_reserves_all_converted_leave(tx, partial):
    payroll = approve(tx, prepare_separation(tx))
    if partial:
        pay(tx, payroll, amount="1500.00")
    balance = tx.leave_balance(EMPLOYEE, tx.today)
    assert balance["available_minutes"] == 0
    assert balance["reserved_minutes"] == 2400


def test_partial_separation_prevents_second_conversion_and_still_settles(tx):
    payroll = pay(tx, approve(tx, prepare_separation(tx)), amount="1500.00")
    with pytest.raises(EmployeeConflict, match="Insufficient eligible"):
        conversion_request(tx)
    paid = pay(tx, payroll, amount="1000.00")
    assert paid["status"] == "paid"
    assert [r["payload"]["amount"] for r in tx.all("payments")] == [
        "1500.00",
        "1000.00",
    ]
    balance = tx.leave_balance(EMPLOYEE, tx.today)
    assert balance["available_minutes"] == 0
    assert balance["reserved_minutes"] == 0
    debits = [r for r in tx.all("leave_ledger") if r["payload"]["kind"] == "conversion"]
    assert [r["payload"]["minutes"] for r in debits] == [-2400]


def test_partial_separation_prevents_ordinary_leave_using_reserved_credits(tx):
    pay(tx, approve(tx, prepare_separation(tx)), amount="1500.00")
    with pytest.raises(EmployeeConflict, match="Insufficient eligible"):
        tx.call(
            "leave_request",
            actor=EMPLOYEE,
            work_date="2026-10-09",
            minutes=480,
            leave_kind="ordinary",
            reason="Synthetic request against reserved balance",
        )


def test_separation_final_payment_does_not_hide_a_new_entitlement_deficit(tx):
    payroll = pay(tx, approve(tx, prepare_separation(tx)), amount="1500.00")
    tx.call(
        "leave_balance_adjust",
        as_of="2026-10-09",
        minutes=-480,
        kind="correction",
        reason="Reviewed prior consumption",
    )
    with pytest.raises(EmployeeConflict, match="Insufficient eligible"):
        pay(tx, payroll, amount="1000.00")
    assert len(tx.all("payments")) == 1
    assert tx.get("payroll", payroll["id"])["payload"]["paid_amount"] == "1500.00"


def test_repreparing_unpaid_separation_excludes_its_own_reservation(tx):
    payroll = approve(tx, prepare_separation(tx))
    draft = prepare_separation(
        tx, id=payroll["id"], expected_version=payroll["version"]
    )
    assert draft["payload"]["conversion_minutes"] == 2400
    assert tx.leave_balance(EMPLOYEE, tx.today)["reserved_minutes"] == 0
    paid = pay(tx, approve(tx, draft))
    assert paid["status"] == "paid"
    assert tx.leave_balance(EMPLOYEE, tx.today)["available_minutes"] == 0


@pytest.mark.parametrize("decision", ["rejected", "stale"])
def test_unpaid_inactive_separation_does_not_reserve_leave(tx, decision):
    draft = prepare_separation(tx)
    if decision == "rejected":
        tx.call(
            "payroll_approve",
            id=draft["id"],
            expected_version=draft["version"],
            decision="rejected",
            reason="Reviewed rejection",
        )
    else:
        approve(tx, draft)
        tx.call(
            "leave_balance_adjust",
            as_of="2026-10-09",
            minutes=0,
            kind="correction",
            reason="Reviewed correction invalidates unpaid snapshot",
        )
    assert tx.get("payroll", draft["id"])["status"] == decision
    assert tx.leave_balance(EMPLOYEE, tx.today)["available_minutes"] == 2400
    assert conversion_request(tx)["status"] == "approved"


def test_existing_partial_separation_reserves_without_a_new_ledger_record(tx):
    original = prepare_separation(tx)
    tx.seed(
        "payroll",
        original["id"],
        {**original["payload"], "paid_amount": "1500.00", "balance_due": "1000.00"},
        status="partially_paid",
        version=3,
    )
    assert tx.leave_balance(EMPLOYEE, tx.today)["available_minutes"] == 0
