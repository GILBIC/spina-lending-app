from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .renewal_treatment_readiness_repository import (
    PostgresRenewalTreatmentReadinessRepository,
    RenewalTreatmentReadinessError,
)


DECISION_POLICY_VERSION = "renewal_treatment_decision_evidence_v1"
SUPPORTED_DECISIONS = {
    "modification_no_derecognition",
    "derecognition",
}


@dataclass(frozen=True, slots=True)
class RenewalTreatmentDecisionRecord:
    decision_id: UUID
    renewal_execution_event_id: UUID
    old_loan_id: UUID
    old_loan_number: str
    new_loan_id: UUID
    new_loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    renewal_business_date: date
    readiness_review_token: str
    readiness_policy_version: str
    decision: str
    decision_policy_version: str
    accounting_policy_reference: str
    qualitative_assessment: dict[str, Any]
    decision_rationale: str
    supporting_evidence_reference: str
    old_gross_carrying_amount: Decimal
    original_daily_eir: Decimal
    renewal_cash_disbursed_amount: Decimal
    renewal_settlement_amount: Decimal
    renewal_other_deduction_amount: Decimal
    schedule_id: UUID
    schedule_version: int
    contract_reference: str
    contract_evidence_reference: str
    installment_count: int
    contractual_cash_total: Decimal
    present_value_at_original_eir: Decimal
    present_value_change_amount: Decimal
    present_value_change_percent: Decimal
    reviewed_by_user_id: UUID
    reviewed_at: datetime
    void_id: UUID | None
    void_reason: str | None
    voided_by_user_id: UUID | None
    voided_at: datetime | None
    is_active: bool
    automatic_classification_enabled: bool
    quantitative_threshold_decisive: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool


class RenewalTreatmentDecisionError(RuntimeError):
    code = "renewal_treatment_decision_error"


class RenewalTreatmentDecisionNotFound(RenewalTreatmentDecisionError):
    code = "renewal_treatment_decision_not_found"


class RenewalTreatmentDecisionConflict(RenewalTreatmentDecisionError):
    code = "renewal_treatment_decision_conflict"


