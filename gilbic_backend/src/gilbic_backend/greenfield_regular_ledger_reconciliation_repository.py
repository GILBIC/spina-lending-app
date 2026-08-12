from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection
from .eir_cash_allocation import EirCashSourceEvent
from .greenfield_regular_eir_rollforward import (
    GreenfieldRegularRenewalRollForward,
    build_greenfield_regular_renewal_rollforward,
)
from .greenfield_regular_ledger_reconciliation import (
    GreenfieldRegularActualJournalLine,
    GreenfieldRegularActualProtectedJournal,
    GreenfieldRegularLedgerReconciliation,
    build_greenfield_regular_ledger_reconciliation,
)
from .regular_eir_accrual_journal_preview import AccountingFiscalPeriodReference


MAX_SOURCE_EVENTS = 5000
CANDIDATE_STATUS = "greenfield_regular_ledger_reconciliation_candidate"


class GreenfieldRegularLedgerReconciliationError(RuntimeError):
    code = "greenfield_regular_ledger_reconciliation_error"


@dataclass(frozen=True, slots=True)
class GreenfieldRegularLedgerReconciliationPreview:
    renewal_execution_event_id: UUID
    renewal_disbursement_event_id: UUID
    old_loan_id: UUID
    old_loan_number: str
    new_loan_id: UUID
    new_loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    target_date: date
    executed_at: datetime
    old_loan_settlement_amount: Decimal
    anchor_posting_id: UUID | None
    anchor_journal_entry_id: UUID | None
    anchor_entry_number: str | None
    anchor_date: date | None
    initial_gross_carrying_amount: Decimal | None
    initial_loan_component: Decimal | None
    initial_accrued_interest_component: Decimal | None
    daily_eir: Decimal | None
    contractual_due_date: date | None
    rollforward_readiness_status: str
    active_source_count: int
    protected_complete_active_source_count: int
    voided_posted_source_count: int
    voided_unreversed_source_count: int
    unprotected_posted_journal_count: int
    reconciliation_readiness_status: str
    exact_reconciliation_preview_enabled: bool
    reconciliation_policy_version: str
    accounting_carrying_amount_ready: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool
    rollforward: GreenfieldRegularRenewalRollForward | None
    reconciliation: GreenfieldRegularLedgerReconciliation | None


