"""Explicit components preserve mixed transactions and gross cash directions."""

from copy import deepcopy
from decimal import Decimal

import pytest

from gilbic_backend import financial_reporting


def mixed():
    return [
        {"id": "asset", "account_code": "1500", "debit": "1000.00", "credit": "0.00"},
        {"id": "cash", "account_code": "1010", "debit": "0.00", "credit": "400.00"},
        {"id": "debt", "account_code": "2300", "debit": "0.00", "credit": "600.00"},
    ]


def component(
    debit="asset",
    credit="debt",
    amount="600.00",
    category="noncash_investing_financing",
):
    return {
        "debit_line_id": debit,
        "credit_line_id": credit,
        "amount": amount,
        "classification": category,
        "evidence_reference": "test:contract",
        "evidence_digest": "a" * 64,
    }


def parts():
    return [
        component(credit="cash", amount="400.00", category="cash_investing"),
        component(),
    ]


def validate(lines=None, components=None, cash=None):
    validator = getattr(financial_reporting, "validate_disclosure_components", None)
    assert callable(validator), "Mixed-journal component review is not implemented"
    return validator(
        lines=mixed() if lines is None else lines,
        components=parts() if components is None else components,
        cash_account_codes=["1010"],
        cash_allocations={"cash": [{"category": "investing", "amount": "-400.00"}]}
        if cash is None
        else cash,
    )


def test_mixed_asset_keeps_cash_and_noncash_distinct():
    result = validate()
    assert result == {
        "cash_investing": Decimal("400.00"),
        "noncash_investing_financing": Decimal("600.00"),
    }


@pytest.mark.parametrize(
    "amount",
    [
        "0.00",
        "-1.00",
        "1.001",
        "1",
        "1e2",
        "NaN",
        "Infinity",
        600,
        600.0,
        True,
        None,
        "0600.00",
        "600.00 ",
        "10000000000000000.00",
    ],
)
def test_components_require_positive_exact_money_strings(amount):
    values = parts()
    values[1]["amount"] = amount
    with pytest.raises(ValueError):
        validate(components=values)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.pop(),
        lambda p: p.append(deepcopy(p[1])),
        lambda p: p[1].update(amount="599.99"),
        lambda p: p[1].update(amount="600.01"),
        lambda p: p[1].update(debit_line_id="foreign"),
        lambda p: p[1].update(debit_line_id="debt", credit_line_id="asset"),
        lambda p: p[1].update(classification="cash_financing"),
        lambda p: p[0].update(classification="noncash_investing"),
        lambda p: p[0].update(classification="cash_financing"),
        lambda p: p[1].update(classification="invented"),
        lambda p: p[1].update(evidence_reference=" "),
        lambda p: p[1].update(evidence_digest="invalid"),
        lambda p: p[1].update(hidden_amount="600.00"),
    ],
)
def test_incomplete_ambiguous_or_misclassified_components_are_rejected(mutation):
    values = parts()
    mutation(values)
    with pytest.raises(ValueError):
        validate(components=values)


def test_repeated_pair_and_category_must_be_one_explicit_component():
    values = [parts()[0], component(amount="300.00"), component(amount="300.00")]
    with pytest.raises(ValueError, match="Duplicate"):
        validate(components=values)


def test_cash_classification_is_required_and_cannot_be_netted():
    with pytest.raises(ValueError, match="cash"):
        validate(cash={})
    lines = [
        {"id": "in", "account_code": "1010", "debit": "500.00", "credit": "0.00"},
        {"id": "income", "account_code": "4100", "debit": "0.00", "credit": "500.00"},
        {"id": "out", "account_code": "1010", "debit": "0.00", "credit": "500.00"},
        {"id": "expense", "account_code": "5100", "debit": "500.00", "credit": "0.00"},
    ]
    values = [
        component("in", "income", "500.00", "cash_operating"),
        component("expense", "out", "500.00", "cash_operating"),
    ]
    assert validate(
        lines,
        values,
        {
            "in": [{"category": "operating", "amount": "500.00"}],
            "out": [{"category": "operating", "amount": "-500.00"}],
        },
    ) == {"cash_operating": Decimal("1000.00")}
    with pytest.raises(ValueError):
        validate(
            lines,
            values,
            {
                "in": [{"category": "operating", "amount": "0.00"}],
                "out": [{"category": "operating", "amount": "0.00"}],
            },
        )


def test_large_amounts_preserve_each_cent_without_float():
    lines = [
        {
            "id": "asset",
            "account_code": "1500",
            "debit": "9999999999999999.99",
            "credit": "0.00",
        },
        {
            "id": "debt",
            "account_code": "2300",
            "debit": "0.00",
            "credit": "9999999999999999.99",
        },
    ]
    assert validate(lines, [component(amount="9999999999999999.99")], {}) == {
        "noncash_investing_financing": Decimal("9999999999999999.99")
    }


@pytest.mark.parametrize(
    "category",
    [
        "noncash_investing",
        "noncash_financing",
        "noncash_investing_financing",
        "noncash_operating",
        "noncash_reclassification",
    ],
)
def test_noncash_categories_remain_distinct(category):
    lines = [dict(mixed()[0], debit="600.00"), mixed()[2]]
    assert validate(lines, [component(category=category)], {}) == {
        category: Decimal("600.00")
    }


def report(*, journals=None, policy=True, opening="0.00", closing="600.00"):
    builder = getattr(financial_reporting, "journal_disclosure_report", None)
    assert callable(builder), (
        "Complete posted-journal coverage report is not implemented"
    )
    candidate = {
        "journal_entry_id": "mixed",
        "entry_number": "GJ-1",
        "posting_date": "2026-10-05",
        "source_type": "manual",
        "reversal_of_entry_id": None,
        "lines": mixed(),
        "source_status": "current",
        "protected_kind": None,
        "review_status": "current",
        "components": parts(),
    }
    return builder(
        policy_valid=policy,
        financing_accounts=[
            {
                "code": "2300",
                "name": "Borrowings",
                "opening": Decimal(opening),
                "closing": Decimal(closing),
            }
        ],
        journals=[candidate] if journals is None else journals,
    )


def test_financing_rollforward_counts_only_its_liability_side():
    result = report()
    assert result["status"] == "complete_for_posted_ledger"
    assert result["coverage"] == {
        "journal_count": 1,
        "reviewed_count": 1,
        "excluded_count": 0,
        "blocked_count": 0,
    }
    assert result["financing_liabilities"] == [
        {
            "account_code": "2300",
            "account_name": "Borrowings",
            "opening_balance": "0.00",
            "cash_changes": "0.00",
            "noncash_changes": "600.00",
            "opening_adjustments": "0.00",
            "closing_balance": "600.00",
            "difference": "0.00",
            "reconciled": True,
        }
    ]
    assert len(result["noncash_components"]) == 1
    assert result["noncash_components"][0]["amount"] == "600.00"
    assert "noncash_total" not in result


@pytest.mark.parametrize(
    "status", ["review_required", "policy_changed", "source_changed"]
)
def test_missing_or_stale_review_never_certifies_balances(status):
    candidate = {
        "journal_entry_id": "unreviewed",
        "entry_number": "GJ-2",
        "posting_date": "2026-10-05",
        "source_type": "manual",
        "reversal_of_entry_id": None,
        "lines": mixed(),
        "source_status": "current",
        "protected_kind": None,
        "review_status": status,
        "components": None,
    }
    result = report(journals=[candidate])
    assert result["status"] == "disclosure_review_required"
    assert result["coverage"]["blocked_count"] == 1
    assert result["noncash_components"] == []
    assert result["financing_liabilities"][0]["noncash_changes"] is None
    assert result["financing_liabilities"][0]["reconciled"] is False


def test_financing_difference_remains_a_blocker():
    result = report(closing="601.00")
    assert result["status"] == "financing_reconciliation_required"
    assert result["financing_liabilities"][0]["difference"] == "1.00"


def test_zero_activity_requires_current_policy():
    assert report(journals=[], closing="0.00")["status"] == "complete_for_posted_ledger"
    assert (
        report(journals=[], policy=False, closing="0.00")["status"]
        == "disclosure_policy_required"
    )


def test_debt_to_equity_has_one_financing_change():
    journal = {
        "journal_entry_id": "conversion",
        "entry_number": "GJ-3",
        "posting_date": "2026-10-05",
        "source_type": "manual",
        "reversal_of_entry_id": None,
        "source_status": "current",
        "protected_kind": None,
        "review_status": "current",
        "lines": [
            {"id": "debt", "account_code": "2300", "debit": "600.00", "credit": "0.00"},
            {
                "id": "equity",
                "account_code": "3000",
                "debit": "0.00",
                "credit": "600.00",
            },
        ],
        "components": [component("debt", "equity", "600.00", "noncash_financing")],
    }
    result = report(journals=[journal], opening="600.00", closing="0.00")
    assert result["financing_liabilities"][0]["noncash_changes"] == "-600.00"
    assert result["status"] == "complete_for_posted_ledger"
