from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


class LoanRenewalExecutionEvidenceError(RuntimeError):
    code = "loan_renewal_execution_evidence_error"


class LoanRenewalExecutionEvidenceNotFound(LoanRenewalExecutionEvidenceError):
    code = "loan_renewal_execution_evidence_not_found"


class LoanRenewalExecutionEvidenceConflict(LoanRenewalExecutionEvidenceError):
    code = "loan_renewal_execution_evidence_conflict"


class LoanRenewalExecutionEvidenceInvalid(LoanRenewalExecutionEvidenceError):
    code = "loan_renewal_execution_evidence_invalid"


@dataclass(frozen=True, slots=True)
class LoanRenewalExecutionEvidenceRecord:
    event_id: UUID
    old_loan_id: UUID
    old_loan_number: str
    new_loan_id: UUID
    new_loan_number: str
    disbursement_event_id: UUID
    client_id: UUID
    client_code: str
    client_name: str
    renewal_request_id: UUID | None
    business_date: date
    executed_at: datetime
    old_loan_settlement_amount: Decimal
    external_reference: str
    evidence_note: str
    old_loan_principal_snapshot: Decimal
    old_loan_date_released_snapshot: date
    old_loan_status_snapshot: str
    new_loan_principal_snapshot: Decimal
    new_loan_date_released_snapshot: date
    new_loan_status_snapshot: str
    recorded_by_user_id: UUID
    recorded_at: datetime
    is_voided: bool
    voided_by_user_id: UUID | None
    voided_at: datetime | None
    void_reason: str | None


@dataclass(frozen=True, slots=True)
class LoanRenewalExecutionReadinessRecord:
    disbursement_event_id: UUID
    new_loan_id: UUID
    new_loan_number: str
    renewal_execution_event_id: UUID | None
    old_loan_id: UUID | None
    old_loan_number: str | None
    client_id: UUID
    client_code: str
    client_name: str
    renewal_request_id: UUID | None
    renewal_request_status: str | None
    new_loan_type_code: str
    new_loan_type_name: str
    new_loan_calculation_mode: str
    new_loan_principal: Decimal
    old_loan_principal: Decimal | None
    release_business_date: date
    disbursed_at: datetime
    cash_disbursed_amount: Decimal
    settlement_amount: Decimal
    other_deduction_amount: Decimal
    funding_account_system_key: str
    release_external_reference: str
    execution_business_date: date | None
    executed_at: datetime | None
    old_loan_settlement_amount: Decimal | None
    execution_external_reference: str | None
    readiness_status: str
    source_event_key: str | None
    journal_lines_enabled: bool
    automatic_source_posting: bool


