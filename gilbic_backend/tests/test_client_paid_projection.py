"""Applied payment facts, including interest, are independent of principal balance."""

from dataclasses import asdict
from decimal import Decimal

import pytest
from gilbic_backend.client_loan_api import _loan_payload
from gilbic_backend.client_loan_repository import PostgresClientLoanRepository
from test_client_loan_api import CLIENT_USER_ID, FakeLoans


@pytest.mark.parametrize(
    "principal,remaining,applied",
    [
        ("5000.00", "5900.00", "100.00"),
        ("5000.00", "0.00", "6000.00"),
        ("5000.00", "4950.00", "0.00"),
    ],
)
def test_client_paid_total_uses_applied_receipts(principal, remaining, applied):
    row = asdict(FakeLoans().list_for_user(user_id=CLIENT_USER_ID).loans[0])
    row.update(
        principal=Decimal(principal),
        remaining_balance=Decimal(remaining),
        paid_amount=Decimal(applied),
    )
    payload = _loan_payload(PostgresClientLoanRepository._loan_from_row(row))
    assert payload["paid_amount"] == applied
    assert payload["remaining_balance"] == remaining
