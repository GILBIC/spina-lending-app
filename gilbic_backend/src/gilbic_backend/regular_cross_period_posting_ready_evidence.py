from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import money
from .regular_collection_journal_preview import RegularCollectionJournalPreview
from .regular_cross_period_accounting_sequence_preview import (
    REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION,
    RegularCrossPeriodAccountingSequenceEntryPreview,
    RegularCrossPeriodAccountingSequencePreview,
    build_regular_cross_period_accounting_sequence_preview,
)
from .regular_cross_period_posting_coordinate_preview import (
    REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION,
    RegularCrossPeriodPostingCoordinateEntryPreview,
    RegularCrossPeriodPostingCoordinatePreview,
    build_regular_cross_period_posting_coordinate_preview,
)
from .regular_cross_period_posting_identity_preview import (
    REGULAR_CROSS_PERIOD_POSTING_IDENTITY_PREVIEW_POLICY_VERSION,
    RegularCrossPeriodPostingIdentityEntryPreview,
    RegularCrossPeriodPostingIdentityPreview,
    build_regular_cross_period_posting_identity_preview,
)
from .regular_eir_accrual_journal_preview import AccountingFiscalPeriodReference
from .regular_eir_period_journal_preview import RegularEirPeriodJournalProposalPreview


ZERO = Decimal("0.00")
REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION = (
    "regular_cross_period_posting_ready_evidence_v1"
)


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodPostingReadyJournalLineEvidence:
    line_order: int
    account_system_key: str
    side: str
    amount: Decimal
    label: str


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodPostingReadyEntryEvidence:
    sequence_order: int
    entry_type: str
    bundle_entry_key: str
    sequence_preview_entry_key: str
    coordinate_preview_key: str
    identity_preview_key: str
    upstream_related_source_event_key: str
    source_type: str
    source_reference: str
    source_event_key: str
    related_collection_source_event_key: str
    recognition_date: date
    proposed_posting_date: date
    amount: Decimal
    fiscal_period_id: UUID
    fiscal_period_label: str
    fiscal_period_start_date: date
    fiscal_period_end_date: date
    fiscal_period_status: str
    journal_lines: tuple[RegularCrossPeriodPostingReadyJournalLineEvidence, ...]
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool
    posting_eligible: bool = False


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodPostingReadyEvidenceBundle:
    transaction_id: UUID
    collection_source_event_key: str
    sequence_policy_version: str
    coordinate_policy_version: str
    identity_policy_version: str
    bundle_policy_version: str
    disposition: str
    blocker_code: str | None
    posting_eligible: bool
    automatic_source_posting_enabled: bool
    posting_coordinate_ready: bool
    posting_identity_ready: bool
    posting_ready_evidence_complete: bool
    message: str
    ordered_entries: tuple[RegularCrossPeriodPostingReadyEntryEvidence, ...]
    zero_cent_fiscal_period_ids: tuple[UUID, ...]


def _blocked(
    identity: RegularCrossPeriodPostingIdentityPreview,
    *,
    sequence_policy_version: str,
    blocker_code: str,
    message: str,
) -> RegularCrossPeriodPostingReadyEvidenceBundle:
    return RegularCrossPeriodPostingReadyEvidenceBundle(
        transaction_id=identity.transaction_id,
        collection_source_event_key=identity.collection_source_event_key,
        sequence_policy_version=sequence_policy_version,
        coordinate_policy_version=identity.coordinate_policy_version,
        identity_policy_version=identity.identity_policy_version,
        bundle_policy_version=(
            REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION
        ),
        disposition="regular_cross_period_posting_ready_evidence_blocked",
        blocker_code=blocker_code,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        posting_coordinate_ready=False,
        posting_identity_ready=False,
        posting_ready_evidence_complete=False,
        message=message,
        ordered_entries=(),
        zero_cent_fiscal_period_ids=(),
    )


def _bundle_entry_key(
    identity: RegularCrossPeriodPostingIdentityEntryPreview,
) -> str:
    return f"regular_posting_ready_evidence:{identity.identity_preview_key}"


def _line_evidence(lines) -> tuple[RegularCrossPeriodPostingReadyJournalLineEvidence, ...]:
    return tuple(
        RegularCrossPeriodPostingReadyJournalLineEvidence(
            line_order=index,
            account_system_key=line.account_system_key,
            side=line.side,
            amount=line.amount,
            label=line.label,
        )
        for index, line in enumerate(lines, start=1)
    )


