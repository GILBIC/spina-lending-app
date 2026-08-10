from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import money
from .regular_collection_journal_preview import RegularCollectionJournalPreview
from .regular_eir_accrual_journal_preview import (
    REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION,
)
from .regular_eir_period_journal_preview import (
    REGULAR_EIR_PERIOD_JOURNAL_PREVIEW_POLICY_VERSION,
    RegularEirFiscalPeriodJournalProposal,
    RegularEirPeriodJournalProposalPreview,
)


ZERO = Decimal("0.00")
REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION = (
    "regular_cross_period_accounting_sequence_preview_v1"
)


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodAccountingSequenceEntryPreview:
    sequence_order: int
    entry_type: str
    preview_entry_key: str
    related_source_event_key: str
    recognition_date: date
    amount: Decimal
    fiscal_period_id: UUID | None
    disposition: str
    posting_eligible: bool


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodAccountingSequencePreview:
    transaction_id: UUID
    sequence_key: str
    collection_source_event_key: str
    collection_date: date
    required_eir_accrual_before_collection: Decimal
    sequence_policy_version: str
    disposition: str
    blocker_code: str | None
    posting_eligible: bool
    automatic_source_posting_enabled: bool
    message: str
    ordered_entries: tuple[RegularCrossPeriodAccountingSequenceEntryPreview, ...]
    zero_cent_fiscal_period_ids: tuple[UUID, ...]


def _sequence_key(transaction_id: UUID) -> str:
    return f"regular_cross_period_sequence_preview:collection:{transaction_id}"


def _period_entry_key(transaction_id: UUID, fiscal_period_id: UUID) -> str:
    return (
        f"regular_eir_period_sequence_preview:collection:{transaction_id}:"
        f"fiscal_period:{fiscal_period_id}"
    )


def _collection_entry_key(transaction_id: UUID) -> str:
    return f"regular_collection_sequence_preview:collection:{transaction_id}"


def _blocked(
    collection: RegularCollectionJournalPreview,
    *,
    blocker_code: str,
    message: str,
) -> RegularCrossPeriodAccountingSequencePreview:
    return RegularCrossPeriodAccountingSequencePreview(
        transaction_id=collection.transaction_id,
        sequence_key=_sequence_key(collection.transaction_id),
        collection_source_event_key=collection.source_event_key,
        collection_date=collection.collection_date,
        required_eir_accrual_before_collection=(
            collection.required_eir_accrual_before_collection
        ),
        sequence_policy_version=(
            REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION
        ),
        disposition="regular_cross_period_accounting_sequence_preview_blocked",
        blocker_code=blocker_code,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        message=message,
        ordered_entries=(),
        zero_cent_fiscal_period_ids=(),
    )


def _collection_preview_is_exact(
    preview: RegularCollectionJournalPreview,
) -> bool:
    if (
        preview.disposition != "collection_journal_lines_preview_ready"
        or preview.posting_eligible
        or not preview.balanced
        or preview.amount <= ZERO
        or preview.required_eir_accrual_before_collection <= ZERO
        or preview.amount != money(preview.amount)
        or preview.required_eir_accrual_before_collection
        != money(preview.required_eir_accrual_before_collection)
        or preview.total_debit != preview.amount
        or preview.total_credit != preview.amount
        or not preview.proposed_lines
        or preview.source_event_key != f"collection:{preview.transaction_id}"
    ):
        return False

    first, *credits = preview.proposed_lines
    if (
        first.account_system_key != "cash_collector_custody"
        or first.side != "debit"
        or first.amount != preview.amount
        or first.amount != money(first.amount)
        or not credits
    ):
        return False

    expected_credit_keys = {
        "accrued_interest_receivable",
        "loans_receivable_regular",
    }
    observed_credit_keys: set[str] = set()
    credit_total = ZERO
    for line in credits:
        if (
            line.account_system_key not in expected_credit_keys
            or line.account_system_key in observed_credit_keys
            or line.side != "credit"
            or line.amount <= ZERO
            or line.amount != money(line.amount)
        ):
            return False
        observed_credit_keys.add(line.account_system_key)
        credit_total += line.amount

    calculated_debit = sum(
        (line.amount for line in preview.proposed_lines if line.side == "debit"),
        ZERO,
    )
    calculated_credit = sum(
        (line.amount for line in preview.proposed_lines if line.side == "credit"),
        ZERO,
    )
    return (
        credit_total == preview.amount
        and calculated_debit == preview.total_debit
        and calculated_credit == preview.total_credit
    )


