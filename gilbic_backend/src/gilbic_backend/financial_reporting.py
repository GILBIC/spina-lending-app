"""Exact posted-ledger equity and direct cash flow calculations."""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from uuid import UUID

ZERO = Decimal("0.00")
CATEGORIES = ("operating", "investing", "financing")


def money(value):
    return format(value, ".2f")


def equity_rollforward(pack, *, opening_equity, equity_movements):
    movements = [
        {
            "account_code": row.account_code,
            "account_name": row.account_name,
            "amount": money(row.total_credit - row.total_debit),
        }
        for row in equity_movements
        if row.account_type == "equity" and row.total_credit != row.total_debit
    ]
    expected = (
        opening_equity
        + pack.net_income
        + sum((Decimal(row["amount"]) for row in movements), ZERO)
    )
    return {
        "opening_equity": money(opening_equity),
        "profit_or_loss": money(pack.net_income),
        "other_equity_movements": movements,
        "closing_equity": money(pack.total_equity),
        "reconciliation_difference": money(pack.total_equity - expected),
        "reconciled": expected == pack.total_equity,
        "notice": "Opening and closing equity include unclosed earnings. Formal retained-earnings transfers are excluded from movements to avoid counting profit twice.",
    }


def _exact_amount(value):
    if not isinstance(value, str | Decimal):
        raise TypeError("Exact decimal text is required")
    amount = Decimal(value)
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Finite exact-cent amount is required")
    return amount


def _internal_groups(lines, parsed, invalid):
    """Only repository-verified transfer principals may offset across journals."""
    keys = [("journal", line["journal_entry_id"]) for line in lines]
    transfers = defaultdict(list)
    for index, (line, entries) in enumerate(zip(lines, parsed, strict=True)):
        internal_amount = sum(
            (value for category, value in entries if category == "internal"), ZERO
        )
        proof = line.get("internal_transfer")
        if proof is None:
            if line["source_type"] == "treasury_owned_transfer":
                invalid.add(index)
            continue
        try:
            transfer_id = str(UUID(str(proof["transfer_id"])))
            principal = _exact_amount(proof["principal"])
            leg = proof["leg"]
            if (
                line["source_type"] != "treasury_owned_transfer"
                or leg not in {"source", "destination"}
                or principal == ZERO
                or (principal < ZERO) != (leg == "source")
                or (internal_amount != ZERO and internal_amount != principal)
            ):
                raise ValueError(
                    "Internal allocation must match its protected principal"
                )
            keys[index] = ("transfer", transfer_id)
            transfers[transfer_id].append((index, leg, principal, internal_amount))
        except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError):
            invalid.add(index)
    for group in transfers.values():
        indices = [index for index, _, _, _ in group]
        # A leg outside the period or selected cash definition is not an
        # internal cash pair. Its actual movement still needs classification.
        if len(group) == 1 and group[0][3] == ZERO:
            continue
        if (
            len(group) != 2
            or {leg for _, leg, _, _ in group} != {"source", "destination"}
            or len({lines[index]["journal_entry_id"] for index in indices}) != 2
            or sum((principal for _, _, principal, _ in group), ZERO) != ZERO
            or any(principal != internal for _, _, principal, internal in group)
            or any(index in invalid for index in indices)
        ):
            invalid.update(indices)
    return keys


def _collector_internal_groups(lines, parsed, invalid):
    """A proven custody handover does not create another business cash receipt."""
    settlements = defaultdict(list)
    for index, (line, entries) in enumerate(zip(lines, parsed, strict=True)):
        if line["source_type"] != "collector_liability":
            continue
        try:
            proof = line["collector_cash"]
            kind = proof["source_kind"]
            source_id = str(UUID(str(proof["source_id"])))
            journal = str(UUID(str(proof["journal_entry_id"])))
            principal = _exact_amount(proof["internal_principal"])
            amount = _exact_amount(line["amount"])
            internal = sum(
                (value for category, value in entries if category == "internal"), ZERO
            )
            if (
                journal != str(line["journal_entry_id"])
                or kind not in {"settlement", "return_debit", "return_reversal"}
                or (kind != "settlement" and principal != ZERO)
                or abs(principal) > abs(amount)
                or (principal != ZERO and principal * amount <= ZERO)
                or (internal != ZERO and internal != principal)
                or (kind == "return_debit" and amount >= ZERO)
                or (kind == "return_reversal" and amount <= ZERO)
            ):
                raise ValueError("Current exact Collector cash proof is required")
            if principal != ZERO:
                settlements[journal].append((index, source_id, principal, internal))
        except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError):
            invalid.add(index)
    for group in settlements.values():
        # If custody is outside the selected cash definition, this is one
        # actual selected-cash movement and still needs explicit classification.
        if len(group) == 1 and group[0][3] == ZERO:
            continue
        indices = [item[0] for item in group]
        if (
            len(group) != 2
            or len({source for _, source, _, _ in group}) != 1
            or len({lines[index]["account_code"] for index in indices}) != 2
            or sum((principal for _, _, principal, _ in group), ZERO) != ZERO
            or any(principal != internal for _, _, principal, internal in group)
            or any(index in invalid for index in indices)
        ):
            invalid.update(indices)


