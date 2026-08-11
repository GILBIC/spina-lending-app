from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import EirCashAllocation, money
from .greenfield_regular_eir_rollforward import GreenfieldRegularRenewalRollForward
from .regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
    RegularEirAccrualPeriodEvidence,
    allocate_regular_eir_period_split,
)


ZERO = Decimal("0.00")
GREENFIELD_REGULAR_LEDGER_RECONCILIATION_POLICY_VERSION = (
    "greenfield_regular_ledger_reconciliation_v1"
)


@dataclass(frozen=True, slots=True)
class GreenfieldRegularExpectedJournalLine:
    line_number: int
    account_system_key: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True, slots=True)
class GreenfieldRegularExpectedJournal:
    transaction_id: UUID
    sequence_order: int
    entry_type: str
    source_type: str
    source_reference: str
    source_event_key: str
    posting_date: date
    fiscal_period_id: UUID
    amount: Decimal
    lines: tuple[GreenfieldRegularExpectedJournalLine, ...]


@dataclass(frozen=True, slots=True)
class GreenfieldRegularActualJournalLine:
    line_number: int
    account_system_key: str
    debit: Decimal
    credit: Decimal
    loan_id: UUID | None
    client_id: UUID | None


@dataclass(frozen=True, slots=True)
class GreenfieldRegularActualProtectedJournal:
    transaction_id: UUID
    transaction_is_voided: bool
    sequence_order: int
    entry_type: str
    source_type: str
    source_reference: str
    source_event_key: str
    posting_date: date
    fiscal_period_id: UUID
    journal_status: str
    posting_audit_exact: bool
    lines: tuple[GreenfieldRegularActualJournalLine, ...]
    reversal_present: bool = False
    reversal_exact: bool = False


@dataclass(frozen=True, slots=True)
class GreenfieldRegularLedgerReconciliation:
    loan_id: UUID
    anchor_date: date
    target_date: date
    disposition: str
    blocker_code: str | None
    message: str
    expected_active_transaction_count: int
    expected_journal_count: int
    exact_posted_journal_count: int
    ignored_voided_reversed_journal_count: int
    unprotected_posted_journal_count: int
    expected_loan_component_through_last_source: Decimal
    expected_accrued_interest_through_last_source: Decimal
    ledger_loan_component_through_last_source: Decimal | None
    ledger_accrued_interest_through_last_source: Decimal | None
    ledger_gross_carrying_through_last_source: Decimal | None
    target_gross_carrying_amount: Decimal | None
    target_accrued_interest_component: Decimal | None
    target_loan_component: Decimal | None
    tail_effective_interest_accrued: Decimal
    protected_regular_journals_reconciled: bool
    target_ledger_reconciled: bool
    accounting_carrying_amount_ready: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool
    policy_version: str = GREENFIELD_REGULAR_LEDGER_RECONCILIATION_POLICY_VERSION


