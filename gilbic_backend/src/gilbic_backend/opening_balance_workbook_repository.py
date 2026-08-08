from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class OpeningBalanceWorkbookSummary:
    workbook_id: UUID | None
    cutover_date: date | None
    status: str
    line_count: int
    source_reference_count: int
    verified_line_count: int
    pending_line_count: int
    profit_loss_policy_confirmed: bool
    profit_loss_policy_note: str | None
    total_debit: Decimal
    total_credit: Decimal
    balance_variance: Decimal
    worksheet_balanced: bool
    ready_for_review: bool
    ready_to_post: bool
    opening_balance_posting_enabled: bool
    automatic_source_posting_enabled: bool


@dataclass(frozen=True, slots=True)
class OpeningBalanceWorkbookLine:
    workbook_id: UUID | None
    account_code: str
    system_key: str
    account_name: str
    account_type: str
    normal_balance: str
    source_reference_amount: Decimal | None
    source_basis: str
    requirement_type: str
    guidance: str
    proposed_debit: Decimal | None
    proposed_credit: Decimal | None
    verification_status: str
    evidence_note: str | None
    measurement_reference_amount: Decimal | None
    measurement_status: str | None
    measurement_note: str | None


@dataclass(frozen=True, slots=True)
class LoanMeasurementSummary:
    active_loan_count: int
    measured_loan_count: int
    review_required_count: int
    actual_cash_received: Decimal
    effective_interest_income: Decimal
    regular_loan_component: Decimal
    seven_by_seven_loan_component: Decimal
    accrued_interest_component: Decimal
    gross_carrying_amount: Decimal
    measurement_status: str
    measurement_policy_version: str
    ecl_included: bool
    ready_to_post: bool


@dataclass(frozen=True, slots=True)
class LoanMeasurement:
    loan_id: UUID
    loan_number: str
    client_name: str
    calculation_mode: str
    policy_version: str
    date_released: date
    due_date: date
    cutover_date: date | None
    days_elapsed: int | None
    principal: Decimal
    operational_balance: Decimal
    daily_eir: Decimal | None
    daily_eir_percent: Decimal | None
    contractual_cash_due: Decimal | None
    actual_cash_received: Decimal | None
    effective_interest_income: Decimal | None
    loan_component: Decimal | None
    accrued_interest_component: Decimal | None
    gross_carrying_amount: Decimal | None
    contractual_unpaid_interest: Decimal | None
    measurement_status: str
    measurement_note: str


@dataclass(frozen=True, slots=True)
class OpeningBalanceWorkbook:
    summary: OpeningBalanceWorkbookSummary
    lines: tuple[OpeningBalanceWorkbookLine, ...]
    measurement_summary: LoanMeasurementSummary
    loan_measurements: tuple[LoanMeasurement, ...]


class OpeningBalanceWorkbookError(RuntimeError):
    code = "opening_balance_workbook_error"


class OpeningBalanceWorkbookNotFound(OpeningBalanceWorkbookError):
    code = "opening_balance_workbook_not_found"


class OpeningBalanceWorkbookConflict(OpeningBalanceWorkbookError):
    code = "opening_balance_workbook_conflict"


class OpeningBalanceWorkbookValidation(OpeningBalanceWorkbookError):
    code = "opening_balance_workbook_validation"


