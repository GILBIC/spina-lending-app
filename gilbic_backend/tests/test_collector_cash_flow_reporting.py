"""Collector custody transfers are internal; only actual excess is new cash."""

from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.financial_reporting import cash_flow_statement
from test_financial_reporting_supplement import cash, policy


def settlement():
    journal, source = uuid4(), uuid4()
    custody = cash("-100.00", "internal")
    received = cash(
        "110.00",
        allocations=[
            {"category": "internal", "amount": "100.00"},
            {"category": "operating", "amount": "10.00"},
        ],
    )
    for line, code, principal in (
        (custody, "1020", "-100.00"),
        (received, "1030", "100.00"),
    ):
        line.update(
            journal_entry_id=journal,
            account_code=code,
            source_type="collector_liability",
            collector_cash={
                "source_kind": "settlement",
                "source_id": str(source),
                "journal_entry_id": str(journal),
                "internal_principal": principal,
            },
        )
    return custody, received


def report(lines, closing="110.00"):
    return cash_flow_statement(
        policy=policy(),
        opening_cash=Decimal("100.00"),
        closing_cash=Decimal(closing),
        lines=lines,
    )


def test_collector_settlement_excludes_custody_transfer_but_keeps_actual_excess():
    result = report(settlement())
    assert result["reconciled"] is True
    assert result["categories"]["operating"] == {
        "receipts": "10.00",
        "payments": "0.00",
        "net": "10.00",
    }


@pytest.mark.parametrize("damage", ["operating", "mixed", "excess", "missing"])
def test_settlement_cannot_inflate_gross_flows_or_hide_excess(damage):
    custody, received = settlement()
    if damage == "excess":
        received["allocations"] = [{"category": "internal", "amount": "110.00"}]
    else:
        for line in (custody, received):
            line["allocations"] = [
                {
                    "category": "financing"
                    if damage == "mixed" and line is received
                    else "operating",
                    "amount": format(line["amount"], ".2f"),
                }
            ]
            if damage == "missing":
                line.pop("collector_cash")
    result = report([custody, received])
    assert result["status"] == "classification_required"
    assert result["net_cash_flow"] is None
    assert result["reconciled"] is False


def test_unselected_custody_account_cannot_offset_the_only_selected_cash_leg():
    _, received = settlement()
    received["allocations"] = [{"category": "operating", "amount": "110.00"}]
    result = report([received], closing="210.00")
    assert result["reconciled"] is True
    assert result["categories"]["operating"]["receipts"] == "110.00"


@pytest.mark.parametrize("damage", ["none", "missing", "invented_internal"])
def test_actual_collector_return_remains_external_cash_with_exact_proof(damage):
    line = cash("-5.00", "operating")
    line["source_type"] = "collector_liability"
    line["collector_cash"] = {
        "source_kind": "return_debit",
        "source_id": str(uuid4()),
        "journal_entry_id": str(line["journal_entry_id"]),
        "internal_principal": "0.00",
    }
    if damage == "missing":
        line.pop("collector_cash")
    elif damage == "invented_internal":
        line["collector_cash"]["internal_principal"] = "-5.00"
    result = report([line], closing="95.00")
    assert result["reconciled"] is (damage == "none")
