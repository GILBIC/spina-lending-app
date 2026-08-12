from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import money
from .greenfield_regular_eir_rollforward import GreenfieldRegularRenewalRollForward
from .regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
    RegularEirAccrualPeriodEvidence,
    allocate_regular_eir_period_split,
)


ZERO = Decimal("0.00")
POLICY_VERSION = "greenfield_regular_renewal_boundary_eir_v1"


@dataclass(frozen=True, slots=True)
class GreenfieldRegularRenewalBoundaryEirLine:
    account_system_key: str
    side: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class GreenfieldRegularRenewalBoundaryEirPeriodProposal:
    fiscal_period_id: UUID
    fiscal_period_label: str
    accrual_start_date_inclusive: date
    accrual_end_date_inclusive: date
    posting_date: date
    day_count: int
    amount: Decimal
    source_type: str
    source_reference: str
    source_event_key: str
    proposed_lines: tuple[GreenfieldRegularRenewalBoundaryEirLine, ...]


@dataclass(frozen=True, slots=True)
class GreenfieldRegularRenewalBoundaryEirPreview:
    renewal_execution_event_id: UUID
    loan_id: UUID
    target_date: date
    amount: Decimal
    disposition: str
    blocker_code: str | None
    message: str
    period_proposals: tuple[GreenfieldRegularRenewalBoundaryEirPeriodProposal, ...]
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool
    posting_eligible: bool
    automatic_source_posting: bool
    policy_version: str = POLICY_VERSION


def _blocked(
    rollforward: GreenfieldRegularRenewalRollForward,
    *,
    renewal_execution_event_id: UUID,
    blocker_code: str,
    message: str,
) -> GreenfieldRegularRenewalBoundaryEirPreview:
    return GreenfieldRegularRenewalBoundaryEirPreview(
        renewal_execution_event_id=renewal_execution_event_id,
        loan_id=rollforward.loan_id,
        target_date=rollforward.target_date,
        amount=money(rollforward.tail_effective_interest_accrued),
        disposition="renewal_boundary_eir_journal_preview_blocked",
        blocker_code=blocker_code,
        message=message,
        period_proposals=(),
        total_debit=ZERO,
        total_credit=ZERO,
        balanced=False,
        posting_eligible=False,
        automatic_source_posting=False,
    )


def _validate_tail_chain(
    rollforward: GreenfieldRegularRenewalRollForward,
) -> bool:
    daily = rollforward.tail_daily_accruals
    amount = money(rollforward.tail_effective_interest_accrued)
    if not daily:
        return amount == ZERO

    last_boundary = (
        rollforward.allocations[-1].collection_date
        if rollforward.allocations
        else rollforward.anchor_date
    )
    expected_date = last_boundary + timedelta(days=1)
    previous_closing: Decimal | None = None
    total_raw = Decimal("0")
    for item in daily:
        if item.accrual_date != expected_date:
            return False
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
        total_raw += item.effective_interest_raw
        previous_closing = item.closing_gross_carrying_raw
        expected_date += timedelta(days=1)

    return (
        daily[-1].accrual_date == rollforward.target_date
        and money(total_raw) == amount
    )


