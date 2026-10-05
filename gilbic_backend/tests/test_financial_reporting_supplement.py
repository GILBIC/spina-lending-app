"""Cash and equity must reconcile without counting formal close transfers twice."""

from decimal import Decimal
from uuid import uuid4

import pytest
from test_financial_statements import movement, sample_pack

from gilbic_backend import financial_reporting as reporting


def policy():
    return {
        "id": str(uuid4()),
        "cash_definition_valid": True,
        "cash_account_codes": ["1010", "1020", "1030"],
        "framework_label": "Internal accrual lending reports",
        "notes": [],
    }


def cash(amount, category=None, *, journal=None, allocations=None):
    return {
        "journal_line_id": str(uuid4()),
        "journal_entry_id": str(journal or uuid4()),
        "account_code": "1010",
        "amount": Decimal(amount),
        "entry_number": "SYNTHETIC",
        "source_type": "manual",
        "allocations": allocations
        if allocations is not None
        else ([{"category": category, "amount": amount}] if category else None),
    }


def test_equity_includes_opening_unclosed_earnings_without_double_close():
    pack = sample_pack()
    equity = reporting.equity_rollforward(
        pack,
        opening_equity=Decimal(4700),
        equity_movements=(movement("3000", "Capital", "equity", credit="100"),),
    )
    assert equity["opening_equity"] == "4700.00"
    assert equity["profit_or_loss"] == "1000.00"
    assert equity["other_equity_movements"] == [
        {"account_code": "3000", "account_name": "Capital", "amount": "100.00"}
    ]
    assert equity["closing_equity"] == "5800.00"
    assert equity["reconciled"] is True


def test_missing_cash_policy_never_returns_a_zero_statement():
    result = reporting.cash_flow_statement(
        policy=None, opening_cash=None, closing_cash=None, lines=[]
    )
    assert result["status"] == "cash_definition_required"
    assert result["closing_cash"] is None
    assert result["reconciled"] is False


def test_opening_reversal_is_a_balance_adjustment_without_cash_flow():
    reversal = cash("-100", "financing") | {
        "source_type": "reversal",
        "is_opening_adjustment": True,
    }
    result = reporting.cash_flow_statement(
        policy=policy(),
        opening_cash=Decimal(100),
        closing_cash=Decimal(0),
        lines=[reversal],
    )
    assert result["opening_balance_adjustments"] == "-100.00"
    assert result["categories"]["financing"]["payments"] == "0.00"
    assert result["reconciled"] is True


def test_cash_flows_keep_gross_inflows_and_outflows_and_reconcile():
    result = reporting.cash_flow_statement(
        policy=policy(),
        opening_cash=Decimal(100),
        closing_cash=Decimal(180),
        lines=[
            cash("100", "financing"),
            cash("20", "operating"),
            cash("-40", "operating"),
        ],
    )
    assert result["status"] == "complete_for_posted_ledger"
    assert result["categories"]["operating"] == {
        "receipts": "20.00",
        "payments": "40.00",
        "net": "-20.00",
    }
    assert result["net_cash_flow"] == "80.00"
    assert result["reconciled"] is True


def test_unclassified_offsets_cannot_disappear_in_zero_net_cash():
    result = reporting.cash_flow_statement(
        policy=policy(),
        opening_cash=Decimal(100),
        closing_cash=Decimal(100),
        lines=[cash("100"), cash("-100")],
    )
    assert result["status"] == "classification_required"
    assert result["unclassified_line_count"] == 2
    assert result["net_cash_flow"] is None
    assert result["reconciled"] is False


def test_internal_transfers_are_net_zero_by_journal_and_fee_stays_operating():
    journal = uuid4()
    result = reporting.cash_flow_statement(
        policy=policy(),
        opening_cash=Decimal(100),
        closing_cash=Decimal(98),
        lines=[
            cash(
                "-102",
                journal=journal,
                allocations=[
                    {"category": "internal", "amount": "-100"},
                    {"category": "operating", "amount": "-2"},
                ],
            ),
            cash("100", "internal", journal=journal),
        ],
    )
    assert result["net_cash_flow"] == "-2.00"
    assert result["categories"]["operating"]["payments"] == "2.00"
    assert result["reconciled"] is True


@pytest.mark.parametrize(
    "allocations",
    [
        [{"category": "internal", "amount": "100"}],
        [{"category": "operating", "amount": "99"}],
        [
            {"category": "operating", "amount": "101"},
            {"category": "financing", "amount": "-1"},
        ],
        [{"category": "unknown", "amount": "100"}],
        [{"category": "operating", "amount": "NaN"}],
    ],
)
def test_malformed_or_unbalanced_classification_remains_unavailable(allocations):
    result = reporting.cash_flow_statement(
        policy=policy(),
        opening_cash=Decimal(0),
        closing_cash=Decimal(100),
        lines=[cash("100", allocations=allocations)],
    )
    assert result["status"] == "classification_required"
    assert result["reconciled"] is False
