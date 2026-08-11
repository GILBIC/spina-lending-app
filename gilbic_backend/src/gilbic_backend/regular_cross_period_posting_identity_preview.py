from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from .regular_collection_journal_preview import RegularCollectionJournalPreview
from .regular_cross_period_accounting_sequence_preview import (
    RegularCrossPeriodAccountingSequencePreview,
)
from .regular_cross_period_posting_coordinate_preview import (
    REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION,
    RegularCrossPeriodPostingCoordinateEntryPreview,
    RegularCrossPeriodPostingCoordinatePreview,
    build_regular_cross_period_posting_coordinate_preview,
)
from .regular_eir_accrual_journal_preview import AccountingFiscalPeriodReference
from .regular_eir_period_journal_preview import RegularEirPeriodJournalProposalPreview


REGULAR_CROSS_PERIOD_POSTING_IDENTITY_PREVIEW_POLICY_VERSION = (
    "regular_cross_period_posting_identity_v1"
)


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodPostingIdentityEntryPreview:
    sequence_order: int
    entry_type: str
    identity_preview_key: str
    coordinate_preview_key: str
    source_type: str
    source_reference: str
    source_event_key: str
    related_collection_source_event_key: str
    amount: Decimal
    proposed_posting_date: date
    fiscal_period_id: UUID
    posting_eligible: bool = False


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodPostingIdentityPreview:
    transaction_id: UUID
    collection_source_event_key: str
    coordinate_policy_version: str
    identity_policy_version: str
    disposition: str
    blocker_code: str | None
    posting_eligible: bool
    automatic_source_posting_enabled: bool
    posting_identity_ready: bool
    message: str
    ordered_identities: tuple[RegularCrossPeriodPostingIdentityEntryPreview, ...]
    zero_cent_fiscal_period_ids: tuple[UUID, ...]


def _blocked(
    coordinates: RegularCrossPeriodPostingCoordinatePreview,
    *,
    blocker_code: str,
    message: str,
) -> RegularCrossPeriodPostingIdentityPreview:
    return RegularCrossPeriodPostingIdentityPreview(
        transaction_id=coordinates.transaction_id,
        collection_source_event_key=coordinates.collection_source_event_key,
        coordinate_policy_version=coordinates.coordinate_policy_version,
        identity_policy_version=(
            REGULAR_CROSS_PERIOD_POSTING_IDENTITY_PREVIEW_POLICY_VERSION
        ),
        disposition="regular_cross_period_posting_identity_preview_blocked",
        blocker_code=blocker_code,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        posting_identity_ready=False,
        message=message,
        ordered_identities=(),
        zero_cent_fiscal_period_ids=(),
    )


def _collection_source_key(transaction_id: UUID) -> str:
    return f"collection:{transaction_id}"


def _eir_period_source_key(
    collection_source_event_key: str,
    fiscal_period_id: UUID,
) -> str:
    return (
        f"eir_accrual:{collection_source_event_key}:"
        f"fiscal_period:{fiscal_period_id}"
    )


def _identity_preview_key(coordinate_preview_key: str) -> str:
    return f"regular_posting_identity_preview:{coordinate_preview_key}"


def _entry_identity(
    *,
    transaction_id: UUID,
    collection_source_event_key: str,
    coordinate: RegularCrossPeriodPostingCoordinateEntryPreview,
) -> RegularCrossPeriodPostingIdentityEntryPreview:
    if coordinate.entry_type == "collection":
        source_type = "collection"
        source_reference = str(transaction_id)
        source_event_key = collection_source_event_key
    else:
        source_type = "regular_eir_accrual"
        source_reference = (
            f"{transaction_id}:fiscal_period:{coordinate.fiscal_period_id}"
        )
        source_event_key = _eir_period_source_key(
            collection_source_event_key,
            coordinate.fiscal_period_id,
        )

    return RegularCrossPeriodPostingIdentityEntryPreview(
        sequence_order=coordinate.sequence_order,
        entry_type=coordinate.entry_type,
        identity_preview_key=_identity_preview_key(
            coordinate.coordinate_preview_key
        ),
        coordinate_preview_key=coordinate.coordinate_preview_key,
        source_type=source_type,
        source_reference=source_reference,
        source_event_key=source_event_key,
        related_collection_source_event_key=collection_source_event_key,
        amount=coordinate.amount,
        proposed_posting_date=coordinate.proposed_posting_date,
        fiscal_period_id=coordinate.fiscal_period_id,
        posting_eligible=False,
    )