class PostgresRenewalTreatmentDecisionRepository:
    def __init__(
        self,
        *,
        readiness_repository: PostgresRenewalTreatmentReadinessRepository | None = None,
    ) -> None:
        self._readiness_repository = (
            readiness_repository or PostgresRenewalTreatmentReadinessRepository()
        )

    def get_for_execution(
        self,
        *,
        renewal_execution_event_id: UUID,
        active_only: bool = False,
    ) -> tuple[RenewalTreatmentDecisionRecord, ...]:
        try:
            with open_connection() as connection:
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute(
                        """
                        select *
                        from accounting.renewal_treatment_decision_status
                        where renewal_execution_event_id = %s
                          and (%s = false or is_active = true)
                        order by reviewed_at desc, decision_id desc
                        """,
                        (renewal_execution_event_id, active_only),
                    ).fetchall()
                    return tuple(self._from_row(row) for row in rows)
        except psycopg.Error as error:
            raise self._database_error(error) from error

    def record(
        self,
        *,
        renewal_execution_event_id: UUID,
        actor_user_id: UUID,
        expected_review_token: str,
        decision: str,
        accounting_policy_reference: str,
        qualitative_assessment: dict[str, Any],
        decision_rationale: str,
        supporting_evidence_reference: str,
    ) -> RenewalTreatmentDecisionRecord:
        normalized_decision = decision.strip()
        if normalized_decision not in SUPPORTED_DECISIONS:
            raise RenewalTreatmentDecisionConflict(
                "Choose an explicit modification_no_derecognition or derecognition decision."
            )
        if len(expected_review_token.strip()) != 64:
            raise RenewalTreatmentDecisionConflict(
                "The exact current renewal treatment-readiness review token is required."
            )
        if not qualitative_assessment:
            raise RenewalTreatmentDecisionConflict(
                "A non-empty qualitative accounting assessment is required."
            )

        try:
            readiness_record = self._readiness_repository.load(
                renewal_execution_event_id=renewal_execution_event_id,
            )
        except RenewalTreatmentReadinessError as error:
            raise RenewalTreatmentDecisionConflict(str(error)) from error

        readiness = readiness_record.readiness
        source = readiness_record.source
        if readiness.disposition != "renewal_accounting_treatment_review_ready":
            raise RenewalTreatmentDecisionConflict(
                readiness.message
                or "Renewal treatment evidence is not ready for a reviewed decision."
            )
        if readiness_record.review_token != expected_review_token:
            raise RenewalTreatmentDecisionConflict(
                "Renewal treatment-readiness evidence changed after review. Refresh the evidence and review the current token before recording a decision."
            )
        if (
            readiness.old_gross_carrying_amount is None
            or readiness.original_daily_eir is None
            or readiness.schedule_id is None
            or readiness.schedule_version is None
            or readiness.contract_reference is None
            or readiness.evidence_reference is None
            or readiness.contractual_cash_total is None
            or readiness.present_value_at_original_eir is None
            or readiness.present_value_change_amount is None
            or readiness.present_value_change_percent is None
            or readiness.installment_count <= 0
        ):
            raise RenewalTreatmentDecisionConflict(
                "Renewal treatment readiness is missing a required authoritative measurement snapshot."
            )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    decision_id = cursor.execute(
                        """
                        select accounting.record_renewal_treatment_decision(
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s::jsonb, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            renewal_execution_event_id,
                            source.old_loan_id,
                            source.new_loan_id,
                            source.client_id,
                            source.target_date,
                            expected_review_token,
                            readiness.policy_version,
                            normalized_decision,
                            DECISION_POLICY_VERSION,
                            accounting_policy_reference.strip(),
                            Jsonb(qualitative_assessment),
                            decision_rationale.strip(),
                            supporting_evidence_reference.strip(),
                            readiness.old_gross_carrying_amount,
                            readiness.original_daily_eir,
                            readiness.renewal_cash_disbursed_amount,
                            readiness.renewal_settlement_amount,
                            readiness.renewal_other_deduction_amount,
                            readiness.schedule_id,
                            readiness.schedule_version,
                            readiness.contract_reference,
                            readiness.evidence_reference,
                            readiness.installment_count,
                            readiness.contractual_cash_total,
                            readiness.present_value_at_original_eir,
                            readiness.present_value_change_amount,
                            readiness.present_value_change_percent,
                            actor_user_id,
                        ),
                    ).fetchone()[0]
                    row = cursor.execute(
                        """
                        select *
                        from accounting.renewal_treatment_decision_status
                        where decision_id = %s
                        """,
                        (decision_id,),
                    ).fetchone()
                    if row is None:
                        raise RenewalTreatmentDecisionError(
                            "Recorded renewal treatment decision could not be reloaded."
                        )
                    return self._from_row(row)
        except RenewalTreatmentDecisionError:
            raise
        except psycopg.Error as error:
            raise self._database_error(error) from error

    def void(
        self,
        *,
        decision_id: UUID,
        actor_user_id: UUID,
        reason: str,
    ) -> RenewalTreatmentDecisionRecord:
        normalized_reason = reason.strip()
        if len(normalized_reason) < 3:
            raise RenewalTreatmentDecisionConflict(
                "Enter a clear reason for voiding renewal treatment decision evidence."
            )
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select accounting.void_renewal_treatment_decision(%s, %s, %s)",
                        (decision_id, actor_user_id, normalized_reason),
                    ).fetchone()
                    row = cursor.execute(
                        """
                        select *
                        from accounting.renewal_treatment_decision_status
                        where decision_id = %s
                        """,
                        (decision_id,),
                    ).fetchone()
                    if row is None:
                        raise RenewalTreatmentDecisionNotFound(
                            "Renewal treatment decision evidence was not found."
                        )
                    return self._from_row(row)
        except RenewalTreatmentDecisionError:
            raise
        except psycopg.Error as error:
            raise self._database_error(error) from error

    @staticmethod
    def _database_error(error: psycopg.Error) -> RenewalTreatmentDecisionError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "not found" in lowered:
            return RenewalTreatmentDecisionNotFound(message)
        if any(
            token in lowered
            for token in (
                "already",
                "requires",
                "required",
                "unsupported",
                "choose",
                "different active",
                "void",
                "match",
                "mismatch",
            )
        ):
            return RenewalTreatmentDecisionConflict(message)
        return RenewalTreatmentDecisionError(
            message or "Renewal treatment decision evidence operation failed."
        )

    @staticmethod
    def _from_row(row) -> RenewalTreatmentDecisionRecord:
        return RenewalTreatmentDecisionRecord(
            decision_id=UUID(str(row["decision_id"])),
            renewal_execution_event_id=UUID(str(row["renewal_execution_event_id"])),
            old_loan_id=UUID(str(row["old_loan_id"])),
            old_loan_number=str(row["old_loan_number"]),
            new_loan_id=UUID(str(row["new_loan_id"])),
            new_loan_number=str(row["new_loan_number"]),
            client_id=UUID(str(row["client_id"])),
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            renewal_business_date=row["renewal_business_date"],
            readiness_review_token=str(row["readiness_review_token"]),
            readiness_policy_version=str(row["readiness_policy_version"]),
            decision=str(row["decision"]),
            decision_policy_version=str(row["decision_policy_version"]),
            accounting_policy_reference=str(row["accounting_policy_reference"]),
            qualitative_assessment=dict(row["qualitative_assessment"]),
            decision_rationale=str(row["decision_rationale"]),
            supporting_evidence_reference=str(row["supporting_evidence_reference"]),
            old_gross_carrying_amount=Decimal(row["old_gross_carrying_amount"]),
            original_daily_eir=Decimal(row["original_daily_eir"]),
            renewal_cash_disbursed_amount=Decimal(
                row["renewal_cash_disbursed_amount"]
            ),
            renewal_settlement_amount=Decimal(row["renewal_settlement_amount"]),
            renewal_other_deduction_amount=Decimal(
                row["renewal_other_deduction_amount"]
            ),
            schedule_id=UUID(str(row["schedule_id"])),
            schedule_version=int(row["schedule_version"]),
            contract_reference=str(row["contract_reference"]),
            contract_evidence_reference=str(row["contract_evidence_reference"]),
            installment_count=int(row["installment_count"]),
            contractual_cash_total=Decimal(row["contractual_cash_total"]),
            present_value_at_original_eir=Decimal(
                row["present_value_at_original_eir"]
            ),
            present_value_change_amount=Decimal(row["present_value_change_amount"]),
            present_value_change_percent=Decimal(
                row["present_value_change_percent"]
            ),
            reviewed_by_user_id=UUID(str(row["reviewed_by_user_id"])),
            reviewed_at=row["reviewed_at"],
            void_id=(None if row["void_id"] is None else UUID(str(row["void_id"]))),
            void_reason=(None if row["void_reason"] is None else str(row["void_reason"])),
            voided_by_user_id=(
                None
                if row["voided_by_user_id"] is None
                else UUID(str(row["voided_by_user_id"]))
            ),
            voided_at=row["voided_at"],
            is_active=bool(row["is_active"]),
            automatic_classification_enabled=bool(
                row["automatic_classification_enabled"]
            ),
            quantitative_threshold_decisive=bool(
                row["quantitative_threshold_decisive"]
            ),
            journal_lines_enabled=bool(row["journal_lines_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )
