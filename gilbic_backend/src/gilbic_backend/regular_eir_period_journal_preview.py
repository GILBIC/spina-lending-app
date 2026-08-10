from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import money
from .regular_eir_accrual_journal_preview import (
    REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION,
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


def _evidence_is_exact(
    preview: RegularEirAccrualJournalPreview,
    evidence: tuple[RegularEirAccrualPeriodEvidence, ...],
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

    expected_first_accrual_date = (
        preview.accrual_start_date_exclusive + timedelta(days=1)
    )
    expected_last_accrual_date = preview.accrual_end_date_inclusive

    raw_total = Decimal("0")
    allocated_total = ZERO
    base_total = ZERO
    previous_accrual_end: date | None = None
    for index, item in enumerate(evidence):
        segment_day_count = (
            item.accrual_end_date_inclusive
            - item.accrual_start_date_inclusive
        ).days + 1
        if (
            item.status != "open"
            or item.day_count <= 0
            or item.day_count != segment_day_count
            or item.period_start_date > item.period_end_date
            or item.accrual_start_date_inclusive
            > item.accrual_end_date_inclusive
            or not (
                item.period_start_date
                <= item.accrual_start_date_inclusive
                <= item.accrual_end_date_inclusive
                <= item.period_end_date
            )
            or (
                index == 0
                and item.accrual_start_date_inclusive
                != expected_first_accrual_date
            )
            or (
                previous_accrual_end is not None
                and item.accrual_start_date_inclusive
                != previous_accrual_end + timedelta(days=1)
            )
            or item.effective_interest_raw < 0
            or item.effective_interest_rounded
            != money(item.effective_interest_raw)
            or item.effective_interest_floor < ZERO
            or item.effective_interest_floor
            != item.effective_interest_floor.quantize(CENT)
            or item.effective_interest_floor > item.effective_interest_raw
            or item.fractional_cent_remainder
            != item.effective_interest_raw - item.effective_interest_floor
            or item.fractional_cent_remainder < 0
            or item.fractional_cent_remainder >= CENT
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
        allocated_total += item.effective_interest_allocated
        base_total += item.effective_interest_floor

    if previous_accrual_end != expected_last_accrual_date:
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
        item.period_id: rank
        for rank, item in enumerate(ranked, start=1)
    }
    if any(
        item.allocation_rank != expected_ranks[item.period_id]
        for item in evidence
    ):
        return False

    cents_to_award_raw = (preview.amount - base_total) / CENT
    cents_to_award = int(cents_to_award_raw)
    if (
        cents_to_award_raw != Decimal(cents_to_award)
        or cents_to_award < 0
        or cents_to_award > len(evidence)
    ):
        return False

    expected_recipients = {
        item.period_id for item in ranked[:cents_to_award]
    }
    for item in evidence:
        expected_adjustment = (
            CENT if item.period_id in expected_recipients else ZERO
        )
        if (
            item.residual_cent_adjustment != expected_adjustment
            or item.received_residual_cent
            != (item.period_id in expected_recipients)
            or item.effective_interest_allocated
            != item.effective_interest_floor + expected_adjustment
        ):
            return False

    return (
        money(raw_total) == preview.amount
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
        (line.amount for line in lines if line.side == "debit"), ZERO
    )
    total_credit = sum(
        (line.amount for line in lines if line.side == "credit"), ZERO
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
) -> RegularEirPeriodJournalProposalPreview:
    """Map reconciled cross-period EIR cents to balanced read-only lines.

    This Stage 5D.8 mapper consumes only the protected Stage 5D.7 allocation
    evidence. It creates no journal draft, posting date, write path, or posting
    identity. The higher-level Regular accounting sequence therefore remains
    fail-closed until a separate protected cross-period sequencing stage exists.
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
    if preview.disposition != "fiscal_period_split_allocation_preview_ready":
        return _blocked(
            preview,
            blocker_code=preview.disposition,
            message=(
                "Reconciled cross-period Regular EIR allocation evidence is "
                "required before per-period journal lines can be proposed."
            ),
        )
    if (
        preview.period_split_policy_version
        != REGULAR_EIR_PERIOD_SPLIT_POLICY_VERSION
    ):
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
    if not _evidence_is_exact(preview, preview.period_split_evidence):
        return _blocked(
            preview,
            blocker_code="eir_period_split_evidence_not_exact",
            message=(
                "The fiscal-period evidence does not satisfy the deterministic "
                "allocation and complete accrual-coverage contract. No journal "
                "lines are exposed."
            ),
        )

    proposals = tuple(
        _period_proposal(evidence) for evidence in preview.period_split_evidence
    )
    if any(not proposal.balanced for proposal in proposals):
        return _blocked(
            preview,
            blocker_code="eir_period_journal_lines_not_balanced",
            message=(
                "At least one fiscal-period journal-line proposal is not balanced."
            ),
        )

    total_debit = sum((proposal.total_debit for proposal in proposals), ZERO)
    total_credit = sum((proposal.total_credit for proposal in proposals), ZERO)
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
