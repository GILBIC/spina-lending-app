"""Accountant review handoff for complete configured reporting periods."""

import html
from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

from .financial_reporting import cash_flow_statement, journal_disclosure_report, money

NOTICE = (
    "Accountant review package. The statements retain each configured period's "
    "cash definition, classifications, notes and unresolved evidence. The ledger "
    "and Trial Balance cover the full selected range. Full-range statements use "
    "exact movements and recompute cash flows across period boundaries. Missing or "
    "inconsistent retained policy and unresolved source evidence remain explicit. "
    "This download does not certify source completeness or statutory acceptance."
)


def _sum_lines(groups):
    result = {}
    for lines in groups:
        for row in lines:
            code = row["account_code"]
            if code not in result:
                result[code] = row | {"amount": Decimal(0)}
            result[code]["amount"] += Decimal(row["amount"])
    return [
        row | {"amount": money(row["amount"])}
        for _, row in sorted(result.items())
        if row["amount"]
    ]


def _range_transfer_lines(lines):
    """Offset exact owned principals when both cash legs are inside this range.

    Per-period classifications may treat an unmatched transfer leg as a cash
    flow. The broader range removes the proven principal, preserving the fee's
    retained category only where its allocation is unambiguous.
    """
    result = deepcopy(lines)
    pairs = defaultdict(list)
    for line in result:
        proof = line.get("internal_transfer")
        if proof and line["source_type"] == "treasury_owned_transfer":
            pairs[proof["transfer_id"]].append(line)
    for pair in pairs.values():
        if (
            len(pair) != 2
            or {line["internal_transfer"]["leg"] for line in pair}
            != {"source", "destination"}
            or len({line["journal_entry_id"] for line in pair}) != 2
            or sum(
                (Decimal(line["internal_transfer"]["principal"]) for line in pair),
                Decimal(0),
            )
            != 0
        ):
            continue
        for line in pair:
            principal = Decimal(line["internal_transfer"]["principal"])
            amount = Decimal(line["amount"])
            if not principal or principal * amount <= 0 or abs(principal) > abs(amount):
                continue
            remainder = amount - principal
            allocations = line.get("allocations") or []
            if any(item["category"] == "internal" for item in allocations):
                continue
            if remainder and (
                len(allocations) != 1 or Decimal(allocations[0]["amount"]) != amount
            ):
                # Exact principal is known, but an ambiguous fee split still
                # requires evidence. Do not consume arbitrary categories.
                continue
            line["allocations"] = [{"category": "internal", "amount": money(principal)}]
            if remainder:
                line["allocations"].append(
                    {"category": allocations[0]["category"], "amount": money(remainder)}
                )
            line["range_internal_adjustment"] = True
    return result


