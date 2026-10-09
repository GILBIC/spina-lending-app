"""Exercise real employee commands with synthetic, memory-backed persistence."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from gilbic_backend.employee_operations import EmployeeConflict
from gilbic_backend.employee_operations_models import ACTION_ADAPTER
from gilbic_backend.employee_operations_payroll import _advance_allocations
from gilbic_backend.employee_operations_repository import EmployeeTransaction

EMPLOYEE, OWNER, DEVICE = UUID(int=1), UUID(int=2), UUID(int=3)


class MemoryTransaction(EmployeeTransaction):
    """Replace only database reads/writes; retain rules, roles and fingerprints."""

    def __init__(self, monkeypatch, *, hire_date="2024-01-01", opening=2400):
        super().__init__(
            None, SimpleNamespace(user_id=EMPLOYEE, registered_device_id=DEVICE)
        )
        monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(OWNER))
        self.today = date(2026, 10, 9)
        self.rows = {}
        self.seed(
            "profiles",
            EMPLOYEE,
            {
                "active": True,
                "hire_date": hire_date,
                "daily_rate": "500.00",
                "ordinary_leave_days_per_year": 5,
                "staff_manager": False,
            },
        )
        self.seed(
            "leave_ledger",
            uuid4(),
            {
                "kind": "opening",
                "as_of": "2026-10-09",
                "minutes": opening,
            },
        )

    def seed(self, domain, identity, payload, status="recorded", version=1):
        row = {
            "id": str(identity),
            "employee_id": str(EMPLOYEE),
            "version": version,
            "status": status,
            "payload": deepcopy(payload),
            "created_by": str(EMPLOYEE),
            "created_at": "2026-10-09T00:00:00+00:00",
            "updated_at": "2026-10-09T00:00:00+00:00",
        }
        self.rows.setdefault(domain, {})[str(identity)] = row
        return deepcopy(row)

    def all(self, domain, employee_id=None):
        return [
            deepcopy(row)
            for row in self.rows.get(domain, {}).values()
            if employee_id is None or row["employee_id"] == str(employee_id)
        ]

    def get(self, domain, identity, *, required=True):
        row = self.rows.get(domain, {}).get(str(identity))
        if row is None and required:
            raise EmployeeConflict("The requested employee record does not exist")
        return deepcopy(row)

    def save(self, domain, identity, employee_id, payload, status, *, expected=None):
        before = self.get(domain, identity, required=False)
        version = before["version"] if before else 0
        if version != (self.command.expected_version if expected is None else expected):
            raise EmployeeConflict("The record changed")
        assert str(employee_id) == str(EMPLOYEE)
        return self.seed(domain, identity, payload, status, version + 1)

    def effective_profile(self, employee_id, on_date):
        return self.profile(employee_id)["payload"]

    def call(self, action, *, actor=OWNER, **payload):
        self.actor = SimpleNamespace(user_id=actor, registered_device_id=DEVICE)
        self._command = ACTION_ADAPTER.validate_python(
            {
                "action": action,
                "id": uuid4(),
                "request_id": uuid4(),
                "employee_id": EMPLOYEE,
                "expected_version": 0,
                **payload,
            }
        )
        return self.execute()


def conversion_request(tx, *, as_of="2026-10-09", minutes=2400):
    request = tx.call(
        "leave_conversion_request",
        actor=EMPLOYEE,
        as_of=as_of,
        minutes=minutes,
        reason="Convert eligible unused leave",
    )
    return tx.call(
        "request_decide",
        id=request["id"],
        expected_version=1,
        decision="approved",
        reason="Reviewed conversion",
    )


def prepare_conversion(tx, request):
    return tx.call(
        "payroll_prepare",
        week_start="2026-10-04",
        payroll_kind="leave_conversion",
        leave_conversion_request_id=request["id"],
        withholding_override="0.00",
        withholding_basis="Reviewed zero withholding",
        reason="Leave conversion",
    )


def approve(tx, payroll):
    return tx.call(
        "payroll_approve",
        id=payroll["id"],
        expected_version=payroll["version"],
        decision="approved",
        reason="Reviewed payroll",
    )


def pay(
    tx,
    payroll,
    *,
    amount="2500.00",
    occurred_at="2026-10-09T09:00:00+08:00",
    result="completed",
):
    return tx.call(
        "payroll_payment",
        id=payroll["id"],
        expected_version=payroll["version"],
        amount=amount,
        occurred_at=occurred_at,
        payment_method="cash",
        employee_acknowledgment="Received salary",
        result=result,
    )


def test_future_leave_entitlement_cannot_be_prepared_for_immediate_payment(monkeypatch):
    tx = MemoryTransaction(monkeypatch, hire_date="2026-01-01", opening=0)
    request = conversion_request(tx, as_of="2027-10-09")
    with pytest.raises(EmployeeConflict, match="[Ee]ligible|[Ff]uture|[Ee]ntitlement"):
        prepare_conversion(tx, request)
    assert tx.all("payroll") == []
    assert tx.all("payments") == []


@pytest.mark.parametrize("stage", ["approval", "payment"])
@pytest.mark.parametrize(
    "occurred_at", ["2026-10-09T09:00:00+08:00", "2027-10-09T09:00:00+08:00"]
)
def test_existing_future_conversion_snapshot_cannot_be_approved_or_paid(
    monkeypatch, stage, occurred_at
):
    tx = MemoryTransaction(monkeypatch, hire_date="2026-01-01", opening=0)
    request = conversion_request(tx, as_of="2027-10-09")
    identity = uuid4()
    fingerprint, versions = tx.fingerprint(EMPLOYEE, identity)
    # Snapshot from before the guard: still must not allow an ineligible payout.
    payroll = tx.seed(
        "payroll",
        identity,
        {
            "payroll_kind": "leave_conversion",
            "period_end": "2027-10-09",
            "leave_conversion_request_id": request["id"],
            "conversion_minutes": 2400,
            "input_fingerprint": fingerprint,
            "input_versions": versions,
            "net_pay": "2500.00",
            "paid_amount": "0.00",
            "balance_due": "2500.00",
        },
        "draft" if stage == "approval" else "approved",
    )
    with pytest.raises(EmployeeConflict, match="[Ee]ligible|[Ff]uture|[Ee]ntitlement"):
        approve(tx, payroll) if stage == "approval" else pay(
            tx, payroll, occurred_at=occurred_at
        )
    assert tx.all("payments") == []
    assert tx.get("payroll", identity)["payload"]["paid_amount"] == "0.00"


def test_conversion_cannot_be_backdated_before_actual_eligibility(monkeypatch):
    tx = MemoryTransaction(monkeypatch, hire_date="2025-10-09")
    payroll = approve(tx, prepare_conversion(tx, conversion_request(tx)))
    with pytest.raises(EmployeeConflict, match="[Ee]ligible|[Ff]uture|[Ee]ntitlement"):
        pay(tx, payroll, occurred_at="2026-10-08T23:30:00+08:00")
    assert tx.all("payments") == []


def test_time_passing_since_approval_rechecks_conversion_entitlement(monkeypatch):
    tx = MemoryTransaction(monkeypatch)
    # Already-known future correction does not change the source fingerprint later.
    tx.seed(
        "leave_ledger",
        uuid4(),
        {"kind": "correction", "as_of": "2026-10-10", "minutes": -480},
    )
    payroll = approve(tx, prepare_conversion(tx, conversion_request(tx)))
    tx.today = date(2026, 10, 10)
    with pytest.raises(EmployeeConflict, match="[Ee]ligible|[Ee]ntitlement"):
        pay(tx, payroll, occurred_at="2026-10-10T09:00:00+08:00")
    assert tx.all("payments") == []


def test_partially_paid_conversion_rechecks_remaining_credit_entitlement(monkeypatch):
    tx = MemoryTransaction(monkeypatch)
    payroll = approve(tx, prepare_conversion(tx, conversion_request(tx)))
    partial = pay(tx, payroll, amount="1000.00")
    tx.call(
        "leave_balance_adjust",
        as_of="2026-10-09",
        minutes=-480,
        kind="correction",
        reason="Reviewed prior consumption",
    )
    with pytest.raises(EmployeeConflict, match="[Ee]ligible|[Ee]ntitlement"):
        pay(tx, partial, amount="1500.00")
    assert tx.get("payroll", payroll["id"])["payload"]["paid_amount"] == "1000.00"
    assert len(tx.all("payments")) == 1


@pytest.mark.parametrize("split", [False, True])
def test_valid_full_balance_conversion_settles_once_without_counting_own_reservation(
    monkeypatch, split
):
    tx = MemoryTransaction(monkeypatch)
    request = conversion_request(tx)
    assert tx.leave_balance(EMPLOYEE, tx.today)["available_minutes"] == 0
    payroll = approve(tx, prepare_conversion(tx, request))
    if split:
        payroll = pay(tx, payroll, amount="1000.00")
    paid = pay(tx, payroll, amount="1500.00" if split else "2500.00")
    assert paid["status"] == "paid"
    assert paid["payload"]["paid_amount"] == "2500.00"
    assert tx.get("requests", request["id"])["status"] == "settled"
    assert tx.leave_balance(EMPLOYEE, tx.today)["available_minutes"] == 0
    debits = [r for r in tx.all("leave_ledger") if r["payload"]["kind"] == "conversion"]
    assert [r["payload"]["minutes"] for r in debits] == [-2400]


def seed_advance(tx, *, disbursed=True):
    return tx.seed(
        "advances",
        uuid4(),
        {
            "amount": "200.00",
            "disbursed_amount": "200.00" if disbursed else "0.00",
            "outstanding_amount": "200.00" if disbursed else "0.00",
            "repaid_amount": "0.00",
            "installments": [
                {"due_date": "2026-10-10", "amount": "100.00"},
                {"due_date": "2026-10-17", "amount": "100.00"},
            ],
            "repayment_history": [],
        },
        "disbursed" if disbursed else "requested",
    )


def propose_terms(tx, advance):
    return tx.call(
        "advance_terms",
        actor=EMPLOYEE,
        id=advance["id"],
        expected_version=advance["version"],
        installments=[
            {"due_date": "2026-10-17", "amount": "100.00"},
            {"due_date": "2026-10-24", "amount": "100.00"},
        ],
        employee_acknowledgment="I agree to proposed dates",
        payroll_authorization="Prior salary recovery authority",
        reason="Request postponement",
    )


def allocations(tx, end=date(2026, 10, 10)):
    return _advance_allocations(tx, EMPLOYEE, end, uuid4(), Decimal("1000.00"))


def test_pending_disbursed_advance_reschedule_requires_payroll_review(monkeypatch):
    tx = MemoryTransaction(monkeypatch)
    advance = seed_advance(tx)
    assert allocations(tx)[0][0]["amount"] == "100.00"
    propose_terms(tx, advance)
    with pytest.raises(EmployeeConflict, match="[Tt]erms|[Rr]eschedule"):
        allocations(tx)
    assert (
        tx.get("advances", advance["id"])["payload"]["installments"]
        == advance["payload"]["installments"]
    )


@pytest.mark.parametrize(
    "decision,expected_due", [("approved", []), ("rejected", ["100.00"])]
)
def test_advance_terms_decision_applies_only_authorized_schedule(
    monkeypatch, decision, expected_due
):
    tx = MemoryTransaction(monkeypatch)
    proposal = propose_terms(tx, seed_advance(tx))
    decided = tx.call(
        "advance_decide",
        id=proposal["id"],
        expected_version=proposal["version"],
        decision=decision,
        reason="Independent review",
    )
    assert decided["status"] == "disbursed"
    assert "proposed_terms" not in decided["payload"]
    assert [item["amount"] for item in allocations(tx)[0]] == expected_due
    assert [item["amount"] for item in allocations(tx, date(2026, 10, 17))[0]] == [
        "100.00"
    ]


def test_undisbursed_terms_do_not_create_a_payroll_deduction(monkeypatch):
    tx = MemoryTransaction(monkeypatch)
    propose_terms(tx, seed_advance(tx, disbursed=False))
    assert allocations(tx) == ([], [])


@pytest.mark.parametrize("stage", ["approval", "payment"])
def test_existing_weekly_snapshot_cannot_skip_pending_advance_terms(monkeypatch, stage):
    tx = MemoryTransaction(monkeypatch)
    propose_terms(tx, seed_advance(tx))
    identity = uuid4()
    fingerprint, versions = tx.fingerprint(EMPLOYEE, identity)
    payroll = tx.seed(
        "payroll",
        identity,
        {
            "payroll_kind": "weekly",
            "period_end": "2026-10-10",
            "input_fingerprint": fingerprint,
            "input_versions": versions,
            "advance_allocations": [],
            "net_pay": "2500.00",
            "paid_amount": "0.00",
            "balance_due": "2500.00",
        },
        "draft" if stage == "approval" else "approved",
    )
    with pytest.raises(EmployeeConflict, match="[Tt]erms|[Rr]eschedule"):
        approve(tx, payroll) if stage == "approval" else pay(tx, payroll)
    assert tx.all("payments") == []


def test_eligible_conversion_uses_manila_payout_date(monkeypatch):
    tx = MemoryTransaction(monkeypatch, hire_date="2025-10-09")
    payroll = approve(tx, prepare_conversion(tx, conversion_request(tx)))
    paid = pay(tx, payroll, occurred_at="2026-10-08T16:01:00+00:00")
    assert paid["status"] == "paid"
