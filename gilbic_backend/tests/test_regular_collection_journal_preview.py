from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.eir_cash_allocation import EirCashAllocation
from gilbic_backend.regular_collection_journal_preview import (
    build_regular_collection_journal_preview,
)


TX_ID = UUID("11111111-1111-4111-8111-111111111111")


def allocation(
    *,
    amount: str = "15.00",
    accrued: str = "11.10",
    loan: str = "3.90",
    required_accrual: str = "1.10",
    disposition: str = "allocation_reference_ready",
) -> EirCashAllocation:
    cash = Decimal(amount)
    to_accrued = Decimal(accrued)
    to_loan = Decimal(loan)
    return EirCashAllocation(
        transaction_id=TX_ID,
        source_event_key=f"collection:{TX_ID}",
        collection_date=date(2026, 8, 9),
        amount=cash,
        effective_interest_accrued_since_prior_event=Decimal(required_accrual),
        gross_carrying_before=Decimal("111.10"),
        accrued_interest_before=Decimal("11.10"),
        loan_component_before=Decimal("100.00"),
        cash_to_accrued_interest=to_accrued,
        cash_to_loan_component=to_loan,
        gross_carrying_after=Decimal("96.10"),
        accrued_interest_after=Decimal("0.00"),
        loan_component_after=Decimal("96.10"),
        posting_eligible=False,
        disposition=disposition,
        message="Read-only allocation reference.",
    )


def preview(item: EirCashAllocation, **overrides: object):
    values: dict[str, object] = {
        "allocation_result_status": "allocation_reference_ready",
        "opening_balance_posted": True,
        "protected_snapshot_available": True,
        "protected_snapshot_reconciled": True,
        "source_history_complete": True,
        "account_configuration_ready": True,
    }
    values.update(overrides)
    return build_regular_collection_journal_preview(item, **values)  # type: ignore[arg-type]


def test_mixed_regular_cash_builds_exact_balanced_read_only_lines() -> None:
    result = preview(allocation())

    assert result.disposition == "collection_journal_lines_preview_ready"
    assert result.posting_eligible is False
    assert result.balanced is True
    assert result.total_debit == Decimal("15.00")
    assert result.total_credit == Decimal("15.00")
    assert result.required_eir_accrual_before_collection == Decimal("1.10")
    assert [
        (line.account_system_key, line.side, line.amount)
        for line in result.proposed_lines
    ] == [
        ("cash_collector_custody", "debit", Decimal("15.00")),
        ("accrued_interest_receivable", "credit", Decimal("11.10")),
        ("loans_receivable_regular", "credit", Decimal("3.90")),
    ]


@pytest.mark.parametrize(
    ("item", "expected_keys"),
    [
        (
            allocation(amount="5.00", accrued="5.00", loan="0.00"),
            ["cash_collector_custody", "accrued_interest_receivable"],
        ),
        (
            allocation(amount="5.00", accrued="0.00", loan="5.00"),
            ["cash_collector_custody", "loans_receivable_regular"],
        ),
    ],
)
def test_zero_credit_lines_are_omitted(
    item: EirCashAllocation,
    expected_keys: list[str],
) -> None:
    result = preview(item)

    assert result.balanced is True
    assert [line.account_system_key for line in result.proposed_lines] == expected_keys


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"opening_balance_posted": False}, "opening_balance_posting_required"),
        (
            {"protected_snapshot_available": False},
            "protected_cutover_snapshot_required",
        ),
        (
            {"protected_snapshot_reconciled": False},
            "protected_cutover_snapshot_not_reconciled",
        ),
        ({"source_history_complete": False}, "source_history_incomplete"),
        (
            {
                "account_configuration_ready": False,
                "account_configuration_blocker": "Missing account 1020.",
            },
            "account_configuration_required",
        ),
        ({"is_voided": True}, "voided_before_accounting"),
        ({"existing_journal_status": "draft"}, "draft_exists"),
        ({"existing_journal_status": "posted"}, "already_posted"),
        ({"reversal_status": "draft"}, "reversal_draft_exists"),
        ({"reversal_status": "posted"}, "already_reversed"),
        (
            {"allocation_result_status": "post_maturity_review_required"},
            "eir_allocation_not_ready",
        ),
    ],
)
def test_safety_gates_never_expose_lines(
    overrides: dict[str, object],
    expected: str,
) -> None:
    result = preview(allocation(), **overrides)

    assert result.disposition == expected
    assert result.posting_eligible is False
    assert result.proposed_lines == ()
    assert result.balanced is False


def test_unreconciled_or_invalid_split_is_blocked() -> None:
    mismatch = preview(allocation(amount="15.00", accrued="10.00", loan="4.99"))
    negative = preview(
        allocation(
            amount="15.00",
            accrued="15.00",
            loan="0.00",
            required_accrual="-0.01",
        )
    )

    assert mismatch.disposition == "allocation_not_reconciled"
    assert negative.disposition == "allocation_components_invalid"


def test_deterministic_replay_returns_identical_preview() -> None:
    first = preview(allocation())
    second = preview(allocation())

    assert first == second
    assert first.source_event_key == f"collection:{TX_ID}"
