"""Read projections must agree with actual receipt facts and database business date."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
import treasury_test_support
from gilbic_backend.client_loan_api import _loan_payload as client_payload
from gilbic_backend.management_loan_api import _loan_payload as management_payload
from test_management_paid_projection_postgres import receipt, register
from treasury_test_support import connect

from gilbic_backend import client_loan_repository as clients
from gilbic_backend import management_loan_repository as management

treasury = treasury_test_support.treasury


@pytest.mark.parametrize(
    "applied,remaining,voided,entry_type,want",
    [
        ("100.00", "5900.00", False, "payment", "100.00"),
        ("6000.00", "0.00", False, "payment", "6000.00"),
        ("100.00", "6000.00", True, "payment", "0.00"),
        ("100.00", "5900.00", False, "advance", "100.00"),
        ("0.00", "6000.00", False, "pass", "0.00"),
    ],
)
def test_client_reads_applied_nonvoid_receipts_from_database(
    treasury, monkeypatch, applied, remaining, voided, entry_type, want
):
    f = treasury
    with connect() as conn:
        conn.execute(
            "update lending.loans set principal=5000 where id=%s", (f["loan_id"],)
        )
        conn.execute(
            "insert into lending.loan_collection_state(loan_id,remaining_balance) values(%s,%s)",
            (f["loan_id"], Decimal(remaining)),
        )
    register(f, total="6000.00")
    receipt(
        f,
        amount="0.00" if entry_type == "pass" else "6500.00",
        applied=applied,
        voided=voided,
        entry_type=entry_type,
    )
    monkeypatch.setattr(clients, "open_connection", connect)
    portfolio = clients.PostgresClientLoanRepository().list_for_user(
        user_id=f["client_actor"].user_id
    )
    assert len(portfolio.loans) == 1
    payload = client_payload(portfolio.loans[0])
    assert payload["paid_amount"] == want
    assert payload["remaining_balance"] == remaining


@pytest.mark.parametrize(
    "due_offset,status,balance,want",
    [
        (-1, "active", "5000.00", True),
        (0, "active", "5000.00", False),
        (-1, "paid", "0.00", False),
        (None, "draft", "5000.00", False),
    ],
)
def test_management_row_and_summary_share_database_date(
    treasury, monkeypatch, due_offset, status, balance, want
):
    f = treasury
    with connect() as conn:
        database_date = conn.execute("select current_date as today").fetchone()["today"]
        due = (
            database_date + timedelta(days=due_offset)
            if due_offset is not None
            else None
        )
        conn.execute(
            "update lending.loans set due_date=%s,status=%s,date_released=%s where id=%s",
            (
                due,
                status,
                database_date - timedelta(days=30) if due else None,
                f["loan_id"],
            ),
        )
        conn.execute(
            "insert into lending.loan_collection_state(loan_id,remaining_balance) values(%s,%s)",
            (f["loan_id"], Decimal(balance)),
        )
        expected_total = conn.execute("""
            select count(*) as total from lending.loans loan
            left join lending.loan_collection_state state on state.loan_id=loan.id
            where lower(loan.status)='active' and loan.due_date < current_date
              and coalesce(state.remaining_balance,loan.principal)>0
        """).fetchone()["total"]

    class WrongHostDate(date):
        @classmethod
        def today(cls):
            return database_date + timedelta(days=-2 if want else 2)

    monkeypatch.setattr(management, "date", WrongHostDate)
    monkeypatch.setattr(management, "open_connection", connect)
    portfolio = management.PostgresManagementLoanRepository().list_portfolio(
        query=f["loan_id"].hex, status="all", limit=50, offset=0
    )
    assert portfolio.summary.overdue_active_count == expected_total
    assert len(portfolio.loans) == 1
    assert management_payload(portfolio.loans[0])["is_overdue"] is want
