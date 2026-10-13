"""Exact posted-ledger equity and direct cash flow calculations."""

import re
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
                or kind
                not in {
                    "settlement",
                    "return_debit",
                    "return_reversal",
                    "credit_application",
                }
                or (kind != "settlement" and principal != ZERO)
                or abs(principal) > abs(amount)
                or (principal != ZERO and principal * amount <= ZERO)
                or (internal != ZERO and internal != principal)
                or (kind == "return_debit" and amount >= ZERO)
                or (kind == "return_reversal" and amount <= ZERO)
                or (
                    kind == "credit_application"
                    and (line["account_code"] != "1020" or amount >= ZERO)
                )
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


DISCLOSURE_CLASSIFICATIONS = (
    "cash_operating",
    "cash_investing",
    "cash_financing",
    "cash_internal",
    "noncash_investing",
    "noncash_financing",
    "noncash_investing_financing",
    "noncash_operating",
    "noncash_reclassification",
)


def journal_disclosure_report(*, policy_valid, financing_accounts, journals):
    """Project independently validated retained reviews without inventing residuals."""
    changes = {
        account["code"]: {"cash": ZERO, "noncash": ZERO, "opening": ZERO}
        for account in financing_accounts
    }
    coverage = {
        "journal_count": len(journals),
        "reviewed_count": 0,
        "excluded_count": 0,
        "blocked_count": 0,
    }
    blockers, disclosed = [], []
    for journal in journals:
        identity = {
            key: journal[key]
            for key in (
                "journal_entry_id",
                "entry_number",
                "posting_date",
                "source_type",
                "reversal_of_entry_id",
            )
        }
        source_status = journal["source_status"]
        protected = journal["protected_kind"]
        if source_status != "current" or (
            not protected and journal["review_status"] != "current"
        ):
            coverage["blocked_count"] += 1
            blockers.append(
                identity
                | {
                    "reason": source_status
                    if source_status != "current"
                    else journal["review_status"]
                }
            )
            continue
        by_id = {line["id"]: line for line in journal["lines"]}
        if protected:
            coverage["excluded_count"] += 1
            for line in by_id.values():
                code = line["account_code"]
                if code in changes and protected in {"opening", "opening_reversal"}:
                    changes[code]["opening"] += _exact_amount(
                        line["credit"]
                    ) - _exact_amount(line["debit"])
            continue
        coverage["reviewed_count"] += 1
        for part in journal["components"]:
            category = part["classification"]
            amount = _exact_amount(part["amount"])
            bucket = "cash" if category.startswith("cash_") else "noncash"
            for field, sign in (("debit_line_id", -1), ("credit_line_id", 1)):
                code = by_id[part[field]]["account_code"]
                if code in changes:
                    changes[code][bucket] += amount * sign
            if bucket == "noncash":
                disclosed.append(
                    identity
                    | part
                    | {
                        "debit_account_code": by_id[part["debit_line_id"]][
                            "account_code"
                        ],
                        "credit_account_code": by_id[part["credit_line_id"]][
                            "account_code"
                        ],
                    }
                )
    complete = policy_valid and not blockers
    financing = []
    for account in financing_accounts:
        values = changes[account["code"]]
        difference = (
            account["closing"] - account["opening"] - sum(values.values(), ZERO)
        )
        financing.append(
            {
                "account_code": account["code"],
                "account_name": account["name"],
                "opening_balance": money(account["opening"]),
                "cash_changes": money(values["cash"]) if complete else None,
                "noncash_changes": money(values["noncash"]) if complete else None,
                "opening_adjustments": money(values["opening"]) if complete else None,
                "closing_balance": money(account["closing"]),
                "difference": money(difference) if complete else None,
                "reconciled": complete and difference == ZERO,
            }
        )
    return {
        "status": "disclosure_policy_required"
        if not policy_valid
        else "disclosure_review_required"
        if blockers
        else "financing_reconciliation_required"
        if any(not row["reconciled"] for row in financing)
        else "complete_for_posted_ledger",
        "scope": "all_posted_journals",
        "coverage": coverage,
        "blockers": blockers,
        "noncash_components": disclosed if policy_valid else [],
        "financing_liabilities": financing,
        "notice": "Coverage is limited to the posted ledger and retained financing-account policy. Components are gross reviewed amounts; reversals identify their original journal. No aggregate noncash total is inferred.",
    }


