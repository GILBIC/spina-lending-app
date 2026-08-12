from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from .eir_cash_allocation import money
from .greenfield_regular_ledger_reconciliation import (
    GreenfieldRegularActualJournalLine,
    GreenfieldRegularLedgerReconciliation,
)
from .greenfield_regular_renewal_boundary_eir import (
    GreenfieldRegularRenewalBoundaryEirPreview,
)


ZERO = Decimal("0.00")
FINAL_POLICY_VERSION = "greenfield_regular_renewal_final_reconciliation_v1"
BOUNDARY_BLOCKER = "renewal_boundary_eir_accrual_not_posted"


@dataclass(frozen=True, slots=True)
class GreenfieldRegularRenewalBoundaryActualJournal:
    sequence_order: int
    journal_entry_id: UUID
    source_type: str
    source_reference: str
    source_event_key: str
    posting_date: object
    fiscal_period_id: UUID
    journal_status: str
    entry_number: str | None
    posting_audit_exact: bool
    lines: tuple[GreenfieldRegularActualJournalLine, ...]


@dataclass(frozen=True, slots=True)
class GreenfieldRegularRenewalFinalReconciliation:
    renewal_execution_event_id: UUID
    old_loan_id: UUID
    disposition: str
    blocker_code: str | None
    message: str
    protected_source_journals_reconciled: bool
    expected_boundary_journal_count: int
    exact_posted_boundary_journal_count: int
    boundary_effective_interest_amount: Decimal
    ledger_loan_component_before_boundary: Decimal
    ledger_accrued_interest_before_boundary: Decimal
    ledger_gross_carrying_before_boundary: Decimal
    final_ledger_loan_component: Decimal | None
    final_ledger_accrued_interest_component: Decimal | None
    final_ledger_gross_carrying_amount: Decimal | None
    target_loan_component: Decimal | None
    target_accrued_interest_component: Decimal | None
    target_gross_carrying_amount: Decimal | None
    target_ledger_reconciled: bool
    accounting_carrying_amount_ready: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool
    policy_version: str = FINAL_POLICY_VERSION


def _blocked(
    *,
    renewal_execution_event_id: UUID,
    old_loan_id: UUID,
    source_reconciliation: GreenfieldRegularLedgerReconciliation,
    boundary_preview: GreenfieldRegularRenewalBoundaryEirPreview | None,
    blocker_code: str,
    message: str,
    exact_posted_boundary_journal_count: int = 0,
    final_loan: Decimal | None = None,
    final_accrued: Decimal | None = None,
) -> GreenfieldRegularRenewalFinalReconciliation:
    before_loan = money(
        source_reconciliation.ledger_loan_component_through_last_source or ZERO
    )
    before_accrued = money(
        source_reconciliation.ledger_accrued_interest_through_last_source or ZERO
    )
    before_gross = money(before_loan + before_accrued)
    expected_count = (
        len(boundary_preview.period_proposals) if boundary_preview is not None else 0
    )
    boundary_amount = (
        money(boundary_preview.amount) if boundary_preview is not None else ZERO
    )
    final_gross = (
        money(final_loan + final_accrued)
        if final_loan is not None and final_accrued is not None
        else None
    )
    return GreenfieldRegularRenewalFinalReconciliation(
        renewal_execution_event_id=renewal_execution_event_id,
        old_loan_id=old_loan_id,
        disposition="greenfield_regular_renewal_final_reconciliation_blocked",
        blocker_code=blocker_code,
        message=message,
        protected_source_journals_reconciled=(
            source_reconciliation.protected_regular_journals_reconciled
        ),
        expected_boundary_journal_count=expected_count,
        exact_posted_boundary_journal_count=exact_posted_boundary_journal_count,
        boundary_effective_interest_amount=boundary_amount,
        ledger_loan_component_before_boundary=before_loan,
        ledger_accrued_interest_before_boundary=before_accrued,
        ledger_gross_carrying_before_boundary=before_gross,
        final_ledger_loan_component=(
            None if final_loan is None else money(final_loan)
        ),
        final_ledger_accrued_interest_component=(
            None if final_accrued is None else money(final_accrued)
        ),
        final_ledger_gross_carrying_amount=final_gross,
        target_loan_component=source_reconciliation.target_loan_component,
        target_accrued_interest_component=(
            source_reconciliation.target_accrued_interest_component
        ),
        target_gross_carrying_amount=(
            source_reconciliation.target_gross_carrying_amount
        ),
        target_ledger_reconciled=False,
        accounting_carrying_amount_ready=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )


def _lines_exact(
    *,
    actual: GreenfieldRegularRenewalBoundaryActualJournal,
    amount: Decimal,
    old_loan_id: UUID,
    client_id: UUID,
) -> bool:
    if len(actual.lines) != 2:
        return False
    by_account = {line.account_system_key: line for line in actual.lines}
    if len(by_account) != 2:
        return False
    debit = by_account.get("accrued_interest_receivable")
    credit = by_account.get("interest_income_regular")
    if debit is None or credit is None:
        return False
    expected = money(amount)
    return (
        money(debit.debit) == expected
        and money(debit.credit) == ZERO
        and debit.loan_id == old_loan_id
        and debit.client_id == client_id
        and money(credit.debit) == ZERO
        and money(credit.credit) == expected
        and credit.loan_id == old_loan_id
        and credit.client_id == client_id
    )


def build_greenfield_regular_renewal_final_reconciliation(
    *,
    renewal_execution_event_id: UUID,
    old_loan_id: UUID,
    client_id: UUID,
    source_reconciliation: GreenfieldRegularLedgerReconciliation,
    boundary_preview: GreenfieldRegularRenewalBoundaryEirPreview | None,
    actual_boundary_journals: tuple[
        GreenfieldRegularRenewalBoundaryActualJournal, ...
    ],
) -> GreenfieldRegularRenewalFinalReconciliation:
    if (
        source_reconciliation.blocker_code != BOUNDARY_BLOCKER
        or not source_reconciliation.protected_regular_journals_reconciled
        or source_reconciliation.accounting_carrying_amount_ready
    ):
        return _blocked(
            renewal_execution_event_id=renewal_execution_event_id,
            old_loan_id=old_loan_id,
            source_reconciliation=source_reconciliation,
            boundary_preview=boundary_preview,
            blocker_code=(
                source_reconciliation.blocker_code
                or "protected_regular_source_reconciliation_not_boundary_ready"
            ),
            message=(
                "The protected Regular source ledger must reconcile exactly with "
                "renewal-boundary EIR as its sole remaining blocker before final "
                "old-loan carrying-amount reconciliation can run."
            ),
        )
    if (
        boundary_preview is None
        or boundary_preview.renewal_execution_event_id
        != renewal_execution_event_id
        or boundary_preview.loan_id != old_loan_id
        or boundary_preview.disposition
        != "renewal_boundary_eir_journal_preview_ready"
        or boundary_preview.blocker_code is not None
        or not boundary_preview.balanced
        or boundary_preview.posting_eligible
        or boundary_preview.automatic_source_posting
        or boundary_preview.amount <= ZERO
        or not boundary_preview.period_proposals
    ):
        return _blocked(
            renewal_execution_event_id=renewal_execution_event_id,
            old_loan_id=old_loan_id,
            source_reconciliation=source_reconciliation,
            boundary_preview=boundary_preview,
            blocker_code="renewal_boundary_eir_preview_not_exact",
            message=(
                "Exact read-only renewal-boundary EIR coordinates are required "
                "before protected posting history can be reconciled."
            ),
        )

    if not actual_boundary_journals:
        return _blocked(
            renewal_execution_event_id=renewal_execution_event_id,
            old_loan_id=old_loan_id,
            source_reconciliation=source_reconciliation,
            boundary_preview=boundary_preview,
            blocker_code="renewal_boundary_eir_protected_posting_required",
            message=(
                "The exact renewal-boundary EIR preview is ready, but no protected "
                "Management-confirmed posted boundary journal audit exists yet."
            ),
        )

    expected_by_key = {
        proposal.source_event_key: proposal
        for proposal in boundary_preview.period_proposals
    }
    actual_by_key = {
        journal.source_event_key: journal for journal in actual_boundary_journals
    }
    if (
        len(expected_by_key) != len(boundary_preview.period_proposals)
        or len(actual_by_key) != len(actual_boundary_journals)
        or set(expected_by_key) != set(actual_by_key)
    ):
        return _blocked(
            renewal_execution_event_id=renewal_execution_event_id,
            old_loan_id=old_loan_id,
            source_reconciliation=source_reconciliation,
            boundary_preview=boundary_preview,
            blocker_code="renewal_boundary_eir_protected_posting_set_not_exact",
            message=(
                "Protected posted renewal-boundary EIR source identities do not "
                "exactly match the currently recomputed boundary preview."
            ),
            exact_posted_boundary_journal_count=len(
                set(expected_by_key) & set(actual_by_key)
            ),
        )

    exact_count = 0
    for expected in boundary_preview.period_proposals:
        actual = actual_by_key[expected.source_event_key]
        if (
            actual.source_type != expected.source_type
            or actual.source_reference != expected.source_reference
            or actual.source_event_key != expected.source_event_key
            or actual.posting_date != expected.posting_date
            or actual.fiscal_period_id != expected.fiscal_period_id
            or actual.journal_status != "posted"
            or not actual.entry_number
            or not actual.posting_audit_exact
            or not _lines_exact(
                actual=actual,
                amount=expected.amount,
                old_loan_id=old_loan_id,
                client_id=client_id,
            )
        ):
            return _blocked(
                renewal_execution_event_id=renewal_execution_event_id,
                old_loan_id=old_loan_id,
                source_reconciliation=source_reconciliation,
                boundary_preview=boundary_preview,
                blocker_code="renewal_boundary_eir_protected_posted_journal_not_exact",
                message=(
                    "A protected renewal-boundary EIR journal does not exactly "
                    "match its recomputed source identity, period, posting audit, "
                    "dimensions, or 1120/4000 line coordinates."
                ),
                exact_posted_boundary_journal_count=exact_count,
            )
        exact_count += 1

    before_loan = source_reconciliation.ledger_loan_component_through_last_source
    before_accrued = (
        source_reconciliation.ledger_accrued_interest_through_last_source
    )
    target_loan = source_reconciliation.target_loan_component
    target_accrued = source_reconciliation.target_accrued_interest_component
    target_gross = source_reconciliation.target_gross_carrying_amount
    if any(
        value is None
        for value in (
            before_loan,
            before_accrued,
            target_loan,
            target_accrued,
            target_gross,
        )
    ):
        return _blocked(
            renewal_execution_event_id=renewal_execution_event_id,
            old_loan_id=old_loan_id,
            source_reconciliation=source_reconciliation,
            boundary_preview=boundary_preview,
            blocker_code="renewal_target_components_incomplete",
            message="Complete source-ledger and target carrying components are required.",
            exact_posted_boundary_journal_count=exact_count,
        )

    final_loan = money(before_loan)
    final_accrued = money(before_accrued + boundary_preview.amount)
    final_gross = money(final_loan + final_accrued)
    if (
        final_loan != money(target_loan)
        or final_accrued != money(target_accrued)
        or final_gross != money(target_gross)
    ):
        return _blocked(
            renewal_execution_event_id=renewal_execution_event_id,
            old_loan_id=old_loan_id,
            source_reconciliation=source_reconciliation,
            boundary_preview=boundary_preview,
            blocker_code="renewal_boundary_eir_final_ledger_not_reconciled",
            message=(
                "Protected boundary journals are exact, but the final old-loan "
                "ledger components do not equal the authoritative renewal-date "
                "greenfield EIR measurement."
            ),
            exact_posted_boundary_journal_count=exact_count,
            final_loan=final_loan,
            final_accrued=final_accrued,
        )

    return GreenfieldRegularRenewalFinalReconciliation(
        renewal_execution_event_id=renewal_execution_event_id,
        old_loan_id=old_loan_id,
        disposition="greenfield_regular_renewal_final_reconciliation_ready",
        blocker_code=None,
        message=(
            "Protected Regular source journals and the explicit Management-posted "
            "renewal-boundary EIR journals reconcile exactly to the authoritative "
            "renewal-date old-loan carrying amount. This carrying amount is now "
            "authoritative accounting evidence for the next renewal treatment decision."
        ),
        protected_source_journals_reconciled=True,
        expected_boundary_journal_count=len(boundary_preview.period_proposals),
        exact_posted_boundary_journal_count=exact_count,
        boundary_effective_interest_amount=money(boundary_preview.amount),
        ledger_loan_component_before_boundary=money(before_loan),
        ledger_accrued_interest_before_boundary=money(before_accrued),
        ledger_gross_carrying_before_boundary=money(before_loan + before_accrued),
        final_ledger_loan_component=final_loan,
        final_ledger_accrued_interest_component=final_accrued,
        final_ledger_gross_carrying_amount=final_gross,
        target_loan_component=money(target_loan),
        target_accrued_interest_component=money(target_accrued),
        target_gross_carrying_amount=money(target_gross),
        target_ledger_reconciled=True,
        accounting_carrying_amount_ready=True,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )