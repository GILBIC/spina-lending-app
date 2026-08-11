from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


class LoanDisbursementEvidenceError(RuntimeError):
    code = "loan_disbursement_evidence_error"


class LoanDisbursementEvidenceNotFound(LoanDisbursementEvidenceError):
    code = "loan_disbursement_evidence_not_found"


class LoanDisbursementEvidenceConflict(LoanDisbursementEvidenceError):
    code = "loan_disbursement_evidence_conflict"


class LoanDisbursementEvidenceInvalid(LoanDisbursementEvidenceError):
    code = "loan_disbursement_evidence_invalid"


@dataclass(frozen=True, slots=True)
class LoanDisbursementEvidenceRecord:
    event_id: UUID
    loan_id: UUID
    loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    event_kind: str
    business_date: date
    disbursed_at: datetime
    cash_disbursed_amount: Decimal
    settlement_amount: Decimal
    other_deduction_amount: Decimal
    funding_account_system_key: str
    external_reference: str
    evidence_note: str
    principal_snapshot: Decimal
    date_released_snapshot: date
    loan_status_snapshot: str
    recorded_by_user_id: UUID
    recorded_at: datetime
    is_voided: bool
    voided_by_user_id: UUID | None
    voided_at: datetime | None
    void_reason: str | None


@dataclass(frozen=True, slots=True)
class LoanDisbursementReadinessRecord:
    loan_id: UUID
    loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    loan_type_code: str
    loan_type_name: str
    calculation_mode: str
    principal: Decimal
    date_released: date
    loan_status: str
    disbursement_event_id: UUID | None
    event_kind: str | None
    business_date: date | None
    disbursed_at: datetime | None
    cash_disbursed_amount: Decimal | None
    settlement_amount: Decimal | None
    other_deduction_amount: Decimal | None
    funding_account_system_key: str | None
    external_reference: str | None
    readiness_status: str
    source_event_key: str | None
    journal_lines_enabled: bool
    automatic_source_posting: bool


class PostgresLoanDisbursementEvidenceRepository:
    def list_readiness(
        self,
        *,
        readiness_status: str | None = None,
        limit: int = 100,
    ) -> tuple[LoanDisbursementReadinessRecord, ...]:
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
                        from accounting.loan_disbursement_source_readiness
                        where (%s::text is null or readiness_status = %s::text)
                        order by date_released desc, loan_number, loan_id
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
        loan_id: UUID,
        event_kind: str,
        business_date: date,
        disbursed_at: datetime,
        cash_disbursed_amount: Decimal,
        settlement_amount: Decimal,
        other_deduction_amount: Decimal,
        funding_account_system_key: str,
        external_reference: str,
        evidence_note: str,
    ) -> LoanDisbursementEvidenceRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    event_id = cursor.execute(
                        """
                        select accounting.record_loan_disbursement_evidence(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) as event_id
                        """,
                        (
                            loan_id,
                            actor_user_id,
                            event_kind,
                            business_date,
                            disbursed_at,
                            cash_disbursed_amount,
                            settlement_amount,
                            other_deduction_amount,
                            funding_account_system_key,
                            external_reference,
                            evidence_note,
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
    ) -> LoanDisbursementEvidenceRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select accounting.void_loan_disbursement_evidence(%s, %s, %s)",
                        (event_id, actor_user_id, reason),
                    )
                    return self._fetch_event(cursor, event_id=event_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @staticmethod
    def _fetch_event(cursor, *, event_id: UUID) -> LoanDisbursementEvidenceRecord:
        row = cursor.execute(
            """
            select
                event.*,
                loan.loan_number,
                client.client_code,
                client.full_name as client_name
            from lending.loan_disbursement_events event
            join lending.loans loan on loan.id = event.loan_id
            join lending.clients client on client.id = event.client_id
            where event.id = %s
            """,
            (event_id,),
        ).fetchone()
        if row is None:
            raise LoanDisbursementEvidenceNotFound(
                "Loan disbursement evidence was not found."
            )
        return LoanDisbursementEvidenceRecord(
            event_id=row["id"],
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            event_kind=str(row["event_kind"]),
            business_date=row["business_date"],
            disbursed_at=row["disbursed_at"],
            cash_disbursed_amount=Decimal(row["cash_disbursed_amount"]),
            settlement_amount=Decimal(row["settlement_amount"]),
            other_deduction_amount=Decimal(row["other_deduction_amount"]),
            funding_account_system_key=str(row["funding_account_system_key"]),
            external_reference=str(row["external_reference"]),
            evidence_note=str(row["evidence_note"] or ""),
            principal_snapshot=Decimal(row["principal_snapshot"]),
            date_released_snapshot=row["date_released_snapshot"],
            loan_status_snapshot=str(row["loan_status_snapshot"]),
            recorded_by_user_id=row["recorded_by_user_id"],
            recorded_at=row["recorded_at"],
            is_voided=bool(row["is_voided"]),
            voided_by_user_id=row["voided_by_user_id"],
            voided_at=row["voided_at"],
            void_reason=str(row["void_reason"]) if row["void_reason"] else None,
        )

    @staticmethod
    def _readiness_from_row(row) -> LoanDisbursementReadinessRecord:
        return LoanDisbursementReadinessRecord(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            loan_type_code=str(row["loan_type_code"]),
            loan_type_name=str(row["loan_type_name"]),
            calculation_mode=str(row["calculation_mode"]),
            principal=Decimal(row["principal"]),
            date_released=row["date_released"],
            loan_status=str(row["loan_status"]),
            disbursement_event_id=row["disbursement_event_id"],
            event_kind=str(row["event_kind"]) if row["event_kind"] else None,
            business_date=row["business_date"],
            disbursed_at=row["disbursed_at"],
            cash_disbursed_amount=(
                Decimal(row["cash_disbursed_amount"])
                if row["cash_disbursed_amount"] is not None
                else None
            ),
            settlement_amount=(
                Decimal(row["settlement_amount"])
                if row["settlement_amount"] is not None
                else None
            ),
            other_deduction_amount=(
                Decimal(row["other_deduction_amount"])
                if row["other_deduction_amount"] is not None
                else None
            ),
            funding_account_system_key=(
                str(row["funding_account_system_key"])
                if row["funding_account_system_key"]
                else None
            ),
            external_reference=(
                str(row["external_reference"])
                if row["external_reference"]
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
    def _map_error(error: psycopg.Error) -> LoanDisbursementEvidenceError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lower = message.lower()
        if "not found" in lower:
            return LoanDisbursementEvidenceNotFound(message)
        if (
            "already" in lower
            or "different active" in lower
            or "journal history" in lower
            or "cannot" in lower
        ):
            return LoanDisbursementEvidenceConflict(message)
        return LoanDisbursementEvidenceInvalid(message or "Loan disbursement evidence failed validation.")
