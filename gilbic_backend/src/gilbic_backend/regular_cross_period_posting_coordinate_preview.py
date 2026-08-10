from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from .regular_collection_journal_preview import RegularCollectionJournalPreview
from .regular_cross_period_accounting_sequence_preview import (
    REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION,
    RegularCrossPeriodAccountingSequenceEntryPreview,
    RegularCrossPeriodAccountingSequencePreview,
    build_regular_cross_period_accounting_sequence_preview,
)
from .regular_eir_accrual_journal_preview import AccountingFiscalPeriodReference
from .regular_eir_period_journal_preview import RegularEirPeriodJournalProposalPreview


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


def _affected_period_replay_is_exact(
    period_journal: RegularEirPeriodJournalProposalPreview,
    periods: tuple[AccountingFiscalPeriodReference, ...],
) -> bool:
    proposals = period_journal.period_proposals
    if (
        not proposals
        or len({proposal.fiscal_period_id for proposal in proposals}) != len(proposals)
    ):
        return False

    by_id = {period.period_id: period for period in periods}
    for proposal in proposals:
        period = by_id.get(proposal.fiscal_period_id)
        if period is None:
            return False
        if (
            period.label != proposal.fiscal_period_label
            or period.start_date != proposal.period_start_date
            or period.end_date != proposal.period_end_date
            or period.status != "open"
        ):
            return False
    return True


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
    protected_period_journal: RegularEirPeriodJournalProposalPreview,
    protected_collection: RegularCollectionJournalPreview,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> RegularCrossPeriodPostingCoordinatePreview:
    """Prove candidate posting dates and fiscal periods without posting identity.

    The Stage 5D.10 sequence must replay exactly from the protected Stage 5D.8
    period journal and protected collection preview. Each affected fiscal-period
    reference must replay by ID, label and date boundaries and must still be open.
    Candidate posting dates equal the already-proven recognition dates.

    This mapper creates no source_type, source_reference, source_event_key, journal
    number, journal draft, persistence record, or posting permission. Deterministic
    posting identity remains a separate later policy decision.
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

    replayed_sequence = build_regular_cross_period_accounting_sequence_preview(
        protected_period_journal,
        protected_collection,
    )
    if replayed_sequence != sequence:
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_sequence_replay_not_exact",
            message=(
                "The supplied Stage 5D.10 sequence does not exactly replay from "
                "the protected Stage 5D.8 period journal and collection previews."
            ),
        )
    if (
        replayed_sequence.disposition
        != "regular_cross_period_accounting_sequence_preview_ready"
        or replayed_sequence.blocker_code is not None
        or replayed_sequence.sequence_policy_version
        != REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION
        or replayed_sequence.posting_eligible
        or replayed_sequence.automatic_source_posting_enabled
        or not replayed_sequence.ordered_entries
        or replayed_sequence.ordered_entries[-1].entry_type != "collection"
    ):
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_sequence_not_ready",
            message="The protected Stage 5D.10 sequence is not an exact ready preview.",
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
    if not _affected_period_replay_is_exact(
        protected_period_journal,
        protected_fiscal_periods,
    ):
        return _blocked(
            sequence,
            blocker_code="posting_coordinate_fiscal_period_replay_not_exact",
            message=(
                "Affected fiscal-period references do not exactly replay the Stage "
                "5D.8 period IDs, labels and date boundaries, or are no longer open."
            ),
        )

    periods_by_id = {
        period.period_id: period for period in protected_fiscal_periods
    }
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

        if entry.entry_type != "eir_accrual_period" or entry.fiscal_period_id is None:
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_entry_type_review",
                message="The protected sequence contains an unexpected entry type.",
            )
        period = periods_by_id.get(entry.fiscal_period_id)
        if period is None or period.status != "open":
            return _blocked(
                sequence,
                blocker_code="posting_coordinate_period_not_open",
                message="A positive EIR posting coordinate has no exact open period.",
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
