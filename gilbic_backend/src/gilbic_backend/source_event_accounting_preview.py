from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class CollectionSourceEvent:
    transaction_id: UUID
    receipt_number: str
    client_id: UUID
    client_code: str
    client_name: str
    loan_id: UUID
    loan_number: str
    loan_type_code: str
    loan_type_name: str
    calculation_mode: str
    collection_date: date
    accepted_at: datetime
    entry_type: str
    amount: Decimal
    is_voided: bool
    voided_at: datetime | None
    journal_entry_id: UUID | None = None
    journal_status: str | None = None
    journal_entry_number: str | None = None
    reversal_entry_id: UUID | None = None
    reversal_status: str | None = None
    reversal_entry_number: str | None = None


@dataclass(frozen=True, slots=True)
class AccountingPreviewLine:
    account_system_key: str
    side: str
    amount: Decimal
    label: str


@dataclass(frozen=True, slots=True)
class CollectionAccountingPreview:
    transaction_id: UUID
    source_event_key: str
    receipt_number: str
    client_id: UUID
    client_code: str
    client_name: str
    loan_id: UUID
    loan_number: str
    loan_type_code: str
    loan_type_name: str
    collection_date: date
    accepted_at: datetime
    entry_type: str
    amount: Decimal
    is_voided: bool
    voided_at: datetime | None
    disposition: str
    posting_eligible: bool
    message: str
    proposed_lines: tuple[AccountingPreviewLine, ...]
    existing_journal_entry_id: UUID | None
    existing_journal_status: str | None
    existing_journal_entry_number: str | None
    reversal_entry_id: UUID | None
    reversal_status: str | None
    reversal_entry_number: str | None


def collection_source_event_key(transaction_id: UUID) -> str:
    return f"collection:{transaction_id}"


def _receivable_key(calculation_mode: str) -> str | None:
    if calculation_mode == "fixed_daily":
        return "loans_receivable_regular"
    if calculation_mode == "seven_by_seven":
        return "loans_receivable_7x7"
    return None


def _lines(event: CollectionSourceEvent) -> tuple[AccountingPreviewLine, ...]:
    receivable_key = _receivable_key(event.calculation_mode)
    if receivable_key is None or event.amount <= ZERO:
        return ()
    receivable_label = (
        "Loans Receivable - 7x7"
        if receivable_key == "loans_receivable_7x7"
        else "Loans Receivable - Regular"
    )
    return (
        AccountingPreviewLine(
            account_system_key="cash_collector_custody",
            side="debit",
            amount=event.amount,
            label="Cash - Collector Custody",
        ),
        AccountingPreviewLine(
            account_system_key=receivable_key,
            side="credit",
            amount=event.amount,
            label=receivable_label,
        ),
    )