def build_greenfield_regular_renewal_boundary_eir_preview(
    rollforward: GreenfieldRegularRenewalRollForward,
    *,
    renewal_execution_event_id: UUID,
    fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> GreenfieldRegularRenewalBoundaryEirPreview:
    """Build read-only no-cash EIR coordinates at an authoritative renewal date.

    This is an implementation improvement inside the existing Regular
    renewal/refinance/restructure accounting requirement. It reuses the existing
    deterministic fiscal-period cent allocation policy. It does not create a
    journal, claim posting eligibility, or enable automatic source posting.
    """

    if (
        rollforward.disposition
        != "greenfield_regular_renewal_rollforward_preview_ready"
        or rollforward.blocker_code is not None
        or not rollforward.measurement_preview_ready
    ):
        return _blocked(
            rollforward,
            renewal_execution_event_id=renewal_execution_event_id,
            blocker_code=(
                rollforward.blocker_code
                or "greenfield_regular_rollforward_not_ready"
            ),
            message=rollforward.message,
        )

    target_amount = money(rollforward.tail_effective_interest_accrued)
    if target_amount < ZERO:
        return _blocked(
            rollforward,
            renewal_execution_event_id=renewal_execution_event_id,
            blocker_code="renewal_boundary_eir_amount_invalid",
            message="Renewal-boundary EIR cannot be negative.",
        )
    if not _validate_tail_chain(rollforward):
        return _blocked(
            rollforward,
            renewal_execution_event_id=renewal_execution_event_id,
            blocker_code="renewal_boundary_eir_daily_evidence_not_exact",
            message=(
                "The renewal-boundary daily EIR chain is incomplete, non-contiguous, "
                "or does not reconcile to the measured tail amount."
            ),
        )
    if target_amount == ZERO:
        return GreenfieldRegularRenewalBoundaryEirPreview(
            renewal_execution_event_id=renewal_execution_event_id,
            loan_id=rollforward.loan_id,
            target_date=rollforward.target_date,
            amount=ZERO,
            disposition="no_renewal_boundary_eir_required",
            blocker_code=None,
            message=(
                "The exact daily chain reaches the renewal boundary without a cent "
                "of EIR to recognize."
            ),
            period_proposals=(),
            total_debit=ZERO,
            total_credit=ZERO,
            balanced=True,
            posting_eligible=False,
            automatic_source_posting=False,
        )

    grouped: dict[
        UUID,
        tuple[AccountingFiscalPeriodReference, list[tuple[date, Decimal]]],
    ] = {}
    for item in rollforward.tail_daily_accruals:
        matching = tuple(
            period
            for period in fiscal_periods
            if period.start_date <= item.accrual_date <= period.end_date
        )
        if len(matching) != 1 or matching[0].status != "open":
            return _blocked(
                rollforward,
                renewal_execution_event_id=renewal_execution_event_id,
                blocker_code="renewal_boundary_fiscal_period_not_ready",
                message=(
                    "Every renewal-boundary EIR day must belong to exactly one open "
                    "fiscal period."
                ),
            )
        period = matching[0]
        if period.period_id not in grouped:
            grouped[period.period_id] = (period, [])
        grouped[period.period_id][1].append(
            (item.accrual_date, item.effective_interest_raw)
        )

    evidence: list[RegularEirAccrualPeriodEvidence] = []
    for period, rows in sorted(
        grouped.values(),
        key=lambda value: (
            value[0].start_date,
            value[0].end_date,
            str(value[0].period_id),
        ),
    ):
        raw = sum((amount for _, amount in rows), Decimal("0"))
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
                effective_interest_raw=raw,
                effective_interest_rounded=money(raw),
            )
        )

    allocated = allocate_regular_eir_period_split(
        tuple(evidence),
        target_amount=target_amount,
    )
    if allocated is None:
        return _blocked(
            rollforward,
            renewal_execution_event_id=renewal_execution_event_id,
            blocker_code="renewal_boundary_eir_period_allocation_not_exact",
            message=(
                "Renewal-boundary EIR could not be allocated exactly to fiscal "
                "period cents under the existing deterministic policy."
            ),
        )

    proposals: list[GreenfieldRegularRenewalBoundaryEirPeriodProposal] = []
    for item in allocated:
        amount = money(item.effective_interest_allocated)
        if amount == ZERO:
            continue
        source_reference = (
            f"{renewal_execution_event_id}:fiscal_period:{item.period_id}"
        )
        proposals.append(
            GreenfieldRegularRenewalBoundaryEirPeriodProposal(
                fiscal_period_id=item.period_id,
                fiscal_period_label=item.label,
                accrual_start_date_inclusive=item.accrual_start_date_inclusive,
                accrual_end_date_inclusive=item.accrual_end_date_inclusive,
                posting_date=item.accrual_end_date_inclusive,
                day_count=item.day_count,
                amount=amount,
                source_type="regular_renewal_eir_accrual",
                source_reference=source_reference,
                source_event_key=(
                    "renewal_eir_accrual:"
                    f"{renewal_execution_event_id}:fiscal_period:{item.period_id}"
                ),
                proposed_lines=(
                    GreenfieldRegularRenewalBoundaryEirLine(
                        account_system_key="accrued_interest_receivable",
                        side="debit",
                        amount=amount,
                    ),
                    GreenfieldRegularRenewalBoundaryEirLine(
                        account_system_key="interest_income_regular",
                        side="credit",
                        amount=amount,
                    ),
                ),
            )
        )

    total_debit = sum(
        (
            line.amount
            for proposal in proposals
            for line in proposal.proposed_lines
            if line.side == "debit"
        ),
        ZERO,
    )
    total_credit = sum(
        (
            line.amount
            for proposal in proposals
            for line in proposal.proposed_lines
            if line.side == "credit"
        ),
        ZERO,
    )
    if total_debit != target_amount or total_credit != target_amount:
        return _blocked(
            rollforward,
            renewal_execution_event_id=renewal_execution_event_id,
            blocker_code="renewal_boundary_eir_journal_coordinates_not_exact",
            message=(
                "Renewal-boundary EIR journal coordinates do not balance exactly "
                "to the measured tail amount."
            ),
        )

    return GreenfieldRegularRenewalBoundaryEirPreview(
        renewal_execution_event_id=renewal_execution_event_id,
        loan_id=rollforward.loan_id,
        target_date=rollforward.target_date,
        amount=target_amount,
        disposition="renewal_boundary_eir_journal_preview_ready",
        blocker_code=None,
        message=(
            "Exact read-only renewal-boundary EIR coordinates are available. "
            "Journal creation and posting remain disabled."
        ),
        period_proposals=tuple(proposals),
        total_debit=total_debit,
        total_credit=total_credit,
        balanced=True,
        posting_eligible=False,
        automatic_source_posting=False,
    )
