"""Portfolio rows use the same database-date decision as the summary and sort."""

from dataclasses import asdict
from datetime import date

import pytest
from gilbic_backend.management_loan_api import _loan_payload
from gilbic_backend.management_loan_repository import PostgresManagementLoanRepository
from test_management_loan_api import FakeManagementLoans


@pytest.mark.parametrize(
    "due_date,database_overdue",
    [
        (date(2099, 1, 1), True),
        (date(2000, 1, 1), False),
        (None, False),
    ],
)
def test_overdue_payload_preserves_database_decision(due_date, database_overdue):
    row = asdict(
        FakeManagementLoans()
        .list_portfolio(query="", status="all", limit=50, offset=0)
        .loans[0]
    )
    row.update(due_date=due_date, is_overdue=database_overdue)
    payload = _loan_payload(PostgresManagementLoanRepository._record_from_row(row))
    assert payload["is_overdue"] is database_overdue
