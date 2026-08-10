from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR
from uuid import UUID

from .eir_cash_allocation import EirCashAllocation, money


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION = "regular_eir_period_split_v1"
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
class RegularEirAccrualPeriodEvidence:
    period_id: UUID
    label: str
    period_start_date: date
    period_end_date: date
    status: str
    accrual_start_date_inclusive: date
    accrual_end_date_inclusive: date
    day_count: int
    effective_interest_raw: Decimal
    effective_interest_rounded: Decimal
    effective_interest_floor: Decimal = ZERO
    fractional_cent_remainder: Decimal = Decimal("0")
    allocation_rank: int | None = None
    residual_cent_adjustment: Decimal = ZERO
    effective_interest_allocated: Decimal = ZERO
    received_residual_cent: bool = False


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
    period_split_evidence: tuple[RegularEirAccrualPeriodEvidence, ...] = ()
    period_rounded_total: Decimal = ZERO
    rounding_residual: Decimal = ZERO
    split_policy_required: bool = False
    period_split_policy_version: str | None = None
    period_allocated_total: Decimal = ZERO
    unallocated_residual: Decimal = ZERO
    period_allocation_reconciled: bool = False


def _source_event_key(allocation: EirCashAllocation) -> str:
    return f"eir_accrual:{allocation.source_event_key}"


def _blocked(
    allocation: EirCashAllocation,
    *,
    accrual_start_date: date,
    disposition: str,
    message: str,
    period: AccountingFiscalPeriodReference | None = None,
    period_split_evidence: tuple[RegularEirAccrualPeriodEvidence, ...] = (),
    period_rounded_total: Decimal = ZERO,
    rounding_residual: Decimal = ZERO,
    split_policy_required: bool = False,
    period_split_policy_version: str | None = None,
    period_allocated_total: Decimal = ZERO,
    unallocated_residual: Decimal = ZERO,
    period_allocation_reconciled: bool = False,
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
        period_split_evidence=period_split_evidence,
        period_rounded_total=period_rounded_total,
        rounding_residual=rounding_residual,
        split_policy_required=split_policy_required,
        period_split_policy_version=period_split_policy_version,
        period_allocated_total=period_allocated_total,
        unallocated_residual=unallocated_residual,
        period_allocation_reconciled=period_allocation_reconciled,
    )


def allocate_regular_eir_period_split(
    evidence: tuple[RegularEirAccrualPeriodEvidence, ...],
    *,
    target_amount: Decimal,
) -> tuple[RegularEirAccrualPeriodEvidence, ...] | None:
    """Allocate a recognized cent total by largest fractional remainder.

    Exact raw amounts remain untouched. Each positive period first receives its
    whole-cent floor. Remaining cents are awarded by descending fractional-cent
    remainder, then larger raw amount, earlier period, and stable period UUID.
    The result is chronological and independent of input order.
    """

    if (
        not evidence
        or target_amount < ZERO
        or target_amount != money(target_amount)
        or len({item.period_id for item in evidence}) != len(evidence)
    ):
        return None

    bases: dict[UUID, Decimal] = {}
    remainders: dict[UUID, Decimal] = {}
    total_raw = Decimal("0")
    for item in evidence:
        if (
            item.status != "open"
            or item.day_count <= 0
            or item.period_start_date > item.period_end_date
            or item.accrual_start_date_inclusive
            > item.accrual_end_date_inclusive
            or not (
                item.period_start_date
                <= item.accrual_start_date_inclusive
                <= item.accrual_end_date_inclusive
                <= item.period_end_date
            )
            or item.effective_interest_raw < 0
            or item.effective_interest_rounded
            != money(item.effective_interest_raw)
        ):
            return None
        base = item.effective_interest_raw.quantize(CENT, rounding=ROUND_FLOOR)
        bases[item.period_id] = base
        remainders[item.period_id] = item.effective_interest_raw - base
        total_raw += item.effective_interest_raw

    if money(total_raw) != target_amount:
        return None

    base_total = sum(bases.values(), ZERO)
    cents_to_award_raw = (target_amount - base_total) / CENT
    cents_to_award = int(cents_to_award_raw)
    if (
        cents_to_award_raw != Decimal(cents_to_award)
        or cents_to_award < 0
        or cents_to_award > len(evidence)
    ):
        return None

    ranked = sorted(
        evidence,
        key=lambda item: (
            -remainders[item.period_id],
            -item.effective_interest_raw,
            item.period_start_date,
            str(item.period_id),
        ),
    )
    ranks = {item.period_id: index for index, item in enumerate(ranked, start=1)}
    recipients = {item.period_id for item in ranked[:cents_to_award]}

    allocated = tuple(
        replace(
            item,
            effective_interest_floor=bases[item.period_id],
            fractional_cent_remainder=remainders[item.period_id],
            allocation_rank=ranks[item.period_id],
            residual_cent_adjustment=(
                CENT if item.period_id in recipients else ZERO
            ),
            effective_interest_allocated=(
                bases[item.period_id]
                + (CENT if item.period_id in recipients else ZERO)
            ),
            received_residual_cent=item.period_id in recipients,
        )
        for item in sorted(
            evidence,
            key=lambda item: (
                item.period_start_date,
                item.period_end_date,
                str(item.period_id),
            ),
        )
    )
    allocated_total = sum(
        (item.effective_interest_allocated for item in allocated),
        ZERO,
    )
    if allocated_total != target_amount:
        return None
    return allocated