def build_range_statements(packs, *, comparative=None):
    """Project only authorized same-snapshot packs covering contiguous periods."""
    first, last = packs[0], packs[-1]
    supplements = [pack["reporting_supplement"] for pack in packs]
    income = _sum_lines(pack["profit_or_loss"]["income_lines"] for pack in packs)
    expenses = _sum_lines(pack["profit_or_loss"]["expense_lines"] for pack in packs)
    total_income = sum((Decimal(row["amount"]) for row in income), Decimal(0))
    total_expenses = sum((Decimal(row["amount"]) for row in expenses), Decimal(0))
    profit = total_income - total_expenses
    equity_movements = _sum_lines(
        s["changes_in_equity"]["other_equity_movements"] for s in supplements
    )
    opening_equity = Decimal(supplements[0]["changes_in_equity"]["opening_equity"])
    closing_equity = Decimal(last["financial_position"]["total_equity"])
    equity_difference = (
        closing_equity
        - opening_equity
        - profit
        - sum((Decimal(row["amount"]) for row in equity_movements), Decimal(0))
    )
    policies = [s["cash_flows"].get("policy") for s in supplements]
    first_policy = policies[0]
    common_cash = first_policy is not None and all(
        p is not None
        and p.get("cash_definition_valid") is True
        and set(p["cash_account_codes"]) == set(first_policy["cash_account_codes"])
        for p in policies
    )
    lines = _range_transfer_lines(
        [line for s in supplements for line in s["cash_flows"].get("cash_lines", [])]
    )
    cash = cash_flow_statement(
        policy=policies[0] if common_cash else None,
        opening_cash=Decimal(supplements[0]["cash_flows"]["opening_cash"])
        if common_cash
        else None,
        closing_cash=Decimal(supplements[-1]["cash_flows"]["closing_cash"])
        if common_cash
        else None,
        lines=[line | {"amount": Decimal(line["amount"])} for line in lines],
    )
    cash["policy_versions"] = [p["id"] if p else None for p in policies]
    cash["cash_lines"] = lines
    if not common_cash:
        cash["status"] = "range_cash_definition_review_required"
    else:
        cash["notice"] = (
            "Exact selected-range cash flows. Protected owned-transfer principals offset when both selected cash legs are inside the range. Unresolved fees and classifications remain blocked."
        )
    disclosures = [s.get("journal_disclosures") or {} for s in supplements]
    financing_policies = [d.get("policy") for d in disclosures]
    first_financing_policy = financing_policies[0]
    valid_financing = (
        common_cash
        and first_financing_policy is not None
        and all(
            p is not None
            and p.get("definition_valid") is True
            and set(p["financing_account_codes"])
            == set(first_financing_policy["financing_account_codes"])
            for p in financing_policies
        )
    )
    financing = []
    if valid_financing:
        closing = {
            a["account_code"]: a for a in disclosures[-1]["financing_liabilities"]
        }
        financing = [
            {
                "code": a["account_code"],
                "name": a["account_name"],
                "opening": Decimal(a["opening_balance"]),
                "closing": Decimal(closing[a["account_code"]]["closing_balance"]),
            }
            for a in disclosures[0]["financing_liabilities"]
        ]
    disclosure = journal_disclosure_report(
        policy_valid=valid_financing,
        financing_accounts=financing,
        journals=[j for d in disclosures for j in d.get("journals", [])],
    )
    return {
        "period": {
            "period_id": None,
            "label": "Selected reporting range",
            "start_date": first["period"]["start_date"],
            "end_date": last["period"]["end_date"],
            "status": "closed"
            if all(p["period"]["status"] == "closed" for p in packs)
            else "includes_open_periods",
        },
        "profit_or_loss": {
            "income_lines": income,
            "expense_lines": expenses,
            "total_income": money(total_income),
            "total_expenses": money(total_expenses),
            "net_income": money(profit),
        },
        "financial_position": deepcopy(last["financial_position"]),
        "reporting_supplement": {
            "changes_in_equity": {
                "opening_equity": money(opening_equity),
                "profit_or_loss": money(profit),
                "other_equity_movements": equity_movements,
                "closing_equity": money(closing_equity),
                "reconciliation_difference": money(equity_difference),
                "reconciled": equity_difference == 0,
            },
            "cash_flows": cash,
            "journal_disclosures": disclosure,
            "notes": {
                "status": "retained_period_notes",
                "items": [
                    note | {"fiscal_period_id": p["period"]["period_id"]}
                    for p in packs
                    for note in p["reporting_supplement"]["notes"]["items"]
                ],
            },
            "noncash_activity": [
                item for s in supplements for item in s.get("noncash_activity", [])
            ],
            "comparative": comparative,
        },
        "source": "posted_general_ledger_only",
        "statutory_acceptance": False,
    }


def validate_reporting_scope(report, start_date, end_date):
    if (
        report.get("start_date") != start_date.isoformat()
        or report.get("end_date") != end_date.isoformat()
    ):
        raise ValueError("Reporting range does not match the exported ledger range.")
    packs = report.get("period_statements")
    if not isinstance(packs, list) or not packs:
        raise ValueError("Reporting requires complete configured fiscal periods.")
    expected, identities = start_date, set()
    for pack in packs:
        period = pack["period"]
        first, last = (
            date.fromisoformat(period["start_date"]),
            date.fromisoformat(period["end_date"]),
        )
        if (
            first != expected
            or last < first
            or last > end_date
            or period["period_id"] in identities
        ):
            raise ValueError(
                "Reporting periods must cover the range exactly without gaps, overlap or duplicate periods."
            )
        identities.add(period["period_id"])
        expected = last + timedelta(days=1)
    if expected != end_date + timedelta(days=1):
        raise ValueError("Reporting periods do not cover the complete selected range.")
    return packs


def reporting_manifest(report):
    return {
        "scope": "accountant_review",
        "book": report["book"],
        "start_date": report["start_date"],
        "end_date": report["end_date"],
        "period_count": len(report["period_statements"]),
        "annual_consolidation": report.get(
            "annual_consolidation", "accountant_review_required"
        ),
        "statutory_acceptance": False,
    }


