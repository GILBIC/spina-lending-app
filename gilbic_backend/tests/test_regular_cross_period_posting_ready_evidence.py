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
    build_regular_cross_period_posting_coordinate_preview,
)
from gilbic_backend.regular_cross_period_posting_identity_preview import (
    build_regular_cross_period_posting_identity_preview,
)
from gilbic_backend.regular_cross_period_posting_ready_evidence import (
    REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION,
    build_regular_cross_period_posting_ready_evidence_bundle,
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
    coordinates = build_regular_cross_period_posting_coordinate_preview(
        sequence,
        protected_period_journal=period_journal,
        protected_collection=collection,
        protected_fiscal_periods=periods,
    )
    identity = build_regular_cross_period_posting_identity_preview(
        coordinates,
        protected_sequence=sequence,
        protected_period_journal=period_journal,
        protected_collection=collection,
        protected_fiscal_periods=periods,
    )
    assert identity.disposition == "regular_cross_period_posting_identity_preview_ready"
    return sequence, coordinates, identity, periods, period_journal, collection


def _build(sequence, coordinates, identity, periods, period_journal, collection):
    return build_regular_cross_period_posting_ready_evidence_bundle(
        sequence,
        coordinates,
        identity,
        protected_period_journal=period_journal,
        protected_collection=collection,
        protected_fiscal_periods=periods,
    )


def test_posting_ready_bundle_fuses_exact_order_coordinates_identity_and_lines() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.disposition == "regular_cross_period_posting_ready_evidence_complete"
    assert result.blocker_code is None
    assert result.bundle_policy_version == (
        REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION
    )
    assert result.posting_coordinate_ready is True
    assert result.posting_identity_ready is True
    assert result.posting_ready_evidence_complete is True
    assert result.posting_eligible is False
    assert result.automatic_source_posting_enabled is False

    july, august, cash = result.ordered_entries
    assert [item.sequence_order for item in result.ordered_entries] == [1, 2, 3]
    assert [item.entry_type for item in result.ordered_entries] == [
        "eir_accrual_period",
        "eir_accrual_period",
        "collection",
    ]

    assert july.recognition_date == date(2026, 7, 31)
    assert july.proposed_posting_date == date(2026, 7, 31)
    assert july.fiscal_period_id == JULY_ID
    assert july.source_event_key == (
        f"eir_accrual:collection:{TX_ID}:fiscal_period:{JULY_ID}"
    )
    assert august.proposed_posting_date == date(2026, 8, 1)
    assert august.fiscal_period_id == AUGUST_ID
    assert cash.proposed_posting_date == date(2026, 8, 1)
    assert cash.source_event_key == f"collection:{TX_ID}"
    assert cash.source_type == "collection"


def test_bundle_preserves_every_upstream_preview_coordinate_and_identity() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    for sequence_entry, coordinate, identity_entry, bundled in zip(
        sequence.ordered_entries,
        coordinates.ordered_coordinates,
        identity.ordered_identities,
        result.ordered_entries,
        strict=True,
    ):
        assert bundled.sequence_order == sequence_entry.sequence_order
        assert bundled.sequence_preview_entry_key == sequence_entry.preview_entry_key
        assert bundled.coordinate_preview_key == coordinate.coordinate_preview_key
        assert bundled.identity_preview_key == identity_entry.identity_preview_key
        assert bundled.recognition_date == sequence_entry.recognition_date
        assert bundled.recognition_date == coordinate.recognition_date
        assert bundled.proposed_posting_date == coordinate.proposed_posting_date
        assert bundled.proposed_posting_date == identity_entry.proposed_posting_date
        assert bundled.amount == sequence_entry.amount
        assert bundled.amount == coordinate.amount
        assert bundled.amount == identity_entry.amount
        assert bundled.source_type == identity_entry.source_type
        assert bundled.source_reference == identity_entry.source_reference
        assert bundled.source_event_key == identity_entry.source_event_key
        assert (
            bundled.related_collection_source_event_key
            == identity_entry.related_collection_source_event_key
        )


def test_bundle_binds_exact_balanced_journal_line_evidence() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    july, august, cash = result.ordered_entries
    for eir in (july, august):
        assert eir.balanced is True
        assert eir.total_debit == eir.amount
        assert eir.total_credit == eir.amount
        assert [line.line_order for line in eir.journal_lines] == [1, 2]
        assert [
            (line.account_system_key, line.side, line.amount)
            for line in eir.journal_lines
        ] == [
            ("accrued_interest_receivable", "debit", eir.amount),
            ("interest_income_regular", "credit", eir.amount),
        ]

    assert cash.balanced is True
    assert cash.total_debit == cash.amount == Decimal("1.00")
    assert cash.total_credit == cash.amount
    assert cash.journal_lines[0].account_system_key == "cash_collector_custody"
    assert cash.journal_lines[0].side == "debit"
    assert cash.journal_lines[0].amount == Decimal("1.00")
    assert sum(
        line.amount for line in cash.journal_lines if line.side == "credit"
    ) == Decimal("1.00")


def test_bundle_is_evidence_only_and_creates_no_journal_object() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.posting_ready_evidence_complete is True
    assert result.posting_eligible is False
    assert result.automatic_source_posting_enabled is False
    assert not hasattr(result, "journal_entry_id")
    assert not hasattr(result, "entry_number")
    assert not hasattr(result, "journal_status")
    assert not hasattr(result, "posted_at")
    for entry in result.ordered_entries:
        assert entry.posting_eligible is False
        assert not hasattr(entry, "journal_entry_id")
        assert not hasattr(entry, "entry_number")
        assert not hasattr(entry, "journal_status")
        assert not hasattr(entry, "posted_at")


def test_zero_cent_period_stays_evidence_and_has_no_fake_bundle_entry() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context(
        daily_eir=Decimal("0.000025")
    )
    assert sequence.zero_cent_fiscal_period_ids == (JULY_ID,)

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.disposition == "regular_cross_period_posting_ready_evidence_complete"
    assert result.zero_cent_fiscal_period_ids == (JULY_ID,)
    assert [item.entry_type for item in result.ordered_entries] == [
        "eir_accrual_period",
        "collection",
    ]
    assert all(item.fiscal_period_id != JULY_ID for item in result.ordered_entries)
    assert result.ordered_entries[0].fiscal_period_id == AUGUST_ID


def test_same_protected_inputs_replay_to_identical_bundle() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()

    first = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )
    second = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert first == second


