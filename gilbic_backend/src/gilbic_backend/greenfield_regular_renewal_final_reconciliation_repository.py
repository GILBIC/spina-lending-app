from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection
from .greenfield_regular_ledger_reconciliation import (
    GreenfieldRegularActualJournalLine,
)
from .greenfield_regular_ledger_reconciliation_repository import (
    GreenfieldRegularLedgerReconciliationPreview,
    PostgresGreenfieldRegularLedgerReconciliationRepository,
)
from .greenfield_regular_renewal_final_reconciliation import (
    GreenfieldRegularRenewalBoundaryActualJournal,
    GreenfieldRegularRenewalFinalReconciliation,
    build_greenfield_regular_renewal_final_reconciliation,
)


@dataclass(frozen=True, slots=True)
class GreenfieldRegularRenewalFinalReconciliationRecord:
    source: GreenfieldRegularLedgerReconciliationPreview
    final: GreenfieldRegularRenewalFinalReconciliation


class GreenfieldRegularRenewalFinalReconciliationError(RuntimeError):
    code = "greenfield_regular_renewal_final_reconciliation_error"


class GreenfieldRegularRenewalFinalReconciliationNotFound(
    GreenfieldRegularRenewalFinalReconciliationError
):
    code = "greenfield_regular_renewal_final_reconciliation_not_found"


