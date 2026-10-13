"""Owned transfers may cross journals without becoming gross business cash flows."""

from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.financial_reporting import cash_flow_statement
from test_financial_reporting_supplement import cash, policy


def pair():
    transfer = str(uuid4())
    source = cash(
        "-102.00",
        allocations=[
            {"category": "internal", "amount": "-100.00"},
            {"category": "operating", "amount": "-2.00"},
        ],
    )
    destination = cash("100.00", "internal")
    for line, leg, principal in (
        (source, "source", "-100.00"),
        (destination, "destination", "100.00"),
    ):
        line["source_type"] = "treasury_owned_transfer"
        line["internal_transfer"] = {
            "transfer_id": transfer,
            "leg": leg,
            "principal": Decimal(principal),
        }
    return source, destination


def statement(lines, closing="98.00"):
    return cash_flow_statement(
        policy=policy(),
        opening_cash=Decimal("100.00"),
        closing_cash=Decimal(closing),
        lines=lines,
    )


def test_proven_same_period_transfer_excludes_principal_but_retains_fee():
    result = statement(pair())
    assert result["reconciled"] is True
    assert result["net_cash_flow"] == "-2.00"
    assert result["categories"]["operating"] == {
        "receipts": "0.00",
        "payments": "2.00",
        "net": "-2.00",
    }


@pytest.mark.parametrize(
    "damage", ["different_transfer", "same_leg", "fee", "unproven"]
)
def test_cross_journal_internal_offsets_need_exact_retained_transfer_principal(damage):
    source, destination = pair()
    if damage == "different_transfer":
        destination["internal_transfer"]["transfer_id"] = str(uuid4())
    elif damage == "same_leg":
        destination["internal_transfer"]["leg"] = "source"
    elif damage == "fee":
        source["allocations"] = [{"category": "internal", "amount": "-102.00"}]
    else:
        destination.pop("internal_transfer")
    result = statement([source, destination])
    assert result["status"] == "classification_required"
    assert result["net_cash_flow"] is None
    assert result["reconciled"] is False


def test_later_destination_cannot_net_an_earlier_periods_transfer():
    source, _ = pair()
    result = statement([source], closing="-2.00")
    assert result["status"] == "classification_required"
    assert result["reconciled"] is False


@pytest.mark.parametrize("destination_category", ["operating", "financing"])
def test_known_internal_pair_cannot_inflate_gross_business_cash_flows(
    destination_category,
):
    source, destination = pair()
    source["allocations"] = [{"category": "operating", "amount": "-102.00"}]
    destination["allocations"] = [
        {"category": destination_category, "amount": "100.00"}
    ]
    result = statement([source, destination])
    assert result["status"] == "classification_required"
    assert result["unclassified_line_count"] == 2
    assert result["reconciled"] is False
    assert result["net_cash_flow"] is None


def test_single_cash_leg_may_retain_explicit_noninternal_classification():
    source, _ = pair()
    source["allocations"] = [{"category": "operating", "amount": "-102.00"}]
    result = statement([source], closing="-2.00")
    assert result["reconciled"] is True
    assert result["categories"]["operating"]["payments"] == "102.00"


def test_correction_removing_proof_cannot_turn_a_transfer_into_business_flows():
    source, destination = pair()
    for line in (source, destination):
        line.pop("internal_transfer")
        line["allocations"] = [
            {"category": "operating", "amount": format(line["amount"], ".2f")}
        ]
    result = statement([source, destination])
    assert result["status"] == "classification_required"
    assert result["unclassified_line_count"] == 2
    assert result["reconciled"] is False
