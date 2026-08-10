from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR
from uuid import UUID

from .eir_cash_allocation import EirCashAllocation, money
from .regular_eir_accrual_journal_preview import (
    REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION,
    AccountingFiscalPeriodReference,
    RegularEirAccrualJournalLine,
    RegularEirAccrualJournalPreview,
    RegularEirAccrualPeriodEvidence,
)


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
REGULAR_EIR_PERIOD_JOURNAL_PREVIEW_POLICY_VERSION = (
    "regular_eir_period_journal_preview_v1"
)


@dataclass(frozen=True, slots=True)
class RegularEirFiscalPeriodJournalProposal:
    fiscal_period_id: UUID
    fiscal_period_label: str
    period_start_date: date
    period_end_date: date
    accrual_start_date_inclusive: date
    accrual_end_date_inclusive: date
    allocated_amount: Decimal
    disposition: str
    proposed_lines: tuple[RegularEirAccrualJournalLine, ...]
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool
    posting_eligible: bool


@dataclass(frozen=True, slots=True)
class RegularEirPeriodJournalProposalPreview:
    transaction_id: UUID
    related_collection_source_event_key: str
    source_event_key: str
    amount: Decimal
    period_split_policy_version: str | None
    journal_preview_policy_version: str
    period_allocated_total: Decimal
    unallocated_residual: Decimal
    disposition: str
    blocker_code: str | None
    message: str
    period_proposals: tuple[RegularEirFiscalPeriodJournalProposal, ...]
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool
    posting_eligible: bool
    automatic_source_posting_enabled: bool


def _blocked(
    preview: RegularEirAccrualJournalPreview,
    *,
    blocker_code: str,
    message: str,
) -> RegularEirPeriodJournalProposalPreview:
    return RegularEirPeriodJournalProposalPreview(
        transaction_id=preview.transaction_id,
        related_collection_source_event_key=(
            preview.related_collection_source_event_key
        ),
        source_event_key=preview.source_event_key,
        amount=preview.amount,
        period_split_policy_version=preview.period_split_policy_version,
        journal_preview_policy_version=(
            REGULAR_EIR_PERIOD_JOURNAL_PREVIEW_POLICY_VERSION
        ),
        period_allocated_total=preview.period_allocated_total,
        unallocated_residual=preview.unallocated_residual,
        disposition="eir_period_journal_lines_preview_blocked",
        blocker_code=blocker_code,
        message=message,
        period_proposals=(),
        total_debit=ZERO,
        total_credit=ZERO,
        balanced=False,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
    )


def _source_allocation_is_exact(
    preview: RegularEirAccrualJournalPreview,
    protected_allocation: EirCashAllocation,
) -> bool:
    expected_collection_source_key = (
        f"collection:{protected_allocation.transaction_id}"
    )
    return (
        protected_allocation.disposition == "allocation_reference_ready"
        and protected_allocation.posting_eligible is False
        and protected_allocation.source_event_key == expected_collection_source_key
        and protected_allocation.transaction_id == preview.transaction_id
        and protected_allocation.source_event_key
        == preview.related_collection_source_event_key
        and preview.source_event_key
        == f"eir_accrual:{expected_collection_source_key}"
        and protected_allocation.collection_date
        == preview.accrual_end_date_inclusive
        and protected_allocation.collection_date == preview.posting_date
        and protected_allocation.effective_interest_accrued_since_prior_event
        == preview.amount
        and preview.amount > ZERO
        and preview.amount == money(preview.amount)
    )


def _source_preview_control_envelope_is_exact(
    preview: RegularEirAccrualJournalPreview,
) -> bool:
    return (
        preview.fiscal_period_id is None
        and preview.fiscal_period_label is None
        and preview.fiscal_period_status is None
        and preview.proposed_lines == ()
        and preview.total_debit == ZERO
        and preview.total_credit == ZERO
        and preview.balanced is False
        and preview.split_policy_required is False
    )