def _period_proposal_is_exact(
    proposal: RegularEirFiscalPeriodJournalProposal,
) -> bool:
    amount = proposal.allocated_amount
    if (
        proposal.posting_eligible
        or not proposal.balanced
        or proposal.period_start_date > proposal.period_end_date
        or not (
            proposal.period_start_date
            <= proposal.accrual_start_date_inclusive
            <= proposal.accrual_end_date_inclusive
            <= proposal.period_end_date
        )
        or amount < ZERO
        or amount != money(amount)
        or proposal.total_debit != amount
        or proposal.total_credit != amount
    ):
        return False

    if amount == ZERO:
        return (
            proposal.disposition == "no_eir_accrual_journal_required_for_period"
            and proposal.proposed_lines == ()
        )

    if (
        proposal.disposition
        != "eir_accrual_journal_lines_preview_ready_for_period"
        or len(proposal.proposed_lines) != 2
    ):
        return False

    debit, credit = proposal.proposed_lines
    return (
        debit.account_system_key == "accrued_interest_receivable"
        and debit.side == "debit"
        and debit.amount == amount
        and debit.amount == money(debit.amount)
        and credit.account_system_key == "interest_income_regular"
        and credit.side == "credit"
        and credit.amount == amount
        and credit.amount == money(credit.amount)
    )


def _period_preview_is_exact(
    preview: RegularEirPeriodJournalProposalPreview,
    *,
    collection: RegularCollectionJournalPreview,
) -> bool:
    expected_collection_key = f"collection:{collection.transaction_id}"
    proposals = preview.period_proposals
    if (
        preview.transaction_id != collection.transaction_id
        or preview.related_collection_source_event_key != expected_collection_key
        or preview.related_collection_source_event_key != collection.source_event_key
        or preview.source_event_key != f"eir_accrual:{expected_collection_key}"
        or preview.disposition != "eir_period_journal_lines_preview_ready"
        or preview.blocker_code is not None
        or preview.period_split_policy_version
        != REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION
        or preview.journal_preview_policy_version
        != REGULAR_EIR_PERIOD_JOURNAL_PREVIEW_POLICY_VERSION
        or preview.posting_eligible
        or preview.automatic_source_posting_enabled
        or not preview.balanced
        or preview.amount <= ZERO
        or preview.amount != money(preview.amount)
        or preview.amount != collection.required_eir_accrual_before_collection
        or preview.period_allocated_total != preview.amount
        or preview.unallocated_residual != ZERO
        or preview.total_debit != preview.amount
        or preview.total_credit != preview.amount
        or len(proposals) < 2
        or len({proposal.fiscal_period_id for proposal in proposals}) != len(proposals)
    ):
        return False

    previous: RegularEirFiscalPeriodJournalProposal | None = None
    allocated_total = ZERO
    calculated_debit = ZERO
    calculated_credit = ZERO
    for proposal in proposals:
        if not _period_proposal_is_exact(proposal):
            return False
        if previous is not None:
            if (
                previous.accrual_end_date_inclusive != previous.period_end_date
                or proposal.accrual_start_date_inclusive != proposal.period_start_date
                or proposal.period_start_date
                != previous.period_end_date + timedelta(days=1)
            ):
                return False
        previous = proposal
        allocated_total += proposal.allocated_amount
        calculated_debit += proposal.total_debit
        calculated_credit += proposal.total_credit

    if previous is None or previous.accrual_end_date_inclusive != collection.collection_date:
        return False

    return (
        allocated_total == preview.amount
        and calculated_debit == preview.total_debit
        and calculated_credit == preview.total_credit
    )