def build_collection_accounting_preview(
    event: CollectionSourceEvent,
    *,
    cutover_date: date | None,
) -> CollectionAccountingPreview:
    """Build a read-only accounting interpretation of one collection event.

    This intentionally maps only cash movement against the amortized-cost loan
    carrying amount. EIR interest recognition is a separate accounting event and
    is never inferred from PAYMENT/ADV cash. PASS is non-cash. Voids are shown as
    either no-accounting-needed or controlled-reversal-required depending on
    whether a future source journal already exists.
    """

    source_key = collection_source_event_key(event.transaction_id)
    base = dict(
        transaction_id=event.transaction_id,
        source_event_key=source_key,
        receipt_number=event.receipt_number,
        client_id=event.client_id,
        client_code=event.client_code,
        client_name=event.client_name,
        loan_id=event.loan_id,
        loan_number=event.loan_number,
        loan_type_code=event.loan_type_code,
        loan_type_name=event.loan_type_name,
        collection_date=event.collection_date,
        accepted_at=event.accepted_at,
        entry_type=event.entry_type,
        amount=event.amount,
        is_voided=event.is_voided,
        voided_at=event.voided_at,
        existing_journal_entry_id=event.journal_entry_id,
        existing_journal_status=event.journal_status,
        existing_journal_entry_number=event.journal_entry_number,
        reversal_entry_id=event.reversal_entry_id,
        reversal_status=event.reversal_status,
        reversal_entry_number=event.reversal_entry_number,
    )

    if event.entry_type == "pass":
        if event.journal_entry_id is not None:
            return CollectionAccountingPreview(
                **base,
                disposition="unexpected_journal",
                posting_eligible=False,
                message="PASS is a non-cash event but an accounting journal already exists for this source key. Review is required.",
                proposed_lines=(),
            )
        return CollectionAccountingPreview(
            **base,
            disposition="informational_only",
            posting_eligible=False,
            message="PASS records no cash movement and creates no accounting journal proposal.",
            proposed_lines=(),
        )

    if event.entry_type not in {"payment", "advance"} or event.amount <= ZERO:
        return CollectionAccountingPreview(
            **base,
            disposition="unsupported_event",
            posting_eligible=False,
            message="This source event is not supported for accounting automation and requires review.",
            proposed_lines=(),
        )

    if event.is_voided:
        if event.journal_entry_id is None:
            return CollectionAccountingPreview(
                **base,
                disposition="voided_before_accounting",
                posting_eligible=False,
                message="The collection was voided before any source journal existed. No accounting entry should be created.",
                proposed_lines=(),
            )
        if event.journal_status == "draft":
            return CollectionAccountingPreview(
                **base,
                disposition="voided_draft_requires_cancel",
                posting_eligible=False,
                message="The collection is voided and its source journal is still a draft. The draft must be cancelled; do not post it.",
                proposed_lines=(),
            )
        if event.journal_status == "posted":
            if event.reversal_entry_id is None:
                return CollectionAccountingPreview(
                    **base,
                    disposition="reversal_required",
                    posting_eligible=False,
                    message="The collection was voided after its source journal posted. A controlled reversal is required; never edit the posted journal.",
                    proposed_lines=(),
                )
            if event.reversal_status == "posted":
                return CollectionAccountingPreview(
                    **base,
                    disposition="reversed",
                    posting_eligible=False,
                    message="The posted source journal already has a posted controlled reversal.",
                    proposed_lines=(),
                )
            return CollectionAccountingPreview(
                **base,
                disposition="reversal_draft_exists",
                posting_eligible=False,
                message="A controlled reversal draft already exists and must pass the normal posting controls.",
                proposed_lines=(),
            )
        return CollectionAccountingPreview(
            **base,
            disposition="voided_accounting_review",
            posting_eligible=False,
            message="The voided collection has an unexpected accounting state and requires review.",
            proposed_lines=(),
        )

    if cutover_date is None:
        return CollectionAccountingPreview(
            **base,
            disposition="cutover_required",
            posting_eligible=False,
            message="Opening-balance cutover must be established before post-cutover source events can be mapped.",
            proposed_lines=(),
        )
    if event.collection_date < cutover_date:
        return CollectionAccountingPreview(
            **base,
            disposition="pre_cutover",
            posting_eligible=False,
            message="This collection is before the opening-balance cutover date and must not be posted again as a new source event.",
            proposed_lines=(),
        )
    if event.collection_date == cutover_date:
        return CollectionAccountingPreview(
            **base,
            disposition="cutover_date_review",
            posting_eligible=False,
            message="The workbook uses a date-only cutover. Same-day collections cannot be ordered against the opening snapshot and require cutover review.",
            proposed_lines=(),
        )

    receivable_key = _receivable_key(event.calculation_mode)
    if receivable_key is None:
        return CollectionAccountingPreview(
            **base,
            disposition="policy_review",
            posting_eligible=False,
            message="This loan calculation mode has no approved accounting source-event mapping yet.",
            proposed_lines=(),
        )

    if event.journal_entry_id is not None:
        if event.journal_status == "posted":
            return CollectionAccountingPreview(
                **base,
                disposition="already_posted",
                posting_eligible=False,
                message="A posted accounting journal already exists for this deterministic collection source key.",
                proposed_lines=_lines(event),
            )
        if event.journal_status == "draft":
            return CollectionAccountingPreview(
                **base,
                disposition="draft_exists",
                posting_eligible=False,
                message="An accounting journal draft already exists for this deterministic collection source key.",
                proposed_lines=_lines(event),
            )
        return CollectionAccountingPreview(
            **base,
            disposition="accounting_state_review",
            posting_eligible=False,
            message="An unexpected accounting journal state exists for this source event.",
            proposed_lines=_lines(event),
        )

    return CollectionAccountingPreview(
        **base,
        disposition="preview_ready",
        posting_eligible=False,
        message=(
            "Read-only proposal only: debit Cash - Collector Custody and credit the loan carrying amount. "
            "EIR interest recognition remains a separate accounting event. Automatic source posting is disabled."
        ),
        proposed_lines=_lines(event),
    )