def _build_period_split_evidence(
    allocation: EirCashAllocation,
    *,
    accrual_start_date: date,
    fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> tuple[
    tuple[RegularEirAccrualPeriodEvidence, ...],
    Decimal,
    Decimal,
] | None:
    """Aggregate exact daily EIR by period before policy allocation."""

    expected_dates: list[date] = []
    current_date = accrual_start_date + timedelta(days=1)
    while current_date <= allocation.collection_date:
        expected_dates.append(current_date)
        current_date += timedelta(days=1)

    daily_accruals = allocation.daily_accruals
    if not daily_accruals or tuple(
        item.accrual_date for item in daily_accruals
    ) != tuple(expected_dates):
        return None

    previous_closing: Decimal | None = None
    grouped: dict[
        UUID,
        tuple[AccountingFiscalPeriodReference, list[tuple[date, Decimal]]],
    ] = {}
    total_raw = Decimal("0")
    for item in daily_accruals:
        if (
            item.opening_gross_carrying_raw < 0
            or item.effective_interest_raw < 0
            or item.closing_gross_carrying_raw
            != item.opening_gross_carrying_raw + item.effective_interest_raw
            or (
                previous_closing is not None
                and item.opening_gross_carrying_raw != previous_closing
            )
        ):
            return None
        previous_closing = item.closing_gross_carrying_raw

        matching_periods = tuple(
            period
            for period in fiscal_periods
            if period.start_date <= item.accrual_date <= period.end_date
        )
        if len(matching_periods) != 1:
            return None
        period = matching_periods[0]
        if period.period_id not in grouped:
            grouped[period.period_id] = (period, [])
        grouped[period.period_id][1].append(
            (item.accrual_date, item.effective_interest_raw)
        )
        total_raw += item.effective_interest_raw

    if money(total_raw) != allocation.effective_interest_accrued_since_prior_event:
        return None

    evidence: list[RegularEirAccrualPeriodEvidence] = []
    for period, rows in sorted(
        grouped.values(),
        key=lambda value: (
            value[0].start_date,
            value[0].end_date,
            str(value[0].period_id),
        ),
    ):
        period_raw = sum((amount for _, amount in rows), Decimal("0"))
        evidence.append(
            RegularEirAccrualPeriodEvidence(
                period_id=period.period_id,
                label=period.label,
                period_start_date=period.start_date,
                period_end_date=period.end_date,
                status=period.status,
                accrual_start_date_inclusive=rows[0][0],
                accrual_end_date_inclusive=rows[-1][0],
                day_count=len(rows),
                effective_interest_raw=period_raw,
                effective_interest_rounded=money(period_raw),
            )
        )

    period_rounded_total = sum(
        (item.effective_interest_rounded for item in evidence),
        ZERO,
    )
    rounding_residual = money(
        allocation.effective_interest_accrued_since_prior_event
        - period_rounded_total
    )
    return tuple(evidence), period_rounded_total, rounding_residual


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
    belongs to one open fiscal period. For a cross-period interval, the approved
    largest-remainder policy produces reconciled read-only period evidence, while
    journal-line creation remains blocked for a later protected stage.
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
        if disposition == "fiscal_period_split_required":
            split_evidence = _build_period_split_evidence(
                allocation,
                accrual_start_date=accrual_start_date,
                fiscal_periods=overlapping,
            )
            if split_evidence is not None:
                evidence, period_rounded_total, rounding_residual = split_evidence
                if any(item.status != "open" for item in evidence):
                    return _blocked(
                        allocation,
                        accrual_start_date=accrual_start_date,
                        disposition="fiscal_period_split_period_not_open",
                        message=(
                            "The approved period-split policy is available, but every "
                            "affected fiscal period must be open before allocated "
                            "evidence can be exposed."
                        ),
                        period_split_evidence=evidence,
                        period_rounded_total=period_rounded_total,
                        rounding_residual=rounding_residual,
                        split_policy_required=False,
                        period_split_policy_version=(
                            REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION
                        ),
                    )
                allocated_evidence = allocate_regular_eir_period_split(
                    evidence,
                    target_amount=amount,
                )
                if allocated_evidence is None:
                    return _blocked(
                        allocation,
                        accrual_start_date=accrual_start_date,
                        disposition="fiscal_period_split_allocation_review",
                        message=(
                            "Exact period evidence could not be reconciled under the "
                            "approved deterministic policy. No allocation or journal "
                            "lines are exposed."
                        ),
                        period_split_evidence=evidence,
                        period_rounded_total=period_rounded_total,
                        rounding_residual=rounding_residual,
                        split_policy_required=False,
                        period_split_policy_version=(
                            REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION
                        ),
                    )
                period_allocated_total = sum(
                    (
                        item.effective_interest_allocated
                        for item in allocated_evidence
                    ),
                    ZERO,
                )
                unallocated_residual = money(amount - period_allocated_total)
                return _blocked(
                    allocation,
                    accrual_start_date=accrual_start_date,
                    disposition="fiscal_period_split_allocation_preview_ready",
                    message=(
                        "The EIR interval crosses fiscal periods. Exact daily EIR "
                        "has been allocated to cents under the approved deterministic "
                        "largest-remainder policy. The evidence reconciles exactly, "
                        "but journal-line creation remains disabled."
                    ),
                    period_split_evidence=allocated_evidence,
                    period_rounded_total=period_rounded_total,
                    rounding_residual=rounding_residual,
                    split_policy_required=False,
                    period_split_policy_version=(
                        REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION
                    ),
                    period_allocated_total=period_allocated_total,
                    unallocated_residual=unallocated_residual,
                    period_allocation_reconciled=(unallocated_residual == ZERO),
                )
        message = (
            "The EIR interval crosses fiscal periods, but complete exact daily "
            "accrual evidence is unavailable. Allocation remains blocked rather "
            "than inferring missing daily or fiscal-period evidence."
            if disposition == "fiscal_period_split_required"
            else "One fiscal period must cover every day in the EIR accrual interval."
        )
        return _blocked(
            allocation,
            accrual_start_date=accrual_start_date,
            disposition=(
                "fiscal_period_split_evidence_required"
                if disposition == "fiscal_period_split_required"
                else disposition
            ),
            message=message,
            split_policy_required=False,
            period_split_policy_version=(
                REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION
                if disposition == "fiscal_period_split_required"
                else None
            ),
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
