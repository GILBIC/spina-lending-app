from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from gilbic_backend.greenfield_regular_ledger_reconciliation import (
    GreenfieldRegularActualJournalLine,
    GreenfieldRegularLedgerReconciliation,
)
from gilbic_backend.greenfield_regular_renewal_boundary_eir import (
    GreenfieldRegularRenewalBoundaryEirLine,
    GreenfieldRegularRenewalBoundaryEirPeriodProposal,
    GreenfieldRegularRenewalBoundaryEirPreview,
)
from gilbic_backend.greenfield_regular_renewal_final_reconciliation import (
    GreenfieldRegularRenewalBoundaryActualJournal,
    build_greenfield_regular_renewal_final_reconciliation,
)


EXECUTION_ID = UUID("11111111-1111-4111-8111-111111111111")
LOAN_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
PERIOD_ID = UUID("44444444-4444-4444-8444-444444444444")
JOURNAL_ID = UUID("55555555-5555-4555-8555-555555555555")


def _source_reconciliation() -> GreenfieldRegularLedgerReconciliation:
    return GreenfieldRegularLedgerReconciliation(
        loan_id=LOAN_ID,
        anchor_date=date(2026, 8, 1),
        target_date=date(2026, 8, 31),
        disposition="greenfield_regular_ledger_reconciliation_blocked",
        blocker_code="renewal_boundary_eir_accrual_not_posted",
        message="source journals exact, boundary EIR remains",
        expected_active_transaction_count=2,
        expected_journal_count=4,
        exact_posted_journal_count=4,
        ignored_voided_reversed_journal_count=0,
        unprotected_posted_journal_count=0,
        expected_loan_component_through_last_source=Decimal("4800.00"),
        expected_accrued_interest_through_last_source=Decimal("311.13"),
        ledger_loan_component_through_last_source=Decimal("4800.00"),
        ledger_accrued_interest_through_last_source=Decimal("311.13"),
        ledger_gross_carrying_through_last_source=Decimal("5111.13"),
        target_gross_carrying_amount=Decimal("5272.35"),
        target_accrued_interest_component=Decimal("472.35"),
        target_loan_component=Decimal("4800.00"),
        tail_effective_interest_accrued=Decimal("161.22"),
        protected_regular_journals_reconciled=True,
        target_ledger_reconciled=False,
        accounting_carrying_amount_ready=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )


def _boundary_preview() -> GreenfieldRegularRenewalBoundaryEirPreview:
    source_reference = f"{EXECUTION_ID}:fiscal_period:{PERIOD_ID}"
    source_key = f"renewal_eir_accrual:{EXECUTION_ID}:fiscal_period:{PERIOD_ID}"
    amount = Decimal("161.22")
    return GreenfieldRegularRenewalBoundaryEirPreview(
        renewal_execution_event_id=EXECUTION_ID,
        loan_id=LOAN_ID,
        target_date=date(2026, 8, 31),
        amount=amount,
        disposition="renewal_boundary_eir_journal_preview_ready",
        blocker_code=None,
        message="ready",
        period_proposals=(
            GreenfieldRegularRenewalBoundaryEirPeriodProposal(
                fiscal_period_id=PERIOD_ID,
                fiscal_period_label="August 2026",
                accrual_start_date_inclusive=date(2026, 8, 21),
                accrual_end_date_inclusive=date(2026, 8, 31),
                posting_date=date(2026, 8, 31),
                day_count=11,
                amount=amount,
                source_type="regular_renewal_eir_accrual",
                source_reference=source_reference,
                source_event_key=source_key,
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
            ),
        ),
        total_debit=amount,
        total_credit=amount,
        balanced=True,
        posting_eligible=False,
        automatic_source_posting=False,
    )


