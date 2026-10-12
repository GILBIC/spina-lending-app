"""Shared exact public statement payload for reads and review downloads."""

from decimal import Decimal

from .accounting_book_repository import book_identity_payload
from .financial_statements_repository import (
    FinancialStatementLine,
    FinancialStatementPack,
)


def _decimal(value: Decimal) -> str:
    return format(value, ".2f")


def _line_payload(line: FinancialStatementLine) -> dict[str, object]:
    return {
        "account_code": line.account_code,
        "account_name": line.account_name,
        "amount": _decimal(line.amount),
    }


def statement_pack_payload(pack: FinancialStatementPack) -> dict[str, object]:
    result = {
        "book": book_identity_payload(pack.book_identity),
        "period": {
            "period_id": str(pack.period.period_id),
            "label": pack.period.label,
            "start_date": pack.period.start_date.isoformat(),
            "end_date": pack.period.end_date.isoformat(),
            "status": pack.period.status,
        },
        "profit_or_loss": {
            "income_lines": [_line_payload(line) for line in pack.income_lines],
            "expense_lines": [_line_payload(line) for line in pack.expense_lines],
            "total_income": _decimal(pack.total_income),
            "total_expenses": _decimal(pack.total_expenses),
            "net_income": _decimal(pack.net_income),
        },
        "financial_position": {
            "as_of_date": pack.period.end_date.isoformat(),
            "asset_lines": [_line_payload(line) for line in pack.asset_lines],
            "liability_lines": [_line_payload(line) for line in pack.liability_lines],
            "equity_lines": [_line_payload(line) for line in pack.equity_lines],
            "total_assets": _decimal(pack.total_assets),
            "total_liabilities": _decimal(pack.total_liabilities),
            "recorded_equity": _decimal(pack.recorded_equity),
            "unclosed_earnings_to_date": _decimal(pack.unclosed_earnings_to_date),
            "total_equity": _decimal(pack.total_equity),
            "total_liabilities_and_equity": _decimal(pack.total_liabilities_and_equity),
            "balanced": pack.balanced,
        },
        "source": "posted_general_ledger_only",
        "assurance": {
            "arithmetic_balanced": pack.balanced,
            "comprehensive_source_coverage": False,
            "annual_reporting_package_complete": False,
        },
        "notice": (
            "These statements are generated only from posted General Ledger entries. "
            "Draft journals are excluded. Balanced totals do not establish that all "
            "business activity and liabilities have been recorded. Source reconciliation "
            "and retained accounting review are still required. This report does not yet include "
            "a complete annual reporting package."
        ),
    }
    if pack.reporting_supplement:
        supplemental = pack.reporting_supplement
        result["reporting_supplement"] = supplemental | {
            "comparative": statement_pack_payload(supplemental["comparative"])
            if supplemental["comparative"] is not None
            else None
        }
    return result
