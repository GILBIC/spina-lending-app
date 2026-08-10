from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import EirCashAllocation


ZERO = Decimal("0.00")
REGULAR_EIR_ACCRUAL_ACCOUNT_KEYS = (
    "accrued_interest_receivable",
    "interest_income_regular",
)


@dataclass(frozen=True, slots=True)
class AccountingFiscalPeriodReference:
    period_id: UUID
    label: str
    start_date: date
    end_date: date
    status: str


@dataclass(frozen=True, slots=True)
class RegularEirAccrualJournalLine:
    account_system_key: str
    side: str
    amount: Decimal
    label: str


@dataclass(frozen=True, slots=True)
class RegularEirAccrualJournalPreview:
    transaction_id: UUID
    related_collection_source_event_key: str
    source_event_key: str
    accrual_start_date_exclusive: date
    accrual_end_date_inclusive: date
    posting_date: date
    fiscal_period_id: UUID | None
    fiscal_period_label: str | None
    fiscal_period_status: str | None
    amount: Decimal
    disposition: str
    posting_eligible: bool
    message: str
    proposed_lines: tuple[RegularEirAccrualJournalLine, ...]
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool


def _source_event_key(allocation: EirCashAllocation) -> str:
    return f"eir_accrual:{allocation.source_event_key}"


def _blocked(
    allocation: EirCashAllocation,
    *,
    accrual_start_date: date,
    disposition: str,
    message: str,
    period: AccountingFiscalPeriodReference | None = None,
) -> RegularEirAccrualJournalPreview:
    return RegularEirAccrualJournalPreview(
        transaction_id=allocation.transaction_id,
        related_collection_source_event_key=allocation.source_event_key,
        source_event_key=_source_event_key(allocation),
        accrual_start_date_exclusive=accrual_start_date,
        accrual_end_date_inclusive=allocation.collection_date,
        posting_date=allocation.collection_date,
        fiscal_period_id=period.period_id if period is not None else None,
        fiscal_period_label=period.label if period is not None else None,
        fiscal_period_status=period.status if period is not None else None,
        amount=allocation.effective_interest_accrued_since_prior_event,
        disposition=disposition,
        posting_eligible=False,
        message=message,
        proposed_lines=(),
        total_debit=ZERO,
        total_credit=ZERO,
        balanced=False,
    )


