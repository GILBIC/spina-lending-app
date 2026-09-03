from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


ZERO = Decimal("0.00")
SUPPORTED_EIR_MODES = frozenset({"fixed_daily", "seven_by_seven"})


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
    cash_received_amount: Decimal | None = None
    unallocated_amount: Decimal = ZERO
    journal_entry_id: UUID | None = None
    journal_status: str | None = None
    journal_entry_number: str | None = None
    reversal_entry_id: UUID | None = None
    reversal_status: str | None = None
    reversal_entry_number: str | None = None

    @property
    def receipt_cash_amount(self) -> Decimal:
        """Actual custody cash represented by this receipt.

        Older callers only supplied ``amount`` because receipt cash and loan
        application were historically the same value. New receipt-first readers
        pass ``cash_received_amount`` explicitly while ``amount`` is the portion
        applied to the loan/accounting source event.
        """

        if self.cash_received_amount is None:
            return self.amount
        return self.cash_received_amount


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
    cash_received_amount: Decimal
    unallocated_amount: Decimal
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


def build_collection_accounting_preview(
    event: CollectionSourceEvent,
    *,
    cutover_date: date | None,
) -> CollectionAccountingPreview:
    """Classify one collection for future accounting without inventing entries.

    Receipt custody and loan application are intentionally separate. ``event.amount``
    is the amount already authorized to apply to the loan; ``receipt_cash_amount``
    is the full physical/GCash receipt. Any unresolved cash blocks source-accounting
    automation until an authorized allocation (and the corresponding accounting
    treatment for unapplied cash) is established.

    The Stage 5D EIR engine carries loans in two accounting components: a loan
    component (1100 Regular or 1110 7x7) plus accrued effective interest (1120).
    Applied cash is allocated to accrued EIR first and then the loan component.
    This preview proves source identity, cutover, void/reversal and duplicate state,
    then blocks journal mapping until protected EIR evidence is available.
    """

    source_key = collection_source_event_key(event.transaction_id)
    receipt_cash = event.receipt_cash_amount
    unallocated = event.unallocated_amount
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
        cash_received_amount=receipt_cash,
        unallocated_amount=unallocated,
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

    if event.entry_type not in {"payment", "advance"} or receipt_cash <= ZERO:
        return CollectionAccountingPreview(
            **base,
            disposition="unsupported_event",
            posting_eligible=False,
            message="This source event is not supported for accounting automation and requires review.",
            proposed_lines=(),
        )

    if event.amount < ZERO or unallocated < ZERO or event.amount + unallocated != receipt_cash:
        return CollectionAccountingPreview(
            **base,
            disposition="receipt_application_mismatch",
            posting_eligible=False,
            message=(
                "Receipt cash does not reconcile to the loan-applied plus unallocated amounts. "
                "Accounting is blocked until the receipt application is reconciled."
            ),
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

    if unallocated > ZERO:
        return CollectionAccountingPreview(
            **base,
            disposition="unallocated_cash_review",
            posting_eligible=False,
            message=(
                "This receipt contains real cash that is still unallocated to a loan obligation. "
                "Keep the full receipt in custody/remittance, but do not reduce the loan or create an automatic source journal for the unresolved amount. Management allocation review is required."
            ),
            proposed_lines=(),
        )

    if event.amount <= ZERO:
        return CollectionAccountingPreview(
            **base,
            disposition="no_applied_loan_cash",
            posting_eligible=False,
            message="No part of this receipt is currently applied to the loan, so no loan source journal may be proposed.",
            proposed_lines=(),
        )

    if event.calculation_mode not in SUPPORTED_EIR_MODES:
        return CollectionAccountingPreview(
            **base,
            disposition="policy_review",
            posting_eligible=False,
            message="This loan calculation mode has no approved EIR source-event allocation policy yet.",
            proposed_lines=(),
        )

    if event.journal_entry_id is not None:
        if event.journal_status == "posted":
            return CollectionAccountingPreview(
                **base,
                disposition="already_posted",
                posting_eligible=False,
                message="A posted accounting journal already exists for this deterministic collection source key. Review its EIR allocation before enabling any future automation.",
                proposed_lines=(),
            )
        if event.journal_status == "draft":
            return CollectionAccountingPreview(
                **base,
                disposition="draft_exists",
                posting_eligible=False,
                message="An accounting journal draft already exists for this deterministic collection source key. It must be reviewed against the EIR allocation policy before posting.",
                proposed_lines=(),
            )
        return CollectionAccountingPreview(
            **base,
            disposition="accounting_state_review",
            posting_eligible=False,
            message="An unexpected accounting journal state exists for this source event.",
            proposed_lines=(),
        )

    return CollectionAccountingPreview(
        **base,
        disposition="eir_allocation_required",
        posting_eligible=False,
        message=(
            "The receipt is an authoritative post-cutover cash source and its loan-applied amount is reconciled, but no journal lines are proposed yet. "
            "The EIR carrying amount is split between the loan component and accrued effective interest; applied cash must be allocated to accrued EIR first and then principal/carrying amount using an event-date EIR schedule. Automatic source posting remains disabled."
        ),
        proposed_lines=(),
    )