class PostgresGreenfieldRegularLedgerReconciliationRepository:
    def list_previews(
        self,
        *,
        reconciliation_readiness_status: str | None = None,
        renewal_execution_event_id: UUID | None = None,
        old_loan_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[GreenfieldRegularLedgerReconciliationPreview, ...]:
        safe_limit = max(1, min(int(limit), 250))
        normalized_status = (
            reconciliation_readiness_status.strip()
            if reconciliation_readiness_status
            and reconciliation_readiness_status.strip()
            else None
        )
        try:
            with open_connection() as connection:
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute(
                        """
                        select *
                        from accounting.greenfield_regular_renewal_ledger_reconciliation_targets
                        where (%s::text is null or reconciliation_readiness_status = %s::text)
                          and (%s::uuid is null or renewal_execution_event_id = %s::uuid)
                          and (%s::uuid is null or old_loan_id = %s::uuid)
                        order by target_date desc, old_loan_number, renewal_execution_event_id
                        limit %s
                        """,
                        (
                            normalized_status,
                            normalized_status,
                            renewal_execution_event_id,
                            renewal_execution_event_id,
                            old_loan_id,
                            old_loan_id,
                            safe_limit,
                        ),
                    ).fetchall()

                    previews: list[GreenfieldRegularLedgerReconciliationPreview] = []
                    for row in rows:
                        rollforward = None
                        reconciliation = None
                        if (
                            str(row["rollforward_readiness_status"])
                            == "greenfield_regular_renewal_rollforward_target_ready"
                            and bool(row["measurement_preview_enabled"])
                            and row["anchor_date"] is not None
                        ):
                            events = self._load_source_events(
                                cursor,
                                loan_id=row["old_loan_id"],
                                anchor_date=row["anchor_date"],
                                target_date=row["target_date"],
                            )
                            if len(events) > MAX_SOURCE_EVENTS:
                                raise GreenfieldRegularLedgerReconciliationError(
                                    "Greenfield Regular source history exceeded the protected 5,000-event reconciliation limit."
                                )
                            rollforward = build_greenfield_regular_renewal_rollforward(
                                loan_id=row["old_loan_id"],
                                anchor_date=row["anchor_date"],
                                target_date=row["target_date"],
                                contractual_due_date=row["contractual_due_date"],
                                daily_eir=Decimal(row["daily_eir"]),
                                initial_gross_carrying_amount=Decimal(
                                    row["initial_gross_carrying_amount"]
                                ),
                                initial_accrued_interest_component=Decimal(
                                    row["initial_accrued_interest_component"]
                                ),
                                initial_loan_component=Decimal(
                                    row["initial_loan_component"]
                                ),
                                source_events=events,
                            )

                            if rollforward.measurement_preview_ready:
                                periods = self._load_fiscal_periods(
                                    cursor,
                                    anchor_date=row["anchor_date"],
                                    target_date=row["target_date"],
                                )
                                actual = self._load_actual_journals(
                                    cursor,
                                    loan_id=row["old_loan_id"],
                                    client_id=row["client_id"],
                                    anchor_date=row["anchor_date"],
                                    target_date=row["target_date"],
                                )
                                reconciliation = (
                                    build_greenfield_regular_ledger_reconciliation(
                                        rollforward,
                                        fiscal_periods=periods,
                                        actual_journals=actual,
                                        candidate_status=str(
                                            row["reconciliation_readiness_status"]
                                        ),
                                        unprotected_posted_journal_count=int(
                                            row["unprotected_posted_journal_count"] or 0
                                        ),
                                    )
                                )
                        previews.append(
                            self._from_row(
                                row,
                                rollforward=rollforward,
                                reconciliation=reconciliation,
                            )
                        )
            return tuple(previews)
        except GreenfieldRegularLedgerReconciliationError:
            raise
        except psycopg.Error as error:
            message = str(error).split("CONTEXT:", 1)[0].strip()
            raise GreenfieldRegularLedgerReconciliationError(
                message
                or "Greenfield Regular protected-ledger reconciliation could not be loaded."
            ) from error

    @staticmethod
    def _load_source_events(
        cursor,
        *,
        loan_id: UUID,
        anchor_date: date,
        target_date: date,
    ) -> tuple[EirCashSourceEvent, ...]:
        rows = cursor.execute(
            """
            select
                transaction.id as transaction_id,
                transaction.collection_date,
                transaction.accepted_at,
                transaction.entry_type,
                transaction.amount,
                transaction.is_voided
            from lending.collection_transactions transaction
            where transaction.loan_id = %s
              and transaction.collection_date > %s
              and transaction.collection_date < %s
              and transaction.is_voided = false
              and transaction.entry_type in ('payment', 'advance')
              and transaction.amount > 0
            order by transaction.collection_date, transaction.accepted_at, transaction.id
            limit %s
            """,
            (loan_id, anchor_date, target_date, MAX_SOURCE_EVENTS + 1),
        ).fetchall()
        return tuple(
            EirCashSourceEvent(
                transaction_id=UUID(str(row["transaction_id"])),
                collection_date=row["collection_date"],
                accepted_at=row["accepted_at"],
                entry_type=str(row["entry_type"]),
                amount=Decimal(row["amount"]),
                is_voided=bool(row["is_voided"]),
            )
            for row in rows
        )

    @staticmethod
    def _load_fiscal_periods(
        cursor,
        *,
        anchor_date: date,
        target_date: date,
    ) -> tuple[AccountingFiscalPeriodReference, ...]:
        rows = cursor.execute(
            """
            select id, label, start_date, end_date, status
            from accounting.fiscal_periods
            where end_date > %s
              and start_date <= %s
            order by start_date, end_date, id
            """,
            (anchor_date, target_date),
        ).fetchall()
        return tuple(
            AccountingFiscalPeriodReference(
                period_id=UUID(str(row["id"])),
                label=str(row["label"]),
                start_date=row["start_date"],
                end_date=row["end_date"],
                status=str(row["status"]),
            )
            for row in rows
        )

    @staticmethod
    def _load_lines(
        cursor,
        *,
        journal_entry_id: UUID,
    ) -> tuple[GreenfieldRegularActualJournalLine, ...]:
        rows = cursor.execute(
            """
            select
                line.line_number,
                account.system_key as account_system_key,
                line.debit,
                line.credit,
                line.loan_id,
                line.client_id
            from accounting.journal_lines line
            join accounting.accounts account on account.id = line.account_id
            where line.journal_entry_id = %s
            order by line.line_number, line.id
            """,
            (journal_entry_id,),
        ).fetchall()
        return tuple(
            GreenfieldRegularActualJournalLine(
                line_number=int(row["line_number"]),
                account_system_key=str(row["account_system_key"]),
                debit=Decimal(row["debit"] or 0),
                credit=Decimal(row["credit"] or 0),
                loan_id=(
                    UUID(str(row["loan_id"])) if row["loan_id"] is not None else None
                ),
                client_id=(
                    UUID(str(row["client_id"]))
                    if row["client_id"] is not None
                    else None
                ),
            )
            for row in rows
        )

    @staticmethod
    def _reversal_lines_are_exact(
        original: tuple[GreenfieldRegularActualJournalLine, ...],
        reversal: tuple[GreenfieldRegularActualJournalLine, ...],
    ) -> bool:
        if len(original) != len(reversal) or not original:
            return False
        expected = sorted(
            (
                line.account_system_key,
                line.loan_id,
                line.client_id,
                Decimal(line.credit),
                Decimal(line.debit),
            )
            for line in original
        )
        observed = sorted(
            (
                line.account_system_key,
                line.loan_id,
                line.client_id,
                Decimal(line.debit),
                Decimal(line.credit),
            )
            for line in reversal
        )
        return observed == expected

    @classmethod
    def _load_actual_journals(
        cls,
        cursor,
        *,
        loan_id: UUID,
        client_id: UUID,
        anchor_date: date,
        target_date: date,
    ) -> tuple[GreenfieldRegularActualProtectedJournal, ...]:
        rows = cursor.execute(
            """
            select
                preparation.transaction_id,
                transaction.is_voided as transaction_is_voided,
                prepared_entry.sequence_order,
                prepared_entry.entry_type,
                journal.id as journal_entry_id,
                journal.status as journal_status,
                journal.source_type,
                journal.source_reference,
                journal.source_event_key,
                journal.posting_date,
                journal.fiscal_period_id,
                journal.entry_number,
                posted.posting_set_id,
                posted.entry_number as audit_entry_number,
                posted.source_event_key as audit_source_event_key,
                posting_set.loan_id as audit_loan_id,
                reversal_set.id as reversal_set_id,
                reversal_set.transaction_id as reversal_transaction_id,
                reversal_set.expected_entry_count as reversal_expected_entry_count,
                reversal_set.reversed_entry_count,
                reversal_entry.reversal_journal_entry_id,
                reversal_entry.original_entry_number,
                reversal_entry.reversal_entry_number,
                reversal_entry.original_source_event_key,
                reversal_entry.reversal_source_event_key,
                reversal_journal.status as reversal_journal_status,
                reversal_journal.source_type as reversal_journal_source_type,
                reversal_journal.source_event_key as reversal_journal_source_event_key,
                reversal_journal.reversal_of_entry_id
            from accounting.regular_journal_draft_preparations preparation
            join lending.collection_transactions transaction
              on transaction.id = preparation.transaction_id
            join accounting.regular_journal_draft_preparation_entries prepared_entry
              on prepared_entry.preparation_id = preparation.id
            join accounting.regular_journal_posting_entries posted
              on posted.preparation_id = preparation.id
             and posted.sequence_order = prepared_entry.sequence_order
             and posted.journal_entry_id = prepared_entry.journal_entry_id
            join accounting.regular_journal_posting_sets posting_set
              on posting_set.id = posted.posting_set_id
            join accounting.journal_entries journal
              on journal.id = prepared_entry.journal_entry_id
            left join accounting.regular_journal_reversal_entries reversal_entry
              on reversal_entry.original_journal_entry_id = journal.id
            left join accounting.regular_journal_reversal_sets reversal_set
              on reversal_set.id = reversal_entry.reversal_set_id
            left join accounting.journal_entries reversal_journal
              on reversal_journal.id = reversal_entry.reversal_journal_entry_id
            where preparation.loan_id = %s
              and transaction.collection_date > %s
              and transaction.collection_date < %s
            order by transaction.collection_date, preparation.transaction_id,
                     prepared_entry.sequence_order
            """,
            (loan_id, anchor_date, target_date),
        ).fetchall()

        result: list[GreenfieldRegularActualProtectedJournal] = []
        for row in rows:
            journal_entry_id = UUID(str(row["journal_entry_id"]))
            lines = cls._load_lines(cursor, journal_entry_id=journal_entry_id)
            line_dimensions_exact = bool(lines) and all(
                line.loan_id == loan_id and line.client_id == client_id
                for line in lines
            )
            posting_audit_exact = (
                UUID(str(row["audit_loan_id"])) == loan_id
                and row["journal_status"] == "posted"
                and row["entry_number"] is not None
                and row["entry_number"] == row["audit_entry_number"]
                and row["source_event_key"] == row["audit_source_event_key"]
                and line_dimensions_exact
            )

            reversal_id = row["reversal_journal_entry_id"]
            reversal_present = reversal_id is not None
            reversal_exact = False
            if reversal_present:
                reversal_journal_id = UUID(str(reversal_id))
                reversal_lines = cls._load_lines(
                    cursor,
                    journal_entry_id=reversal_journal_id,
                )
                reversal_exact = (
                    row["reversal_set_id"] is not None
                    and row["reversal_transaction_id"] == row["transaction_id"]
                    and int(row["reversal_expected_entry_count"] or 0) > 0
                    and int(row["reversed_entry_count"] or 0)
                    == int(row["reversal_expected_entry_count"] or 0)
                    and row["original_entry_number"] == row["entry_number"]
                    and row["original_source_event_key"] == row["source_event_key"]
                    and row["reversal_entry_number"] is not None
                    and row["reversal_journal_status"] == "posted"
                    and row["reversal_journal_source_type"]
                    == "regular_collection_void_reversal"
                    and row["reversal_journal_source_event_key"]
                    == row["reversal_source_event_key"]
                    and row["reversal_of_entry_id"] == row["journal_entry_id"]
                    and cls._reversal_lines_are_exact(lines, reversal_lines)
                )

            result.append(
                GreenfieldRegularActualProtectedJournal(
                    transaction_id=UUID(str(row["transaction_id"])),
                    transaction_is_voided=bool(row["transaction_is_voided"]),
                    sequence_order=int(row["sequence_order"]),
                    entry_type=str(row["entry_type"]),
                    source_type=str(row["source_type"]),
                    source_reference=str(row["source_reference"]),
                    source_event_key=str(row["source_event_key"]),
                    posting_date=row["posting_date"],
                    fiscal_period_id=UUID(str(row["fiscal_period_id"])),
                    journal_status=str(row["journal_status"]),
                    posting_audit_exact=posting_audit_exact,
                    lines=lines,
                    reversal_present=reversal_present,
                    reversal_exact=reversal_exact,
                )
            )
        return tuple(result)

    @staticmethod
    def _from_row(
        row,
        *,
        rollforward: GreenfieldRegularRenewalRollForward | None,
        reconciliation: GreenfieldRegularLedgerReconciliation | None,
    ) -> GreenfieldRegularLedgerReconciliationPreview:
        return GreenfieldRegularLedgerReconciliationPreview(
            renewal_execution_event_id=row["renewal_execution_event_id"],
            renewal_disbursement_event_id=row["renewal_disbursement_event_id"],
            old_loan_id=row["old_loan_id"],
            old_loan_number=str(row["old_loan_number"]),
            new_loan_id=row["new_loan_id"],
            new_loan_number=str(row["new_loan_number"]),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            target_date=row["target_date"],
            executed_at=row["executed_at"],
            old_loan_settlement_amount=Decimal(row["old_loan_settlement_amount"]),
            anchor_posting_id=row["anchor_posting_id"],
            anchor_journal_entry_id=row["anchor_journal_entry_id"],
            anchor_entry_number=(
                str(row["anchor_entry_number"])
                if row["anchor_entry_number"]
                else None
            ),
            anchor_date=row["anchor_date"],
            initial_gross_carrying_amount=(
                Decimal(row["initial_gross_carrying_amount"])
                if row["initial_gross_carrying_amount"] is not None
                else None
            ),
            initial_loan_component=(
                Decimal(row["initial_loan_component"])
                if row["initial_loan_component"] is not None
                else None
            ),
            initial_accrued_interest_component=(
                Decimal(row["initial_accrued_interest_component"])
                if row["initial_accrued_interest_component"] is not None
                else None
            ),
            daily_eir=(
                Decimal(row["daily_eir"])
                if row["daily_eir"] is not None
                else None
            ),
            contractual_due_date=row["contractual_due_date"],
            rollforward_readiness_status=str(row["rollforward_readiness_status"]),
            active_source_count=int(row["active_source_count"] or 0),
            protected_complete_active_source_count=int(
                row["protected_complete_active_source_count"] or 0
            ),
            voided_posted_source_count=int(row["voided_posted_source_count"] or 0),
            voided_unreversed_source_count=int(
                row["voided_unreversed_source_count"] or 0
            ),
            unprotected_posted_journal_count=int(
                row["unprotected_posted_journal_count"] or 0
            ),
            reconciliation_readiness_status=str(
                row["reconciliation_readiness_status"]
            ),
            exact_reconciliation_preview_enabled=bool(
                row["exact_reconciliation_preview_enabled"]
            ),
            reconciliation_policy_version=str(row["reconciliation_policy_version"]),
            accounting_carrying_amount_ready=(
                reconciliation.accounting_carrying_amount_ready
                if reconciliation is not None
                else False
            ),
            journal_lines_enabled=False,
            automatic_source_posting=False,
            rollforward=rollforward,
            reconciliation=reconciliation,
        )
