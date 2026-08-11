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
    REGULAR_CROSS_PERIOD_POSTING_IDENTITY_PREVIEW_POLICY_VERSION,
    build_regular_cross_period_posting_identity_preview,
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
    assert (
        coordinates.disposition
        == "regular_cross_period_posting_coordinate_preview_ready"
    )
    return coordinates, sequence, periods, period_journal, collection


def _build(coordinates, sequence, periods, period_journal, collection):
    return build_regular_cross_period_posting_identity_preview(
        coordinates,
        protected_sequence=sequence,
        protected_period_journal=period_journal,
        protected_collection=collection,
        protected_fiscal_periods=periods,
    )


def test_cross_period_identity_is_deterministic_and_collision_free() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.disposition == "regular_cross_period_posting_identity_preview_ready"
    assert result.blocker_code is None
    assert result.identity_policy_version == (
        REGULAR_CROSS_PERIOD_POSTING_IDENTITY_PREVIEW_POLICY_VERSION
    )
    assert result.posting_identity_ready is True
    assert result.posting_eligible is False
    assert result.automatic_source_posting_enabled is False

    july, august, cash = result.ordered_identities
    assert [item.sequence_order for item in result.ordered_identities] == [1, 2, 3]
    assert [item.entry_type for item in result.ordered_identities] == [
        "eir_accrual_period",
        "eir_accrual_period",
        "collection",
    ]

    assert july.source_type == "regular_eir_accrual"
    assert july.source_reference == f"{TX_ID}:fiscal_period:{JULY_ID}"
    assert july.source_event_key == (
        f"eir_accrual:collection:{TX_ID}:fiscal_period:{JULY_ID}"
    )
    assert august.source_event_key == (
        f"eir_accrual:collection:{TX_ID}:fiscal_period:{AUGUST_ID}"
    )

    assert cash.source_type == "collection"
    assert cash.source_reference == str(TX_ID)
    assert cash.source_event_key == f"collection:{TX_ID}"
    assert cash.source_event_key == result.collection_source_event_key

    keys = [item.source_event_key for item in result.ordered_identities]
    assert len(keys) == len(set(keys))
    assert f"eir_accrual:collection:{TX_ID}" not in keys
    assert all(item.posting_eligible is False for item in result.ordered_identities)


def test_identity_keeps_proven_coordinates_unchanged() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()

    result = _build(coordinates, sequence, periods, period_journal, collection)

    for coordinate, identity in zip(
        coordinates.ordered_coordinates,
        result.ordered_identities,
        strict=True,
    ):
        assert identity.sequence_order == coordinate.sequence_order
        assert identity.entry_type == coordinate.entry_type
        assert identity.coordinate_preview_key == coordinate.coordinate_preview_key
        assert identity.amount == coordinate.amount
        assert identity.proposed_posting_date == coordinate.proposed_posting_date
        assert identity.fiscal_period_id == coordinate.fiscal_period_id


def test_identity_preview_has_no_journal_object_or_posting_permission() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.posting_identity_ready is True
    assert result.posting_eligible is False
    for item in result.ordered_identities:
        assert not hasattr(item, "journal_entry_id")
        assert not hasattr(item, "entry_number")
        assert not hasattr(item, "journal_status")
        assert not hasattr(item, "posted_at")
        assert item.posting_eligible is False


def test_zero_cent_period_receives_no_fake_posting_identity() -> None:
    coordinates, sequence, periods, period_journal, collection = _context(
        daily_eir=Decimal("0.000025")
    )
    assert coordinates.zero_cent_fiscal_period_ids == (JULY_ID,)

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.disposition == "regular_cross_period_posting_identity_preview_ready"
    assert result.zero_cent_fiscal_period_ids == (JULY_ID,)
    assert [item.entry_type for item in result.ordered_identities] == [
        "eir_accrual_period",
        "collection",
    ]
    assert all(item.fiscal_period_id != JULY_ID for item in result.ordered_identities)


def test_same_protected_inputs_replay_to_identical_identity() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()

    first = _build(coordinates, sequence, periods, period_journal, collection)
    second = _build(coordinates, sequence, periods, period_journal, collection)

    assert first == second


def test_coordinate_posting_eligibility_fails_closed() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    coordinates = replace(coordinates, posting_eligible=True)

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.disposition == "regular_cross_period_posting_identity_preview_blocked"
    assert result.blocker_code == "posting_identity_posting_control_review"
    assert result.ordered_identities == ()
    assert result.posting_identity_ready is False


def test_coordinate_automatic_posting_fails_closed() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    coordinates = replace(coordinates, automatic_source_posting_enabled=True)

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_identity_posting_control_review"
    assert result.ordered_identities == ()


def test_coordinate_cannot_claim_identity_was_already_ready() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    coordinates = replace(coordinates, posting_identity_ready=True)

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_identity_posting_control_review"
    assert result.ordered_identities == ()


def test_coordinate_preview_key_tampering_fails_exact_replay() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    first = coordinates.ordered_coordinates[0]
    coordinates = replace(
        coordinates,
        ordered_coordinates=(
            replace(first, coordinate_preview_key="tampered-coordinate"),
            *coordinates.ordered_coordinates[1:],
        ),
    )

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_identity_coordinate_replay_not_exact"
    assert result.ordered_identities == ()


def test_collection_source_key_tampering_fails_exact_replay() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    coordinates = replace(
        coordinates,
        collection_source_event_key=f"collection:{JULY_ID}",
    )

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_identity_coordinate_replay_not_exact"
    assert result.ordered_identities == ()


def test_protected_sequence_substitution_fails_exact_replay() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    sequence = replace(sequence, collection_source_event_key=f"collection:{JULY_ID}")

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_identity_coordinate_replay_not_exact"
    assert result.ordered_identities == ()


def test_protected_period_journal_tampering_fails_exact_replay() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    period_journal = replace(period_journal, period_allocated_total=Decimal("0.01"))

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_identity_coordinate_replay_not_exact"
    assert result.ordered_identities == ()


def test_protected_collection_tampering_fails_exact_replay() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    collection = replace(collection, total_credit=Decimal("0.99"))

    result = _build(coordinates, sequence, periods, period_journal, collection)

    assert result.blocker_code == "posting_identity_coordinate_replay_not_exact"
    assert result.ordered_identities == ()


def test_closed_affected_period_fails_exact_replay() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()
    july, august = periods

    result = _build(
        coordinates,
        sequence,
        (replace(july, status="closed"), august),
        period_journal,
        collection,
    )

    assert result.blocker_code == "posting_identity_coordinate_replay_not_exact"
    assert result.ordered_identities == ()


def test_collection_identity_is_existing_source_key_not_new_namespace() -> None:
    coordinates, sequence, periods, period_journal, collection = _context()

    result = _build(coordinates, sequence, periods, period_journal, collection)

    cash = result.ordered_identities[-1]
    assert cash.entry_type == "collection"
    assert cash.source_event_key == collection.source_event_key
    assert cash.source_event_key == sequence.collection_source_event_key