def cash_flow_statement(*, policy, opening_cash, closing_cash, lines):
    empty = {
        "status": "cash_definition_required",
        "policy": policy,
        "opening_cash": None,
        "closing_cash": None,
        "opening_balance_adjustments": None,
        "net_cash_flow": None,
        "reconciled": False,
        "categories": {},
        "unclassified_line_count": len(lines),
        "unclassified_lines": [],
        "reconciliation_difference": None,
    }
    if policy is None:
        return empty
    if policy.get("cash_definition_valid") is not True:
        return empty | {"status": "cash_definition_changed"}
    opening_adjustments = sum(
        (
            line["amount"]
            for line in lines
            if line["source_type"] == "opening_balance"
            or line.get("is_opening_adjustment") is True
        ),
        ZERO,
    )
    lines = [
        line
        for line in lines
        if line["source_type"] != "opening_balance"
        and line.get("is_opening_adjustment") is not True
    ]
    parsed = []
    invalid = set()
    internal = defaultdict(lambda: ZERO)
    for index, line in enumerate(lines):
        entries = []
        try:
            amount = _exact_amount(line["amount"])
            allocations = line.get("allocations")
            if not isinstance(allocations, list) or not allocations:
                raise ValueError("Classification required")
            for item in allocations:
                value = _exact_amount(item["amount"])
                category = item["category"]
                if (
                    category not in (*CATEGORIES, "internal")
                    or value == 0
                    or value * amount <= 0
                ):
                    raise ValueError(
                        "Classification must retain the cash line direction"
                    )
                entries.append((category, value))
            if sum((value for _, value in entries), ZERO) != amount:
                raise ValueError("Classification must account for the exact cash line")
        except (KeyError, TypeError, ValueError, InvalidOperation):
            invalid.add(index)
        parsed.append(entries)
    internal_keys = _internal_groups(lines, parsed, invalid)
    _collector_internal_groups(lines, parsed, invalid)
    for index, entries in enumerate(parsed):
        for category, value in entries:
            if category == "internal":
                internal[internal_keys[index]] += value
    for index, line in enumerate(lines):
        if internal[internal_keys[index]] != ZERO and any(
            category == "internal" for category, _ in parsed[index]
        ):
            invalid.add(index)
    totals = {
        category: {"receipts": ZERO, "payments": ZERO, "net": ZERO}
        for category in CATEGORIES
    }
    for index, entries in enumerate(parsed):
        if index in invalid:
            continue
        for category, value in entries:
            if category == "internal":
                continue
            totals[category]["receipts" if value > 0 else "payments"] += abs(value)
            totals[category]["net"] += value
    net = sum((values["net"] for values in totals.values()), ZERO)
    difference = closing_cash - opening_cash - opening_adjustments - net
    reconciled = not invalid and difference == ZERO
    return {
        "status": "classification_required"
        if invalid
        else "complete_for_posted_ledger"
        if reconciled
        else "cash_reconciliation_required",
        "policy": policy,
        "opening_cash": money(opening_cash),
        "closing_cash": money(closing_cash),
        "opening_balance_adjustments": money(opening_adjustments),
        "net_cash_flow": None if invalid else money(net),
        "reconciled": reconciled,
        "categories": {
            category: {key: money(value) for key, value in values.items()}
            for category, values in totals.items()
        },
        "unclassified_line_count": len(invalid),
        "unclassified_lines": [
            {
                key: money(line[key]) if key == "amount" else str(line[key])
                for key in (
                    "journal_line_id",
                    "journal_entry_id",
                    "account_code",
                    "amount",
                    "entry_number",
                    "source_type",
                )
            }
            for index, line in enumerate(lines)
            if index in invalid
        ],
        "reconciliation_difference": None if invalid else money(difference),
        "notice": "Direct cash flows use retained line classifications and the selected cash definition. Internal amounts must offset within one journal or the exact protected principal legs of one owned transfer within this period. The separate inventory lists journals with no cash leg; mixed cash and noncash transactions still require disclosure review.",
    }
