from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import money
from .regular_cross_period_accounting_sequence_preview import (
    REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION,
    RegularCrossPeriodAccountingSequenceEntryPreview,
    RegularCrossPeriodAccountingSequencePreview,
)
from .regular_eir_accrual_journal_preview import AccountingFiscalPeriodReference


ZERO = Decimal("0.00")
REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION = (
    "regular_cross_period_posting_coordinates_v1"
)


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodPostingCoordinateEntryPreview:
    sequence_order: int
    entry_type: str
    coordinate_preview_key: str
    upstream_preview_entry_key: str
    recognition_date: date
    proposed_posting_date: date
    amount: Decimal
    fiscal_period_id: UUID
    fiscal_period_label: str
    fiscal_period_start_date: date
    fiscal_period_end_date: date
    fiscal_period_status: str
    posting_eligible: bool = False


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodPostingCoordinatePreview:
    transaction_id: UUID
    collection_source_event_key: str
    sequence_policy_version: str
    coordinate_policy_version: str
    disposition: str
    blocker_code: str | None
    posting_eligible: bool
    automatic_source_posting_enabled: bool
    posting_identity_ready: bool
    message: str
    ordered_coordinates: tuple[RegularCrossPeriodPostingCoordinateEntryPreview, ...]
    zero_cent_fiscal_period_ids: tuple[UUID, ...]


def _blocked(
    sequence: RegularCrossPeriodAccountingSequencePreview,
    *,
    blocker_code: str,
    message: str,
) -> RegularCrossPeriodPostingCoordinatePreview:
    return RegularCrossPeriodPostingCoordinatePreview(
        transaction_id=sequence.transaction_id,
        collection_source_event_key=sequence.collection_source_event_key,
        sequence_policy_version=sequence.sequence_policy_version,
        coordinate_policy_version=(
            REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION
        ),
        disposition="regular_cross_period_posting_coordinate_preview_blocked",
        blocker_code=blocker_code,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        posting_identity_ready=False,
        message=message,
        ordered_coordinates=(),
        zero_cent_fiscal_period_ids=(),
    )


def _coordinate_key(entry: RegularCrossPeriodAccountingSequenceEntryPreview) -> str:
    return f"regular_posting_coordinate_preview:{entry.preview_entry_key}"


def _protected_periods_are_structurally_exact(
    periods: tuple[AccountingFiscalPeriodReference, ...],
) -> bool:
    if not periods or len({period.period_id for period in periods}) != len(periods):
        return False
    for period in periods:
        if (
            not period.label.strip()
            or period.start_date > period.end_date
            or period.status not in {"open", "review", "closed"}
        ):
            return False

    ordered = sorted(
        periods,
        key=lambda item: (item.start_date, item.end_date, str(item.period_id)),
    )
    return all(
        current.start_date > previous.end_date
        for previous, current in zip(ordered, ordered[1:])
    )


