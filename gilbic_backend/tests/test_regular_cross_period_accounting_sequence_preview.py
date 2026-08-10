from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from gilbic_backend.eir_cash_allocation import (
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
)
from gilbic_backend.regular_collection_journal_preview import (
    build_regular_collection_journal_preview,
)
from gilbic_backend.regular_cross_period_accounting_sequence_preview import (
    REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION,
    build_regular_cross_period_accounting_sequence_preview,
)
from gilbic_backend.regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
    build_regular_eir_accrual_journal_preview,
)
from gilbic_backend.regular_eir_period_journal_preview import (
    build_regular_eir_period_journal_proposal_preview,
)


LOAN_ID = UUID("11111111-1111-4111-8111-111111111111")
TX_ID = UUID("22222222-2222-4222-8222-222222222222")
OTHER_TX_ID = UUID("77777777-7777-4777-8777-777777777777")
JULY_ID = UUID("33333333-3333-4333-8333-333333333333")
AUGUST_ID = UUID("44444444-4444-4444-8444-444444444444")


def _context(*, daily_eir: Decimal = Decimal("0.0001")):
    state = EirCutoverState(
        loan_id=LOAN_ID,
        calculation_mode="fixed_daily",
        cutover_date=date(2026, 7, 30),
        due_date=date(2026, 12, 6),
        measurement_status="measured",
        daily_eir=daily_eir,
        loan_component=Decimal("100.00"),
        accrued_interest_component=Decimal("0.00"),
        gross_carrying_amount=Decimal("100.00"),
    )
    event = EirCashSourceEvent(
        transaction_id=TX_ID,
        collection_date=date(2026, 8, 1),
        accepted_at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        entry_type="payment",
        amount=Decimal("1.00"),
    )
    allocation_result = allocate_event_date_eir_cash(state, (event,))
    assert allocation_result.status == "allocation_reference_ready"
    allocation = allocation_result.allocations[0]

    july = AccountingFiscalPeriodReference(
        period_id=JULY_ID,
        label="July 2026",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        status="open",
    )
    august = AccountingFiscalPeriodReference(
        period_id=AUGUST_ID,
        label="August 2026",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        status="open",
    )
    periods = (july, august)

    accrual = build_regular_eir_accrual_journal_preview(
        allocation,
        allocation_result_status=allocation_result.status,
        accrual_start_date=state.cutover_date,
        fiscal_periods=periods,
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )
    period_journal = build_regular_eir_period_journal_proposal_preview(
        accrual,
        protected_allocation=allocation,
        protected_fiscal_periods=periods,
    )
    collection = build_regular_collection_journal_preview(
        allocation,
        allocation_result_status=allocation_result.status,
        opening_balance_posted=True,
        protected_snapshot_available=True,
        protected_snapshot_reconciled=True,
        source_history_complete=True,
        account_configuration_ready=True,
    )
    return period_journal, collection


def _build(period_journal, collection):
    return build_regular_cross_period_accounting_sequence_preview(
        period_journal,
        collection,
    )


def test_positive_periods_are_recognized_in_period_order_before_collection() -> None:
    period_journal, collection = _context()
    july, august = period_journal.period_proposals
    assert july.allocated_amount == Decimal("0.01")
    assert august.allocated_amount == Decimal("0.01")

    result = _build(period_journal, collection)

    assert result.disposition == "regular_cross_period_accounting_sequence_preview_ready"
    assert result.blocker_code is None
    assert result.sequence_policy_version == (
        REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION
    )
    assert result.required_eir_accrual_before_collection == Decimal("0.02")
    assert result.posting_eligible is False
    assert result.automatic_source_posting_enabled is False
    assert result.zero_cent_fiscal_period_ids == ()
    assert [entry.sequence_order for entry in result.ordered_entries] == [1, 2, 3]
    assert [entry.entry_type for entry in result.ordered_entries] == [
        "eir_accrual_period",
        "eir_accrual_period",
        "collection",
    ]

    july_entry, august_entry, collection_entry = result.ordered_entries
    assert july_entry.fiscal_period_id == JULY_ID
    assert july_entry.recognition_date == date(2026, 7, 31)
    assert july_entry.amount == Decimal("0.01")
    assert july_entry.related_source_event_key == f"eir_accrual:collection:{TX_ID}"
    assert july_entry.preview_entry_key.endswith(f"fiscal_period:{JULY_ID}")

    assert august_entry.fiscal_period_id == AUGUST_ID
    assert august_entry.recognition_date == date(2026, 8, 1)
    assert august_entry.amount == Decimal("0.01")
    assert august_entry.related_source_event_key == f"eir_accrual:collection:{TX_ID}"

    assert collection_entry.fiscal_period_id is None
    assert collection_entry.recognition_date == date(2026, 8, 1)
    assert collection_entry.related_source_event_key == f"collection:{TX_ID}"
    assert collection_entry.amount == Decimal("1.00")
    assert collection_entry.sequence_order > august_entry.sequence_order
    assert all(entry.posting_eligible is False for entry in result.ordered_entries)


