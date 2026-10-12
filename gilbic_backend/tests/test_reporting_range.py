from copy import deepcopy
from uuid import uuid4

from gilbic_backend import reporting_review_export as reporting


def pack(
    first, last, *, opening, closing, income="0.00", expense="0.00", cash_lines=None
):
    return {
        "period": {
            "period_id": str(uuid4()),
            "label": first,
            "start_date": first,
            "end_date": last,
            "status": "closed",
        },
        "profit_or_loss": {
            "income_lines": [
                {"account_code": "4000", "account_name": "Income", "amount": income}
            ],
            "expense_lines": [
                {"account_code": "5100", "account_name": "Expense", "amount": expense}
            ],
            "total_income": income,
            "total_expenses": expense,
            "net_income": str(
                __import__("decimal").Decimal(income)
                - __import__("decimal").Decimal(expense)
            ),
        },
        "financial_position": {
            "as_of_date": last,
            "total_equity": closing,
            "balanced": True,
        },
        "reporting_supplement": {
            "changes_in_equity": {
                "opening_equity": opening,
                "other_equity_movements": [],
            },
            "cash_flows": {
                "opening_cash": opening,
                "closing_cash": closing,
                "cash_lines": cash_lines or [],
                "policy": {
                    "id": str(uuid4()),
                    "cash_definition_valid": True,
                    "cash_account_codes": ["1010", "1030"],
                },
            },
            "notes": {"items": []},
            "noncash_activity": [],
        },
    }


def test_range_profit_equity_and_position_use_movements_and_final_balance():
    packs = [
        pack(
            "2026-01-01",
            "2026-01-31",
            opening="90071992547409.91",
            closing="90071992547410.01",
            income="0.11",
            expense="0.01",
        ),
        pack(
            "2026-02-01",
            "2026-02-28",
            opening="90071992547410.01",
            closing="90071992547410.03",
            income="0.03",
            expense="0.01",
        ),
    ]
    result = reporting.build_range_statements(packs)
    assert result["profit_or_loss"]["net_income"] == "0.12"
    assert result["profit_or_loss"]["income_lines"][0]["amount"] == "0.14"
    assert result["financial_position"]["total_equity"] == "90071992547410.03"
    assert result["reporting_supplement"]["changes_in_equity"]["reconciled"] is True
    assert result["reporting_supplement"]["comparative"] is None


def test_range_transfer_crossing_months_offsets_principal_and_retains_fee():
    transfer = str(uuid4())

    def line(amount, leg):
        return {
            "journal_line_id": str(uuid4()),
            "journal_entry_id": str(uuid4()),
            "entry_number": leg,
            "account_code": "1010" if leg == "source" else "1030",
            "source_type": "treasury_owned_transfer",
            "amount": amount,
            "allocations": [{"category": "operating", "amount": amount}],
            "is_opening_adjustment": False,
            "internal_transfer": {
                "transfer_id": transfer,
                "leg": leg,
                "principal": "-100.00" if leg == "source" else "100.00",
            },
        }

    packs = [
        pack(
            "2026-01-01",
            "2026-01-31",
            opening="105.00",
            closing="0.00",
            expense="5.00",
            cash_lines=[line("-105.00", "source")],
        ),
        pack(
            "2026-02-01",
            "2026-02-28",
            opening="0.00",
            closing="100.00",
            cash_lines=[line("100.00", "destination")],
        ),
    ]
    before = deepcopy(packs)
    cash = reporting.build_range_statements(packs)["reporting_supplement"]["cash_flows"]
    assert cash["reconciled"] is True
    assert cash["categories"]["operating"] == {
        "receipts": "0.00",
        "payments": "5.00",
        "net": "-5.00",
    }
    assert cash["net_cash_flow"] == "-5.00"
    assert packs == before


def test_range_does_not_invent_common_cash_definition_or_prior_balances():
    packs = [
        pack("2026-01-01", "2026-01-31", opening="0.00", closing="0.00"),
        pack("2026-02-01", "2026-02-28", opening="0.00", closing="0.00"),
    ]
    packs[1]["reporting_supplement"]["cash_flows"]["policy"]["cash_account_codes"] = [
        "1010"
    ]
    result = reporting.build_range_statements(packs)
    assert (
        result["reporting_supplement"]["cash_flows"]["status"]
        == "range_cash_definition_review_required"
    )
    assert result["reporting_supplement"]["cash_flows"]["net_cash_flow"] is None
    assert result["reporting_supplement"]["comparative"] is None