def _actual(*, audit_exact: bool = True, amount: str = "161.22"):
    value = Decimal(amount)
    return (
        GreenfieldRegularRenewalBoundaryActualJournal(
            sequence_order=1,
            journal_entry_id=JOURNAL_ID,
            source_type="regular_renewal_eir_accrual",
            source_reference=f"{EXECUTION_ID}:fiscal_period:{PERIOD_ID}",
            source_event_key=(
                f"renewal_eir_accrual:{EXECUTION_ID}:fiscal_period:{PERIOD_ID}"
            ),
            posting_date=date(2026, 8, 31),
            fiscal_period_id=PERIOD_ID,
            journal_status="posted",
            entry_number="JE-202608-00000099",
            posting_audit_exact=audit_exact,
            lines=(
                GreenfieldRegularActualJournalLine(
                    line_number=1,
                    account_system_key="accrued_interest_receivable",
                    debit=value,
                    credit=Decimal("0.00"),
                    loan_id=LOAN_ID,
                    client_id=CLIENT_ID,
                ),
                GreenfieldRegularActualJournalLine(
                    line_number=2,
                    account_system_key="interest_income_regular",
                    debit=Decimal("0.00"),
                    credit=value,
                    loan_id=LOAN_ID,
                    client_id=CLIENT_ID,
                ),
            ),
        ),
    )


def test_final_reconciliation_requires_protected_boundary_posting() -> None:
    result = build_greenfield_regular_renewal_final_reconciliation(
        renewal_execution_event_id=EXECUTION_ID,
        old_loan_id=LOAN_ID,
        client_id=CLIENT_ID,
        source_reconciliation=_source_reconciliation(),
        boundary_preview=_boundary_preview(),
        actual_boundary_journals=(),
    )
    assert result.blocker_code == "renewal_boundary_eir_protected_posting_required"
    assert result.accounting_carrying_amount_ready is False
    assert result.automatic_source_posting is False


def test_final_reconciliation_rejects_inexact_protected_posting_audit() -> None:
    result = build_greenfield_regular_renewal_final_reconciliation(
        renewal_execution_event_id=EXECUTION_ID,
        old_loan_id=LOAN_ID,
        client_id=CLIENT_ID,
        source_reconciliation=_source_reconciliation(),
        boundary_preview=_boundary_preview(),
        actual_boundary_journals=_actual(audit_exact=False),
    )
    assert result.blocker_code == "renewal_boundary_eir_protected_posted_journal_not_exact"
    assert result.accounting_carrying_amount_ready is False


def test_exact_protected_boundary_posting_promotes_authoritative_carrying_amount() -> None:
    result = build_greenfield_regular_renewal_final_reconciliation(
        renewal_execution_event_id=EXECUTION_ID,
        old_loan_id=LOAN_ID,
        client_id=CLIENT_ID,
        source_reconciliation=_source_reconciliation(),
        boundary_preview=_boundary_preview(),
        actual_boundary_journals=_actual(),
    )
    assert result.disposition == "greenfield_regular_renewal_final_reconciliation_ready"
    assert result.blocker_code is None
    assert result.expected_boundary_journal_count == 1
    assert result.exact_posted_boundary_journal_count == 1
    assert result.final_ledger_loan_component == Decimal("4800.00")
    assert result.final_ledger_accrued_interest_component == Decimal("472.35")
    assert result.final_ledger_gross_carrying_amount == Decimal("5272.35")
    assert result.target_ledger_reconciled is True
    assert result.accounting_carrying_amount_ready is True
    assert result.journal_lines_enabled is False
    assert result.automatic_source_posting is False


def test_boundary_amount_mismatch_never_promotes_carrying_amount() -> None:
    result = build_greenfield_regular_renewal_final_reconciliation(
        renewal_execution_event_id=EXECUTION_ID,
        old_loan_id=LOAN_ID,
        client_id=CLIENT_ID,
        source_reconciliation=_source_reconciliation(),
        boundary_preview=_boundary_preview(),
        actual_boundary_journals=_actual(amount="161.21"),
    )
    assert result.blocker_code == "renewal_boundary_eir_protected_posted_journal_not_exact"
    assert result.accounting_carrying_amount_ready is False