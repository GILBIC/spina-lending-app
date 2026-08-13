from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class EclCreditRiskLabelSummary:
    loan_count: int
    dpd_ready_count: int
    dpd_data_required_count: int
    label_review_required_count: int
    label_refresh_required_count: int
    current_label_ready_count: int
    stage_1_count: int
    stage_2_count: int
    stage_3_count: int
    default_count: int
    write_off_supported_count: int
    cash_recovery_observed_count: int
    cured_count: int
    quantitative_ecl_ready: bool
    ecl_amount: Decimal | None
    ecl_calculation_enabled: bool
    account_1190_posting_enabled: bool
    automatic_source_posting: bool


@dataclass(frozen=True, slots=True)
class EclCreditRiskLabelLoan:
    loan_id: UUID
    loan_number: str
    loan_status: str
    schedule_id: UUID | None
    schedule_version: int | None
    contract_reference: str | None
    dpd_data_status: str
    days_past_due: int | None
    due_unpaid_amount: Decimal
    thirty_day_sicr_backstop_reached: bool
    ninety_day_default_backstop_reached: bool
    current_dpd_risk_band: str | None
    review_id: int | None
    review_version: int | None
    stage_label: str | None
    default_label: bool | None
    write_off_label: str | None
    recovery_label: str | None
    primary_evidence_basis: str | None
    evidence_reference: str | None
    review_note: str | None
    sicr_backstop_rebutted: bool | None
    default_backstop_rebutted: bool | None
    rebuttal_evidence_reference: str | None
    rebuttal_note: str | None
    write_off_evidence_reference: str | None
    write_off_note: str | None
    recovery_transaction_id: UUID | None
    reviewer_name: str | None
    reviewed_at: datetime | None
    current_label_ready: bool
    label_review_status: str
    quantitative_ecl_ready: bool
    ecl_calculation_enabled: bool
    account_1190_posting_enabled: bool
    automatic_source_posting: bool


@dataclass(frozen=True, slots=True)
class EclQuantitativeInputReadinessSummary:
    loan_count: int
    quantitative_input_ready_count: int
    contractual_schedule_dpd_blocked_count: int
    credit_risk_label_blocked_count: int
    original_eir_initial_carrying_blocked_count: int
    protected_history_blocked_count: int
    current_carrying_blocked_count: int
    outcome_evidence_blocked_count: int
    forward_looking_evidence_blocked_count: int
    quantitative_ecl_ready: bool
    ecl_amount: Decimal | None
    ecl_calculation_enabled: bool
    account_1190_posting_enabled: bool
    automatic_source_posting: bool


@dataclass(frozen=True, slots=True)
class EclQuantitativeInputReadinessLoan:
    loan_id: UUID
    loan_number: str
    loan_status: str
    loan_type_code: str
    loan_type_name: str
    calculation_mode: str
    schedule_id: UUID | None
    schedule_version: int | None
    contract_reference: str | None
    dpd_data_status: str
    days_past_due: int | None
    current_dpd_risk_band: str | None
    review_id: int | None
    review_version: int | None
    stage_label: str | None
    default_label: bool | None
    write_off_label: str | None
    recovery_label: str | None
    label_review_status: str
    contractual_schedule_dpd_ready: bool
    current_credit_risk_label_ready: bool
    original_eir_initial_carrying_ready: bool
    protected_collection_posting_reversal_history_ready: bool
    authoritative_current_carrying_ready: bool
    required_loss_recovery_writeoff_outcome_evidence_ready: bool
    approved_forward_looking_evidence_ready: bool
    blocker_codes: tuple[str, ...]
    blockers: tuple[dict[str, object], ...]
    quantitative_input_ready: bool
    ecl_amount: Decimal | None
    ecl_calculation_enabled: bool
    account_1190_posting_enabled: bool
    automatic_source_posting: bool


class EclCreditRiskLabelError(RuntimeError):
    code = "ecl_credit_risk_label_error"


