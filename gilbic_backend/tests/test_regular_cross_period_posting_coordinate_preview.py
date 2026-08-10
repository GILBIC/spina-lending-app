from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
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
    build_regular_cross_period_accounting_sequence_preview,
)
from gilbic_backend.regular_cross_period_posting_coordinate_preview import (
    REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION,
    build_regular_cross_period_posting_coordinate_preview,
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
JULY_ID = UUID("33333333-3333-4333-8333-333333333333")
AUGUST_ID = UUID("44444444-4444-4444-8444-444444444444")
OTHER_ID = UUID("55555555-5555-4555-8555-555555555555")


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
    sequence = build_regular_cross_period_accounting_sequence_preview(
        period_journal,
        collection,
    )
    assert sequence.disposition == "regular_cross_period_accounting_sequence_preview_ready"
    return sequence, periods, period_journal, collection


def _build(sequence, periods, period_journal, collection):
    return build_regular_cross_period_posting_coordinate_preview(
        sequence,
        protected_period_journal=period_journal,
        protected_collection=collection,
        protected_fiscal_periods=periods,
    )


def test_positive_periods_receive_exact_open_period_posting_coordinates() -> None:
    sequence, periods, period_journal, collection_preview = _context()

    result = _build(sequence, periods, period_journal, collection_preview)

    assert result.disposition == "regular_cross_period_posting_coordinate_preview_ready"
    assert result.blocker_code is None
    assert result.coordinate_policy_version == (
        REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION
    )
    assert result.posting_eligible is False
    assert result.automatic_source_posting_enabled is False
    assert result.posting_identity_ready is False
    assert result.zero_cent_fiscal_period_ids == ()

    july, august, collection = result.ordered_coordinates
    assert [item.sequence_order for item in result.ordered_coordinates] == [1, 2, 3]
    assert [item.entry_type for item in result.ordered_coordinates] == [
        "eir_accrual_period",
        "eir_accrual_period",
        "collection",
    ]

    assert july.fiscal_period_id == JULY_ID
    assert july.fiscal_period_label == "July 2026"
    assert july.fiscal_period_start_date == date(2026, 7, 1)
    assert july.fiscal_period_end_date == date(2026, 7, 31)
    assert july.recognition_date == date(2026, 7, 31)
    assert july.proposed_posting_date == date(2026, 7, 31)
    assert july.amount == Decimal("0.01")
    assert july.fiscal_period_status == "open"

    assert august.fiscal_period_id == AUGUST_ID
    assert august.recognition_date == date(2026, 8, 1)
    assert august.proposed_posting_date == date(2026, 8, 1)
    assert august.amount == Decimal("0.01")

    assert collection.fiscal_period_id == AUGUST_ID
    assert collection.recognition_date == date(2026, 8, 1)
    assert collection.proposed_posting_date == date(2026, 8, 1)
    assert collection.amount == Decimal("1.00")
    assert august.sequence_order < collection.sequence_order
    assert all(item.posting_eligible is False for item in result.ordered_coordinates)


def test_coordinate_preview_deliberately_has_no_posting_source_identity() -> None:
    sequence, periods, period_journal, collection = _context()

    result = _build(sequence, periods, period_journal, collection)

    assert result.posting_identity_ready is False
    for item in result.ordered_coordinates:
        assert not hasattr(item, "source_type")
        assert not hasattr(item, "source_reference")
        assert not hasattr(item, "source_event_key")
        assert not hasattr(item, "entry_number")
        assert not hasattr(item, "journal_entry_id")


def test_zero_cent_period_remains_evidence_without_fake_coordinate() -> None:
    sequence, periods, period_journal, collection_preview = _context(
        daily_eir=Decimal("0.000025")
    )
    assert sequence.zero_cent_fiscal_period_ids == (JULY_ID,)

    result = _build(sequence, periods, period_journal, collection_preview)

    assert result.disposition == "regular_cross_period_posting_coordinate_preview_ready"
    assert result.zero_cent_fiscal_period_ids == (JULY_ID,)
    assert [item.entry_type for item in result.ordered_coordinates] == [
        "eir_accrual_period",
        "collection",
    ]
    eir, collection = result.ordered_coordinates
    assert eir.fiscal_period_id == AUGUST_ID
    assert collection.fiscal_period_id == AUGUST_ID
    assert eir.proposed_posting_date == collection.proposed_posting_date


def test_same_inputs_replay_to_identical_coordinates() -> None:
    sequence, periods, period_journal, collection = _context()

    first = _build(sequence, periods, period_journal, collection)
    second = _build(sequence, periods, period_journal, collection)

    assert first == second


def test_upstream_posting_eligibility_fails_closed() -> None:
    sequence, periods, period_journal, collection = _context()
    sequence = replace(sequence, posting_eligible=True)

    result = _build(sequence, periods, period_journal, collection)

    assert result.disposition == "regular_cross_period_posting_coordinate_preview_blocked"
    assert result.blocker_code == "posting_coordinate_posting_control_review"
    assert result.ordered_coordinates == ()
    assert result.posting_identity_ready is False


def test_upstream_automatic_source_posting_fails_closed() -> None:
    sequence, periods, period_journal, collection = _context()
    sequence = replace(sequence, automatic_source_posting_enabled=True)

    result = _build(sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_coordinate_posting_control_review"
    assert result.ordered_coordinates == ()


def test_sequence_policy_tampering_fails_protected_replay() -> None:
    sequence, periods, period_journal, collection = _context()
    sequence = replace(sequence, sequence_policy_version="tampered-policy")

    result = _build(sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_coordinate_sequence_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_sequence_preview_identity_tampering_fails_protected_replay() -> None:
    sequence, periods, period_journal, collection = _context()
    first = sequence.ordered_entries[0]
    sequence = replace(
        sequence,
        ordered_entries=(
            replace(first, preview_entry_key="tampered-preview-key"),
            *sequence.ordered_entries[1:],
        ),
    )

    result = _build(sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_coordinate_sequence_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_zero_cent_period_substitution_fails_protected_replay() -> None:
    sequence, periods, period_journal, collection = _context(
        daily_eir=Decimal("0.000025")
    )
    sequence = replace(sequence, zero_cent_fiscal_period_ids=(OTHER_ID,))
    september = AccountingFiscalPeriodReference(
        period_id=OTHER_ID,
        label="September 2026",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        status="open",
    )

    result = _build(
        sequence,
        (*periods, september),
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_coordinate_sequence_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_tampered_protected_collection_fails_sequence_replay() -> None:
    sequence, periods, period_journal, collection = _context()
    collection = replace(collection, total_credit=Decimal("0.99"))

    result = _build(sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_coordinate_sequence_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_duplicate_fiscal_period_identity_fails_closed() -> None:
    sequence, periods, period_journal, collection = _context()
    july, august = periods
    periods = (july, replace(august, period_id=JULY_ID))

    result = _build(sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_coordinate_fiscal_period_set_not_exact"
    assert result.ordered_coordinates == ()


def test_overlapping_protected_fiscal_periods_fail_closed() -> None:
    sequence, periods, period_journal, collection = _context()
    july, august = periods
    overlap = AccountingFiscalPeriodReference(
        period_id=OTHER_ID,
        label="Overlap",
        start_date=date(2026, 7, 31),
        end_date=date(2026, 8, 2),
        status="open",
    )

    result = _build(sequence, (july, overlap, august), period_journal, collection)

    assert result.blocker_code == "posting_coordinate_fiscal_period_set_not_exact"
    assert result.ordered_coordinates == ()


def test_protected_period_label_must_replay_stage5d8_evidence() -> None:
    sequence, periods, period_journal, collection = _context()
    july, august = periods

    result = _build(
        sequence,
        (replace(july, label="Tampered July"), august),
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_coordinate_fiscal_period_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_protected_period_dates_must_replay_stage5d8_evidence() -> None:
    sequence, periods, period_journal, collection = _context()
    july, august = periods

    result = _build(
        sequence,
        (replace(july, start_date=date(2026, 7, 2)), august),
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_coordinate_fiscal_period_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_positive_period_status_change_fails_protected_period_replay() -> None:
    sequence, periods, period_journal, collection = _context()
    july, august = periods

    result = _build(
        sequence,
        (replace(july, status="closed"), august),
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_coordinate_fiscal_period_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_zero_cent_period_status_change_fails_protected_period_replay() -> None:
    sequence, periods, period_journal, collection = _context(
        daily_eir=Decimal("0.000025")
    )
    july, august = periods
    assert sequence.zero_cent_fiscal_period_ids == (JULY_ID,)

    result = _build(
        sequence,
        (replace(july, status="review"), august),
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_coordinate_fiscal_period_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_missing_collection_period_fails_protected_period_replay() -> None:
    sequence, periods, period_journal, collection = _context()
    july, _ = periods

    result = _build(sequence, (july,), period_journal, collection)

    assert result.blocker_code == "posting_coordinate_fiscal_period_replay_not_exact"
    assert result.ordered_coordinates == ()


def test_unrelated_future_closed_period_does_not_change_coordinates() -> None:
    sequence, periods, period_journal, collection = _context()
    future = AccountingFiscalPeriodReference(
        period_id=OTHER_ID,
        label="September 2026",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        status="closed",
    )

    result = _build(sequence, (*periods, future), period_journal, collection)

    assert result.disposition == "regular_cross_period_posting_coordinate_preview_ready"
    assert [item.fiscal_period_id for item in result.ordered_coordinates] == [
        JULY_ID,
        AUGUST_ID,
        AUGUST_ID,
    ]
    assert result.posting_identity_ready is False