def test_upstream_posting_permission_fails_closed() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()
    identity = replace(identity, posting_eligible=True)

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.disposition == "regular_cross_period_posting_ready_evidence_blocked"
    assert result.blocker_code == "posting_ready_upstream_posting_control_review"
    assert result.ordered_entries == ()
    assert result.posting_ready_evidence_complete is False


def test_upstream_automatic_posting_fails_closed() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()
    identity = replace(identity, automatic_source_posting_enabled=True)

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_ready_upstream_posting_control_review"
    assert result.ordered_entries == ()


def test_sequence_substitution_fails_exact_replay() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()
    sequence = replace(sequence, sequence_key="tampered-sequence")

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_ready_sequence_replay_not_exact"
    assert result.ordered_entries == ()


def test_coordinate_substitution_fails_exact_replay() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()
    first = coordinates.ordered_coordinates[0]
    coordinates = replace(
        coordinates,
        ordered_coordinates=(
            replace(first, proposed_posting_date=date(2026, 7, 30)),
            *coordinates.ordered_coordinates[1:],
        ),
    )

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_ready_coordinate_replay_not_exact"
    assert result.ordered_entries == ()


def test_identity_substitution_fails_exact_replay() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()
    first = identity.ordered_identities[0]
    identity = replace(
        identity,
        ordered_identities=(
            replace(first, source_event_key=f"eir_accrual:collection:{TX_ID}"),
            *identity.ordered_identities[1:],
        ),
    )

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_ready_identity_replay_not_exact"
    assert result.ordered_entries == ()


def test_protected_collection_line_tampering_fails_exact_replay() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()
    collection = replace(collection, total_credit=Decimal("0.99"))

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_ready_sequence_replay_not_exact"
    assert result.ordered_entries == ()


def test_closed_affected_period_fails_coordinate_replay() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()
    july, august = periods
    periods = (replace(july, status="closed"), august)

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_ready_coordinate_replay_not_exact"
    assert result.ordered_entries == ()


def test_collection_remains_last_with_existing_collection_source_identity() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    cash = result.ordered_entries[-1]
    assert cash.entry_type == "collection"
    assert cash.source_event_key == collection.source_event_key
    assert cash.source_event_key == result.collection_source_event_key
    assert cash.related_collection_source_event_key == result.collection_source_event_key
    assert cash.upstream_related_source_event_key == collection.source_event_key


def test_bundle_source_and_preview_keys_are_unique() -> None:
    sequence, coordinates, identity, periods, period_journal, collection = _context()

    result = _build(
        sequence,
        coordinates,
        identity,
        periods,
        period_journal,
        collection,
    )

    assert len({entry.source_event_key for entry in result.ordered_entries}) == len(
        result.ordered_entries
    )
    assert len({entry.bundle_entry_key for entry in result.ordered_entries}) == len(
        result.ordered_entries
    )
    assert all(
        entry.bundle_entry_key.startswith("regular_posting_ready_evidence:")
        for entry in result.ordered_entries
    )