def _blocked(
    *,
    rollforward: GreenfieldRegularRenewalRollForward,
    blocker_code: str,
    message: str,
    expected_active_transaction_count: int,
    expected_journal_count: int = 0,
    exact_posted_journal_count: int = 0,
    ignored_voided_reversed_journal_count: int = 0,
    unprotected_posted_journal_count: int = 0,
    expected_loan_component_through_last_source: Decimal | None = None,
    expected_accrued_interest_through_last_source: Decimal | None = None,
    ledger_loan_component_through_last_source: Decimal | None = None,
    ledger_accrued_interest_through_last_source: Decimal | None = None,
    protected_regular_journals_reconciled: bool = False,
) -> GreenfieldRegularLedgerReconciliation:
    expected_loan = money(
        expected_loan_component_through_last_source
        if expected_loan_component_through_last_source is not None
        else rollforward.initial_loan_component
    )
    expected_accrued = money(
        expected_accrued_interest_through_last_source
        if expected_accrued_interest_through_last_source is not None
        else rollforward.initial_accrued_interest_component
    )
    ledger_gross = (
        money(
            Decimal(ledger_loan_component_through_last_source)
            + Decimal(ledger_accrued_interest_through_last_source)
        )
        if ledger_loan_component_through_last_source is not None
        and ledger_accrued_interest_through_last_source is not None
        else None
    )
    return GreenfieldRegularLedgerReconciliation(
        loan_id=rollforward.loan_id,
        anchor_date=rollforward.anchor_date,
        target_date=rollforward.target_date,
        disposition="greenfield_regular_ledger_reconciliation_blocked",
        blocker_code=blocker_code,
        message=message,
        expected_active_transaction_count=expected_active_transaction_count,
        expected_journal_count=expected_journal_count,
        exact_posted_journal_count=exact_posted_journal_count,
        ignored_voided_reversed_journal_count=ignored_voided_reversed_journal_count,
        unprotected_posted_journal_count=unprotected_posted_journal_count,
        expected_loan_component_through_last_source=expected_loan,
        expected_accrued_interest_through_last_source=expected_accrued,
        ledger_loan_component_through_last_source=(
            money(ledger_loan_component_through_last_source)
            if ledger_loan_component_through_last_source is not None
            else None
        ),
        ledger_accrued_interest_through_last_source=(
            money(ledger_accrued_interest_through_last_source)
            if ledger_accrued_interest_through_last_source is not None
            else None
        ),
        ledger_gross_carrying_through_last_source=ledger_gross,
        target_gross_carrying_amount=rollforward.gross_carrying_amount_at_target,
        target_accrued_interest_component=(
            rollforward.accrued_interest_component_at_target
        ),
        target_loan_component=rollforward.loan_component_at_target,
        tail_effective_interest_accrued=rollforward.tail_effective_interest_accrued,
        protected_regular_journals_reconciled=protected_regular_journals_reconciled,
        target_ledger_reconciled=False,
        accounting_carrying_amount_ready=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )


def _period_for_date(
    periods: tuple[AccountingFiscalPeriodReference, ...],
    target_date: date,
) -> AccountingFiscalPeriodReference | None:
    matching = tuple(
        period
        for period in periods
        if period.start_date <= target_date <= period.end_date
    )
    if len(matching) != 1 or matching[0].status != "open":
        return None
    return matching[0]


def _expected_eir_journals(
    allocation: EirCashAllocation,
    *,
    periods: tuple[AccountingFiscalPeriodReference, ...],
) -> tuple[GreenfieldRegularExpectedJournal, ...] | None:
    target_amount = money(allocation.effective_interest_accrued_since_prior_event)
    if target_amount == ZERO:
        return ()
    if target_amount < ZERO or not allocation.daily_accruals:
        return None

    grouped: dict[
        UUID,
        tuple[AccountingFiscalPeriodReference, list[tuple[date, Decimal]]],
    ] = {}
    for daily in allocation.daily_accruals:
        period = _period_for_date(periods, daily.accrual_date)
        if period is None:
            return None
        if period.period_id not in grouped:
            grouped[period.period_id] = (period, [])
        grouped[period.period_id][1].append(
            (daily.accrual_date, daily.effective_interest_raw)
        )

    evidence: list[RegularEirAccrualPeriodEvidence] = []
    for period, rows in sorted(
        grouped.values(),
        key=lambda item: (
            item[0].start_date,
            item[0].end_date,
            str(item[0].period_id),
        ),
    ):
        raw_amount = sum((amount for _, amount in rows), Decimal("0"))
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
                effective_interest_raw=raw_amount,
                effective_interest_rounded=money(raw_amount),
            )
        )

    allocated = allocate_regular_eir_period_split(
        tuple(evidence),
        target_amount=target_amount,
    )
    if allocated is None:
        return None

    journals: list[GreenfieldRegularExpectedJournal] = []
    for item in allocated:
        amount = item.effective_interest_allocated
        if amount == ZERO:
            continue
        source_reference = (
            f"{allocation.transaction_id}:fiscal_period:{item.period_id}"
        )
        source_event_key = (
            f"eir_accrual:collection:{allocation.transaction_id}:"
            f"fiscal_period:{item.period_id}"
        )
        journals.append(
            GreenfieldRegularExpectedJournal(
                transaction_id=allocation.transaction_id,
                sequence_order=len(journals) + 1,
                entry_type="eir_accrual_period",
                source_type="regular_eir_accrual",
                source_reference=source_reference,
                source_event_key=source_event_key,
                posting_date=item.accrual_end_date_inclusive,
                fiscal_period_id=item.period_id,
                amount=amount,
                lines=(
                    GreenfieldRegularExpectedJournalLine(
                        line_number=1,
                        account_system_key="accrued_interest_receivable",
                        debit=amount,
                        credit=ZERO,
                    ),
                    GreenfieldRegularExpectedJournalLine(
                        line_number=2,
                        account_system_key="interest_income_regular",
                        debit=ZERO,
                        credit=amount,
                    ),
                ),
            )
        )
    return tuple(journals)