def _fiscal_period_references_are_exact(
    evidence: tuple[RegularEirAccrualPeriodEvidence, ...],
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> bool:
    if (
        not protected_fiscal_periods
        or len({period.period_id for period in protected_fiscal_periods})
        != len(protected_fiscal_periods)
        or any(period.start_date > period.end_date for period in protected_fiscal_periods)
    ):
        return False

    period_by_id = {
        period.period_id: period for period in protected_fiscal_periods
    }
    matched_period_ids: set[UUID] = set()
    for item in evidence:
        period = period_by_id.get(item.period_id)
        if (
            period is None
            or period.period_id in matched_period_ids
            or period.status != "open"
            or item.label != period.label
            or item.period_start_date != period.start_date
            or item.period_end_date != period.end_date
            or item.status != period.status
        ):
            return False

        current_date = item.accrual_start_date_inclusive
        while current_date <= item.accrual_end_date_inclusive:
            owners = tuple(
                candidate
                for candidate in protected_fiscal_periods
                if candidate.start_date <= current_date <= candidate.end_date
            )
            if len(owners) != 1 or owners[0].period_id != period.period_id:
                return False
            current_date += timedelta(days=1)

        matched_period_ids.add(period.period_id)

    return True


def _daily_evidence_is_exact(
    preview: RegularEirAccrualJournalPreview,
    evidence: tuple[RegularEirAccrualPeriodEvidence, ...],
    protected_allocation: EirCashAllocation,
) -> bool:
    expected_dates: list[date] = []
    current_date = preview.accrual_start_date_exclusive + timedelta(days=1)
    while current_date <= preview.accrual_end_date_inclusive:
        expected_dates.append(current_date)
        current_date += timedelta(days=1)

    protected_daily_accruals = protected_allocation.daily_accruals
    if (
        not protected_daily_accruals
        or tuple(item.accrual_date for item in protected_daily_accruals)
        != tuple(expected_dates)
    ):
        return False

    daily_by_date: dict[date, Decimal] = {}
    previous_closing: Decimal | None = None
    daily_raw_total = Decimal("0")
    for item in protected_daily_accruals:
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
            return False
        previous_closing = item.closing_gross_carrying_raw
        daily_by_date[item.accrual_date] = item.effective_interest_raw
        daily_raw_total += item.effective_interest_raw

    if (
        previous_closing is None
        or money(previous_closing) != protected_allocation.gross_carrying_before
        or money(daily_raw_total) != preview.amount
    ):
        return False

    for item in evidence:
        expected_period_raw = Decimal("0")
        current_date = item.accrual_start_date_inclusive
        while current_date <= item.accrual_end_date_inclusive:
            daily_amount = daily_by_date.get(current_date)
            if daily_amount is None:
                return False
            expected_period_raw += daily_amount
            current_date += timedelta(days=1)
        if expected_period_raw != item.effective_interest_raw:
            return False

    return True


def _evidence_is_exact(
    preview: RegularEirAccrualJournalPreview,
    evidence: tuple[RegularEirAccrualPeriodEvidence, ...],
    protected_allocation: EirCashAllocation,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> bool:
    if (
        len(evidence) < 2
        or preview.accrual_start_date_exclusive >= preview.accrual_end_date_inclusive
        or len({item.period_id for item in evidence}) != len(evidence)
    ):
        return False

    chronological = tuple(
        sorted(
            evidence,
            key=lambda item: (
                item.period_start_date,
                item.period_end_date,
                str(item.period_id),
            ),
        )
    )
    if evidence != chronological:
        return False
    if not _fiscal_period_references_are_exact(evidence, protected_fiscal_periods):
        return False

    expected_first_accrual_date = (
        preview.accrual_start_date_exclusive + timedelta(days=1)
    )
    expected_last_accrual_date = preview.accrual_end_date_inclusive

    raw_total = Decimal("0")
    rounded_total = ZERO
    allocated_total = ZERO
    base_total = ZERO
    previous_accrual_end: date | None = None
    for index, item in enumerate(evidence):
        segment_day_count = (
            item.accrual_end_date_inclusive - item.accrual_start_date_inclusive
        ).days + 1
        expected_floor = item.effective_interest_raw.quantize(
            CENT,
            rounding=ROUND_FLOOR,
        )
        expected_remainder = item.effective_interest_raw - expected_floor
        if (
            item.status != "open"
            or item.day_count <= 0
            or item.day_count != segment_day_count
            or item.period_start_date > item.period_end_date
            or item.accrual_start_date_inclusive > item.accrual_end_date_inclusive
            or not (
                item.period_start_date
                <= item.accrual_start_date_inclusive
                <= item.accrual_end_date_inclusive
                <= item.period_end_date
            )
            or (
                index == 0
                and item.accrual_start_date_inclusive != expected_first_accrual_date
            )
            or (
                previous_accrual_end is not None
                and item.accrual_start_date_inclusive
                != previous_accrual_end + timedelta(days=1)
            )
            or item.effective_interest_raw < 0
            or item.effective_interest_rounded != money(item.effective_interest_raw)
            or item.effective_interest_floor != expected_floor
            or item.fractional_cent_remainder != expected_remainder
            or item.allocation_rank is None
            or item.allocation_rank <= 0
            or item.allocation_rank > len(evidence)
            or item.residual_cent_adjustment not in {ZERO, CENT}
            or item.received_residual_cent
            != (item.residual_cent_adjustment == CENT)
            or item.effective_interest_allocated
            != item.effective_interest_floor + item.residual_cent_adjustment
            or item.effective_interest_allocated < ZERO
            or item.effective_interest_allocated
            != money(item.effective_interest_allocated)
        ):
            return False
        previous_accrual_end = item.accrual_end_date_inclusive
        raw_total += item.effective_interest_raw
        rounded_total += item.effective_interest_rounded
        allocated_total += item.effective_interest_allocated
        base_total += item.effective_interest_floor

    if previous_accrual_end != expected_last_accrual_date:
        return False
    if not _daily_evidence_is_exact(preview, evidence, protected_allocation):
        return False

    ranked = tuple(
        sorted(
            evidence,
            key=lambda item: (
                -item.fractional_cent_remainder,
                -item.effective_interest_raw,
                item.period_start_date,
                str(item.period_id),
            ),
        )
    )
    expected_ranks = {
        item.period_id: rank for rank, item in enumerate(ranked, start=1)
    }
    if any(item.allocation_rank != expected_ranks[item.period_id] for item in evidence):
        return False

    cents_to_award_raw = (preview.amount - base_total) / CENT
    cents_to_award = int(cents_to_award_raw)
    if (
        cents_to_award_raw != Decimal(cents_to_award)
        or cents_to_award < 0
        or cents_to_award > len(evidence)
    ):
        return False

    expected_recipients = {item.period_id for item in ranked[:cents_to_award]}
    for item in evidence:
        expected_adjustment = CENT if item.period_id in expected_recipients else ZERO
        if (
            item.residual_cent_adjustment != expected_adjustment
            or item.received_residual_cent != (item.period_id in expected_recipients)
            or item.effective_interest_allocated
            != item.effective_interest_floor + expected_adjustment
        ):
            return False

    expected_rounding_residual = money(preview.amount - rounded_total)
    return (
        money(raw_total) == preview.amount
        and preview.period_rounded_total == rounded_total
        and preview.rounding_residual == expected_rounding_residual
        and allocated_total == preview.amount
        and allocated_total == preview.period_allocated_total
        and preview.unallocated_residual == ZERO
    )


def _period_proposal(
    evidence: RegularEirAccrualPeriodEvidence,
) -> RegularEirFiscalPeriodJournalProposal:
    amount = evidence.effective_interest_allocated
    if amount == ZERO:
        return RegularEirFiscalPeriodJournalProposal(
            fiscal_period_id=evidence.period_id,
            fiscal_period_label=evidence.label,
            period_start_date=evidence.period_start_date,
            period_end_date=evidence.period_end_date,
            accrual_start_date_inclusive=evidence.accrual_start_date_inclusive,
            accrual_end_date_inclusive=evidence.accrual_end_date_inclusive,
            allocated_amount=ZERO,
            disposition="no_eir_accrual_journal_required_for_period",
            proposed_lines=(),
            total_debit=ZERO,
            total_credit=ZERO,
            balanced=True,
            posting_eligible=False,
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
        (line.amount for line in lines if line.side == "debit"),
        ZERO,
    )
    total_credit = sum(
        (line.amount for line in lines if line.side == "credit"),
        ZERO,
    )
    return RegularEirFiscalPeriodJournalProposal(
        fiscal_period_id=evidence.period_id,
        fiscal_period_label=evidence.label,
        period_start_date=evidence.period_start_date,
        period_end_date=evidence.period_end_date,
        accrual_start_date_inclusive=evidence.accrual_start_date_inclusive,
        accrual_end_date_inclusive=evidence.accrual_end_date_inclusive,
        allocated_amount=amount,
        disposition="eir_accrual_journal_lines_preview_ready_for_period",
        proposed_lines=lines,
        total_debit=total_debit,
        total_credit=total_credit,
        balanced=(total_debit == total_credit == amount),
        posting_eligible=False,
    )


def build_regular_eir_period_journal_proposal_preview(
    preview: RegularEirAccrualJournalPreview,
    *,
    protected_allocation: EirCashAllocation,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> RegularEirPeriodJournalProposalPreview:
    """Map reconciled cross-period EIR cents to balanced read-only lines.

    This Stage 5D.8 mapper consumes the protected Stage 5D.7 allocation preview,
    its protected source allocation (including exact daily EIR rows), and protected
    fiscal-period references. It creates no journal draft, posting write path, or
    posting identity. The higher-level Regular accounting sequence therefore
    remains fail-closed until a separate protected cross-period sequencing stage.
    """

    if preview.posting_eligible:
        return _blocked(
            preview,
            blocker_code="eir_period_journal_posting_control_review",
            message=(
                "The source preview unexpectedly claims posting eligibility. "
                "Per-period journal-line proposals remain blocked."
            ),
        )
    if not _source_allocation_is_exact(preview, protected_allocation):
        return _blocked(
            preview,
            blocker_code="eir_period_source_allocation_not_exact",
            message=(
                "The replayed Regular EIR preview is not exactly bound to the "
                "protected source allocation. No journal lines are exposed."
            ),
        )
    if preview.disposition != "fiscal_period_split_allocation_preview_ready":
        return _blocked(
            preview,
            blocker_code=preview.disposition,
            message=(
                "Reconciled cross-period Regular EIR allocation evidence is "
                "required before per-period journal lines can be proposed."
            ),
        )
    if preview.period_split_policy_version != REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION:
        return _blocked(
            preview,
            blocker_code="eir_period_split_policy_mismatch",
            message=(
                "The fiscal-period allocation policy is not the approved "
                "regular_eir_period_split_v1 contract."
            ),
        )
    if (
        not preview.period_allocation_reconciled
        or preview.unallocated_residual != ZERO
        or preview.period_allocated_total != preview.amount
    ):
        return _blocked(
            preview,
            blocker_code="eir_period_split_allocation_not_reconciled",
            message=(
                "The fiscal-period EIR allocation does not exactly reconcile to "
                "the recognized cash-boundary amount."
            ),
        )
    if not _source_preview_control_envelope_is_exact(preview):
        return _blocked(
            preview,
            blocker_code="eir_period_source_preview_not_exact",
            message=(
                "The source cross-period preview contains an unexpected single-"
                "period identity, journal line, balance state, or split-policy "
                "control. No per-period journal lines are exposed."
            ),
        )
    if not _evidence_is_exact(
        preview,
        preview.period_split_evidence,
        protected_allocation,
        protected_fiscal_periods,
    ):
        return _blocked(
            preview,
            blocker_code="eir_period_split_evidence_not_exact",
            message=(
                "The fiscal-period evidence does not satisfy the deterministic "
                "allocation, protected source/daily-EIR binding, protected fiscal-"
                "period identity, complete accrual-coverage, and audit-reconciliation "
                "contract. No journal lines are exposed."
            ),
        )

    proposals = tuple(
        _period_proposal(evidence)
        for evidence in preview.period_split_evidence
    )
    if any(not proposal.balanced for proposal in proposals):
        return _blocked(
            preview,
            blocker_code="eir_period_journal_lines_not_balanced",
            message=(
                "At least one fiscal-period journal-line proposal is not balanced."
            ),
        )

    total_debit = sum(
        (proposal.total_debit for proposal in proposals),
        ZERO,
    )
    total_credit = sum(
        (proposal.total_credit for proposal in proposals),
        ZERO,
    )
    if total_debit != total_credit or total_debit != preview.amount:
        return _blocked(
            preview,
            blocker_code="eir_period_journal_total_not_reconciled",
            message=(
                "Per-period journal-line totals do not reconcile to the recognized "
                "Regular EIR amount."
            ),
        )

    return RegularEirPeriodJournalProposalPreview(
        transaction_id=preview.transaction_id,
        related_collection_source_event_key=preview.related_collection_source_event_key,
        source_event_key=preview.source_event_key,
        amount=preview.amount,
        period_split_policy_version=preview.period_split_policy_version,
        journal_preview_policy_version=(
            REGULAR_EIR_PERIOD_JOURNAL_PREVIEW_POLICY_VERSION
        ),
        period_allocated_total=preview.period_allocated_total,
        unallocated_residual=preview.unallocated_residual,
        disposition="eir_period_journal_lines_preview_ready",
        blocker_code=None,
        message=(
            "Balanced read-only Regular EIR journal-line proposals are available "
            "for each affected open fiscal period. Draft creation, posting dates, "
            "posting identities, automatic posting, and cross-period sequence "
            "composition remain disabled."
        ),
        period_proposals=proposals,
        total_debit=total_debit,
        total_credit=total_credit,
        balanced=True,
        posting_eligible=False,
        automatic_source_posting_enabled=False,
    )