def _sequence_is_structurally_exact(
    sequence: RegularCrossPeriodAccountingSequencePreview,
) -> bool:
    expected_collection_key = f"collection:{sequence.transaction_id}"
    expected_sequence_key = (
        f"regular_cross_period_sequence_preview:collection:{sequence.transaction_id}"
    )
    entries = sequence.ordered_entries
    if (
        sequence.disposition
        != "regular_cross_period_accounting_sequence_preview_ready"
        or sequence.blocker_code is not None
        or sequence.sequence_policy_version
        != REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION
        or sequence.posting_eligible
        or sequence.automatic_source_posting_enabled
        or sequence.collection_source_event_key != expected_collection_key
        or sequence.sequence_key != expected_sequence_key
        or sequence.required_eir_accrual_before_collection <= ZERO
        or sequence.required_eir_accrual_before_collection
        != money(sequence.required_eir_accrual_before_collection)
        or len(entries) < 2
        or entries[-1].entry_type != "collection"
        or [entry.sequence_order for entry in entries]
        != list(range(1, len(entries) + 1))
        or len({entry.preview_entry_key for entry in entries}) != len(entries)
        or len(set(sequence.zero_cent_fiscal_period_ids))
        != len(sequence.zero_cent_fiscal_period_ids)
    ):
        return False

    expected_eir_key = f"eir_accrual:{expected_collection_key}"
    positive_period_ids: set[UUID] = set()
    eir_total = ZERO
    previous_date: date | None = None
    for entry in entries:
        if (
            entry.posting_eligible
            or entry.amount <= ZERO
            or entry.amount != money(entry.amount)
        ):
            return False
        if previous_date is not None and entry.recognition_date < previous_date:
            return False
        previous_date = entry.recognition_date

        if entry.entry_type == "eir_accrual_period":
            if (
                entry.fiscal_period_id is None
                or entry.fiscal_period_id in positive_period_ids
                or entry.related_source_event_key != expected_eir_key
                or entry.preview_entry_key
                != (
                    "regular_eir_period_sequence_preview:collection:"
                    f"{sequence.transaction_id}:fiscal_period:{entry.fiscal_period_id}"
                )
                or entry.recognition_date > sequence.collection_date
            ):
                return False
            positive_period_ids.add(entry.fiscal_period_id)
            eir_total += entry.amount
            continue

        if entry is not entries[-1]:
            return False
        if (
            entry.entry_type != "collection"
            or entry.fiscal_period_id is not None
            or entry.related_source_event_key != expected_collection_key
            or entry.preview_entry_key
            != f"regular_collection_sequence_preview:collection:{sequence.transaction_id}"
            or entry.recognition_date != sequence.collection_date
        ):
            return False

    zero_ids = set(sequence.zero_cent_fiscal_period_ids)
    return (
        eir_total == sequence.required_eir_accrual_before_collection
        and not (positive_period_ids & zero_ids)
        and len(positive_period_ids | zero_ids) >= 2
    )


def _period_by_id(
    periods: tuple[AccountingFiscalPeriodReference, ...],
) -> dict[UUID, AccountingFiscalPeriodReference]:
    return {period.period_id: period for period in periods}


def _periods_containing_date(
    periods: tuple[AccountingFiscalPeriodReference, ...],
    target_date: date,
) -> tuple[AccountingFiscalPeriodReference, ...]:
    return tuple(
        period
        for period in periods
        if period.start_date <= target_date <= period.end_date
    )


def _coordinate(
    entry: RegularCrossPeriodAccountingSequenceEntryPreview,
    period: AccountingFiscalPeriodReference,
) -> RegularCrossPeriodPostingCoordinateEntryPreview:
    return RegularCrossPeriodPostingCoordinateEntryPreview(
        sequence_order=entry.sequence_order,
        entry_type=entry.entry_type,
        coordinate_preview_key=_coordinate_key(entry),
        upstream_preview_entry_key=entry.preview_entry_key,
        recognition_date=entry.recognition_date,
        proposed_posting_date=entry.recognition_date,
        amount=entry.amount,
        fiscal_period_id=period.period_id,
        fiscal_period_label=period.label,
        fiscal_period_start_date=period.start_date,
        fiscal_period_end_date=period.end_date,
        fiscal_period_status=period.status,
        posting_eligible=False,
    )