class EclCreditRiskLabelNotFound(EclCreditRiskLabelError):
    code = "ecl_credit_risk_label_not_found"


class EclCreditRiskLabelBlocked(EclCreditRiskLabelError):
    code = "ecl_credit_risk_label_blocked"


class PostgresEclCreditRiskLabelRepository:
    """Read and record protected current-loan ECL labels and input readiness."""

    _LOAN_COLUMNS = """
        loan_id, loan_number, loan_status, schedule_id, schedule_version,
        contract_reference, dpd_data_status, days_past_due, due_unpaid_amount,
        thirty_day_sicr_backstop_reached, ninety_day_default_backstop_reached,
        current_dpd_risk_band, review_id, review_version, stage_label,
        default_label, write_off_label, recovery_label, primary_evidence_basis,
        evidence_reference, review_note, sicr_backstop_rebutted,
        default_backstop_rebutted, rebuttal_evidence_reference, rebuttal_note,
        write_off_evidence_reference, write_off_note, recovery_transaction_id,
        reviewer_name, reviewed_at, current_label_ready, label_review_status,
        quantitative_ecl_ready, ecl_calculation_enabled,
        account_1190_posting_enabled, automatic_source_posting
    """

    _INPUT_READINESS_COLUMNS = """
        loan_id, loan_number, loan_status, loan_type_code, loan_type_name,
        calculation_mode, schedule_id, schedule_version, contract_reference,
        dpd_data_status, days_past_due, current_dpd_risk_band, review_id,
        review_version, stage_label, default_label, write_off_label,
        recovery_label, label_review_status, contractual_schedule_dpd_ready,
        current_credit_risk_label_ready, original_eir_initial_carrying_ready,
        protected_collection_posting_reversal_history_ready,
        authoritative_current_carrying_ready,
        required_loss_recovery_writeoff_outcome_evidence_ready,
        approved_forward_looking_evidence_ready, blocker_codes, blockers,
        quantitative_input_ready, ecl_amount, ecl_calculation_enabled,
        account_1190_posting_enabled, automatic_source_posting
    """

    def load_queue(
        self,
        *,
        review_status: str = "pending",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[EclCreditRiskLabelSummary, tuple[EclCreditRiskLabelLoan, ...]]:
        where_clause = {
            "pending": "label_review_status = 'label_review_required'",
            "stale": "label_review_status = 'label_refresh_required'",
            "dpd_blocked": "label_review_status = 'dpd_data_required'",
            "reviewed": "label_review_status = 'label_reviewed'",
            "all": "true",
        }.get(review_status)
        if where_clause is None:
            raise ValueError("Unsupported ECL credit-risk label status filter.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        loan_count, dpd_ready_count, dpd_data_required_count,
                        label_review_required_count, label_refresh_required_count,
                        current_label_ready_count, stage_1_count, stage_2_count,
                        stage_3_count, default_count, write_off_supported_count,
                        cash_recovery_observed_count, cured_count,
                        quantitative_ecl_ready, ecl_amount, ecl_calculation_enabled,
                        account_1190_posting_enabled, automatic_source_posting
                    FROM accounting.ecl_credit_risk_label_summary
                    """
                )
                summary_row = cursor.fetchone()
                cursor.execute(
                    f"""
                    SELECT {self._LOAN_COLUMNS}
                    FROM accounting.ecl_credit_risk_label_queue
                    WHERE {where_clause}
                    ORDER BY
                        CASE label_review_status
                            WHEN 'label_refresh_required' THEN 0
                            WHEN 'label_review_required' THEN 1
                            WHEN 'dpd_data_required' THEN 2
                            ELSE 3
                        END,
                        days_past_due DESC NULLS LAST,
                        loan_number
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                loans = tuple(self._loan_from_row(row) for row in cursor.fetchall())
        return self._summary_from_row(summary_row), loans

    def load_quantitative_input_readiness(
        self,
        *,
        readiness_status: str = "blocked",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[
        EclQuantitativeInputReadinessSummary,
        tuple[EclQuantitativeInputReadinessLoan, ...],
    ]:
        where_clause = {
            "blocked": "quantitative_input_ready = false",
            "ready": "quantitative_input_ready = true",
            "all": "true",
        }.get(readiness_status)
        if where_clause is None:
            raise ValueError("Unsupported ECL quantitative input-readiness filter.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        loan_count, quantitative_input_ready_count,
                        contractual_schedule_dpd_blocked_count,
                        credit_risk_label_blocked_count,
                        original_eir_initial_carrying_blocked_count,
                        protected_history_blocked_count,
                        current_carrying_blocked_count,
                        outcome_evidence_blocked_count,
                        forward_looking_evidence_blocked_count,
                        quantitative_ecl_ready, ecl_amount,
                        ecl_calculation_enabled, account_1190_posting_enabled,
                        automatic_source_posting
                    FROM accounting.ecl_quantitative_input_readiness_summary
                    """
                )
                summary_row = cursor.fetchone()
                cursor.execute(
                    f"""
                    SELECT {self._INPUT_READINESS_COLUMNS}
                    FROM accounting.ecl_quantitative_input_readiness
                    WHERE {where_clause}
                    ORDER BY cardinality(blocker_codes) DESC, loan_number
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                loans = tuple(
                    self._input_readiness_loan_from_row(row)
                    for row in cursor.fetchall()
                )
        return self._input_readiness_summary_from_row(summary_row), loans

    def review_labels(
        self,
        *,
        loan_id: UUID,
        stage_label: str,
        default_label: bool,
        write_off_label: str,
        recovery_label: str,
        primary_evidence_basis: str,
        evidence_reference: str,
        review_note: str,
        sicr_backstop_rebutted: bool,
        default_backstop_rebutted: bool,
        rebuttal_evidence_reference: str | None,
        rebuttal_note: str | None,
        write_off_evidence_reference: str | None,
        write_off_note: str | None,
        recovery_transaction_id: UUID | None,
        actor_user_id: UUID,
    ) -> EclCreditRiskLabelLoan:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT accounting.review_ecl_credit_risk_labels(
                            %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s
                        ) AS review_id
                        """,
                        (
                            loan_id,
                            stage_label,
                            default_label,
                            write_off_label,
                            recovery_label,
                            primary_evidence_basis,
                            evidence_reference,
                            review_note,
                            sicr_backstop_rebutted,
                            default_backstop_rebutted,
                            rebuttal_evidence_reference,
                            rebuttal_note,
                            write_off_evidence_reference,
                            write_off_note,
                            recovery_transaction_id,
                            actor_user_id,
                        ),
                    )
                    cursor.fetchone()
                    cursor.execute(
                        f"""
                        SELECT {self._LOAN_COLUMNS}
                        FROM accounting.ecl_credit_risk_label_queue
                        WHERE loan_id = %s
                        """,
                        (loan_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise EclCreditRiskLabelNotFound(
                            "Loan was not found after ECL credit-risk label review."
                        )
                    return self._loan_from_row(row)
        except psycopg.Error as error:
            raise self._review_error(error) from error

    @staticmethod
    def _summary_from_row(row) -> EclCreditRiskLabelSummary:
        return EclCreditRiskLabelSummary(
            loan_count=int(row["loan_count"] or 0),
            dpd_ready_count=int(row["dpd_ready_count"] or 0),
            dpd_data_required_count=int(row["dpd_data_required_count"] or 0),
            label_review_required_count=int(row["label_review_required_count"] or 0),
            label_refresh_required_count=int(row["label_refresh_required_count"] or 0),
            current_label_ready_count=int(row["current_label_ready_count"] or 0),
            stage_1_count=int(row["stage_1_count"] or 0),
            stage_2_count=int(row["stage_2_count"] or 0),
            stage_3_count=int(row["stage_3_count"] or 0),
            default_count=int(row["default_count"] or 0),
            write_off_supported_count=int(row["write_off_supported_count"] or 0),
            cash_recovery_observed_count=int(row["cash_recovery_observed_count"] or 0),
            cured_count=int(row["cured_count"] or 0),
            quantitative_ecl_ready=bool(row["quantitative_ecl_ready"]),
            ecl_amount=(Decimal(row["ecl_amount"]) if row["ecl_amount"] is not None else None),
            ecl_calculation_enabled=bool(row["ecl_calculation_enabled"]),
            account_1190_posting_enabled=bool(row["account_1190_posting_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _input_readiness_summary_from_row(row) -> EclQuantitativeInputReadinessSummary:
        return EclQuantitativeInputReadinessSummary(
            loan_count=int(row["loan_count"] or 0),
            quantitative_input_ready_count=int(row["quantitative_input_ready_count"] or 0),
            contractual_schedule_dpd_blocked_count=int(row["contractual_schedule_dpd_blocked_count"] or 0),
            credit_risk_label_blocked_count=int(row["credit_risk_label_blocked_count"] or 0),
            original_eir_initial_carrying_blocked_count=int(row["original_eir_initial_carrying_blocked_count"] or 0),
            protected_history_blocked_count=int(row["protected_history_blocked_count"] or 0),
            current_carrying_blocked_count=int(row["current_carrying_blocked_count"] or 0),
            outcome_evidence_blocked_count=int(row["outcome_evidence_blocked_count"] or 0),
            forward_looking_evidence_blocked_count=int(row["forward_looking_evidence_blocked_count"] or 0),
            quantitative_ecl_ready=bool(row["quantitative_ecl_ready"]),
            ecl_amount=(Decimal(row["ecl_amount"]) if row["ecl_amount"] is not None else None),
            ecl_calculation_enabled=bool(row["ecl_calculation_enabled"]),
            account_1190_posting_enabled=bool(row["account_1190_posting_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _loan_from_row(row) -> EclCreditRiskLabelLoan:
        return EclCreditRiskLabelLoan(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_status=str(row["loan_status"]),
            schedule_id=row["schedule_id"],
            schedule_version=(int(row["schedule_version"]) if row["schedule_version"] is not None else None),
            contract_reference=(str(row["contract_reference"]) if row["contract_reference"] else None),
            dpd_data_status=str(row["dpd_data_status"]),
            days_past_due=(int(row["days_past_due"]) if row["days_past_due"] is not None else None),
            due_unpaid_amount=Decimal(row["due_unpaid_amount"] or 0),
            thirty_day_sicr_backstop_reached=bool(row["thirty_day_sicr_backstop_reached"]),
            ninety_day_default_backstop_reached=bool(row["ninety_day_default_backstop_reached"]),
            current_dpd_risk_band=(str(row["current_dpd_risk_band"]) if row["current_dpd_risk_band"] else None),
            review_id=(int(row["review_id"]) if row["review_id"] is not None else None),
            review_version=(int(row["review_version"]) if row["review_version"] is not None else None),
            stage_label=(str(row["stage_label"]) if row["stage_label"] else None),
            default_label=row["default_label"],
            write_off_label=(str(row["write_off_label"]) if row["write_off_label"] else None),
            recovery_label=(str(row["recovery_label"]) if row["recovery_label"] else None),
            primary_evidence_basis=(str(row["primary_evidence_basis"]) if row["primary_evidence_basis"] else None),
            evidence_reference=(str(row["evidence_reference"]) if row["evidence_reference"] else None),
            review_note=(str(row["review_note"]) if row["review_note"] else None),
            sicr_backstop_rebutted=row["sicr_backstop_rebutted"],
            default_backstop_rebutted=row["default_backstop_rebutted"],
            rebuttal_evidence_reference=(str(row["rebuttal_evidence_reference"]) if row["rebuttal_evidence_reference"] else None),
            rebuttal_note=(str(row["rebuttal_note"]) if row["rebuttal_note"] else None),
            write_off_evidence_reference=(str(row["write_off_evidence_reference"]) if row["write_off_evidence_reference"] else None),
            write_off_note=(str(row["write_off_note"]) if row["write_off_note"] else None),
            recovery_transaction_id=row["recovery_transaction_id"],
            reviewer_name=(str(row["reviewer_name"]) if row["reviewer_name"] else None),
            reviewed_at=row["reviewed_at"],
            current_label_ready=bool(row["current_label_ready"]),
            label_review_status=str(row["label_review_status"]),
            quantitative_ecl_ready=bool(row["quantitative_ecl_ready"]),
            ecl_calculation_enabled=bool(row["ecl_calculation_enabled"]),
            account_1190_posting_enabled=bool(row["account_1190_posting_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _input_readiness_loan_from_row(row) -> EclQuantitativeInputReadinessLoan:
        raw_blockers = row["blockers"] or []
        return EclQuantitativeInputReadinessLoan(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_status=str(row["loan_status"]),
            loan_type_code=str(row["loan_type_code"]),
            loan_type_name=str(row["loan_type_name"]),
            calculation_mode=str(row["calculation_mode"]),
            schedule_id=row["schedule_id"],
            schedule_version=(int(row["schedule_version"]) if row["schedule_version"] is not None else None),
            contract_reference=(str(row["contract_reference"]) if row["contract_reference"] else None),
            dpd_data_status=str(row["dpd_data_status"]),
            days_past_due=(int(row["days_past_due"]) if row["days_past_due"] is not None else None),
            current_dpd_risk_band=(str(row["current_dpd_risk_band"]) if row["current_dpd_risk_band"] else None),
            review_id=(int(row["review_id"]) if row["review_id"] is not None else None),
            review_version=(int(row["review_version"]) if row["review_version"] is not None else None),
            stage_label=(str(row["stage_label"]) if row["stage_label"] else None),
            default_label=row["default_label"],
            write_off_label=(str(row["write_off_label"]) if row["write_off_label"] else None),
            recovery_label=(str(row["recovery_label"]) if row["recovery_label"] else None),
            label_review_status=str(row["label_review_status"]),
            contractual_schedule_dpd_ready=bool(row["contractual_schedule_dpd_ready"]),
            current_credit_risk_label_ready=bool(row["current_credit_risk_label_ready"]),
            original_eir_initial_carrying_ready=bool(row["original_eir_initial_carrying_ready"]),
            protected_collection_posting_reversal_history_ready=bool(row["protected_collection_posting_reversal_history_ready"]),
            authoritative_current_carrying_ready=bool(row["authoritative_current_carrying_ready"]),
            required_loss_recovery_writeoff_outcome_evidence_ready=bool(row["required_loss_recovery_writeoff_outcome_evidence_ready"]),
            approved_forward_looking_evidence_ready=bool(row["approved_forward_looking_evidence_ready"]),
            blocker_codes=tuple(str(value) for value in (row["blocker_codes"] or [])),
            blockers=tuple(dict(value) for value in raw_blockers),
            quantitative_input_ready=bool(row["quantitative_input_ready"]),
            ecl_amount=(Decimal(row["ecl_amount"]) if row["ecl_amount"] is not None else None),
            ecl_calculation_enabled=bool(row["ecl_calculation_enabled"]),
            account_1190_posting_enabled=bool(row["account_1190_posting_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _review_error(error: psycopg.Error) -> EclCreditRiskLabelError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return EclCreditRiskLabelNotFound(message)
        blocked_markers = (
            "must be ready",
            "requires",
            "cannot",
            "supported",
            "rebut",
            "backstop",
            "recovery transaction",
        )
        if any(marker in lowered for marker in blocked_markers):
            return EclCreditRiskLabelBlocked(message)
        return EclCreditRiskLabelError(message or "ECL credit-risk label review failed.")