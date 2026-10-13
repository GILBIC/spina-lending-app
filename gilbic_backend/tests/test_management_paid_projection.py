from dataclasses import asdict
from decimal import Decimal

import pytest
from gilbic_backend.management_loan_api import _loan_payload
from gilbic_backend.management_loan_repository import PostgresManagementLoanRepository
from test_management_loan_api import FakeManagementLoans


@pytest.mark.parametrize(
    "total,paid,want",
    [
        ("6000.00", "100.00", "1.7"),
        ("6000.00", "0.00", "0.0"),
        (None, "100.00", None),
        ("0.00", "100.00", None),
        ("6000.00", "6100.00", "100.0"),
    ],
)
def test_management_percentage_uses_contract_without_inventing_missing_data(
    total, paid, want
):
    record = (
        FakeManagementLoans()
        .list_portfolio(query="", status="all", limit=50, offset=0)
        .loans[0]
    )
    row = asdict(record)
    row.update(
        contractual_total=Decimal(total) if total is not None else None,
        paid_amount=Decimal(paid),
        remaining_balance=Decimal("5900.00"),
    )
    result = _loan_payload(PostgresManagementLoanRepository._record_from_row(row))
    assert result["paid_amount"] == paid
    assert result["paid_percent"] == want