class PostgresGreenfieldRegularRenewalFinalReconciliationRepository:
    def __init__(
        self,
        *,
        reconciliation_repository: PostgresGreenfieldRegularLedgerReconciliationRepository
        | None = None,
    ) -> None:
        self._reconciliation_repository = (
            reconciliation_repository
            or PostgresGreenfieldRegularLedgerReconciliationRepository()
        )

    def load(
        self,
        *,
        renewal_execution_event_id: UUID,
    ) -> GreenfieldRegularRenewalFinalReconciliationRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._lock_sources(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    records = self._reconciliation_repository.list_previews(
                        renewal_execution_event_id=renewal_execution_event_id,
                        limit=2,
                    )
                    if len(records) != 1:
                        raise GreenfieldRegularRenewalFinalReconciliationNotFound(
                            "Exactly one authoritative greenfield Regular renewal reconciliation record is required."
                        )
                    source = records[0]
                    if source.reconciliation is None:
                        raise GreenfieldRegularRenewalFinalReconciliationNotFound(
                            "Protected source-ledger reconciliation evidence is not available."
                        )
                    actual = self._load_actual_boundary_journals(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                        old_loan_id=source.old_loan_id,
                        client_id=source.client_id,
                    )
                    final = build_greenfield_regular_renewal_final_reconciliation(
                        renewal_execution_event_id=renewal_execution_event_id,
                        old_loan_id=source.old_loan_id,
                        client_id=source.client_id,
                        source_reconciliation=source.reconciliation,
                        boundary_preview=source.renewal_boundary_eir_preview,
                        actual_boundary_journals=actual,
                    )
                    return GreenfieldRegularRenewalFinalReconciliationRecord(
                        source=source,
                        final=final,
                    )
        except GreenfieldRegularRenewalFinalReconciliationError:
            raise
        except psycopg.Error as error:
            message = str(error).split("CONTEXT:", 1)[0].strip()
            raise GreenfieldRegularRenewalFinalReconciliationError(
                message
                or "Final protected Regular renewal reconciliation could not be loaded."
            ) from error

    @staticmethod
    def _lock_sources(cursor, *, renewal_execution_event_id: UUID) -> None:
        cursor.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"renewal-boundary-eir-journal:{renewal_execution_event_id}",),
        )
        cursor.execute(
            """
            LOCK TABLE
                lending.loan_renewal_execution_events,
                lending.loan_disbursement_events,
                lending.loans,
                lending.loan_types,
                lending.clients,
                lending.collection_transactions,
                lending.loan_contract_schedules,
                lending.loan_contract_schedule_registrations,
                lending.loan_contract_installments,
                accounting.loan_disbursement_journal_postings,
                accounting.loan_disbursement_journal_reversals,
                lending.loan_disbursement_cancellations,
                accounting.regular_journal_draft_preparations,
                accounting.regular_journal_draft_preparation_entries,
                accounting.regular_journal_posting_sets,
                accounting.regular_journal_posting_entries,
                accounting.regular_journal_reversal_sets,
                accounting.regular_journal_reversal_entries,
                accounting.journal_entries,
                accounting.journal_lines,
                accounting.fiscal_periods,
                accounting.accounts,
                accounting.renewal_boundary_eir_journal_preparations,
                accounting.renewal_boundary_eir_journal_preparation_entries,
                accounting.renewal_boundary_eir_journal_posting_sets,
                accounting.renewal_boundary_eir_journal_posting_entries
            IN SHARE MODE
            """
        )

    @classmethod
    def _load_actual_boundary_journals(
        cls,
        cursor,
        *,
        renewal_execution_event_id: UUID,
        old_loan_id: UUID,
        client_id: UUID,
    ) -> tuple[GreenfieldRegularRenewalBoundaryActualJournal, ...]:
        rows = cursor.execute(
            """
            select
                prepared_entry.sequence_order,
                prepared_entry.journal_entry_id,
                prepared_entry.fiscal_period_id,
                prepared_entry.posting_date,
                prepared_entry.amount,
                prepared_entry.source_reference,
                prepared_entry.source_event_key,
                journal.status as journal_status,
                journal.entry_number,
                journal.source_type,
                journal.source_reference as journal_source_reference,
                journal.source_event_key as journal_source_event_key,
                journal.posting_date as journal_posting_date,
                journal.fiscal_period_id as journal_fiscal_period_id,
                posting.id as posting_set_id,
                posting.review_token as posting_review_token,
                posting.expected_entry_count,
                posting.posted_entry_count,
                posting.total_debit,
                posting.total_credit,
                posted_entry.entry_number as audit_entry_number,
                posted_entry.source_event_key as audit_source_event_key
            from accounting.renewal_boundary_eir_journal_preparations prepared
            join accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
              on prepared_entry.preparation_id = prepared.id
            join accounting.journal_entries journal
              on journal.id = prepared_entry.journal_entry_id
            left join accounting.renewal_boundary_eir_journal_posting_sets posting
              on posting.preparation_id = prepared.id
            left join accounting.renewal_boundary_eir_journal_posting_entries posted_entry
              on posted_entry.posting_set_id = posting.id
             and posted_entry.preparation_id = prepared.id
             and posted_entry.sequence_order = prepared_entry.sequence_order
             and posted_entry.journal_entry_id = prepared_entry.journal_entry_id
            where prepared.renewal_execution_event_id = %s
              and prepared.old_loan_id = %s
              and prepared.client_id = %s
            order by prepared_entry.sequence_order
            """,
            (renewal_execution_event_id, old_loan_id, client_id),
        ).fetchall()
        result: list[GreenfieldRegularRenewalBoundaryActualJournal] = []
        for row in rows:
            journal_entry_id = UUID(str(row["journal_entry_id"]))
            lines = cls._load_lines(cursor, journal_entry_id=journal_entry_id)
            posting_audit_exact = (
                row["posting_set_id"] is not None
                and row["journal_status"] == "posted"
                and row["entry_number"] is not None
                and row["entry_number"] == row["audit_entry_number"]
                and row["journal_source_event_key"] == row["audit_source_event_key"]
                and row["journal_source_event_key"] == row["source_event_key"]
                and row["journal_source_reference"] == row["source_reference"]
                and row["journal_posting_date"] == row["posting_date"]
                and row["journal_fiscal_period_id"] == row["fiscal_period_id"]
                and int(row["expected_entry_count"] or 0) > 0
                and int(row["posted_entry_count"] or 0)
                == int(row["expected_entry_count"] or 0)
                and row["total_debit"] == row["total_credit"]
            )
            result.append(
                GreenfieldRegularRenewalBoundaryActualJournal(
                    sequence_order=int(row["sequence_order"]),
                    journal_entry_id=journal_entry_id,
                    source_type=str(row["source_type"]),
                    source_reference=str(row["journal_source_reference"]),
                    source_event_key=str(row["journal_source_event_key"]),
                    posting_date=row["journal_posting_date"],
                    fiscal_period_id=UUID(str(row["journal_fiscal_period_id"])),
                    journal_status=str(row["journal_status"]),
                    entry_number=(
                        None if row["entry_number"] is None else str(row["entry_number"])
                    ),
                    posting_audit_exact=posting_audit_exact,
                    lines=lines,
                )
            )
        return tuple(result)

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
                debit=row["debit"],
                credit=row["credit"],
                loan_id=(
                    None if row["loan_id"] is None else UUID(str(row["loan_id"]))
                ),
                client_id=(
                    None if row["client_id"] is None else UUID(str(row["client_id"]))
                ),
            )
            for row in rows
        )