class PostgresOpeningBalanceWorkbookRepository:
    """Manage the protected, non-posting opening-balance cutover workbook."""

    def load_workbook(self) -> OpeningBalanceWorkbook:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return self._load_workbook(cursor)

    def create_workbook(
        self,
        *,
        actor_user_id: UUID,
        cutover_date: date,
    ) -> OpeningBalanceWorkbook:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.create_opening_balance_workbook(%s, %s)
                            as workbook_id
                        """,
                        (cutover_date, actor_user_id),
                    )
                    cursor.fetchone()
                    return self._load_workbook(cursor)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def update_line(
        self,
        *,
        actor_user_id: UUID,
        workbook_id: UUID,
        account_code: str,
        proposed_debit: Decimal | None,
        proposed_credit: Decimal | None,
        verification_status: str,
        evidence_note: str | None,
    ) -> OpeningBalanceWorkbook:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.update_opening_balance_workbook_line(
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            workbook_id,
                            account_code,
                            proposed_debit,
                            proposed_credit,
                            verification_status,
                            evidence_note,
                            actor_user_id,
                        ),
                    )
                    cursor.fetchone()
                    return self._load_workbook(cursor)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def update_policy(
        self,
        *,
        actor_user_id: UUID,
        workbook_id: UUID,
        confirmed: bool,
        policy_note: str | None,
    ) -> OpeningBalanceWorkbook:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.update_opening_balance_workbook_policy(
                            %s, %s, %s, %s
                        )
                        """,
                        (workbook_id, confirmed, policy_note, actor_user_id),
                    )
                    cursor.fetchone()
                    return self._load_workbook(cursor)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def set_status(
        self,
        *,
        actor_user_id: UUID,
        workbook_id: UUID,
        status: str,
    ) -> OpeningBalanceWorkbook:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.set_opening_balance_workbook_status(
                            %s, %s, %s
                        )
                        """,
                        (workbook_id, status, actor_user_id),
                    )
                    cursor.fetchone()
                    return self._load_workbook(cursor)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @classmethod
    def _load_workbook(cls, cursor) -> OpeningBalanceWorkbook:
        cursor.execute(
            """
            select
                workbook_id,
                cutover_date,
                worksheet_status,
                worksheet_line_count,
                source_reference_count,
                profit_loss_policy_confirmed,
                profit_loss_policy_note,
                verified_line_count,
                pending_line_count,
                total_debit,
                total_credit,
                balance_variance,
                worksheet_balanced,
                ready_for_review,
                ready_to_post,
                opening_balance_posting_enabled,
                automatic_source_posting_enabled
            from accounting.opening_balance_cutover_summary
            """
        )
        summary_row = cursor.fetchone()
        if summary_row is None:
            raise OpeningBalanceWorkbookError(
                "Opening-balance workbook summary is unavailable."
            )

        cursor.execute(
            """
            select
                workbook_id,
                account_code,
                system_key,
                account_name,
                account_type,
                normal_balance,
                source_reference_amount,
                source_basis,
                readiness_status,
                guidance,
                proposed_debit,
                proposed_credit,
                verification_status,
                evidence_note,
                measurement_reference_amount,
                measurement_status,
                measurement_note
            from accounting.opening_balance_cutover_worksheet
            order by account_code
            """
        )
        lines = tuple(cls._line_from_row(row) for row in cursor.fetchall())

        cursor.execute(
            """
            select
                active_loan_count,
                measured_loan_count,
                review_required_count,
                actual_cash_received,
                effective_interest_income,
                regular_loan_component,
                seven_by_seven_loan_component,
                accrued_interest_component,
                gross_carrying_amount,
                measurement_status,
                measurement_policy_version,
                ecl_included,
                ready_to_post
            from accounting.loan_measurement_summary
            """
        )
        measurement_summary_row = cursor.fetchone()
        if measurement_summary_row is None:
            raise OpeningBalanceWorkbookError(
                "Accounting loan measurement summary is unavailable."
            )

        cursor.execute(
            """
            select
                loan_id,
                loan_number,
                client_name,
                calculation_mode,
                policy_version,
                date_released,
                due_date,
                cutover_date,
                days_elapsed,
                principal,
                operational_balance,
                daily_eir,
                daily_eir_percent,
                contractual_cash_due,
                actual_cash_received,
                effective_interest_income,
                loan_component,
                accrued_interest_component,
                gross_carrying_amount,
                contractual_unpaid_interest,
                measurement_status,
                measurement_note
            from accounting.loan_measurement_at_cutover
            order by calculation_mode, loan_number
            """
        )
        measurements = tuple(cls._measurement_from_row(row) for row in cursor.fetchall())

        return OpeningBalanceWorkbook(
            summary=OpeningBalanceWorkbookSummary(
                workbook_id=(
                    UUID(str(summary_row["workbook_id"]))
                    if summary_row["workbook_id"] is not None
                    else None
                ),
                cutover_date=summary_row["cutover_date"],
                status=str(summary_row["worksheet_status"]),
                line_count=int(summary_row["worksheet_line_count"] or 0),
                source_reference_count=int(summary_row["source_reference_count"] or 0),
                verified_line_count=int(summary_row["verified_line_count"] or 0),
                pending_line_count=int(summary_row["pending_line_count"] or 0),
                profit_loss_policy_confirmed=bool(
                    summary_row["profit_loss_policy_confirmed"]
                ),
                profit_loss_policy_note=(
                    str(summary_row["profit_loss_policy_note"])
                    if summary_row["profit_loss_policy_note"]
                    else None
                ),
                total_debit=Decimal(summary_row["total_debit"] or 0),
                total_credit=Decimal(summary_row["total_credit"] or 0),
                balance_variance=Decimal(summary_row["balance_variance"] or 0),
                worksheet_balanced=bool(summary_row["worksheet_balanced"]),
                ready_for_review=bool(summary_row["ready_for_review"]),
                ready_to_post=bool(summary_row["ready_to_post"]),
                opening_balance_posting_enabled=bool(
                    summary_row["opening_balance_posting_enabled"]
                ),
                automatic_source_posting_enabled=bool(
                    summary_row["automatic_source_posting_enabled"]
                ),
            ),
            lines=lines,
            measurement_summary=LoanMeasurementSummary(
                active_loan_count=int(measurement_summary_row["active_loan_count"] or 0),
                measured_loan_count=int(measurement_summary_row["measured_loan_count"] or 0),
                review_required_count=int(
                    measurement_summary_row["review_required_count"] or 0
                ),
                actual_cash_received=Decimal(
                    measurement_summary_row["actual_cash_received"] or 0
                ),
                effective_interest_income=Decimal(
                    measurement_summary_row["effective_interest_income"] or 0
                ),
                regular_loan_component=Decimal(
                    measurement_summary_row["regular_loan_component"] or 0
                ),
                seven_by_seven_loan_component=Decimal(
                    measurement_summary_row["seven_by_seven_loan_component"] or 0
                ),
                accrued_interest_component=Decimal(
                    measurement_summary_row["accrued_interest_component"] or 0
                ),
                gross_carrying_amount=Decimal(
                    measurement_summary_row["gross_carrying_amount"] or 0
                ),
                measurement_status=str(
                    measurement_summary_row["measurement_status"]
                ),
                measurement_policy_version=str(
                    measurement_summary_row["measurement_policy_version"]
                ),
                ecl_included=bool(measurement_summary_row["ecl_included"]),
                ready_to_post=bool(measurement_summary_row["ready_to_post"]),
            ),
            loan_measurements=measurements,
        )

    @staticmethod
    def _line_from_row(row) -> OpeningBalanceWorkbookLine:
        def optional_decimal(key: str) -> Decimal | None:
            value = row[key]
            return Decimal(value) if value is not None else None

        return OpeningBalanceWorkbookLine(
            workbook_id=(
                UUID(str(row["workbook_id"])) if row["workbook_id"] is not None else None
            ),
            account_code=str(row["account_code"]),
            system_key=str(row["system_key"]),
            account_name=str(row["account_name"]),
            account_type=str(row["account_type"]),
            normal_balance=str(row["normal_balance"]),
            source_reference_amount=optional_decimal("source_reference_amount"),
            source_basis=str(row["source_basis"]),
            requirement_type=str(row["readiness_status"]),
            guidance=str(row["guidance"]),
            proposed_debit=optional_decimal("proposed_debit"),
            proposed_credit=optional_decimal("proposed_credit"),
            verification_status=str(row["verification_status"]),
            evidence_note=(str(row["evidence_note"]) if row["evidence_note"] else None),
            measurement_reference_amount=optional_decimal(
                "measurement_reference_amount"
            ),
            measurement_status=(
                str(row["measurement_status"]) if row["measurement_status"] else None
            ),
            measurement_note=(
                str(row["measurement_note"]) if row["measurement_note"] else None
            ),
        )

    @staticmethod
    def _measurement_from_row(row) -> LoanMeasurement:
        def optional_decimal(key: str) -> Decimal | None:
            value = row[key]
            return Decimal(value) if value is not None else None

        return LoanMeasurement(
            loan_id=UUID(str(row["loan_id"])),
            loan_number=str(row["loan_number"]),
            client_name=str(row["client_name"]),
            calculation_mode=str(row["calculation_mode"]),
            policy_version=str(row["policy_version"]),
            date_released=row["date_released"],
            due_date=row["due_date"],
            cutover_date=row["cutover_date"],
            days_elapsed=(int(row["days_elapsed"]) if row["days_elapsed"] is not None else None),
            principal=Decimal(row["principal"] or 0),
            operational_balance=Decimal(row["operational_balance"] or 0),
            daily_eir=optional_decimal("daily_eir"),
            daily_eir_percent=optional_decimal("daily_eir_percent"),
            contractual_cash_due=optional_decimal("contractual_cash_due"),
            actual_cash_received=optional_decimal("actual_cash_received"),
            effective_interest_income=optional_decimal("effective_interest_income"),
            loan_component=optional_decimal("loan_component"),
            accrued_interest_component=optional_decimal("accrued_interest_component"),
            gross_carrying_amount=optional_decimal("gross_carrying_amount"),
            contractual_unpaid_interest=optional_decimal("contractual_unpaid_interest"),
            measurement_status=str(row["measurement_status"]),
            measurement_note=str(row["measurement_note"] or ""),
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> OpeningBalanceWorkbookError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return OpeningBalanceWorkbookNotFound(message)
        if (
            "already exists" in lowered
            or "only a draft" in lowered
            or "can only move" in lowered
            or "can only be reopened" in lowered
            or "must remain inside an open accounting period" in lowered
        ):
            return OpeningBalanceWorkbookConflict(message)
        if (
            "requires" in lowered
            or "cannot" in lowered
            or "must be" in lowered
            or "unsupported" in lowered
            or "blocked loan" in lowered
            or "cutover date" in lowered
        ):
            return OpeningBalanceWorkbookValidation(message)
        return OpeningBalanceWorkbookError(
            message or "Opening-balance workbook operation failed."
        )