def build_regular_eir_accrual_journal_preview(
    allocation: EirCashAllocation,
    *,
    allocation_result_status: str,
    accrual_start_date: date,
    fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
    opening_balance_posted: bool,
    protected_snapshot_available: bool,
    protected_snapshot_reconciled: bool,
    source_history_complete: bool,
    account_configuration_ready: bool,
    account_configuration_blocker: str | None = None,
    is_voided: bool = False,
    existing_accrual_journal_status: str | None = None,
    accrual_reversal_status: str | None = None,
    collection_journal_status: str | None = None,
) -> RegularEirAccrualJournalPreview:
    """Build a period-gated Regular EIR accrual proposal without writing a journal.

    The allocator recognizes EIR at a cash-event cent boundary. This stage assigns
    that exact amount to Dr 1120 / Cr 4000 only when every accrued calendar day
    belongs to one open fiscal period. An interval that crosses period boundaries
    remains blocked because splitting the already-rounded boundary amount requires
    a separate, explicitly validated rounding policy.
    """

    if (
        allocation_result_status != "allocation_reference_ready"
        or allocation.disposition != "allocation_reference_ready"
    ):
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="eir_allocation_not_ready",
            message="The complete event-date EIR allocation is not ready.",
        )
    if is_voided:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="voided_before_accounting",
            message="A voided collection never receives an EIR accrual proposal.",
        )
    if accrual_reversal_status == "posted":
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="already_reversed",
            message="The existing EIR accrual already has a posted controlled reversal.",
        )
    if accrual_reversal_status == "draft":
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="reversal_draft_exists",
            message="A controlled reversal draft already exists for this EIR accrual.",
        )
    if existing_accrual_journal_status == "posted":
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="already_posted",
            message="A posted EIR accrual already exists for this deterministic source key.",
        )
    if existing_accrual_journal_status == "draft":
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="draft_exists",
            message="An EIR accrual draft already exists for this deterministic source key.",
        )
    if existing_accrual_journal_status is not None or accrual_reversal_status is not None:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="accounting_state_review",
            message="The EIR accrual has an unexpected journal or reversal state.",
        )
    if not opening_balance_posted:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="opening_balance_posting_required",
            message="The protected opening-balance journal must post first.",
        )
    if not protected_snapshot_available:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="protected_cutover_snapshot_required",
            message="The immutable per-loan cutover EIR snapshot is missing.",
        )
    if not protected_snapshot_reconciled:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="protected_cutover_snapshot_not_reconciled",
            message="The protected cutover snapshot does not reconcile.",
        )
    if not source_history_complete:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="source_history_incomplete",
            message="Complete post-cutover source history is required.",
        )
    if not account_configuration_ready:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="account_configuration_required",
            message=(
                account_configuration_blocker
                or "Required Regular EIR accrual accounts are not ready."
            ),
        )

    amount = allocation.effective_interest_accrued_since_prior_event
    if (
        amount < ZERO
        or accrual_start_date > allocation.collection_date
        or (
            accrual_start_date == allocation.collection_date
            and amount != ZERO
        )
    ):
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="accrual_boundary_invalid",
            message="The recognized EIR amount or accrual boundary is invalid.",
        )
    if amount == ZERO:
        return RegularEirAccrualJournalPreview(
            transaction_id=allocation.transaction_id,
            related_collection_source_event_key=allocation.source_event_key,
            source_event_key=_source_event_key(allocation),
            accrual_start_date_exclusive=accrual_start_date,
            accrual_end_date_inclusive=allocation.collection_date,
            posting_date=allocation.collection_date,
            fiscal_period_id=None,
            fiscal_period_label=None,
            fiscal_period_status=None,
            amount=ZERO,
            disposition="no_eir_accrual_required",
            posting_eligible=False,
            message="No cent of EIR was recognized at this cash-event boundary.",
            proposed_lines=(),
            total_debit=ZERO,
            total_credit=ZERO,
            balanced=True,
        )
    if collection_journal_status is not None:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="collection_accounting_precedes_accrual_review",
            message=(
                "A collection journal state already exists before its required EIR "
                "accrual. Review ordering before proposing another accounting entry."
            ),
        )

    first_accrual_date = accrual_start_date + timedelta(days=1)
    overlapping = tuple(
        period
        for period in fiscal_periods
        if period.end_date >= first_accrual_date
        and period.start_date <= allocation.collection_date
    )
    covering = tuple(
        period
        for period in overlapping
        if period.start_date <= first_accrual_date
        and period.end_date >= allocation.collection_date
    )
    if len(covering) > 1 or (covering and len(overlapping) > 1):
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="fiscal_period_configuration_review",
            message="More than one fiscal period covers the complete accrual interval.",
        )
    if not covering:
        disposition = (
            "fiscal_period_split_required"
            if len(overlapping) > 1
            else "fiscal_period_required"
        )
        message = (
            "The EIR interval crosses fiscal periods. A validated period-splitting "
            "and cent-rounding policy is required before lines can be proposed."
            if disposition == "fiscal_period_split_required"
            else "One fiscal period must cover every day in the EIR accrual interval."
        )
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition=disposition,
            message=message,
        )

    period = covering[0]
    if period.status != "open":
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="fiscal_period_not_open",
            message="The fiscal period covering this EIR accrual is not open.",
            period=period,
        )

    lines = (
        RegularEirAccrualJournalLine(
            account_system_key="accrued_interest_receivable",
            side="debit",
            amount=amount,
            label="Regular effective interest accrued",
        ),
        RegularEirAccrualJournalLine(
            account_system_key="interest_income_regular",
            side="credit",
            amount=amount,
            label="Regular effective interest income",
        ),
    )
    total_debit = sum(
        (line.amount for line in lines if line.side == "debit"), ZERO
    )
    total_credit = sum(
        (line.amount for line in lines if line.side == "credit"), ZERO
    )
    if total_debit != total_credit or total_debit != amount:
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition="proposal_not_balanced",
            message="The read-only Regular EIR accrual proposal is not balanced.",
            period=period,
        )

    return RegularEirAccrualJournalPreview(
        transaction_id=allocation.transaction_id,
        related_collection_source_event_key=allocation.source_event_key,
        source_event_key=_source_event_key(allocation),
        accrual_start_date_exclusive=accrual_start_date,
        accrual_end_date_inclusive=allocation.collection_date,
        posting_date=allocation.collection_date,
        fiscal_period_id=period.period_id,
        fiscal_period_label=period.label,
        fiscal_period_status=period.status,
        amount=amount,
        disposition="eir_accrual_journal_lines_preview_ready",
        posting_eligible=False,
        message=(
            "Balanced read-only Regular EIR accrual lines are available for one "
            "open fiscal period. Draft creation and posting remain disabled."
        ),
        proposed_lines=lines,
        total_debit=total_debit,
        total_credit=total_credit,
        balanced=True,
    )
