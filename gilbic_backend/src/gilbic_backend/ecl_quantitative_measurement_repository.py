from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class EclQuantitativeMeasurementQueueItem:
    loan_id: UUID
    loan_number: str
    loan_status: str
    loan_type_code: str
    loan_type_name: str
    calculation_mode: str
    schedule_id: UUID | None
    schedule_version: int | None
    contract_reference: str | None
    stage_label: str | None
    review_id: int | None
    review_version: int | None
    blocker_codes: tuple[str, ...]
    blockers: tuple[dict[str, object], ...]
    quantitative_input_ready: bool
    measurement_id: UUID | None
    measurement_version: int | None
    measurement_date: date | None
    loss_horizon: str | None
    calculation_digest: str | None
    measurement_forward_evidence_current: bool
    measurement_status: str
    authoritative_ecl_amount: Decimal | None
    read_only_ecl_calculation_enabled: bool
    account_1190_posting_enabled: bool
    automatic_source_posting: bool


@dataclass(frozen=True, slots=True)
class EclQuantitativeMeasurement:
    id: UUID
    loan_id: UUID
    measurement_version: int
    measurement_date: date
    stage_label: str
    loss_horizon: str
    schedule_id: UUID
    schedule_version: int
    contract_reference: str
    label_review_id: int
    label_review_version: int
    original_eir_source_key: str
    original_eir_policy_version: str
    original_daily_eir: Decimal
    original_initial_gross_carrying_amount: Decimal
    forward_evidence_ids: tuple[UUID, ...]
    input_snapshot: dict[str, object]
    contractual_cash_flow_snapshot: tuple[dict[str, object], ...]
    scenario_snapshot: tuple[dict[str, object], ...]
    scenario_count: int
    probability_total: Decimal
    contractual_cash_flow_pv: Decimal
    weighted_expected_cash_shortfall: Decimal
    ecl_amount: Decimal
    calculation_policy_version: str
    discount_basis: str
    rounding_policy: str
    calculation_digest: str
    review_rationale: str
    reviewed_by_user_id: UUID
    reviewed_at: datetime


class EclQuantitativeMeasurementError(RuntimeError):
    code = "ecl_quantitative_measurement_error"


class EclQuantitativeMeasurementNotFound(EclQuantitativeMeasurementError):
    code = "ecl_quantitative_measurement_not_found"


class EclQuantitativeMeasurementBlocked(EclQuantitativeMeasurementError):
    code = "ecl_quantitative_measurement_blocked"


