from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.eir_cash_allocation import EirCashAllocation
from gilbic_backend.regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
    build_regular_eir_accrual_journal_preview,
)


TX_ID = UUID("11111111-1111-4111-8111-111111111111")
AUGUST_ID = UUID("22222222-2222-4222-8222-222222222222")
JULY_ID = UUID("33333333-3333-4333-8333-333333333333")


def allocation(*, accrual: str = "1.10") -> EirCashAllocation:
    return EirCashAllocation(
        transaction_id=TX_ID,
        source_event_key=f"collection:{TX_ID}",
        collection_date=date(2026, 8, 9),
        amount=Decimal("15.00"),
        effective_interest_accrued_since_prior_event=Decimal(accrual),
        gross_carrying_before=Decimal("111.10"),
        accrued_interest_before=Decimal("11.10"),
        loan_component_before=Decimal("100.00"),
        cash_to_accrued_interest=Decimal("11.10"),
        cash_to_loan_component=Decimal("3.90"),
        gross_carrying_after=Decimal("96.10"),
        accrued_interest_after=Decimal("0.00"),
        loan_component_after=Decimal("96.10"),
        posting_eligible=False,
        disposition="allocation_reference_ready",
        message="Read-only allocation reference.",
    )


def period(
    *,
    period_id: UUID = AUGUST_ID,
    label: str = "August 2026",
    start: date = date(2026, 8, 1),
    end: date = date(2026, 8, 31),
    status: str = "open",
) -> AccountingFiscalPeriodReference:
    return AccountingFiscalPeriodReference(
        period_id=period_id,
        label=label,
        start_date=start,
        end_date=end,
        status=status,
    )


def preview(item: EirCashAllocation, **overrides: object):
    values: dict[str, object] = {
        "allocation_result_status": "allocation_reference_ready",
        "accrual_start_date": date(2026, 8, 8),
        "fiscal_periods": (period(),),
        "opening_balance_posted": True,
        "protected_snapshot_available": True,
        "protected_snapshot_reconciled": True,
        "source_history_complete": True,
        "account_configuration_ready": True,
    }
    values.update(overrides)
    return build_regular_eir_accrual_journal_preview(  # type: ignore[arg-type]
        item,
        **values,
    )


def test_open_single_period_builds_exact_balanced_read_only_accrual() -> None:
    result = preview(allocation())

    assert result.disposition == "eir_accrual_journal_lines_preview_ready"
    assert result.source_event_key == f"eir_accrual:collection:{TX_ID}"
    assert result.related_collection_source_event_key == f"collection:{TX_ID}"
    assert result.fiscal_period_id == AUGUST_ID
    assert result.fiscal_period_status == "open"
    assert result.amount == Decimal("1.10")
    assert result.posting_eligible is False
    assert result.balanced is True
    assert result.total_debit == result.total_credit == Decimal("1.10")
    assert [
        (line.account_system_key, line.side, line.amount)
        for line in result.proposed_lines
    ] == [
        ("accrued_interest_receivable", "debit", Decimal("1.10")),
        ("interest_income_regular", "credit", Decimal("1.10")),
    ]


def test_zero_cent_boundary_requires_no_accrual_journal() -> None:
    result = preview(
        allocation(accrual="0.00"),
        fiscal_periods=(),
        accrual_start_date=date(2026, 8, 9),
        collection_journal_status="posted",
    )

    assert result.disposition == "no_eir_accrual_required"
    assert result.proposed_lines == ()
    assert result.total_debit == result.total_credit == Decimal("0.00")
    assert result.balanced is True
    assert result.posting_eligible is False


def test_cross_period_interval_fails_closed_until_split_policy_exists() -> None:
    july = period(
        period_id=JULY_ID,
        label="July 2026",
        start=date(2026, 7, 1),
        end=date(2026, 7, 31),
    )
    result = preview(
        allocation(),
        accrual_start_date=date(2026, 7, 30),
        fiscal_periods=(july, period()),
    )

    assert result.disposition == "fiscal_period_split_required"
    assert result.proposed_lines == ()
    assert result.balanced is False


@pytest.mark.parametrize("status", ["review", "closed"])
def test_non_open_period_never_exposes_lines(status: str) -> None:
    result = preview(allocation(), fiscal_periods=(period(status=status),))

    assert result.disposition == "fiscal_period_not_open"
    assert result.fiscal_period_status == status
    assert result.proposed_lines == ()


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
                "account_configuration_blocker": "Missing account 4000.",
            },
            "account_configuration_required",
        ),
        ({"is_voided": True}, "voided_before_accounting"),
        ({"existing_accrual_journal_status": "draft"}, "draft_exists"),
        ({"existing_accrual_journal_status": "posted"}, "already_posted"),
        ({"accrual_reversal_status": "draft"}, "reversal_draft_exists"),
        ({"accrual_reversal_status": "posted"}, "already_reversed"),
        (
            {"collection_journal_status": "draft"},
            "collection_accounting_precedes_accrual_review",
        ),
        (
            {"allocation_result_status": "post_maturity_review_required"},
            "eir_allocation_not_ready",
        ),
        ({"fiscal_periods": ()}, "fiscal_period_required"),
    ],
)
def test_safety_gates_never_expose_accrual_lines(
    overrides: dict[str, object],
    expected: str,
) -> None:
    result = preview(allocation(), **overrides)

    assert result.disposition == expected
    assert result.posting_eligible is False
    assert result.proposed_lines == ()
    assert result.balanced is False


def test_negative_accrual_and_invalid_boundary_are_blocked() -> None:
    negative = preview(allocation(accrual="-0.01"))
    reversed_boundary = preview(
        allocation(),
        accrual_start_date=date(2026, 8, 10),
    )
    positive_same_day = preview(
        allocation(),
        accrual_start_date=date(2026, 8, 9),
    )

    assert negative.disposition == "accrual_boundary_invalid"
    assert reversed_boundary.disposition == "accrual_boundary_invalid"
    assert positive_same_day.disposition == "accrual_boundary_invalid"


def test_deterministic_replay_returns_identical_preview() -> None:
    first = preview(allocation())
    second = preview(allocation())

    assert first == second