class PostgresLoanRenewalExecutionEvidenceRepository:
    def list_readiness(
        self,
        *,
        readiness_status: str | None = None,
        limit: int = 100,
    ) -> tuple[LoanRenewalExecutionReadinessRecord, ...]:
        safe_limit = max(1, min(int(limit), 250))
        normalized_status = (
            readiness_status.strip() if readiness_status and readiness_status.strip() else None
        )
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute(
                        """
                        select *
                        from accounting.loan_renewal_execution_source_readiness
                        where (%s::text is null or readiness_status = %s::text)
                        order by release_business_date desc, new_loan_number, new_loan_id
                        limit %s
                        """,
                        (normalized_status, normalized_status, safe_limit),
                    ).fetchall()
            return tuple(self._readiness_from_row(row) for row in rows)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def record(
        self,
        *,
        actor_user_id: UUID,
        old_loan_id: UUID,
        new_loan_id: UUID,
        disbursement_event_id: UUID,
        business_date: date,
        executed_at: datetime,
        old_loan_settlement_amount: Decimal,
        external_reference: str,
        evidence_note: str,
        renewal_request_id: UUID | None = None,
    ) -> LoanRenewalExecutionEvidenceRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    event_id = cursor.execute(
                        """
                        select accounting.record_loan_renewal_execution_evidence(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) as event_id
                        """,
                        (
                            old_loan_id,
                            new_loan_id,
                            disbursement_event_id,
                            actor_user_id,
                            business_date,
                            executed_at,
                            old_loan_settlement_amount,
                            external_reference,
                            evidence_note,
                            renewal_request_id,
                        ),
                    ).fetchone()["event_id"]
                    return self._fetch_event(cursor, event_id=event_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def void(
        self,
        *,
        actor_user_id: UUID,
        event_id: UUID,
        reason: str,
    ) -> LoanRenewalExecutionEvidenceRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select accounting.void_loan_renewal_execution_evidence(%s, %s, %s)",
                        (event_id, actor_user_id, reason),
                    )
                    return self._fetch_event(cursor, event_id=event_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @staticmethod
    def _fetch_event(cursor, *, event_id: UUID) -> LoanRenewalExecutionEvidenceRecord:
        row = cursor.execute(
            """
            select
                event.*,
                old_loan.loan_number as old_loan_number,
                new_loan.loan_number as new_loan_number,
                client.client_code,
                client.full_name as client_name
            from lending.loan_renewal_execution_events event
            join lending.loans old_loan on old_loan.id = event.old_loan_id
            join lending.loans new_loan on new_loan.id = event.new_loan_id
            join lending.clients client on client.id = event.client_id
            where event.id = %s
            """,
            (event_id,),
        ).fetchone()
        if row is None:
            raise LoanRenewalExecutionEvidenceNotFound(
                "Renewal execution evidence was not found."
            )
        return LoanRenewalExecutionEvidenceRecord(
            event_id=row["id"],
            old_loan_id=row["old_loan_id"],
            old_loan_number=str(row["old_loan_number"]),
            new_loan_id=row["new_loan_id"],
            new_loan_number=str(row["new_loan_number"]),
            disbursement_event_id=row["disbursement_event_id"],
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            renewal_request_id=row["renewal_request_id"],
            business_date=row["business_date"],
            executed_at=row["executed_at"],
            old_loan_settlement_amount=Decimal(row["old_loan_settlement_amount"]),
            external_reference=str(row["external_reference"]),
            evidence_note=str(row["evidence_note"] or ""),
            old_loan_principal_snapshot=Decimal(row["old_loan_principal_snapshot"]),
            old_loan_date_released_snapshot=row["old_loan_date_released_snapshot"],
            old_loan_status_snapshot=str(row["old_loan_status_snapshot"]),
            new_loan_principal_snapshot=Decimal(row["new_loan_principal_snapshot"]),
            new_loan_date_released_snapshot=row["new_loan_date_released_snapshot"],
            new_loan_status_snapshot=str(row["new_loan_status_snapshot"]),
            recorded_by_user_id=row["recorded_by_user_id"],
            recorded_at=row["recorded_at"],
            is_voided=bool(row["is_voided"]),
            voided_by_user_id=row["voided_by_user_id"],
            voided_at=row["voided_at"],
            void_reason=str(row["void_reason"]) if row["void_reason"] else None,
        )

    @staticmethod
    def _readiness_from_row(row) -> LoanRenewalExecutionReadinessRecord:
        return LoanRenewalExecutionReadinessRecord(
            disbursement_event_id=row["disbursement_event_id"],
            new_loan_id=row["new_loan_id"],
            new_loan_number=str(row["new_loan_number"]),
            renewal_execution_event_id=row["renewal_execution_event_id"],
            old_loan_id=row["old_loan_id"],
            old_loan_number=(
                str(row["old_loan_number"]) if row["old_loan_number"] else None
            ),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            renewal_request_id=row["renewal_request_id"],
            renewal_request_status=(
                str(row["renewal_request_status"])
                if row["renewal_request_status"]
                else None
            ),
            new_loan_type_code=str(row["new_loan_type_code"]),
            new_loan_type_name=str(row["new_loan_type_name"]),
            new_loan_calculation_mode=str(row["new_loan_calculation_mode"]),
            new_loan_principal=Decimal(row["new_loan_principal"]),
            old_loan_principal=(
                Decimal(row["old_loan_principal"])
                if row["old_loan_principal"] is not None
                else None
            ),
            release_business_date=row["release_business_date"],
            disbursed_at=row["disbursed_at"],
            cash_disbursed_amount=Decimal(row["cash_disbursed_amount"]),
            settlement_amount=Decimal(row["settlement_amount"]),
            other_deduction_amount=Decimal(row["other_deduction_amount"]),
            funding_account_system_key=str(row["funding_account_system_key"]),
            release_external_reference=str(row["release_external_reference"]),
            execution_business_date=row["execution_business_date"],
            executed_at=row["executed_at"],
            old_loan_settlement_amount=(
                Decimal(row["old_loan_settlement_amount"])
                if row["old_loan_settlement_amount"] is not None
                else None
            ),
            execution_external_reference=(
                str(row["execution_external_reference"])
                if row["execution_external_reference"]
                else None
            ),
            readiness_status=str(row["readiness_status"]),
            source_event_key=(
                str(row["source_event_key"]) if row["source_event_key"] else None
            ),
            journal_lines_enabled=bool(row["journal_lines_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> LoanRenewalExecutionEvidenceError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lower = message.lower()
        if "not found" in lower:
            return LoanRenewalExecutionEvidenceNotFound(message)
        if (
            "already" in lower
            or "different active" in lower
            or "journal history" in lower
            or "cannot" in lower
            or "used by another" in lower
        ):
            return LoanRenewalExecutionEvidenceConflict(message)
        return LoanRenewalExecutionEvidenceInvalid(
            message or "Renewal execution evidence failed validation."
        )
