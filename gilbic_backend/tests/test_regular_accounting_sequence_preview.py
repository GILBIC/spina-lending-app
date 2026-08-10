from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.eir_cash_allocation import EirCashAllocation
from gilbic_backend.regular_accounting_sequence_preview import (
    build_regular_accounting_sequence_preview,
)
from gilbic_backend.regular_collection_journal_preview import (
    build_regular_collection_journal_preview,
)
from gilbic_backend.regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
    build_regular_eir_accrual_journal_preview,
)


TX_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_TX_ID = UUID("22222222-2222-4222-8222-222222222222")
AUGUST_ID = UUID("33333333-3333-4333-8333-333333333333")
JULY_ID = UUID("44444444-4444-4444-8444-444444444444")


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


def fiscal_period(
    *,
    period_id: UUID = AUGUST_ID,
    label: str = "August 2026",
    start: date = date(2026, 8, 1),
    end: date = date(2026, 8, 31),
) -> AccountingFiscalPeriodReference:
    return AccountingFiscalPeriodReference(
        period_id=period_id,
        label=label,
        start_date=start,
        end_date=end,
        status="open",
    )


def ready_previews(*, accrual: str = "1.10"):
    item = allocation(accrual=accrual)
    collection = build_regular_collection_journal_preview(
        item,
        allocation_result_status="allocation_reference_ready",
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )
    eir_accrual = build_regular_eir_accrual_journal_preview(
        item,
        allocation_result_status="allocation_reference_ready",
        accrual_start_date=(
            date(2026, 8, 9) if accrual == "0.00" else date(2026, 8, 8)
        ),
        fiscal_periods=() if accrual == "0.00" else (fiscal_period(),),
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )
    return eir_accrual, collection


def test_required_eir_accrual_precedes_matching_collection() -> None:
    accrual, collection = ready_previews()

    result = build_regular_accounting_sequence_preview(accrual, collection)

    assert result.disposition == "regular_accounting_sequence_preview_ready"
    assert result.blocker_code is None
    assert result.sequence_key == f"regular_accounting_sequence:collection:{TX_ID}"
    assert result.collection_source_event_key == f"collection:{TX_ID}"
    assert result.required_eir_accrual_before_collection == Decimal("1.10")
    assert result.posting_eligible is False
    assert [
        (
            entry.sequence_order,
            entry.entry_type,
            entry.source_event_key,
            entry.posting_date,
            entry.amount,
        )
        for entry in result.ordered_entries
    ] == [
        (
            1,
            "eir_accrual",
            f"eir_accrual:collection:{TX_ID}",
            date(2026, 8, 9),
            Decimal("1.10"),
        ),
        (
            2,
            "collection",
            f"collection:{TX_ID}",
            date(2026, 8, 9),
            Decimal("15.00"),
        ),
    ]


def test_zero_cent_eir_boundary_exposes_collection_only() -> None:
    accrual, collection = ready_previews(accrual="0.00")

    result = build_regular_accounting_sequence_preview(accrual, collection)

    assert result.disposition == "regular_accounting_sequence_preview_ready"
    assert result.required_eir_accrual_before_collection == Decimal("0.00")
    assert [
        (entry.sequence_order, entry.entry_type, entry.amount)
        for entry in result.ordered_entries
    ] == [(1, "collection", Decimal("15.00"))]


def test_cross_period_accrual_blocks_the_whole_sequence() -> None:
    item = allocation()
    _, collection = ready_previews()
    july = fiscal_period(
        period_id=JULY_ID,
        label="July 2026",
        start=date(2026, 7, 1),
        end=date(2026, 7, 31),
    )
    accrual = build_regular_eir_accrual_journal_preview(
        item,
        allocation_result_status="allocation_reference_ready",
        accrual_start_date=date(2026, 7, 30),
        fiscal_periods=(july, fiscal_period()),
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )

    result = build_regular_accounting_sequence_preview(accrual, collection)

    assert result.disposition == "regular_accounting_sequence_preview_blocked"
    assert result.blocker_code == "fiscal_period_split_required"
    assert result.ordered_entries == ()
    assert result.posting_eligible is False


def test_blocked_collection_never_exposes_a_partial_accrual_sequence() -> None:
    item = allocation()
    accrual, _ = ready_previews()
    collection = build_regular_collection_journal_preview(
        item,
        allocation_result_status="allocation_reference_ready",
        opening_balance_posted=False,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )

    result = build_regular_accounting_sequence_preview(accrual, collection)

    assert result.blocker_code == "opening_balance_posting_required"
    assert result.ordered_entries == ()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda preview: replace(preview, transaction_id=OTHER_TX_ID),
        lambda preview: replace(
            preview,
            related_collection_source_event_key="collection:wrong",
        ),
        lambda preview: replace(preview, source_event_key="eir_accrual:wrong"),
        lambda preview: replace(
            preview,
            accrual_end_date_inclusive=date(2026, 8, 10),
        ),
        lambda preview: replace(preview, posting_date=date(2026, 8, 10)),
        lambda preview: replace(preview, amount=Decimal("1.11")),
    ],
)
def test_identity_date_and_amount_mismatches_fail_closed(mutate) -> None:
    accrual, collection = ready_previews()

    result = build_regular_accounting_sequence_preview(
        mutate(accrual),
        collection,
    )

    assert result.blocker_code == "accounting_sequence_identity_mismatch"
    assert result.ordered_entries == ()


@pytest.mark.parametrize("target", ["accrual", "collection"])
def test_unexpected_posting_eligibility_fails_closed(target: str) -> None:
    accrual, collection = ready_previews()
    if target == "accrual":
        accrual = replace(accrual, posting_eligible=True)
    else:
        collection = replace(collection, posting_eligible=True)

    result = build_regular_accounting_sequence_preview(accrual, collection)

    assert result.blocker_code == "accounting_sequence_posting_control_review"
    assert result.posting_eligible is False
    assert result.ordered_entries == ()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda preview: replace(preview, balanced=False),
        lambda preview: replace(preview, total_credit=Decimal("14.99")),
        lambda preview: replace(preview, proposed_lines=()),
    ],
)
def test_malformed_collection_preview_fails_closed(mutate) -> None:
    accrual, collection = ready_previews()

    result = build_regular_accounting_sequence_preview(accrual, mutate(collection))

    assert result.blocker_code == "collection_preview_not_reconciled"
    assert result.ordered_entries == ()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda preview: replace(preview, balanced=False),
        lambda preview: replace(preview, fiscal_period_status="closed"),
        lambda preview: replace(preview, total_debit=Decimal("1.09")),
        lambda preview: replace(preview, proposed_lines=()),
    ],
)
def test_malformed_eir_accrual_preview_fails_closed(mutate) -> None:
    accrual, collection = ready_previews()

    result = build_regular_accounting_sequence_preview(mutate(accrual), collection)

    assert result.blocker_code == "eir_accrual_preview_not_reconciled"
    assert result.ordered_entries == ()


def test_deterministic_replay_returns_identical_sequence() -> None:
    accrual, collection = ready_previews()

    first = build_regular_accounting_sequence_preview(accrual, collection)
    second = build_regular_accounting_sequence_preview(accrual, collection)

    assert first == second