def _line_set_is_exact(
    lines: tuple[RegularCrossPeriodPostingReadyJournalLineEvidence, ...],
    *,
    amount: Decimal,
) -> tuple[bool, Decimal, Decimal]:
    if (
        amount <= ZERO
        or amount != money(amount)
        or not lines
        or [line.line_order for line in lines] != list(range(1, len(lines) + 1))
        or any(
            not line.account_system_key
            or line.side not in {"debit", "credit"}
            or line.amount <= ZERO
            or line.amount != money(line.amount)
            or not line.label
            for line in lines
        )
    ):
        return False, ZERO, ZERO

    total_debit = sum(
        (line.amount for line in lines if line.side == "debit"),
        ZERO,
    )
    total_credit = sum(
        (line.amount for line in lines if line.side == "credit"),
        ZERO,
    )
    return (
        total_debit == amount and total_credit == amount,
        total_debit,
        total_credit,
    )


def _entry_alignment_is_exact(
    sequence_entry: RegularCrossPeriodAccountingSequenceEntryPreview,
    coordinate: RegularCrossPeriodPostingCoordinateEntryPreview,
    identity: RegularCrossPeriodPostingIdentityEntryPreview,
) -> bool:
    if (
        sequence_entry.sequence_order != coordinate.sequence_order
        or coordinate.sequence_order != identity.sequence_order
        or sequence_entry.entry_type != coordinate.entry_type
        or coordinate.entry_type != identity.entry_type
        or sequence_entry.preview_entry_key != coordinate.upstream_preview_entry_key
        or coordinate.coordinate_preview_key != identity.coordinate_preview_key
        or sequence_entry.amount != coordinate.amount
        or coordinate.amount != identity.amount
        or sequence_entry.recognition_date != coordinate.recognition_date
        or coordinate.proposed_posting_date != identity.proposed_posting_date
        or coordinate.amount != money(coordinate.amount)
        or sequence_entry.posting_eligible
        or coordinate.posting_eligible
        or identity.posting_eligible
    ):
        return False

    if sequence_entry.entry_type == "eir_accrual_period":
        return (
            sequence_entry.fiscal_period_id is not None
            and sequence_entry.fiscal_period_id == coordinate.fiscal_period_id
            and coordinate.fiscal_period_id == identity.fiscal_period_id
            and identity.source_type == "regular_eir_accrual"
        )

    return (
        sequence_entry.entry_type == "collection"
        and sequence_entry.fiscal_period_id is None
        and coordinate.fiscal_period_id == identity.fiscal_period_id
        and identity.source_type == "collection"
    )


