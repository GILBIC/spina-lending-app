from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import EirCashAllocation


ZERO = Decimal("0.00")
REGULAR_COLLECTION_ACCOUNT_KEYS = (
    "cash_collector_custody",
    "loans_receivable_regular",
    "accrued_interest_receivable",
)


@dataclass(frozen=True, slots=True)
class RegularCollectionJournalLine:
    account_system_key: str
    side: str
    amount: Decimal
    label: str


@dataclass(frozen=True, slots=True)
class RegularCollectionJournalPreview:
    transaction_id: UUID
    source_event_key: str
    collection_date: date
    amount: Decimal
    required_eir_accrual_before_collection: Decimal
    disposition: str
    posting_eligible: bool
    message: str
    proposed_lines: tuple[RegularCollectionJournalLine, ...]
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool


def _blocked(
    allocation: EirCashAllocation,
    *,
    disposition: str,
    message: str,
) -> RegularCollectionJournalPreview:
    return RegularCollectionJournalPreview(
        transaction_id=allocation.transaction_id,
        source_event_key=allocation.source_event_key,
        collection_date=allocation.collection_date,
        amount=allocation.amount,
        required_eir_accrual_before_collection=(
            allocation.effective_interest_accrued_since_prior_event
        ),
        disposition=disposition,
        posting_eligible=False,
        message=message,
        proposed_lines=(),
        total_debit=ZERO,
        total_credit=ZERO,
        balanced=False,
    )


def build_regular_collection_journal_preview(
    allocation: EirCashAllocation,
    *,
    allocation_result_status: str,
    opening_balance_posted: bool,
    protected_snapshot_available: bool,
    protected_snapshot_reconciled: bool,
    source_history_complete: bool,
    account_configuration_ready: bool,
    account_configuration_blocker: str | None = None,
    is_voided: bool = False,
    existing_journal_status: str | None = None,
    reversal_status: str | None = None,
) -> RegularCollectionJournalPreview:
    """Build balanced Regular collection lines without creating a journal.

    The collection entry clears cash against the already-established EIR carrying
    components. The effective-interest amount accrued since the prior source
    boundary is reported separately because its Dr 1120 / Cr 4000 accounting,
    fiscal-period handling, and protected posting controls belong to a later
    stage. This preview therefore remains non-posting even when its lines balance.
    """

    if (
        allocation_result_status != "allocation_reference_ready"
        or allocation.disposition != "allocation_reference_ready"
    ):
        return _blocked(
            allocation,
            disposition="eir_allocation_not_ready",
            message=(
                "The complete event-date EIR allocation is not ready, so no "
                "collection journal lines are proposed."
            ),
        )
    if is_voided:
        return _blocked(
            allocation,
            disposition="voided_before_accounting",
            message="A voided collection never receives a new journal-line proposal.",
        )
    if reversal_status == "posted":
        return _blocked(
            allocation,
            disposition="already_reversed",
            message="The existing source journal already has a posted controlled reversal.",
        )
    if reversal_status == "draft":
        return _blocked(
            allocation,
            disposition="reversal_draft_exists",
            message="A controlled reversal draft already exists for this source journal.",
        )
    if existing_journal_status == "posted":
        return _blocked(
            allocation,
            disposition="already_posted",
            message="A posted journal already exists for this deterministic collection source key.",
        )
    if existing_journal_status == "draft":
        return _blocked(
            allocation,
            disposition="draft_exists",
            message="A journal draft already exists for this deterministic collection source key.",
        )
    if existing_journal_status is not None or reversal_status is not None:
        return _blocked(
            allocation,
            disposition="accounting_state_review",
            message="The collection has an unexpected journal or reversal state.",
        )
    if not opening_balance_posted:
        return _blocked(
            allocation,
            disposition="opening_balance_posting_required",
            message=(
                "The protected opening-balance journal must post before "
                "post-cutover collection journal lines can be ledger-anchored."
            ),
        )
    if not protected_snapshot_available:
        return _blocked(
            allocation,
            disposition="protected_cutover_snapshot_required",
            message="The immutable per-loan cutover EIR snapshot is missing.",
        )
    if not protected_snapshot_reconciled:
        return _blocked(
            allocation,
            disposition="protected_cutover_snapshot_not_reconciled",
            message="The protected cutover snapshot batch does not reconcile to the opening journal.",
        )
    if not source_history_complete:
        return _blocked(
            allocation,
            disposition="source_history_incomplete",
            message="Complete post-cutover source history is required before proposing lines.",
        )
    if not account_configuration_ready:
        return _blocked(
            allocation,
            disposition="account_configuration_required",
            message=(
                account_configuration_blocker
                or "Required Regular collection accounting accounts are not ready."
            ),
        )

    cash = allocation.amount
    to_accrued = allocation.cash_to_accrued_interest
    to_loan = allocation.cash_to_loan_component
    required_accrual = allocation.effective_interest_accrued_since_prior_event
    if min(cash, to_accrued, to_loan, required_accrual) < ZERO:
        return _blocked(
            allocation,
            disposition="allocation_components_invalid",
            message="Collection and EIR allocation components cannot be negative.",
        )
    if cash <= ZERO or to_accrued + to_loan != cash:
        return _blocked(
            allocation,
            disposition="allocation_not_reconciled",
            message="The accrued-interest and loan-component credits do not equal accepted cash.",
        )

    lines: list[RegularCollectionJournalLine] = [
        RegularCollectionJournalLine(
            account_system_key="cash_collector_custody",
            side="debit",
            amount=cash,
            label="Accepted collection cash",
        )
    ]
    if to_accrued > ZERO:
        lines.append(
            RegularCollectionJournalLine(
                account_system_key="accrued_interest_receivable",
                side="credit",
                amount=to_accrued,
                label="Cash applied to accrued effective interest",
            )
        )
    if to_loan > ZERO:
        lines.append(
            RegularCollectionJournalLine(
                account_system_key="loans_receivable_regular",
                side="credit",
                amount=to_loan,
                label="Cash applied to Regular loan component",
            )
        )

    total_debit = sum(
        (line.amount for line in lines if line.side == "debit"),
        ZERO,
    )
    total_credit = sum(
        (line.amount for line in lines if line.side == "credit"),
        ZERO,
    )
    if total_debit != total_credit or total_debit != cash:
        return _blocked(
            allocation,
            disposition="proposal_not_balanced",
            message="The read-only collection proposal is not exactly balanced.",
        )

    return RegularCollectionJournalPreview(
        transaction_id=allocation.transaction_id,
        source_event_key=allocation.source_event_key,
        collection_date=allocation.collection_date,
        amount=cash,
        required_eir_accrual_before_collection=required_accrual,
        disposition="collection_journal_lines_preview_ready",
        posting_eligible=False,
        message=(
            "Balanced read-only Regular collection lines are available. The "
            "separate EIR accrual, fiscal-period ordering, draft creation, and "
            "posting controls remain required before any journal may be created."
        ),
        proposed_lines=tuple(lines),
        total_debit=total_debit,
        total_credit=total_credit,
        balanced=True,
    )