def build_regular_cross_period_posting_identity_preview(
    coordinates: RegularCrossPeriodPostingCoordinatePreview,
    *,
    protected_sequence: RegularCrossPeriodAccountingSequencePreview,
    protected_period_journal: RegularEirPeriodJournalProposalPreview,
    protected_collection: RegularCollectionJournalPreview,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> RegularCrossPeriodPostingIdentityPreview:
    """Prove deterministic posting identities without creating a journal.

    The supplied Stage 5D.12 coordinate preview must replay exactly from the
    protected Stage 5D.10 sequence, Stage 5D.8 period journal, protected
    collection preview, and protected fiscal-period references.

    Collection identity preserves the existing deterministic source key.
    Each positive cross-period Regular EIR journal receives a separate source
    key scoped by the protected fiscal-period UUID so the globally unique
    ``accounting.journal_entries.source_event_key`` contract can be satisfied.

    This mapper creates no journal number, journal ID, draft, persistence
    record, posting permission, or automatic source-posting path.
    """

    if (
        coordinates.posting_eligible
        or coordinates.automatic_source_posting_enabled
        or coordinates.posting_identity_ready
    ):
        return _blocked(
            coordinates,
            blocker_code="posting_identity_posting_control_review",
            message=(
                "The upstream coordinate preview unexpectedly enables posting "
                "or claims posting identity readiness."
            ),
        )

    replayed = build_regular_cross_period_posting_coordinate_preview(
        protected_sequence,
        protected_period_journal=protected_period_journal,
        protected_collection=protected_collection,
        protected_fiscal_periods=protected_fiscal_periods,
    )
    if replayed != coordinates:
        return _blocked(
            coordinates,
            blocker_code="posting_identity_coordinate_replay_not_exact",
            message=(
                "The supplied Stage 5D.12 coordinate preview does not exactly "
                "replay from protected accounting evidence."
            ),
        )

    if (
        replayed.disposition
        != "regular_cross_period_posting_coordinate_preview_ready"
        or replayed.blocker_code is not None
        or replayed.coordinate_policy_version
        != REGULAR_CROSS_PERIOD_POSTING_COORDINATE_PREVIEW_POLICY_VERSION
        or replayed.posting_eligible
        or replayed.automatic_source_posting_enabled
        or replayed.posting_identity_ready
        or not replayed.ordered_coordinates
        or replayed.ordered_coordinates[-1].entry_type != "collection"
    ):
        return _blocked(
            coordinates,
            blocker_code="posting_identity_coordinate_preview_not_ready",
            message="The protected Stage 5D.12 coordinate preview is not exact and ready.",
        )

    expected_collection_key = _collection_source_key(replayed.transaction_id)
    if replayed.collection_source_event_key != expected_collection_key:
        return _blocked(
            coordinates,
            blocker_code="posting_identity_collection_source_key_not_exact",
            message=(
                "The protected collection source key is not the deterministic "
                "collection:<transaction_uuid> identity."
            ),
        )

    identities: list[RegularCrossPeriodPostingIdentityEntryPreview] = []
    for coordinate in replayed.ordered_coordinates:
        if coordinate.entry_type not in {"eir_accrual_period", "collection"}:
            return _blocked(
                coordinates,
                blocker_code="posting_identity_entry_type_review",
                message="The protected coordinate sequence contains an unexpected entry type.",
            )
        if coordinate.entry_type == "eir_accrual_period":
            if coordinate.fiscal_period_id in replayed.zero_cent_fiscal_period_ids:
                return _blocked(
                    coordinates,
                    blocker_code="posting_identity_zero_cent_period_conflict",
                    message=(
                        "A zero-cent fiscal period must not receive a posting "
                        "identity because no journal is proposed for that period."
                    ),
                )
        identities.append(
            _entry_identity(
                transaction_id=replayed.transaction_id,
                collection_source_event_key=replayed.collection_source_event_key,
                coordinate=coordinate,
            )
        )

    source_keys = [item.source_event_key for item in identities]
    identity_preview_keys = [item.identity_preview_key for item in identities]
    eir_items = [
        item for item in identities if item.entry_type == "eir_accrual_period"
    ]
    collection_items = [
        item for item in identities if item.entry_type == "collection"
    ]
    old_unsplit_eir_key = f"eir_accrual:{replayed.collection_source_event_key}"

    if (
        [item.sequence_order for item in identities]
        != list(range(1, len(identities) + 1))
        or len(set(source_keys)) != len(source_keys)
        or len(set(identity_preview_keys)) != len(identity_preview_keys)
        or len(collection_items) != 1
        or identities[-1].entry_type != "collection"
        or collection_items[0].source_event_key != replayed.collection_source_event_key
        or any(item.source_event_key == old_unsplit_eir_key for item in eir_items)
        or any(
            not item.source_event_key.startswith(
                f"eir_accrual:{replayed.collection_source_event_key}:fiscal_period:"
            )
            for item in eir_items
        )
        or any(item.posting_eligible for item in identities)
    ):
        return _blocked(
            coordinates,
            blocker_code="posting_identity_result_not_exact",
            message=(
                "Posting identities must be deterministic, globally distinct "
                "within the protected bundle, preserve the collection source "
                "key, and never reuse the unsplit EIR source key."
            ),
        )

    return RegularCrossPeriodPostingIdentityPreview(
        transaction_id=replayed.transaction_id,
        collection_source_event_key=replayed.collection_source_event_key,
        coordinate_policy_version=replayed.coordinate_policy_version,
        identity_policy_version=(
            REGULAR_CROSS_PERIOD_POSTING_IDENTITY_PREVIEW_POLICY_VERSION
        ),
        disposition="regular_cross_period_posting_identity_preview_ready",
        blocker_code=None,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        posting_identity_ready=True,
        message=(
            "Read-only deterministic posting identities are proven. The "
            "collection preserves its existing collection source key, while "
            "each positive cross-period Regular EIR journal receives a separate "
            "fiscal-period-scoped globally unique source key. Journal draft "
            "creation, persistence, posting, and automatic source posting remain disabled."
        ),
        ordered_identities=tuple(identities),
        zero_cent_fiscal_period_ids=replayed.zero_cent_fiscal_period_ids,
    )
