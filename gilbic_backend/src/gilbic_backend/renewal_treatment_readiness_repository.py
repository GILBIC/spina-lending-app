from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection
from .greenfield_regular_renewal_final_reconciliation_repository import (
    GreenfieldRegularRenewalFinalReconciliationError,
    PostgresGreenfieldRegularRenewalFinalReconciliationRepository,
)
from .renewal_treatment_readiness import (
    RenewalTreatmentEvidence,
    RenewalTreatmentInstallment,
    RenewalTreatmentReadiness,
    build_renewal_treatment_readiness,
)


class RenewalTreatmentReadinessError(RuntimeError):
    code = "renewal_treatment_readiness_error"


class RenewalTreatmentReadinessNotFound(RenewalTreatmentReadinessError):
    code = "renewal_treatment_readiness_not_found"


class PostgresRenewalTreatmentReadinessRepository:
    def __init__(
        self,
        *,
        final_reconciliation_repository: PostgresGreenfieldRegularRenewalFinalReconciliationRepository
        | None = None,
    ) -> None:
        self._final_reconciliation_repository = (
            final_reconciliation_repository
            or PostgresGreenfieldRegularRenewalFinalReconciliationRepository()
        )

    def load(
        self,
        *,
        renewal_execution_event_id: UUID,
    ) -> RenewalTreatmentReadiness:
        try:
            final_record = self._final_reconciliation_repository.load(
                renewal_execution_event_id=renewal_execution_event_id,
            )
        except GreenfieldRegularRenewalFinalReconciliationError as error:
            raise RenewalTreatmentReadinessNotFound(str(error)) from error

        try:
            with open_connection() as connection:
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                with connection.cursor(row_factory=dict_row) as cursor:
                    source = self._load_source(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    installments = self._load_installments(
                        cursor,
                        schedule_id=source.get("schedule_id"),
                    )
        except RenewalTreatmentReadinessError:
            raise
        except psycopg.Error as error:
            message = str(error).split("CONTEXT:", 1)[0].strip()
            raise RenewalTreatmentReadinessError(
                message or "Renewal treatment-readiness evidence could not be loaded."
            ) from error

        final_source = final_record.source
        if (
            final_source.old_loan_id != source["old_loan_id"]
            or final_source.new_loan_id != source["new_loan_id"]
            or final_source.client_id != source["client_id"]
            or final_source.target_date != source["business_date"]
        ):
            raise RenewalTreatmentReadinessError(
                "Protected old-loan reconciliation and renewal execution evidence do not identify the same renewal boundary."
            )

        evidence = RenewalTreatmentEvidence(
            renewal_execution_event_id=renewal_execution_event_id,
            old_loan_id=source["old_loan_id"],
            new_loan_id=source["new_loan_id"],
            client_id=source["client_id"],
            business_date=source["business_date"],
            execution_active=not source["execution_is_voided"],
            release_event_kind=source["release_event_kind"],
            release_business_date=source["release_business_date"],
            release_active=not source["release_is_voided"],
            cash_disbursed_amount=Decimal(source["cash_disbursed_amount"]),
            settlement_amount=Decimal(source["release_settlement_amount"]),
            other_deduction_amount=Decimal(source["other_deduction_amount"]),
            new_loan_calculation_mode=source["new_loan_calculation_mode"],
            accounting_carrying_amount_ready=(
                final_record.final.accounting_carrying_amount_ready
            ),
            old_gross_carrying_amount=(
                final_record.final.final_ledger_gross_carrying_amount
            ),
            original_daily_eir=final_source.daily_eir,
            schedule_id=source.get("schedule_id"),
            schedule_version=source.get("schedule_version"),
            schedule_status=source.get("schedule_status"),
            schedule_effective_from=source.get("schedule_effective_from"),
            payment_frequency=source.get("payment_frequency"),
            contract_reference=source.get("contract_reference"),
            contract_signed_date=source.get("contract_signed_date"),
            registration_id=source.get("registration_id"),
            evidence_basis=source.get("evidence_basis"),
            evidence_reference=source.get("evidence_reference"),
            installments=installments,
        )
        return build_renewal_treatment_readiness(evidence)

    @staticmethod
    def _load_source(cursor, *, renewal_execution_event_id: UUID) -> dict:
        rows = cursor.execute(
            """
            select
                execution.id as renewal_execution_event_id,
                execution.old_loan_id,
                execution.new_loan_id,
                execution.client_id,
                execution.business_date,
                execution.executed_at,
                execution.old_loan_settlement_amount,
                execution.is_voided as execution_is_voided,
                release.id as disbursement_event_id,
                release.event_kind as release_event_kind,
                release.business_date as release_business_date,
                release.is_voided as release_is_voided,
                release.cash_disbursed_amount,
                release.settlement_amount as release_settlement_amount,
                release.other_deduction_amount,
                new_loan.principal as new_loan_principal,
                new_loan.date_released as new_loan_date_released,
                new_loan.status as new_loan_status,
                loan_type.calculation_mode as new_loan_calculation_mode,
                schedule.id as schedule_id,
                schedule.schedule_version,
                schedule.status as schedule_status,
                schedule.payment_frequency,
                schedule.contract_reference,
                schedule.contract_signed_date,
                schedule.effective_from as schedule_effective_from,
                registration.id as registration_id,
                registration.evidence_basis,
                registration.evidence_reference
            from lending.loan_renewal_execution_events execution
            join lending.loan_disbursement_events release
              on release.id = execution.disbursement_event_id
            join lending.loans new_loan
              on new_loan.id = execution.new_loan_id
            join lending.loan_types loan_type
              on loan_type.id = new_loan.loan_type_id
            left join lending.loan_contract_schedules schedule
              on schedule.loan_id = execution.new_loan_id
             and schedule.status = 'active'
            left join lending.loan_contract_schedule_registrations registration
              on registration.schedule_id = schedule.id
            where execution.id = %s
            """,
            (renewal_execution_event_id,),
        ).fetchall()
        if len(rows) != 1:
            raise RenewalTreatmentReadinessNotFound(
                "Exactly one authoritative renewal execution and active schedule boundary is required."
            )
        return dict(rows[0])

    @staticmethod
    def _load_installments(
        cursor,
        *,
        schedule_id: UUID | None,
    ) -> tuple[RenewalTreatmentInstallment, ...]:
        if schedule_id is None:
            return ()
        rows = cursor.execute(
            """
            select installment_number, due_date, contractual_amount
            from lending.loan_contract_installments
            where schedule_id = %s
            order by due_date, installment_number
            """,
            (schedule_id,),
        ).fetchall()
        return tuple(
            RenewalTreatmentInstallment(
                installment_number=int(row["installment_number"]),
                due_date=date.fromisoformat(str(row["due_date"])),
                contractual_amount=Decimal(row["contractual_amount"]),
            )
            for row in rows
        )