def test_zero_cent_period_remains_evidence_without_fake_sequence_entry() -> None:
    period_journal, collection = _context(daily_eir=Decimal("0.000025"))
    july, august = period_journal.period_proposals
    assert july.allocated_amount == Decimal("0.00")
    assert august.allocated_amount == Decimal("0.01")

    result = _build(period_journal, collection)

    assert result.disposition == "regular_cross_period_accounting_sequence_preview_ready"
    assert result.zero_cent_fiscal_period_ids == (JULY_ID,)
    assert [entry.entry_type for entry in result.ordered_entries] == [
        "eir_accrual_period",
        "collection",
    ]
    assert result.ordered_entries[0].fiscal_period_id == AUGUST_ID
    assert result.ordered_entries[0].recognition_date == collection.collection_date
    assert result.ordered_entries[1].entry_type == "collection"


def test_same_inputs_replay_to_identical_sequence() -> None:
    period_journal, collection = _context()

    first = _build(period_journal, collection)
    second = _build(period_journal, collection)

    assert first == second


def test_shifted_prior_period_end_blocks_without_partial_sequence() -> None:
    period_journal, collection = _context()
    july, august = period_journal.period_proposals
    tampered = replace(
        period_journal,
        period_proposals=(
            replace(july, accrual_end_date_inclusive=date(2026, 7, 30)),
            august,
        ),
    )

    result = _build(tampered, collection)

    assert result.disposition == "regular_cross_period_accounting_sequence_preview_blocked"
    assert result.blocker_code == "cross_period_eir_period_preview_not_exact"
    assert result.ordered_entries == ()
    assert result.zero_cent_fiscal_period_ids == ()
    assert result.posting_eligible is False


def test_gap_between_period_segments_blocks_without_partial_sequence() -> None:
    period_journal, collection = _context()
    july, august = period_journal.period_proposals
    tampered_august = replace(
        august,
        accrual_start_date_inclusive=august.accrual_start_date_inclusive
        + timedelta(days=1),
    )
    tampered = replace(
        period_journal,
        period_proposals=(july, tampered_august),
    )

    result = _build(tampered, collection)

    assert result.blocker_code == "cross_period_eir_period_preview_not_exact"
    assert result.ordered_entries == ()


def test_swapped_period_order_blocks_without_partial_sequence() -> None:
    period_journal, collection = _context()
    july, august = period_journal.period_proposals
    tampered = replace(period_journal, period_proposals=(august, july))

    result = _build(tampered, collection)

    assert result.blocker_code == "cross_period_eir_period_preview_not_exact"
    assert result.ordered_entries == ()


def test_period_amount_must_equal_collection_required_eir() -> None:
    period_journal, collection = _context()
    collection = replace(
        collection,
        required_eir_accrual_before_collection=Decimal("0.03"),
    )

    result = _build(period_journal, collection)

    assert result.blocker_code == "cross_period_eir_period_preview_not_exact"
    assert result.ordered_entries == ()


def test_collection_source_identity_tampering_blocks() -> None:
    period_journal, collection = _context()
    collection = replace(
        collection,
        transaction_id=OTHER_TX_ID,
        source_event_key=f"collection:{OTHER_TX_ID}",
    )

    result = _build(period_journal, collection)

    assert result.blocker_code == "cross_period_eir_period_preview_not_exact"
    assert result.ordered_entries == ()


def test_unexpected_period_posting_eligibility_blocks() -> None:
    period_journal, collection = _context()
    period_journal = replace(period_journal, posting_eligible=True)

    result = _build(period_journal, collection)

    assert result.blocker_code == "cross_period_sequence_posting_control_review"
    assert result.ordered_entries == ()
    assert result.automatic_source_posting_enabled is False


def test_unexpected_automatic_source_posting_blocks() -> None:
    period_journal, collection = _context()
    period_journal = replace(period_journal, automatic_source_posting_enabled=True)

    result = _build(period_journal, collection)

    assert result.blocker_code == (
        "cross_period_sequence_automatic_posting_control_review"
    )
    assert result.ordered_entries == ()


def test_malformed_collection_lines_block() -> None:
    period_journal, collection = _context()
    collection = replace(collection, total_credit=Decimal("0.99"))

    result = _build(period_journal, collection)

    assert result.blocker_code == "cross_period_collection_preview_not_exact"
    assert result.ordered_entries == ()