def _expected_collection_journal(
    allocation: EirCashAllocation,
    *,
    period: AccountingFiscalPeriodReference,
    sequence_order: int,
) -> GreenfieldRegularExpectedJournal:
    lines: list[GreenfieldRegularExpectedJournalLine] = [
        GreenfieldRegularExpectedJournalLine(
            line_number=1,
            account_system_key="cash_collector_custody",
            debit=money(allocation.amount),
            credit=ZERO,
        )
    ]
    if allocation.cash_to_accrued_interest > ZERO:
        lines.append(
            GreenfieldRegularExpectedJournalLine(
                line_number=len(lines) + 1,
                account_system_key="accrued_interest_receivable",
                debit=ZERO,
                credit=money(allocation.cash_to_accrued_interest),
            )
        )
    if allocation.cash_to_loan_component > ZERO:
        lines.append(
            GreenfieldRegularExpectedJournalLine(
                line_number=len(lines) + 1,
                account_system_key="loans_receivable_regular",
                debit=ZERO,
                credit=money(allocation.cash_to_loan_component),
            )
        )
    return GreenfieldRegularExpectedJournal(
        transaction_id=allocation.transaction_id,
        sequence_order=sequence_order,
        entry_type="collection",
        source_type="collection",
        source_reference=str(allocation.transaction_id),
        source_event_key=f"collection:{allocation.transaction_id}",
        posting_date=allocation.collection_date,
        fiscal_period_id=period.period_id,
        amount=money(allocation.amount),
        lines=tuple(lines),
    )