def build_regular_cross_period_accounting_sequence_preview(
    period_journal: RegularEirPeriodJournalProposalPreview,
    collection: RegularCollectionJournalPreview,
) -> RegularCrossPeriodAccountingSequencePreview:
    """Compose exact cross-period Regular accounting evidence in read-only order.

    The sequence intentionally exposes `recognition_date`, not a journal
    `posting_date`. Period entries use preview-only reference keys, not posting
    source identities. This stage therefore proves order and period recognition
    semantics without creating a journal draft, posting identity, or write path.
    """

    if period_journal.posting_eligible or collection.posting_eligible:
        return _blocked(
            collection,
            blocker_code="cross_period_sequence_posting_control_review",
            message=(
                "An underlying preview unexpectedly claims posting eligibility. "
                "The protected cross-period sequence remains blocked."
            ),
        )
    if period_journal.automatic_source_posting_enabled:
        return _blocked(
            collection,
            blocker_code="cross_period_sequence_automatic_posting_control_review",
            message=(
                "The period EIR preview unexpectedly enables automatic source "
                "posting. The protected sequence remains blocked."
            ),
        )
    if not _collection_preview_is_exact(collection):
        return _blocked(
            collection,
            blocker_code="cross_period_collection_preview_not_exact",
            message=(
                "The Regular collection preview does not exactly reconcile to its "
                "accepted cash and deterministic source identity."
            ),
        )
    if not _period_preview_is_exact(period_journal, collection=collection):
        return _blocked(
            collection,
            blocker_code="cross_period_eir_period_preview_not_exact",
            message=(
                "The protected per-period Regular EIR proposals do not satisfy the "
                "exact cross-period identity, cent, chronological coverage, period-"
                "end recognition, approved-policy, and reconciliation contract."
            ),
        )

    entries: list[RegularCrossPeriodAccountingSequenceEntryPreview] = []
    zero_cent_ids: list[UUID] = []
    for proposal in period_journal.period_proposals:
        if proposal.allocated_amount == ZERO:
            zero_cent_ids.append(proposal.fiscal_period_id)
            continue
        entries.append(
            RegularCrossPeriodAccountingSequenceEntryPreview(
                sequence_order=len(entries) + 1,
                entry_type="eir_accrual_period",
                preview_entry_key=_period_entry_key(
                    collection.transaction_id,
                    proposal.fiscal_period_id,
                ),
                related_source_event_key=period_journal.source_event_key,
                recognition_date=proposal.accrual_end_date_inclusive,
                amount=proposal.allocated_amount,
                fiscal_period_id=proposal.fiscal_period_id,
                disposition=proposal.disposition,
                posting_eligible=False,
            )
        )

    entries.append(
        RegularCrossPeriodAccountingSequenceEntryPreview(
            sequence_order=len(entries) + 1,
            entry_type="collection",
            preview_entry_key=_collection_entry_key(collection.transaction_id),
            related_source_event_key=collection.source_event_key,
            recognition_date=collection.collection_date,
            amount=collection.amount,
            fiscal_period_id=None,
            disposition=collection.disposition,
            posting_eligible=False,
        )
    )

    if any(entry.posting_eligible for entry in entries):
        return _blocked(
            collection,
            blocker_code="cross_period_sequence_entry_posting_control_review",
            message="A sequence entry unexpectedly claims posting eligibility.",
        )
    if len({entry.preview_entry_key for entry in entries}) != len(entries):
        return _blocked(
            collection,
            blocker_code="cross_period_sequence_preview_identity_conflict",
            message="Preview-only sequence entry identities must be unique.",
        )
    if [entry.sequence_order for entry in entries] != list(
        range(1, len(entries) + 1)
    ):
        return _blocked(
            collection,
            blocker_code="cross_period_sequence_order_not_exact",
            message="The read-only cross-period sequence order is not contiguous.",
        )
    if entries[-1].entry_type != "collection":
        return _blocked(
            collection,
            blocker_code="cross_period_collection_not_last",
            message="The collection must be the final item in the protected sequence.",
        )
    if any(
        entry.recognition_date > collection.collection_date
        for entry in entries[:-1]
    ):
        return _blocked(
            collection,
            blocker_code="cross_period_recognition_date_after_collection",
            message="No EIR recognition date may fall after its collection boundary.",
        )

    return RegularCrossPeriodAccountingSequencePreview(
        transaction_id=collection.transaction_id,
        sequence_key=_sequence_key(collection.transaction_id),
        collection_source_event_key=collection.source_event_key,
        collection_date=collection.collection_date,
        required_eir_accrual_before_collection=(
            collection.required_eir_accrual_before_collection
        ),
        sequence_policy_version=(
            REGULAR_CROSS_PERIOD_ACCOUNTING_SEQUENCE_PREVIEW_POLICY_VERSION
        ),
        disposition="regular_cross_period_accounting_sequence_preview_ready",
        blocker_code=None,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
        message=(
            "The exact read-only cross-period Regular accounting order is available. "
            "Positive fiscal-period EIR candidates are recognized at each proven "
            "accrual-segment end, then the collection is last. Recognition dates "
            "and preview-only keys are not journal posting dates or posting source "
            "identities; draft creation and posting remain disabled."
        ),
        ordered_entries=tuple(entries),
        zero_cent_fiscal_period_ids=tuple(zero_cent_ids),
    )
