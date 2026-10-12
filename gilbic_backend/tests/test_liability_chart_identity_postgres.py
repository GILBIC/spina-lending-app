"""Changing a chart label must never remove a liability from completeness."""

import psycopg
import pytest
from test_accounting_book_postgres import book_db as _book_db
from test_liability_control_postgres import liabilities as _liabilities
from test_liability_control_postgres import line, register

book_db = _book_db
liabilities = _liabilities


@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("code", ["2000", "2300"])
@pytest.mark.parametrize(
    "change",
    [
        "code='2399'",
        "account_type='income'",
        "normal_balance='debit'",
        "system_key='changed_control'",
        "is_posting=false",
    ],
)
def test_liability_control_cannot_be_recoded_or_reclassified(
    liabilities, registered, code, change
):
    f = liabilities
    source = line(f, code=code)
    if registered:
        register(
            f, source, kind="trade_payable" if code == "2000" else "borrowing_external"
        )
    with (
        pytest.raises(psycopg.Error, match="control.*definition|immutable"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "UPDATE accounting.accounts SET " + change + " WHERE code=%s", (code,)
        )
    balance = (
        f["conn"]
        .execute(
            "SELECT ledger_balance,schedule_balance,unregistered_line_count FROM accounting.liability_control_reconciliation(%s) WHERE account_code=%s",
            (f["day"], code),
        )
        .fetchone()
    )
    assert balance == (100, 100 if registered else 0, 0 if registered else 1)


def test_unused_liability_control_cannot_be_deleted(liabilities):
    with (
        pytest.raises(psycopg.Error, match="control.*definition|immutable"),
        liabilities["conn"].transaction(),
    ):
        liabilities["conn"].execute("DELETE FROM accounting.accounts WHERE code='2340'")


def test_liability_control_retirement_preserves_historical_reconciliation(liabilities):
    f = liabilities
    register(f, line(f))
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_active=false,name='Retired payables control' WHERE code='2000'"
    )
    assert f["conn"].execute(
        "SELECT ledger_balance,schedule_balance,difference,unregistered_line_count FROM accounting.liability_control_reconciliation(%s) WHERE account_code='2000'",
        (f["day"],),
    ).fetchone() == (100, 100, 0, 0)