def validate_disclosure_components(
    *, lines, components, cash_account_codes, cash_allocations
):
    """Validate an explicit balanced decomposition; never infer economic pairing.

    The database independently enforces these invariants when retaining a review.
    Cash source proof remains the responsibility of the existing cash-flow report.
    The returned amounts are per category, not an aggregate noncash total.
    """
    if not isinstance(components, list) or not 1 <= len(components) <= 1000:
        raise ValueError("Explicit disclosure components are required")
    by_id = {str(line["id"]): line for line in lines}
    if len(by_id) != len(lines) or not lines:
        raise ValueError("Distinct original journal lines are required")
    assigned = defaultdict(lambda: ZERO)
    cash = defaultdict(lambda: defaultdict(lambda: ZERO))
    totals = defaultdict(lambda: ZERO)
    pairs = set()
    keys = {
        "debit_line_id",
        "credit_line_id",
        "amount",
        "classification",
        "evidence_reference",
        "evidence_digest",
    }
    for part in components:
        if not isinstance(part, dict) or set(part) != keys:
            raise ValueError("Exact component fields are required")
        value = part["amount"]
        if (
            not isinstance(value, str)
            or not re.fullmatch(r"(0|[1-9][0-9]{0,15})\.[0-9]{2}", value)
            or Decimal(value) <= ZERO
        ):
            raise ValueError("A positive exact-cent component amount is required")
        amount = Decimal(value)
        category = part["classification"]
        if category not in DISCLOSURE_CLASSIFICATIONS:
            raise ValueError("Unsupported disclosure classification")
        reference = part["evidence_reference"]
        if (
            not isinstance(reference, str)
            or not 1 <= len(reference) <= 1000
            or reference != reference.strip()
        ):
            raise ValueError("A retained evidence reference is required")
        if not isinstance(part["evidence_digest"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", part["evidence_digest"]
        ):
            raise ValueError("A retained evidence digest is required")
        ids = (part["debit_line_id"], part["credit_line_id"])
        if any(
            not isinstance(identity, str) or identity not in by_id for identity in ids
        ):
            raise ValueError("Components must use original journal lines")
        pair = (*ids, category)
        if pair in pairs:
            raise ValueError("Duplicate pair and classification must be combined")
        pairs.add(pair)
        debit, credit = (by_id[identity] for identity in ids)
        if (
            _exact_amount(debit["debit"]) <= ZERO
            or _exact_amount(debit["credit"]) != ZERO
            or _exact_amount(credit["credit"]) <= ZERO
            or _exact_amount(credit["debit"]) != ZERO
        ):
            raise ValueError("Components must pair one debit and one credit")
        has_cash = any(
            line["account_code"] in cash_account_codes for line in (debit, credit)
        )
        if has_cash != category.startswith("cash_"):
            raise ValueError(
                "Cash-connected components cannot be classified as noncash"
            )
        for identity, line, sign in ((ids[0], debit, 1), (ids[1], credit, -1)):
            assigned[identity] += amount
            if line["account_code"] in cash_account_codes:
                cash[identity][category.removeprefix("cash_")] += amount * sign
        totals[category] += amount
    for identity, line in by_id.items():
        if assigned[identity] != _exact_amount(line["debit"]) + _exact_amount(
            line["credit"]
        ):
            raise ValueError("Every original line must be allocated exactly")
        if line["account_code"] in cash_account_codes:
            expected = defaultdict(lambda: ZERO)
            for part in cash_allocations.get(identity) or []:
                expected[part["category"]] += _exact_amount(part["amount"])
            if dict(expected) != dict(cash[identity]):
                raise ValueError(
                    "Components must reconcile to the retained cash classifications"
                )
    return dict(totals)
