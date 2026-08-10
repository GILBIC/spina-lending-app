from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import money
from .regular_collection_journal_preview import RegularCollectionJournalPreview
from .regular_eir_accrual_journal_preview import RegularEirAccrualJournalPreview


ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class RegularAccountingSequenceEntryPreview:
    sequence_order: int
    entry_type: str
    source_event_key: str
    posting_date: date
    amount: Decimal
    disposition: str


@dataclass(frozen=True, slots=True)
class RegularAccountingSequencePreview:
    transaction_id: UUID
    sequence_key: str
    collection_source_event_key: str
    collection_date: date
    required_eir_accrual_before_collection: Decimal
    disposition: str
    blocker_code: str | None
    posting_eligible: bool
    message: str
    ordered_entries: tuple[RegularAccountingSequenceEntryPreview, ...]


def _sequence_key(transaction_id: UUID) -> str:
    return f"regular_accounting_sequence:collection:{transaction_id}"


def _blocked(
    collection: RegularCollectionJournalPreview,
    *,
    blocker_code: str,
    message: str,
) -> RegularAccountingSequencePreview:
    return RegularAccountingSequencePreview(
        transaction_id=collection.transaction_id,
        sequence_key=_sequence_key(collection.transaction_id),
        collection_source_event_key=collection.source_event_key,
        collection_date=collection.collection_date,
        required_eir_accrual_before_collection=(
            collection.required_eir_accrual_before_collection
        ),
        disposition="regular_accounting_sequence_preview_blocked",
        blocker_code=blocker_code,
        posting_eligible=False,
        message=message,
        ordered_entries=(),
    )