def print_reporting_review(report):
    def text(value):
        return html.escape("Unavailable" if value is None else str(value))

    def facts(values):
        return (
            "<dl>"
            + "".join(
                f"<dt>{text(label)}</dt><dd>{text(value)}</dd>"
                for label, value in values
            )
            + "</dl>"
        )

    def table(lines):
        return (
            "<table><thead><tr><th>Account</th><th>Name</th><th>Amount</th></tr></thead><tbody>"
            + "".join(
                f"<tr><td>{text(line['account_code'])}</td><td>{text(line['account_name'])}</td><td>{text(line['amount'])}</td></tr>"
                for line in lines
            )
            + "</tbody></table>"
        )

    def render(pack, comparative=False):
        period, profit, position = (
            pack["period"],
            pack["profit_or_loss"],
            pack["financial_position"],
        )
        supplement = pack.get("reporting_supplement") or {}
        book = report["book"]
        yield f"<section><h2>{'Comparative: ' if comparative else ''}{text(period['label'])}</h2>"
        yield facts(
            [
                ("Book", book.get("entity_label")),
                ("Book ID", book.get("book_id")),
                ("Book type", book.get("kind")),
                ("Book status", book.get("status")),
                ("From", period["start_date"]),
                ("Through", period["end_date"]),
                ("Period status", period["status"]),
            ]
        )
        yield "<h3>Profit or loss</h3>" + table(
            profit.get("income_lines", []) + profit.get("expense_lines", [])
        )
        yield facts(
            [
                (name.replace("_", " ").capitalize(), profit.get(name))
                for name in ("total_income", "total_expenses", "net_income")
            ]
        )
        yield "<h3>Financial position</h3>" + table(
            position.get("asset_lines", [])
            + position.get("liability_lines", [])
            + position.get("equity_lines", [])
        )
        yield facts(
            [
                (name.replace("_", " ").capitalize(), position.get(name))
                for name in (
                    "total_assets",
                    "total_liabilities",
                    "recorded_equity",
                    "unclosed_earnings_to_date",
                    "total_equity",
                    "balanced",
                )
            ]
        )
        for key, title, fields in (
            (
                "changes_in_equity",
                "Changes in equity",
                (
                    "opening_equity",
                    "profit_or_loss",
                    "closing_equity",
                    "reconciliation_difference",
                    "reconciled",
                ),
            ),
            (
                "cash_flows",
                "Cash flows",
                (
                    "status",
                    "opening_cash",
                    "opening_balance_adjustments",
                    "closing_cash",
                    "net_cash_flow",
                    "reconciliation_difference",
                    "unclassified_line_count",
                ),
            ),
        ):
            section = supplement.get(key) or {}
            yield f"<h3>{title}</h3>" + facts(
                [
                    (name.replace("_", " ").capitalize(), section.get(name))
                    for name in fields
                ]
            )
            if key == "changes_in_equity":
                yield table(section.get("other_equity_movements", []))
            else:
                for category, amounts in section.get("categories", {}).items():
                    yield f"<h4>{text(category.capitalize())}</h4>" + facts(
                        [(name.capitalize(), value) for name, value in amounts.items()]
                    )
        notes = supplement.get("notes") or {}
        yield "<h3>Retained Management notes</h3>" + facts(
            [
                ("Status", notes.get("status")),
                ("Framework label", notes.get("framework_label")),
            ]
        )
        for note in notes.get("items", []):
            yield (
                f"<h4>{text(note['title'])}</h4><p class=note>{text(note['text'])}</p>"
                + facts(
                    [
                        ("Evidence reference", note.get("evidence_reference")),
                        ("Evidence digest", note.get("evidence_digest")),
                    ]
                )
            )
        disclosure = supplement.get("journal_disclosures") or {}
        yield "<h3>Journal disclosure coverage</h3>" + facts(
            [
                ("Status", disclosure.get("status")),
                *[
                    (name.replace("_", " "), value)
                    for name, value in disclosure.get("coverage", {}).items()
                ],
            ]
        )
        yield "<p>Exact reviewed components, financing-liability reconciliations, cash classifications and blockers are retained in statement-packs.json.</p>"
        if not comparative:
            prior = supplement.get("comparative")
            if prior:
                yield from render(prior, comparative=True)
            else:
                yield (
                    "<p>No complete configured prior-year range. No comparative balances have been invented.</p>"
                    if period.get("period_id") is None
                    else "<p>No preceding configured period. No comparative balances have been invented.</p>"
                )
        yield "</section>"

    yield (
        "<!doctype html><html lang=en><meta charset=utf-8>"
        "<meta http-equiv=Content-Security-Policy content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>Accounting reporting review</title><style>body{font:12px sans-serif}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #999;padding:4px}dt{font-weight:bold}dd{margin-bottom:6px}.note{white-space:pre-wrap}"
        "section{break-before:page}thead{display:table-header-group}@page{size:A4;margin:12mm}</style><body>"
        f"<h1>Reporting review: {text(report['start_date'])} to {text(report['end_date'])}</h1><p>{text(NOTICE)}</p>"
    ).encode()
    for pack in (
        [report["range_statements"]] if report.get("range_statements") else []
    ) + report["period_statements"]:
        for chunk in render(pack):
            yield chunk.encode("utf-8")
    yield b"</body></html>"