def build_regular_cross_period_posting_coordinate_preview(
    sequence: RegularCrossPeriodAccountingSequencePreview,
    *,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> RegularCrossPeriodPostingCoordinatePreview:
    """Prove candidate posting dates and fiscal periods without posting identity.

    Stage 5D.12 intentionally stops at read-only ledger coordinates. For every
    exact Stage 5D.10 sequence entry, the proposed posting date equals the
    already-proven recognition date and must fall in exactly the intended open
    fiscal period. No source_type, source_reference, source_event_key, journal
    number, draft, persistence record, or posting permission is created here.
    Deterministic posting identity remains a separate later policy decision.
    """

    if sequence.posting_eligible or sequence.automatic_source_posting_enabled:
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_posting_control_review",
            message=(
                "The upstream sequence unexpectedly enables posting. Posting "
                "coordinate evidence remains blocked."
            ),
        )
    if not _sequence_is_structurally_exact(sequence):
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_sequence_not_exact",
            message=(
                "The Stage 5D.10 sequence does not satisfy the exact protected "
                "identity, amount, order, and recognition-date contract."
            ),
        )
    if not _protected_periods_are_structurally_exact(protected_fiscal_periods):
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_fiscal_period_set_not_exact",
            message=(
                "Protected fiscal-period references must have unique identities, "
                "valid ranges and statuses, and no date overlap."
            ),
        )

    periods_by_id = _period_by_id(protected_fiscal_periods)
    affected_period_ids = {
        entry.fiscal_period_id
        for entry in sequence.ordered_entries
        if entry.entry_type == "eir_accrual_period"
        and entry.fiscal_period_id is not None
    } | set(sequence.zero_cent_fiscal_period_ids)

    for period_id in affected_period_ids:
        period = periods_by_id.get(period_id)
        if period is None:
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_protected_period_missing",
                message=(
                    "Every positive or zero-cent affected EIR period must exist in "
                    "the protected fiscal-period reference set."
                ),
            )
        if period.status != "open":
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_period_not_open",
                message=(
                    "All affected EIR fiscal periods must still be open before a "
                    "posting-date coordinate can be considered."
                ),
            )

    collection_periods = _periods_containing_date(
        protected_fiscal_periods,
        sequence.collection_date,
    )
    if len(collection_periods) != 1:
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_collection_period_not_exact",
            message=(
                "The collection date must belong to exactly one protected fiscal "
                "period before a posting-date coordinate can be proposed."
            ),
        )
    collection_period = collection_periods[0]
    if collection_period.status != "open":
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_collection_period_not_open",
            message="The collection posting-date fiscal period is not open.",
        )

    coordinates: list[RegularCrossPeriodPostingCoordinateEntryPreview] = []
    for entry in sequence.ordered_entries:
        if entry.entry_type == "collection":
            coordinates.append(_coordinate(entry, collection_period))
            continue

        period_id = entry.fiscal_period_id
        if period_id is None:
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_period_identity_missing",
                message="A positive EIR sequence entry is missing its fiscal period.",
            )
        period = periods_by_id.get(period_id)
        if period is None:
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_protected_period_missing",
                message="A positive EIR sequence entry has no protected fiscal period.",
            )
        if not period.start_date <= entry.recognition_date <= period.end_date:
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_recognition_outside_period",
                message=(
                    "An EIR recognition date falls outside its protected fiscal "
                    "period. No posting date is proposed."
                ),
            )
        if (
            entry.recognition_date < sequence.collection_date
            and entry.recognition_date != period.end_date
        ):
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_prior_period_end_not_exact",
                message=(
                    "An earlier fiscal-period EIR entry must retain its proven "
                    "period-end recognition date as the candidate posting date."
                ),
            )
        if (
            entry.recognition_date == sequence.collection_date
            and period.period_id != collection_period.period_id
        ):
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_same_day_period_mismatch",
                message=(
                    "Same-day final EIR and collection coordinates must resolve to "
                    "the same protected fiscal period."
                ),
            )
        coordinates.append(_coordinate(entry, period))

    if (
        [item.sequence_order for item in coordinates]
        != list(range(1, len(coordinates) + 1))
        or len({item.coordinate_preview_key for item in coordinates})
        != len(coordinates)
        or any(item.posting_eligible for item in coordinates)
        or any(
            item.proposed_posting_date != item.recognition_date
            for item in coordinates
        )
        or any(
            current.proposed_posting_date < previous.proposed_posting_date
            for previous, current in zip(coordinates, coordinates[1:])
        )
        or coordinates[-1].entry_type != "collection"
    ):
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_result_not_exact",
            message=(
                "Candidate posting coordinates must preserve exact sequence order, "
                "recognition dates, unique preview identities, and collection-last "
                "ordering."
            ),
        )

    return RegularCrossPeriodPostingCoordinatePreview(
        transaction_id=sequence.transaction_id,
        collection_source_event_key=sequence.collection_source_event_key,
        sequence_policy_version=sequence.sequence_policy_version,
        coordinate_policy_version=(
            REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION
        ),
        disposition="regular_cross_period_posting_coordinate_preview_ready",
        blocker_code=None,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        posting_identity_ready=False,
        message=(
            "Read-only candidate posting dates and fiscal-period coordinates are "
            "proven from the protected Stage 5D.10 sequence. Proposed posting dates "
            "equal the proven recognition dates and every affected period is open. "
            "Posting identity, journal draft creation, persistence, and posting "
            "remain deliberately unresolved and disabled."
        ),
        ordered_coordinates=tuple(coordinates),
        zero_cent_fiscal_period_ids=sequence.zero_cent_fiscal_period_ids,
    )
