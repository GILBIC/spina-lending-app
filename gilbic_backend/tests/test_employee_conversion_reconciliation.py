"""No taxability assumptions: ambiguous settled conversion requires review."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.employee_operations import EmployeeConflict
from gilbic_backend.employee_operations_models import PayrollPrepare
from gilbic_backend.employee_operations_payroll import prepare
from test_employee_payroll_reconciliation import Facts, payroll


class Preparation(Facts):
    today = date(2026, 9, 20)

    def __init__(self, rows, *, exempt=False, **changes):
        super().__init__(rows)
        self.exempt = exempt
        self.saved = []
        self.command = PayrollPrepare.model_validate(
            {
                "action": "payroll_prepare",
                "id": str(uuid4()),
                "request_id": str(uuid4()),
                "employee_id": str(uuid4()),
                "expected_version": 0,
                "week_start": "2026-09-19",
                "payroll_kind": "thirteenth_month",
                "reason": "Synthetic annual reconciliation",
                **changes,
            }
        )

    def staff(self, *args):
        pass

    def get(self, *args, **kwargs):
        return None

    def effective_profile(self, *args):
        return {"tax_exempt": self.exempt, "daily_rate": "800.00"}

    def command_payload(self):
        return self.command.model_dump(mode="json")

    def fingerprint(self, *args):
        return "synthetic", {}

    def save(self, domain, identity, employee, payload, status):
        self.saved.append(payload)
        return {"payload": payload, "status": status}


def conversion(*, amount="800.00", tax="-500.00", **kwargs):
    row = payroll("leave_conversion", tax, **kwargs)
    row["payload"]["components"].append({"code": "leave_conversion", "amount": amount})
    row["payload"]["withholding_basis"] = (
        "Retained reviewed tax amount; no taxable basis allocation"
    )
    return row


@pytest.mark.parametrize("kind", ["leave_conversion", "separation"])
@pytest.mark.parametrize("tax", ["0.00", "-500.00"])
def test_automatic_annual_reconciliation_does_not_infer_prior_conversion_taxability(
    kind, tax
):
    row = conversion(tax=tax)
    row["payload"]["payroll_kind"] = kind
    tx = Preparation([row])
    with pytest.raises(
        EmployeeConflict,
        match="[Ll]eave.conversion.*taxable|taxable.*[Ll]eave.conversion",
    ):
        prepare(tx)
    assert tx.saved == []


def test_explicit_reviewed_reconciliation_remains_available_without_adding_taxable_income():
    tx = Preparation(
        [conversion()],
        withholding_override="120.00",
        withholding_basis="Synthetic reviewed final annual tax delta including leave conversion",
    )
    result = prepare(tx)["payload"]
    assert result["annual_facts"]["taxable"] == "300000.00"
    assert result["annual_facts"]["withheld"] == "10500.00"
    assert (
        next(row["amount"] for row in result["components"] if row["code"] == "tax")
        == "-120.00"
    )


@pytest.mark.parametrize(
    "case", ["zero", "previous_year", "future", "exempt", "history_only", "rejected"]
)
def test_supported_unambiguous_records_remain_usable(case):
    row = conversion(
        amount="0.00" if case == "zero" else "800.00",
        end="2025-12-31"
        if case == "previous_year"
        else "2026-09-20"
        if case == "future"
        else "2026-09-19",
        status="rejected" if case == "rejected" else "paid",
    )
    result = prepare(
        Preparation([] if case == "history_only" else [row], exempt=case == "exempt")
    )
    assert result["status"] == "draft"
    assert Decimal(result["payload"]["annual_facts"]["taxable"]) == Decimal("300000.00")
