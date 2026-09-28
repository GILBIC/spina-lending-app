"""Calculation regressions; all facts below are synthetic and read only."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.employee_operations import EmployeeConflict
from gilbic_backend.employee_operations_payroll import _annual_facts


class Facts:
    def __init__(self, payroll, *, through="2026-09-19"):
        self.payroll = payroll
        self.history = {
            "id": str(uuid4()),
            "payload": {
                "year": 2026,
                "through_date": through,
                "basic_earned": "96000.00",
                "taxable_earned": "300000.00",
                "tax_withheld": "10000.00",
                "thirteenth_paid": "0.00",
                "other_benefits_paid": "0.00",
            },
        }

    def profile(self, employee_id):
        return {"payload": {"hire_date": "2024-01-01"}}

    def all(self, domain, employee_id):
        return [self.history] if domain == "payroll_history" else self.payroll


def payroll(kind, tax, *, status="paid", end="2026-09-19", start=None):
    return {
        "id": str(uuid4()),
        "status": status,
        "payload": {
            "payroll_kind": kind,
            "week_start": start or end,
            "period_end": end,
            "components": [{"code": "tax", "amount": tax}],
            "gross_pay": "8000.00",
            "taxable_pay": "8000.00",
        },
    }


@pytest.mark.parametrize(
    "kind", ["thirteenth_month", "separation", "leave_conversion", "adjustment"]
)
@pytest.mark.parametrize(
    "tax,withheld", [("2500.00", "7500.00"), ("-500.00", "10500.00")]
)
def test_completed_tax_components_change_retained_withholding_once(kind, tax, withheld):
    facts = _annual_facts(Facts([payroll(kind, tax)]), uuid4(), date(2026, 9, 19))
    assert facts["withheld"] == Decimal(withheld)


@pytest.mark.parametrize(
    "kind",
    ["weekly", "thirteenth_month", "separation", "leave_conversion", "adjustment"],
)
@pytest.mark.parametrize("status", ["approved", "partially_paid"])
def test_unsettled_tax_requires_resolution_before_annual_reconciliation(kind, status):
    row = payroll(kind, "-500.00", status=status, start="2026-09-13")
    through = "2026-09-12" if kind == "weekly" else "2026-09-19"
    with pytest.raises(EmployeeConflict, match="[Ss]ettle.*tax"):
        _annual_facts(Facts([row], through=through), uuid4(), date(2026, 9, 19))


def test_current_and_future_and_previous_year_tax_are_excluded():
    current = payroll("thirteenth_month", "2500.00", status="approved")
    rows = [
        current,
        payroll("separation", "999.00", end="2026-09-20"),
        payroll("leave_conversion", "999.00", end="2025-12-31"),
    ]
    facts = _annual_facts(Facts(rows), uuid4(), date(2026, 9, 19), current["id"])
    assert facts["withheld"] == Decimal("10000.00")


def test_annual_reconciliation_rejects_history_week_overlap_in_existing_evidence():
    row = payroll("weekly", "0.00", start="2026-09-13")
    with pytest.raises(EmployeeConflict, match="overlap"):
        _annual_facts(Facts([row], through="2026-09-15"), uuid4(), date(2026, 9, 19))


def test_annual_reconciliation_does_not_assign_whole_cross_year_week_to_new_year():
    tx = Facts([payroll("weekly", "0.00", start="2025-12-28", end="2026-01-03")])
    tx.all = lambda domain, employee: [] if domain == "payroll_history" else tx.payroll
    with pytest.raises(EmployeeConflict, match="calendar year"):
        _annual_facts(tx, uuid4(), date(2026, 1, 3))
