from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.renewal_api import _loan_payload
from gilbic_backend.renewal_repository import PostgresRenewalRepository
from gilbic_backend.renewal_workflow_api import _payload
from test_renewal_workflow_cif_conflict_api import WorkflowDatabase


@pytest.mark.parametrize(
    ("paid_cash", "expected_percent", "eligible"),
    [("2999.99", "50.0", False), ("3000.00", "50.0", True), ("6001.00", "100.0", True)],
)
def test_workflow_eligibility_uses_exact_ratio_before_display_rounding(
    paid_cash, expected_percent, eligible
):
    database = WorkflowDatabase(None)
    database.prepare_proof_review()
    row = database.state["row"]
    row.update(
        old_loan_status="active",
        contractual_total=Decimal("6000.00"),
        paid_cash=Decimal(paid_cash),
    )

    result = _payload(database, row)

    assert result["paid_percent"] == expected_percent
    assert result["regular_50_percent_eligible"] is eligible


def _loan_row(*, total, mode="fixed_daily", status="active"):
    return {
        "loan_id": uuid4(),
        "loan_number": "SIGNED-1",
        "loan_type_name": "Regular",
        "calculation_mode": mode,
        "principal": Decimal("3000.00"),
        "contractual_total": total,
        "remaining_balance": Decimal("1000.00"),
        "paid_amount": Decimal("2000.00"),
        "daily_amount": Decimal("50.00"),
        "date_released": date(2026, 1, 1),
        "due_date": date(2026, 5, 1),
        "status": status,
        "pending_request_id": None,
        "blocking_request_status": None,
    }


@pytest.mark.parametrize(
    ("mode", "status", "eligible"),
    [
        ("fixed_daily", "active", False),
        ("seven_by_seven", "active", True),
        ("fixed_daily", "paid", True),
    ],
)
def test_missing_signed_schedule_is_unavailable_without_inventing_percentage(
    mode, status, eligible
):
    loan = PostgresRenewalRepository._loan_from_row(
        _loan_row(total=None, mode=mode, status=status)
    )
    result = _loan_payload(loan)

    assert result["contractual_total"] is None
    assert result["paid_percent"] is None
    assert result["paid_amount"] == "2000.00"
    assert result["eligible"] is eligible
    if not eligible:
        assert "verified signed schedule" in result["eligibility_message"]


def test_missing_workflow_schedule_does_not_claim_zero_paid():
    database = WorkflowDatabase(None)
    database.prepare_proof_review()
    database.state["row"].update(old_loan_status="active", contractual_total=None)

    result = _payload(database, database.state["row"])

    assert result["contractual_total"] is None
    assert result["paid_percent"] is None
    assert result["regular_50_percent_eligible"] is False