def build_expected_greenfield_regular_journals(
    rollforward: GreenfieldRegularRenewalRollForward,
    *,
    fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> tuple[GreenfieldRegularExpectedJournal, ...] | None:
    if (
        not rollforward.measurement_preview_ready
        or rollforward.blocker_code is not None
        or rollforward.disposition
        != "greenfield_regular_renewal_rollforward_preview_ready"
    ):
        return None

    journals: list[GreenfieldRegularExpectedJournal] = []
    for allocation in rollforward.allocations:
        if allocation.disposition != "allocation_reference_ready":
            return None
        eir_journals = _expected_eir_journals(
            allocation,
            periods=fiscal_periods,
        )
        if eir_journals is None:
            return None
        for expected in eir_journals:
            journals.append(
                GreenfieldRegularExpectedJournal(
                    transaction_id=expected.transaction_id,
                    sequence_order=len(
                        [
                            item
                            for item in journals
                            if item.transaction_id == expected.transaction_id
                        ]
                    )
                    + 1,
                    entry_type=expected.entry_type,
                    source_type=expected.source_type,
                    source_reference=expected.source_reference,
                    source_event_key=expected.source_event_key,
                    posting_date=expected.posting_date,
                    fiscal_period_id=expected.fiscal_period_id,
                    amount=expected.amount,
                    lines=expected.lines,
                )
            )
        collection_period = _period_for_date(
            fiscal_periods,
            allocation.collection_date,
        )
        if collection_period is None:
            return None
        sequence_order = (
            sum(
                1
                for item in journals
                if item.transaction_id == allocation.transaction_id
            )
            + 1
        )
        journals.append(
            _expected_collection_journal(
                allocation,
                period=collection_period,
                sequence_order=sequence_order,
            )
        )
    return tuple(journals)


def _actual_lines_match(
    actual: GreenfieldRegularActualProtectedJournal,
    expected: GreenfieldRegularExpectedJournal,
    *,
    loan_id: UUID,
) -> bool:
    if len(actual.lines) != len(expected.lines):
        return False
    actual_by_number = {line.line_number: line for line in actual.lines}
    if len(actual_by_number) != len(actual.lines):
        return False
    for expected_line in expected.lines:
        line = actual_by_number.get(expected_line.line_number)
        if line is None:
            return False
        if (
            line.account_system_key != expected_line.account_system_key
            or money(line.debit) != expected_line.debit
            or money(line.credit) != expected_line.credit
            or line.loan_id != loan_id
            or line.client_id is None
        ):
            return False
    return True


def build_greenfield_regular_ledger_reconciliation(
    rollforward: GreenfieldRegularRenewalRollForward,
    *,
    fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
    actual_journals: tuple[GreenfieldRegularActualProtectedJournal, ...],
    candidate_status: str,
    unprotected_posted_journal_count: int = 0,
) -> GreenfieldRegularLedgerReconciliation:
    """Reconcile protected Regular journal history to a greenfield EIR anchor.

    Stage 5D.27 does not create a journal. It derives the exact journal identities
    and line coordinates already required by the Stage 5D.13-5D.18 protected
    Regular path from the Stage 5D.25 greenfield anchor/Stage 5D.26 allocations,
    then compares those coordinates with immutable protected posted history.

    A positive no-cash EIR tail at the renewal boundary intentionally remains a
    blocker: the existing collection-triggered protected path has no authoritative
    renewal-boundary accrual journal yet. The measured renewal carrying amount is
    therefore not promoted to accounting evidence until that gap is separately
    protected and posted.
    """

    expected_active_transactions = len(rollforward.allocations)
    if (
        rollforward.disposition
        != "greenfield_regular_renewal_rollforward_preview_ready"
        or rollforward.blocker_code is not None
        or not rollforward.measurement_preview_ready
    ):
        return _blocked(
            rollforward=rollforward,
            blocker_code=(
                rollforward.blocker_code
                or "greenfield_regular_rollforward_not_ready"
            ),
            message=rollforward.message,
            expected_active_transaction_count=expected_active_transactions,
        )
    if candidate_status != "greenfield_regular_ledger_reconciliation_candidate":
        return _blocked(
            rollforward=rollforward,
            blocker_code=candidate_status,
            message=(
                "The Stage 5D.27 coarse protected-ledger gate is not ready for "
                "exact source/journal reconciliation."
            ),
            expected_active_transaction_count=expected_active_transactions,
            unprotected_posted_journal_count=unprotected_posted_journal_count,
        )
    if unprotected_posted_journal_count != 0:
        return _blocked(
            rollforward=rollforward,
            blocker_code="unprotected_regular_journal_history_review",
            message=(
                "Posted Regular accounting history exists outside the protected "
                "Stage 5D.17 audit chain. Carrying-amount reconciliation fails closed."
            ),
            expected_active_transaction_count=expected_active_transactions,
            unprotected_posted_journal_count=unprotected_posted_journal_count,
        )

    expected = build_expected_greenfield_regular_journals(
        rollforward,
        fiscal_periods=fiscal_periods,
    )
    if expected is None:
        return _blocked(
            rollforward=rollforward,
            blocker_code="greenfield_regular_expected_journal_coordinates_not_ready",
            message=(
                "Exact protected Regular EIR/collection journal coordinates could "
                "not be replayed from the greenfield anchor and open fiscal periods."
            ),
            expected_active_transaction_count=expected_active_transactions,
        )

    ignored_voided = 0
    active_actual: list[GreenfieldRegularActualProtectedJournal] = []
    for journal in actual_journals:
        if journal.transaction_is_voided:
            if not journal.reversal_present or not journal.reversal_exact:
                return _blocked(
                    rollforward=rollforward,
                    blocker_code="voided_protected_regular_source_not_exactly_reversed",
                    message=(
                        "A voided protected Regular source has posted history without "
                        "an exact Stage 5D.18 reversal."
                    ),
                    expected_active_transaction_count=expected_active_transactions,
                    expected_journal_count=len(expected),
                    ignored_voided_reversed_journal_count=ignored_voided,
                )
            ignored_voided += 1
            continue
        if journal.reversal_present:
            return _blocked(
                rollforward=rollforward,
                blocker_code="active_protected_regular_source_has_reversal",
                message="An active Regular source unexpectedly has protected reversal history.",
                expected_active_transaction_count=expected_active_transactions,
                expected_journal_count=len(expected),
                ignored_voided_reversed_journal_count=ignored_voided,
            )
        active_actual.append(journal)

    expected_by_key = {item.source_event_key: item for item in expected}
    actual_by_key = {item.source_event_key: item for item in active_actual}
    if len(expected_by_key) != len(expected) or len(actual_by_key) != len(active_actual):
        return _blocked(
            rollforward=rollforward,
            blocker_code="protected_regular_source_identity_conflict",
            message="Protected Regular journal source identities are not unique.",
            expected_active_transaction_count=expected_active_transactions,
            expected_journal_count=len(expected),
            ignored_voided_reversed_journal_count=ignored_voided,
        )
    if set(actual_by_key) != set(expected_by_key):
        return _blocked(
            rollforward=rollforward,
            blocker_code="protected_regular_source_posting_gap",
            message=(
                "Protected posted Regular journal identities do not exactly match "
                "the greenfield EIR/collection source set through the renewal boundary."
            ),
            expected_active_transaction_count=expected_active_transactions,
            expected_journal_count=len(expected),
            exact_posted_journal_count=len(set(actual_by_key) & set(expected_by_key)),
            ignored_voided_reversed_journal_count=ignored_voided,
        )

    exact_count = 0
    ledger_loan = money(rollforward.initial_loan_component)
    ledger_accrued = money(rollforward.initial_accrued_interest_component)
    for source_key in sorted(expected_by_key):
        expected_journal = expected_by_key[source_key]
        actual = actual_by_key[source_key]
        if (
            actual.transaction_id != expected_journal.transaction_id
            or actual.sequence_order != expected_journal.sequence_order
            or actual.entry_type != expected_journal.entry_type
            or actual.source_type != expected_journal.source_type
            or actual.source_reference != expected_journal.source_reference
            or actual.source_event_key != expected_journal.source_event_key
            or actual.posting_date != expected_journal.posting_date
            or actual.fiscal_period_id != expected_journal.fiscal_period_id
            or actual.journal_status != "posted"
            or not actual.posting_audit_exact
            or not _actual_lines_match(actual, expected_journal, loan_id=rollforward.loan_id)
        ):
            return _blocked(
                rollforward=rollforward,
                blocker_code="protected_regular_posted_journal_not_exact",
                message=(
                    "A protected Stage 5D.17 journal does not exactly match its "
                    "greenfield source identity, date, period, audit, or line coordinates."
                ),
                expected_active_transaction_count=expected_active_transactions,
                expected_journal_count=len(expected),
                exact_posted_journal_count=exact_count,
                ignored_voided_reversed_journal_count=ignored_voided,
                ledger_loan_component_through_last_source=ledger_loan,
                ledger_accrued_interest_through_last_source=ledger_accrued,
            )
        exact_count += 1
        for line in actual.lines:
            if line.account_system_key == "loans_receivable_regular":
                ledger_loan = money(ledger_loan + line.debit - line.credit)
            elif line.account_system_key == "accrued_interest_receivable":
                ledger_accrued = money(ledger_accrued + line.debit - line.credit)

    if rollforward.allocations:
        expected_loan = money(rollforward.allocations[-1].loan_component_after)
        expected_accrued = money(rollforward.allocations[-1].accrued_interest_after)
    else:
        expected_loan = money(rollforward.initial_loan_component)
        expected_accrued = money(rollforward.initial_accrued_interest_component)

    if ledger_loan != expected_loan or ledger_accrued != expected_accrued:
        return _blocked(
            rollforward=rollforward,
            blocker_code="protected_regular_ledger_component_mismatch",
            message=(
                "Exact protected source journals exist, but their loan/accrued-interest "
                "ledger movement does not reconcile to the event-date EIR state."
            ),
            expected_active_transaction_count=expected_active_transactions,
            expected_journal_count=len(expected),
            exact_posted_journal_count=exact_count,
            ignored_voided_reversed_journal_count=ignored_voided,
            expected_loan_component_through_last_source=expected_loan,
            expected_accrued_interest_through_last_source=expected_accrued,
            ledger_loan_component_through_last_source=ledger_loan,
            ledger_accrued_interest_through_last_source=ledger_accrued,
        )

    if rollforward.tail_effective_interest_accrued > ZERO:
        return _blocked(
            rollforward=rollforward,
            blocker_code="renewal_boundary_eir_accrual_not_posted",
            message=(
                "Protected collection-triggered Regular journals reconcile exactly "
                "through the last source event, but positive no-cash EIR remains from "
                "that boundary through the authoritative renewal date. A separate "
                "protected renewal-boundary accrual is required before the measured "
                "target carrying amount can become authoritative accounting evidence."
            ),
            expected_active_transaction_count=expected_active_transactions,
            expected_journal_count=len(expected),
            exact_posted_journal_count=exact_count,
            ignored_voided_reversed_journal_count=ignored_voided,
            expected_loan_component_through_last_source=expected_loan,
            expected_accrued_interest_through_last_source=expected_accrued,
            ledger_loan_component_through_last_source=ledger_loan,
            ledger_accrued_interest_through_last_source=ledger_accrued,
            protected_regular_journals_reconciled=True,
        )

    target_loan = rollforward.loan_component_at_target
    target_accrued = rollforward.accrued_interest_component_at_target
    target_gross = rollforward.gross_carrying_amount_at_target
    if (
        target_loan is None
        or target_accrued is None
        or target_gross is None
        or ledger_loan != money(target_loan)
        or ledger_accrued != money(target_accrued)
        or money(ledger_loan + ledger_accrued) != money(target_gross)
    ):
        return _blocked(
            rollforward=rollforward,
            blocker_code="greenfield_regular_target_ledger_not_reconciled",
            message=(
                "The protected ledger through the final source does not exactly "
                "equal the Stage 5D.26 renewal-date carrying components."
            ),
            expected_active_transaction_count=expected_active_transactions,
            expected_journal_count=len(expected),
            exact_posted_journal_count=exact_count,
            ignored_voided_reversed_journal_count=ignored_voided,
            expected_loan_component_through_last_source=expected_loan,
            expected_accrued_interest_through_last_source=expected_accrued,
            ledger_loan_component_through_last_source=ledger_loan,
            ledger_accrued_interest_through_last_source=ledger_accrued,
            protected_regular_journals_reconciled=True,
        )

    return GreenfieldRegularLedgerReconciliation(
        loan_id=rollforward.loan_id,
        anchor_date=rollforward.anchor_date,
        target_date=rollforward.target_date,
        disposition="greenfield_regular_ledger_reconciliation_ready",
        blocker_code=None,
        message=(
            "Protected Stage 5D.17/5D.18 Regular source history exactly reconciles "
            "from the Stage 5D.25 greenfield anchor to the Stage 5D.26 target. The "
            "measured carrying amount may be used as authoritative accounting "
            "evidence for the next renewal-treatment decision; no journal is created here."
        ),
        expected_active_transaction_count=expected_active_transactions,
        expected_journal_count=len(expected),
        exact_posted_journal_count=exact_count,
        ignored_voided_reversed_journal_count=ignored_voided,
        unprotected_posted_journal_count=0,
        expected_loan_component_through_last_source=expected_loan,
        expected_accrued_interest_through_last_source=expected_accrued,
        ledger_loan_component_through_last_source=ledger_loan,
        ledger_accrued_interest_through_last_source=ledger_accrued,
        ledger_gross_carrying_through_last_source=money(ledger_loan + ledger_accrued),
        target_gross_carrying_amount=money(target_gross),
        target_accrued_interest_component=money(target_accrued),
        target_loan_component=money(target_loan),
        tail_effective_interest_accrued=ZERO,
        protected_regular_journals_reconciled=True,
        target_ledger_reconciled=True,
        accounting_carrying_amount_ready=True,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )
