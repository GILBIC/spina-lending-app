from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .rolling_schedule import (
    RollingScheduleError,
    RollingScheduleInstallment,
    RollingScheduleShift,
    plan_borrower_catchup_contraction,
    plan_borrower_shortfall_shift,
)


class BorrowerScheduleAdjustmentError(RuntimeError):
    code = "borrower_schedule_adjustment_error"


class BorrowerScheduleAdjustmentNotFound(BorrowerScheduleAdjustmentError):
    code = "borrower_schedule_adjustment_not_found"


class BorrowerScheduleAdjustmentConflict(BorrowerScheduleAdjustmentError):
    code = "borrower_schedule_adjustment_conflict"


@dataclass(frozen=True, slots=True)
class BorrowerScheduleShiftRecord:
    installment_id: int
    installment_number: int
    contractual_due_date: date
    prior_effective_due_date: date
    new_effective_due_date: date
    contractual_amount: Decimal


@dataclass(frozen=True, slots=True)
class BorrowerScheduleAdjustmentRecord:
    adjustment_id: UUID
    loan_id: UUID
    schedule_id: UUID
    adjustment_type: str
    event_date: date
    expected_operational_version: int
    resulting_operational_version: int
    active_borrower_extension_slots_before: int
    active_borrower_extension_slots_after: int
    created_at: datetime
    shifts: tuple[BorrowerScheduleShiftRecord, ...]


class PostgresBorrowerScheduleAdjustmentRepository:
    def record_shortfall(
        self,
        *,
        actor_user_id: UUID,
        loan_id: UUID,
        event_date: date,
        expected_operational_version: int,
    ) -> BorrowerScheduleAdjustmentRecord:
        if expected_operational_version < 0:
            raise BorrowerScheduleAdjustmentConflict(
                "Operational schedule version cannot be negative."
            )

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._lock_loan(cursor, loan_id=loan_id)
                schedule = self._lock_active_registered_schedule(cursor, loan_id=loan_id)
                state_version, active_slots = self._lock_operational_state(
                    cursor,
                    schedule_id=schedule["schedule_id"],
                )
                if state_version != expected_operational_version:
                    raise BorrowerScheduleAdjustmentConflict(
                        "The operational schedule changed. Refresh before recording borrower shortfall."
                    )

                rows = self._load_installments(
                    cursor,
                    schedule_id=schedule["schedule_id"],
                )
                installments = self._rolling_installments(rows)
                blocked_dates = self._active_no_collection_dates(
                    cursor,
                    schedule_id=schedule["schedule_id"],
                )
                try:
                    planned = plan_borrower_shortfall_shift(
                        installments=installments,
                        business_date=event_date,
                        payment_frequency=str(schedule["payment_frequency"]),
                        blocked_dates=blocked_dates,
                        semi_monthly_days=self._semi_monthly_days(schedule["settings"]),
                    )
                except RollingScheduleError as error:
                    raise BorrowerScheduleAdjustmentConflict(str(error)) from error
                if not planned:
                    raise BorrowerScheduleAdjustmentConflict(
                        "No unresolved scheduled installment exists for this borrower shortfall date."
                    )

                resulting_version = state_version + 1
                resulting_slots = active_slots + 1
                cursor.execute(
                    """
                    insert into lending.loan_schedule_adjustments (
                        loan_id,
                        schedule_id,
                        adjustment_type,
                        no_collection_date,
                        event_date,
                        reason,
                        expected_operational_version,
                        resulting_operational_version,
                        actor_user_id
                    )
                    values (%s, %s, 'borrower_shortfall', null, %s, %s, %s, %s, %s)
                    returning id, created_at
                    """,
                    (
                        loan_id,
                        schedule["schedule_id"],
                        event_date,
                        "Borrower scheduled installment shortfall at official day close.",
                        state_version,
                        resulting_version,
                        actor_user_id,
                    ),
                )
                created = cursor.fetchone()
                if created is None:
                    raise BorrowerScheduleAdjustmentConflict(
                        "Borrower shortfall audit record could not be created."
                    )
                adjustment_id = created["id"]
                shift_records = self._persist_shifts(
                    cursor,
                    adjustment_id=adjustment_id,
                    planned=planned,
                    rows=rows,
                    actor_user_id=actor_user_id,
                )
                self._set_operational_state(
                    cursor,
                    schedule_id=schedule["schedule_id"],
                    expected_version=state_version,
                    resulting_version=resulting_version,
                    active_borrower_extension_slots=resulting_slots,
                    actor_user_id=actor_user_id,
                )
                self._invalidate_collection_state(cursor, loan_id=loan_id)

                return BorrowerScheduleAdjustmentRecord(
                    adjustment_id=adjustment_id,
                    loan_id=loan_id,
                    schedule_id=schedule["schedule_id"],
                    adjustment_type="borrower_shortfall",
                    event_date=event_date,
                    expected_operational_version=state_version,
                    resulting_operational_version=resulting_version,
                    active_borrower_extension_slots_before=active_slots,
                    active_borrower_extension_slots_after=resulting_slots,
                    created_at=created["created_at"],
                    shifts=shift_records,
                )

    def record_catchup(
        self,
        *,
        actor_user_id: UUID,
        loan_id: UUID,
        event_date: date,
        expected_operational_version: int,
        completed_catchup_installment_ids: tuple[int, ...],
    ) -> BorrowerScheduleAdjustmentRecord:
        """Persist a standalone borrower catch-up adjustment and invalidate route state."""

        with open_connection() as connection:
            return self.record_catchup_in_transaction(
                connection,
                actor_user_id=actor_user_id,
                loan_id=loan_id,
                event_date=event_date,
                expected_operational_version=expected_operational_version,
                completed_catchup_installment_ids=completed_catchup_installment_ids,
                invalidate_collection_state=True,
            )

    def record_catchup_in_transaction(
        self,
        connection: Any,
        *,
        actor_user_id: UUID,
        loan_id: UUID,
        event_date: date,
        expected_operational_version: int,
        completed_catchup_installment_ids: tuple[int, ...],
        invalidate_collection_state: bool = False,
    ) -> BorrowerScheduleAdjustmentRecord:
        """Persist catch-up using the caller's existing PostgreSQL transaction.

        Payment posting uses this form so receipt allocation and schedule
        contraction commit or roll back together. Standalone callers keep using
        ``record_catchup()``, which also invalidates the collection route state.
        """

        if expected_operational_version < 0:
            raise BorrowerScheduleAdjustmentConflict(
                "Operational schedule version cannot be negative."
            )
        completed_ids = tuple(dict.fromkeys(completed_catchup_installment_ids))
        if not completed_ids:
            raise BorrowerScheduleAdjustmentConflict(
                "At least one completed catch-up installment is required."
            )

        with connection.cursor(row_factory=dict_row) as cursor:
            self._lock_loan(cursor, loan_id=loan_id)
            schedule = self._lock_active_registered_schedule(cursor, loan_id=loan_id)
            state_version, active_slots = self._lock_operational_state(
                cursor,
                schedule_id=schedule["schedule_id"],
            )
            if state_version != expected_operational_version:
                raise BorrowerScheduleAdjustmentConflict(
                    "The operational schedule changed. Refresh before recording borrower catch-up."
                )
            if active_slots <= 0:
                raise BorrowerScheduleAdjustmentConflict(
                    "Borrower catch-up requires an active borrower schedule extension."
                )

            rows = self._load_installments(
                cursor,
                schedule_id=schedule["schedule_id"],
            )
            installments = self._rolling_installments(rows)
            try:
                planned = plan_borrower_catchup_contraction(
                    installments=installments,
                    active_extension_slots=active_slots,
                    completed_catchup_installment_ids=completed_ids,
                )
            except RollingScheduleError as error:
                raise BorrowerScheduleAdjustmentConflict(str(error)) from error

            resulting_version = state_version + 1
            resulting_slots = active_slots - len(completed_ids)
            cursor.execute(
                """
                insert into lending.loan_schedule_adjustments (
                    loan_id,
                    schedule_id,
                    adjustment_type,
                    no_collection_date,
                    event_date,
                    reason,
                    expected_operational_version,
                    resulting_operational_version,
                    actor_user_id
                )
                values (%s, %s, 'borrower_catch_up', null, %s, %s, %s, %s, %s)
                returning id, created_at
                """,
                (
                    loan_id,
                    schedule["schedule_id"],
                    event_date,
                    "Borrower completed normal catch-up installment; remaining schedule contracted.",
                    state_version,
                    resulting_version,
                    actor_user_id,
                ),
            )
            created = cursor.fetchone()
            if created is None:
                raise BorrowerScheduleAdjustmentConflict(
                    "Borrower catch-up audit record could not be created."
                )
            adjustment_id = created["id"]
            shift_records = self._persist_shifts(
                cursor,
                adjustment_id=adjustment_id,
                planned=planned,
                rows=rows,
                actor_user_id=actor_user_id,
            )
            self._set_operational_state(
                cursor,
                schedule_id=schedule["schedule_id"],
                expected_version=state_version,
                resulting_version=resulting_version,
                active_borrower_extension_slots=resulting_slots,
                actor_user_id=actor_user_id,
            )
            if invalidate_collection_state:
                self._invalidate_collection_state(cursor, loan_id=loan_id)

            return BorrowerScheduleAdjustmentRecord(
                adjustment_id=adjustment_id,
                loan_id=loan_id,
                schedule_id=schedule["schedule_id"],
                adjustment_type="borrower_catch_up",
                event_date=event_date,
                expected_operational_version=state_version,
                resulting_operational_version=resulting_version,
                active_borrower_extension_slots_before=active_slots,
                active_borrower_extension_slots_after=resulting_slots,
                created_at=created["created_at"],
                shifts=shift_records,
            )

    @staticmethod
    def _rolling_installments(
        rows: list[dict[str, Any]],
    ) -> tuple[RollingScheduleInstallment, ...]:
        return tuple(
            RollingScheduleInstallment(
                installment_id=int(row["id"]),
                installment_number=int(row["installment_number"]),
                contractual_due_date=row["contractual_due_date"],
                effective_due_date=row["effective_due_date"],
                remaining_amount=max(
                    Decimal(row["contractual_amount"])
                    - Decimal(row["allocated_amount"]),
                    Decimal("0.00"),
                ),
            )
            for row in rows
        )

    def _persist_shifts(
        self,
        cursor: Any,
        *,
        adjustment_id: UUID,
        planned: tuple[RollingScheduleShift, ...],
        rows: list[dict[str, Any]],
        actor_user_id: UUID,
    ) -> tuple[BorrowerScheduleShiftRecord, ...]:
        amount_by_installment_id = {
            int(row["id"]): Decimal(row["contractual_amount"])
            for row in rows
        }
        records: list[BorrowerScheduleShiftRecord] = []
        for shift in planned:
            contractual_amount = amount_by_installment_id[shift.installment_id]
            self._insert_shift_item(
                cursor,
                adjustment_id=adjustment_id,
                shift=shift,
                contractual_amount=contractual_amount,
            )
            self._write_effective_date(
                cursor,
                installment_id=shift.installment_id,
                effective_due_date=shift.new_effective_due_date,
                adjustment_id=adjustment_id,
                actor_user_id=actor_user_id,
            )
            records.append(
                BorrowerScheduleShiftRecord(
                    installment_id=shift.installment_id,
                    installment_number=shift.installment_number,
                    contractual_due_date=shift.contractual_due_date,
                    prior_effective_due_date=shift.prior_effective_due_date,
                    new_effective_due_date=shift.new_effective_due_date,
                    contractual_amount=contractual_amount,
                )
            )
        return tuple(records)

    @staticmethod
    def _lock_loan(cursor: Any, *, loan_id: UUID) -> None:
        cursor.execute(
            "select id from lending.loans where id = %s for update",
            (loan_id,),
        )
        if cursor.fetchone() is None:
            raise BorrowerScheduleAdjustmentNotFound(
                "The selected loan no longer exists."
            )

    @staticmethod
    def _lock_active_registered_schedule(cursor: Any, *, loan_id: UUID) -> dict[str, Any]:
        cursor.execute(
            """
            select
                schedule.id as schedule_id,
                schedule.payment_frequency,
                schedule.settings,
                registration.id as registration_id
            from lending.loan_contract_schedules schedule
            left join lending.loan_contract_schedule_registrations registration
              on registration.schedule_id = schedule.id
            where schedule.loan_id = %s
              and schedule.status = 'active'
            for update of schedule
            """,
            (loan_id,),
        )
        schedule = cursor.fetchone()
        if schedule is None:
            raise BorrowerScheduleAdjustmentNotFound(
                "The selected loan has no active contractual schedule."
            )
        if schedule["registration_id"] is None:
            raise BorrowerScheduleAdjustmentConflict(
                "Borrower schedule adjustment requires a verified registered contractual schedule."
            )
        return schedule

    @staticmethod
    def _lock_operational_state(cursor: Any, *, schedule_id: UUID) -> tuple[int, int]:
        cursor.execute(
            """
            insert into lending.loan_schedule_operational_state (
                schedule_id, operational_version, active_borrower_extension_slots
            ) values (%s, 0, 0)
            on conflict (schedule_id) do nothing
            """,
            (schedule_id,),
        )
        cursor.execute(
            """
            select operational_version, active_borrower_extension_slots
            from lending.loan_schedule_operational_state
            where schedule_id = %s
            for update
            """,
            (schedule_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise BorrowerScheduleAdjustmentConflict(
                "Operational schedule state could not be locked."
            )
        return int(row["operational_version"]), int(row["active_borrower_extension_slots"])

    @staticmethod
    def _load_installments(cursor: Any, *, schedule_id: UUID) -> list[dict[str, Any]]:
        cursor.execute(
            """
            select
                installment.id,
                installment.installment_number,
                installment.due_date as contractual_due_date,
                coalesce(operational.effective_due_date, installment.due_date)
                    as effective_due_date,
                installment.contractual_amount,
                coalesce(sum(allocation.amount_applied) filter (
                    where transaction.is_voided = false
                ), 0)::numeric(18,2) as allocated_amount
            from lending.loan_contract_installments installment
            left join lending.loan_installment_operational_dates operational
              on operational.installment_id = installment.id
            left join lending.loan_installment_payment_allocations allocation
              on allocation.installment_id = installment.id
            left join lending.collection_transactions transaction
              on transaction.id = allocation.transaction_id
            where installment.schedule_id = %s
            group by
                installment.id,
                installment.installment_number,
                installment.due_date,
                operational.effective_due_date,
                installment.contractual_amount
            order by
                coalesce(operational.effective_due_date, installment.due_date),
                installment.installment_number,
                installment.id
            """,
            (schedule_id,),
        )
        return list(cursor.fetchall())

    @staticmethod
    def _active_no_collection_dates(cursor: Any, *, schedule_id: UUID) -> tuple[date, ...]:
        cursor.execute(
            """
            select adjustment.no_collection_date
            from lending.loan_schedule_adjustments adjustment
            where adjustment.schedule_id = %s
              and adjustment.adjustment_type = 'no_collection'
              and not exists (
                    select 1
                    from lending.loan_schedule_adjustments reversal
                    where reversal.reverses_adjustment_id = adjustment.id
              )
            order by adjustment.no_collection_date
            """,
            (schedule_id,),
        )
        return tuple(row["no_collection_date"] for row in cursor.fetchall())

    @staticmethod
    def _semi_monthly_days(settings: object) -> tuple[int, int]:
        if not isinstance(settings, dict):
            return (15, 30)
        value = settings.get("semi_monthly_days")
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return (15, 30)
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return (15, 30)

    @staticmethod
    def _insert_shift_item(
        cursor: Any,
        *,
        adjustment_id: UUID,
        shift: RollingScheduleShift,
        contractual_amount: Decimal,
    ) -> None:
        cursor.execute(
            """
            insert into lending.loan_schedule_adjustment_items (
                adjustment_id,
                installment_id,
                installment_number,
                contractual_due_date,
                prior_effective_due_date,
                new_effective_due_date,
                contractual_amount
            ) values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                adjustment_id,
                shift.installment_id,
                shift.installment_number,
                shift.contractual_due_date,
                shift.prior_effective_due_date,
                shift.new_effective_due_date,
                contractual_amount,
            ),
        )

    @staticmethod
    def _write_effective_date(
        cursor: Any,
        *,
        installment_id: int,
        effective_due_date: date,
        adjustment_id: UUID,
        actor_user_id: UUID,
    ) -> None:
        cursor.execute(
            """
            insert into lending.loan_installment_operational_dates (
                installment_id,
                effective_due_date,
                last_adjustment_id,
                updated_by_user_id
            ) values (%s, %s, %s, %s)
            on conflict (installment_id) do update
            set effective_due_date = excluded.effective_due_date,
                last_adjustment_id = excluded.last_adjustment_id,
                updated_by_user_id = excluded.updated_by_user_id,
                updated_at = now()
            """,
            (
                installment_id,
                effective_due_date,
                adjustment_id,
                actor_user_id,
            ),
        )

    @staticmethod
    def _set_operational_state(
        cursor: Any,
        *,
        schedule_id: UUID,
        expected_version: int,
        resulting_version: int,
        active_borrower_extension_slots: int,
        actor_user_id: UUID,
    ) -> None:
        cursor.execute(
            """
            update lending.loan_schedule_operational_state
            set operational_version = %s,
                active_borrower_extension_slots = %s,
                updated_by_user_id = %s,
                updated_at = now()
            where schedule_id = %s
              and operational_version = %s
            """,
            (
                resulting_version,
                active_borrower_extension_slots,
                actor_user_id,
                schedule_id,
                expected_version,
            ),
        )
        if cursor.rowcount != 1:
            raise BorrowerScheduleAdjustmentConflict(
                "The operational schedule changed while borrower adjustment was being saved."
            )

    @staticmethod
    def _invalidate_collection_state(cursor: Any, *, loan_id: UUID) -> None:
        cursor.execute(
            """
            update lending.loan_collection_state
            set state_version = state_version + 1,
                updated_at = now()
            where loan_id = %s
            """,
            (loan_id,),
        )