def _collection_preview_is_exact(
    preview: RegularCollectionJournalPreview,
) -> bool:
    if (
        preview.disposition != "collection_journal_lines_preview_ready"
        or not preview.balanced
        or preview.amount <= ZERO
        or preview.required_eir_accrual_before_collection < ZERO
        or preview.amount != money(preview.amount)
        or preview.required_eir_accrual_before_collection
        != money(preview.required_eir_accrual_before_collection)
        or preview.total_debit != preview.amount
        or preview.total_credit != preview.amount
        or not preview.proposed_lines
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


def _eir_accrual_preview_is_exact(
    preview: RegularEirAccrualJournalPreview,
) -> bool:
    if (
        preview.amount < ZERO
        or preview.amount != money(preview.amount)
        or preview.accrual_start_date_exclusive
        > preview.accrual_end_date_inclusive
        or preview.posting_date != preview.accrual_end_date_inclusive
        or preview.period_split_evidence
        or preview.period_rounded_total != ZERO
        or preview.rounding_residual != ZERO
        or preview.split_policy_required
    ):
        return False

    if preview.amount == ZERO:
        return (
            preview.disposition == "no_eir_accrual_required"
            and preview.fiscal_period_id is None
            and preview.fiscal_period_label is None
            and preview.fiscal_period_status is None
            and not preview.proposed_lines
            and preview.total_debit == ZERO
            and preview.total_credit == ZERO
            and preview.balanced
        )

    if (
        preview.disposition != "eir_accrual_journal_lines_preview_ready"
        or preview.accrual_start_date_exclusive
        >= preview.accrual_end_date_inclusive
        or preview.fiscal_period_id is None
        or not preview.fiscal_period_label
        or preview.fiscal_period_status != "open"
        or not preview.balanced
        or preview.total_debit != preview.amount
        or preview.total_credit != preview.amount
        or len(preview.proposed_lines) != 2
    ):
        return False

    debit, credit = preview.proposed_lines
    if (
        debit.account_system_key != "accrued_interest_receivable"
        or debit.side != "debit"
        or debit.amount != preview.amount
        or credit.account_system_key != "interest_income_regular"
        or credit.side != "credit"
        or credit.amount != preview.amount
    ):
        return False

    calculated_debit = sum(
        (line.amount for line in preview.proposed_lines if line.side == "debit"),
        ZERO,
    )
    calculated_credit = sum(
        (line.amount for line in preview.proposed_lines if line.side == "credit"),
        ZERO,
    )
    return (
        calculated_debit == preview.total_debit
        and calculated_credit == preview.total_credit
    )


def build_regular_accounting_sequence_preview(
    accrual: RegularEirAccrualJournalPreview,
    collection: RegularCollectionJournalPreview,
) -> RegularAccountingSequencePreview:
    """Pair exact read-only Regular entries in required accounting order.

    This helper composes existing previews only. It does not create a draft or a
    posted journal. Any missing, blocked, postable, malformed, or inconsistent
    preview fails closed to an empty sequence.
    """

    expected_collection_key = f"collection:{collection.transaction_id}"
    if (
        accrual.transaction_id != collection.transaction_id
        or collection.source_event_key != expected_collection_key
        or accrual.related_collection_source_event_key
        != collection.source_event_key
        or accrual.source_event_key != f"eir_accrual:{collection.source_event_key}"
        or accrual.accrual_end_date_inclusive != collection.collection_date
        or accrual.posting_date != collection.collection_date
        or accrual.amount
        != collection.required_eir_accrual_before_collection
    ):
        return _blocked(
            collection,
            blocker_code="accounting_sequence_identity_mismatch",
            message=(
                "The EIR accrual and collection previews do not share one exact "
                "transaction, deterministic source identity, date, and recognized "
                "EIR amount. No ordered entries are exposed."
            ),
        )

    if accrual.posting_eligible or collection.posting_eligible:
        return _blocked(
            collection,
            blocker_code="accounting_sequence_posting_control_review",
            message=(
                "An underlying preview unexpectedly claims posting eligibility. "
                "The read-only accounting sequence remains blocked."
            ),
        )

    if collection.disposition != "collection_journal_lines_preview_ready":
        return _blocked(
            collection,
            blocker_code=collection.disposition,
            message=(
                "The Regular collection preview is not ready, so no partial "
                "accounting sequence is exposed."
            ),
        )
    if not _collection_preview_is_exact(collection):
        return _blocked(
            collection,
            blocker_code="collection_preview_not_reconciled",
            message=(
                "The Regular collection preview does not exactly reconcile to its "
                "accepted cash. No ordered entries are exposed."
            ),
        )

    permitted_accrual_dispositions = {
        "eir_accrual_journal_lines_preview_ready",
        "no_eir_accrual_required",
    }
    if accrual.disposition not in permitted_accrual_dispositions:
        return _blocked(
            collection,
            blocker_code=accrual.disposition,
            message=(
                "The required Regular EIR accrual preview is not ready, so no "
                "partial accounting sequence is exposed."
            ),
        )
    if not _eir_accrual_preview_is_exact(accrual):
        return _blocked(
            collection,
            blocker_code="eir_accrual_preview_not_reconciled",
            message=(
                "The Regular EIR accrual preview does not exactly reconcile to "
                "its recognized amount and open-period evidence. No ordered "
                "entries are exposed."
            ),
        )

    entries: list[RegularAccountingSequenceEntryPreview] = []
    if accrual.amount > ZERO:
        entries.append(
            RegularAccountingSequenceEntryPreview(
                sequence_order=1,
                entry_type="eir_accrual",
                source_event_key=accrual.source_event_key,
                posting_date=accrual.posting_date,
                amount=accrual.amount,
                disposition=accrual.disposition,
            )
        )
    entries.append(
        RegularAccountingSequenceEntryPreview(
            sequence_order=len(entries) + 1,
            entry_type="collection",
            source_event_key=collection.source_event_key,
            posting_date=collection.collection_date,
            amount=collection.amount,
            disposition=collection.disposition,
        )
    )

    return RegularAccountingSequencePreview(
        transaction_id=collection.transaction_id,
        sequence_key=_sequence_key(collection.transaction_id),
        collection_source_event_key=collection.source_event_key,
        collection_date=collection.collection_date,
        required_eir_accrual_before_collection=(
            collection.required_eir_accrual_before_collection
        ),
        disposition="regular_accounting_sequence_preview_ready",
        blocker_code=None,
        posting_eligible=False,
        message=(
            "The exact read-only Regular accounting order is available. Any "
            "required EIR accrual precedes its matching collection; draft "
            "creation and posting remain disabled."
        ),
        ordered_entries=tuple(entries),
    )