class PostgresEclQuantitativeMeasurementRepository:
    """Protected Management repository for Master #296 A3 read-only ECL."""

    _QUEUE_COLUMNS = """
        loan_id, loan_number, loan_status, loan_type_code, loan_type_name,
        calculation_mode, schedule_id, schedule_version, contract_reference,
        stage_label, review_id, review_version, blocker_codes, blockers,
        quantitative_input_ready, measurement_id, measurement_version,
        measurement_date, loss_horizon, calculation_digest,
        measurement_forward_evidence_current, measurement_status,
        authoritative_ecl_amount, read_only_ecl_calculation_enabled,
        account_1190_posting_enabled, automatic_source_posting
    """

    _MEASUREMENT_COLUMNS = """
        id, loan_id, measurement_version, measurement_date, stage_label,
        loss_horizon, schedule_id, schedule_version, contract_reference,
        label_review_id, label_review_version, original_eir_source_key,
        original_eir_policy_version, original_daily_eir,
        original_initial_gross_carrying_amount, forward_evidence_ids,
        input_snapshot, contractual_cash_flow_snapshot, scenario_snapshot,
        scenario_count, probability_total, contractual_cash_flow_pv,
        weighted_expected_cash_shortfall, ecl_amount,
        calculation_policy_version, discount_basis, rounding_policy,
        calculation_digest, review_rationale, reviewed_by_user_id, reviewed_at
    """

    def list_queue(
        self,
        *,
        status: str = "all",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[EclQuantitativeMeasurementQueueItem, ...]:
        where_clause = {
            "all": "true",
            "input_blocked": "measurement_status = 'input_blocked'",
            "measurement_required": "measurement_status = 'measurement_required'",
            "new_measurement_required": "measurement_status = 'new_measurement_required'",
            "measured_read_only": "measurement_status = 'measured_read_only'",
            "ready": "quantitative_input_ready = true",
        }.get(status)
        if where_clause is None:
            raise ValueError("Unsupported quantitative ECL measurement status filter.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._QUEUE_COLUMNS}
                    FROM accounting.ecl_quantitative_measurement_queue
                    WHERE {where_clause}
                    ORDER BY loan_number, loan_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(self._queue_from_row(row) for row in cursor.fetchall())

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        loan_count, input_ready_count, input_blocked_count,
                        measurement_required_count, new_measurement_required_count,
                        measured_count, authoritative_ecl_total,
                        read_only_ecl_calculation_enabled,
                        account_1190_posting_enabled, automatic_source_posting
                    FROM accounting.ecl_quantitative_measurement_summary
                    """
                )
                row = cursor.fetchone()
                if row is None:
                    raise EclQuantitativeMeasurementError(
                        "Quantitative ECL measurement summary is unavailable."
                    )
                return dict(row)

    def record_measurement(
        self,
        *,
        loan_id: UUID,
        measurement_date: date,
        scenarios: list[dict[str, object]],
        review_rationale: str,
        actor_user_id: UUID,
    ) -> EclQuantitativeMeasurement:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT accounting.record_read_only_quantitative_ecl_measurement(
                            %s, %s, %s::jsonb, %s, %s
                        ) AS measurement_id
                        """,
                        (
                            loan_id,
                            measurement_date,
                            json.dumps(scenarios, separators=(",", ":"), default=str),
                            review_rationale,
                            actor_user_id,
                        ),
                    )
                    created = cursor.fetchone()
                    measurement_id = created["measurement_id"]
                    cursor.execute(
                        f"""
                        SELECT {self._MEASUREMENT_COLUMNS}
                        FROM accounting.ecl_quantitative_measurements
                        WHERE id = %s
                        """,
                        (measurement_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise EclQuantitativeMeasurementNotFound(
                            "Quantitative ECL measurement was not found after protected calculation."
                        )
                    return self._measurement_from_row(row)
        except psycopg.Error as error:
            raise self._translate_error(error) from error

    @staticmethod
    def _queue_from_row(row) -> EclQuantitativeMeasurementQueueItem:
        return EclQuantitativeMeasurementQueueItem(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_status=str(row["loan_status"]),
            loan_type_code=str(row["loan_type_code"]),
            loan_type_name=str(row["loan_type_name"]),
            calculation_mode=str(row["calculation_mode"]),
            schedule_id=row["schedule_id"],
            schedule_version=(int(row["schedule_version"]) if row["schedule_version"] is not None else None),
            contract_reference=(str(row["contract_reference"]) if row["contract_reference"] else None),
            stage_label=(str(row["stage_label"]) if row["stage_label"] else None),
            review_id=(int(row["review_id"]) if row["review_id"] is not None else None),
            review_version=(int(row["review_version"]) if row["review_version"] is not None else None),
            blocker_codes=tuple(str(code) for code in (row["blocker_codes"] or ())),
            blockers=tuple(dict(item) for item in (row["blockers"] or ())),
            quantitative_input_ready=bool(row["quantitative_input_ready"]),
            measurement_id=row["measurement_id"],
            measurement_version=(int(row["measurement_version"]) if row["measurement_version"] is not None else None),
            measurement_date=row["measurement_date"],
            loss_horizon=(str(row["loss_horizon"]) if row["loss_horizon"] else None),
            calculation_digest=(str(row["calculation_digest"]) if row["calculation_digest"] else None),
            measurement_forward_evidence_current=bool(row["measurement_forward_evidence_current"]),
            measurement_status=str(row["measurement_status"]),
            authoritative_ecl_amount=row["authoritative_ecl_amount"],
            read_only_ecl_calculation_enabled=bool(row["read_only_ecl_calculation_enabled"]),
            account_1190_posting_enabled=bool(row["account_1190_posting_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _measurement_from_row(row) -> EclQuantitativeMeasurement:
        return EclQuantitativeMeasurement(
            id=row["id"],
            loan_id=row["loan_id"],
            measurement_version=int(row["measurement_version"]),
            measurement_date=row["measurement_date"],
            stage_label=str(row["stage_label"]),
            loss_horizon=str(row["loss_horizon"]),
            schedule_id=row["schedule_id"],
            schedule_version=int(row["schedule_version"]),
            contract_reference=str(row["contract_reference"]),
            label_review_id=int(row["label_review_id"]),
            label_review_version=int(row["label_review_version"]),
            original_eir_source_key=str(row["original_eir_source_key"]),
            original_eir_policy_version=str(row["original_eir_policy_version"]),
            original_daily_eir=row["original_daily_eir"],
            original_initial_gross_carrying_amount=row["original_initial_gross_carrying_amount"],
            forward_evidence_ids=tuple(row["forward_evidence_ids"] or ()),
            input_snapshot=dict(row["input_snapshot"]),
            contractual_cash_flow_snapshot=tuple(dict(item) for item in row["contractual_cash_flow_snapshot"]),
            scenario_snapshot=tuple(dict(item) for item in row["scenario_snapshot"]),
            scenario_count=int(row["scenario_count"]),
            probability_total=row["probability_total"],
            contractual_cash_flow_pv=row["contractual_cash_flow_pv"],
            weighted_expected_cash_shortfall=row["weighted_expected_cash_shortfall"],
            ecl_amount=row["ecl_amount"],
            calculation_policy_version=str(row["calculation_policy_version"]),
            discount_basis=str(row["discount_basis"]),
            rounding_policy=str(row["rounding_policy"]),
            calculation_digest=str(row["calculation_digest"]),
            review_rationale=str(row["review_rationale"]),
            reviewed_by_user_id=row["reviewed_by_user_id"],
            reviewed_at=row["reviewed_at"],
        )

    @staticmethod
    def _translate_error(error: psycopg.Error) -> EclQuantitativeMeasurementError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "loan was not found" in lowered or "was not found" in lowered:
            return EclQuantitativeMeasurementNotFound(message)
        blocked_markers = (
            "required",
            "blocked",
            "must",
            "unsupported",
            "cannot",
            "probability",
            "scenario",
            "evidence",
            "precision",
            "current authoritative date",
            "duplicate",
        )
        if any(marker in lowered for marker in blocked_markers):
            return EclQuantitativeMeasurementBlocked(message)
        return EclQuantitativeMeasurementError(
            message or "Protected quantitative ECL measurement failed."
        )