def build_regular_cross_period_posting_ready_evidence_bundle(
    sequence: RegularCrossPeriodAccountingSequencePreview,
    coordinates: RegularCrossPeriodPostingCoordinatePreview,
    identity: RegularCrossPeriodPostingIdentityPreview,
    *,
    protected_period_journal: RegularEirPeriodJournalProposalPreview,
    protected_collection: RegularCollectionJournalPreview,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> RegularCrossPeriodPostingReadyEvidenceBundle:
    """Fuse protected order, coordinates, identity and lines into read-only evidence.

    This Stage 5D.14 mapper independently replays the Stage 5D.10 sequence,
    Stage 5D.12 posting coordinates and Stage 5D.13 posting identities from the
    same protected journal/source evidence. It then binds each positive journal
    candidate to its exact balanced line set.

    ``posting_ready_evidence_complete=True`` means only that the read-only
    evidence needed by a later draft-creation control is complete. It does not
    grant posting permission and creates no journal ID, entry number, draft,
    persistence row, posting, or automatic source-posting path.
    """

    if (
        sequence.posting_eligible
        or sequence.automatic_source_posting_enabled
        or coordinates.posting_eligible
        or coordinates.automatic_source_posting_enabled
        or identity.posting_eligible
        or identity.automatic_source_posting_enabled
    ):
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_upstream_posting_control_review",
            message=(
                "An upstream protected preview unexpectedly enables posting. "
                "The posting-ready evidence bundle remains blocked."
            ),
        )

    replayed_sequence = build_regular_cross_period_accounting_sequence_preview(
        protected_period_journal,
        protected_collection,
    )
    if replayed_sequence != sequence:
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_sequence_replay_not_exact",
            message=(
                "The supplied Stage 5D.10 sequence does not exactly replay from "
                "the protected period-journal and collection evidence."
            ),
        )

    replayed_coordinates = build_regular_cross_period_posting_coordinate_preview(
        sequence,
        protected_period_journal=protected_period_journal,
        protected_collection=protected_collection,
        protected_fiscal_periods=protected_fiscal_periods,
    )
    if replayed_coordinates != coordinates:
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_coordinate_replay_not_exact",
            message=(
                "The supplied Stage 5D.12 posting coordinates do not exactly "
                "replay from the protected Stage 5D.10/source evidence."
            ),
        )

    replayed_identity = build_regular_cross_period_posting_identity_preview(
        coordinates,
        protected_sequence=sequence,
        protected_period_journal=protected_period_journal,
        protected_collection=protected_collection,
        protected_fiscal_periods=protected_fiscal_periods,
    )
    if replayed_identity != identity:
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_identity_replay_not_exact",
            message=(
                "The supplied Stage 5D.13 posting identities do not exactly "
                "replay from the protected coordinates and source evidence."
            ),
        )

    if (
        replayed_sequence.disposition
        != "regular_cross_period_accounting_sequence_preview_ready"
        or replayed_sequence.blocker_code is not None
        or replayed_sequence.sequence_policy_version
        != REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION
        or replayed_coordinates.disposition
        != "regular_cross_period_posting_coordinate_preview_ready"
        or replayed_coordinates.blocker_code is not None
        or replayed_coordinates.coordinate_policy_version
        != REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION
        or replayed_coordinates.posting_identity_ready
        or replayed_identity.disposition
        != "regular_cross_period_posting_identity_preview_ready"
        or replayed_identity.blocker_code is not None
        or replayed_identity.identity_policy_version
        != REGULAR_CROSS_PERIOD_POSTING_IDENTITY_PREVIEW_POLICY_VERSION
        or not replayed_identity.posting_identity_ready
        or not replayed_sequence.ordered_entries
        or not replayed_coordinates.ordered_coordinates
        or not replayed_identity.ordered_identities
    ):
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_upstream_evidence_not_ready",
            message=(
                "The protected sequence, posting-coordinate, and posting-identity "
                "previews are not simultaneously exact and ready."
            ),
        )

    zero_cent_ids = replayed_sequence.zero_cent_fiscal_period_ids
    if (
        replayed_coordinates.zero_cent_fiscal_period_ids != zero_cent_ids
        or replayed_identity.zero_cent_fiscal_period_ids != zero_cent_ids
        or len(set(zero_cent_ids)) != len(zero_cent_ids)
    ):
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_zero_cent_evidence_not_exact",
            message="Zero-cent fiscal-period evidence does not exactly agree upstream.",
        )

    if not (
        len(replayed_sequence.ordered_entries)
        == len(replayed_coordinates.ordered_coordinates)
        == len(replayed_identity.ordered_identities)
    ):
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_entry_count_not_exact",
            message="Protected sequence, coordinate, and identity entry counts differ.",
        )

    positive_period_proposals = {
        proposal.fiscal_period_id: proposal
        for proposal in protected_period_journal.period_proposals
        if proposal.allocated_amount > ZERO
    }
    if (
        len(positive_period_proposals)
        != sum(
            1
            for entry in replayed_sequence.ordered_entries
            if entry.entry_type == "eir_accrual_period"
        )
        or any(period_id in positive_period_proposals for period_id in zero_cent_ids)
    ):
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_period_line_source_not_exact",
            message=(
                "Positive and zero-cent period journal evidence does not exactly "
                "match the protected sequence."
            ),
        )

    entries: list[RegularCrossPeriodPostingReadyEntryEvidence] = []
    for sequence_entry, coordinate, identity_entry in zip(
        replayed_sequence.ordered_entries,
        replayed_coordinates.ordered_coordinates,
        replayed_identity.ordered_identities,
        strict=True,
    ):
        if not _entry_alignment_is_exact(
            sequence_entry,
            coordinate,
            identity_entry,
        ):
            return _blocked(
                identity,
                sequence_policy_version=sequence.sequence_policy_version,
                blocker_code="posting_ready_entry_alignment_not_exact",
                message=(
                    "Sequence, coordinate, and identity evidence do not align "
                    "exactly for one protected journal candidate."
                ),
            )

        if sequence_entry.entry_type == "eir_accrual_period":
            proposal = positive_period_proposals.get(coordinate.fiscal_period_id)
            if (
                proposal is None
                or proposal.posting_eligible
                or not proposal.balanced
                or proposal.allocated_amount != coordinate.amount
                or proposal.total_debit != coordinate.amount
                or proposal.total_credit != coordinate.amount
            ):
                return _blocked(
                    identity,
                    sequence_policy_version=sequence.sequence_policy_version,
                    blocker_code="posting_ready_period_journal_lines_not_exact",
                    message=(
                        "A positive EIR journal candidate does not exactly bind "
                        "to its protected balanced fiscal-period line proposal."
                    ),
                )
            source_lines = proposal.proposed_lines
        else:
            if (
                protected_collection.posting_eligible
                or not protected_collection.balanced
                or protected_collection.amount != coordinate.amount
                or protected_collection.total_debit != coordinate.amount
                or protected_collection.total_credit != coordinate.amount
                or protected_collection.source_event_key
                != identity_entry.source_event_key
            ):
                return _blocked(
                    identity,
                    sequence_policy_version=sequence.sequence_policy_version,
                    blocker_code="posting_ready_collection_journal_lines_not_exact",
                    message=(
                        "The collection journal candidate does not exactly bind "
                        "to its protected balanced collection line proposal."
                    ),
                )
            source_lines = protected_collection.proposed_lines

        lines = _line_evidence(source_lines)
        lines_exact, total_debit, total_credit = _line_set_is_exact(
            lines,
            amount=coordinate.amount,
        )
        if not lines_exact:
            return _blocked(
                identity,
                sequence_policy_version=sequence.sequence_policy_version,
                blocker_code="posting_ready_journal_line_set_not_exact",
                message=(
                    "A protected journal line set is not positive-cent, balanced, "
                    "contiguous, and exactly equal to its journal amount."
                ),
            )

        entries.append(
            RegularCrossPeriodPostingReadyEntryEvidence(
                sequence_order=sequence_entry.sequence_order,
                entry_type=sequence_entry.entry_type,
                bundle_entry_key=_bundle_entry_key(identity_entry),
                sequence_preview_entry_key=sequence_entry.preview_entry_key,
                coordinate_preview_key=coordinate.coordinate_preview_key,
                identity_preview_key=identity_entry.identity_preview_key,
                upstream_related_source_event_key=(
                    sequence_entry.related_source_event_key
                ),
                source_type=identity_entry.source_type,
                source_reference=identity_entry.source_reference,
                source_event_key=identity_entry.source_event_key,
                related_collection_source_event_key=(
                    identity_entry.related_collection_source_event_key
                ),
                recognition_date=coordinate.recognition_date,
                proposed_posting_date=coordinate.proposed_posting_date,
                amount=coordinate.amount,
                fiscal_period_id=coordinate.fiscal_period_id,
                fiscal_period_label=coordinate.fiscal_period_label,
                fiscal_period_start_date=coordinate.fiscal_period_start_date,
                fiscal_period_end_date=coordinate.fiscal_period_end_date,
                fiscal_period_status=coordinate.fiscal_period_status,
                journal_lines=lines,
                total_debit=total_debit,
                total_credit=total_credit,
                balanced=True,
                posting_eligible=False,
            )
        )

    source_keys = [entry.source_event_key for entry in entries]
    bundle_keys = [entry.bundle_entry_key for entry in entries]
    if (
        [entry.sequence_order for entry in entries]
        != list(range(1, len(entries) + 1))
        or len(set(source_keys)) != len(source_keys)
        or len(set(bundle_keys)) != len(bundle_keys)
        or any(entry.posting_eligible for entry in entries)
        or any(not entry.balanced for entry in entries)
        or entries[-1].entry_type != "collection"
        or entries[-1].source_event_key
        != replayed_sequence.collection_source_event_key
        or entries[-1].related_collection_source_event_key
        != replayed_sequence.collection_source_event_key
        or any(
            current.proposed_posting_date < previous.proposed_posting_date
            for previous, current in zip(entries, entries[1:])
        )
    ):
        return _blocked(
            identity,
            sequence_policy_version=sequence.sequence_policy_version,
            blocker_code="posting_ready_result_not_exact",
            message=(
                "The fused posting-ready evidence must preserve exact order, "
                "balanced lines, distinct posting identities, nondecreasing "
                "posting dates, and collection-last ordering."
            ),
        )

    return RegularCrossPeriodPostingReadyEvidenceBundle(
        transaction_id=replayed_sequence.transaction_id,
        collection_source_event_key=replayed_sequence.collection_source_event_key,
        sequence_policy_version=replayed_sequence.sequence_policy_version,
        coordinate_policy_version=replayed_coordinates.coordinate_policy_version,
        identity_policy_version=replayed_identity.identity_policy_version,
        bundle_policy_version=(
            REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION
        ),
        disposition="regular_cross_period_posting_ready_evidence_complete",
        blocker_code=None,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        posting_coordinate_ready=True,
        posting_identity_ready=True,
        posting_ready_evidence_complete=True,
        message=(
            "Exact read-only posting-ready evidence is complete for the protected "
            "cross-period Regular sequence: order, fiscal-period/posting-date "
            "coordinates, deterministic source identities, and balanced journal "
            "lines are fused all-or-none. This is evidence only; no journal draft, "
            "persistence row, posting permission, posted entry, or automatic "
            "source-posting path is created."
        ),
        ordered_entries=tuple(entries),
        zero_cent_fiscal_period_ids=zero_cent_ids,
    )
