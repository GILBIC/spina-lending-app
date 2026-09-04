from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .no_collection_schedule import (
    NoCollectionScheduleError,
    OperationalInstallment,
    ScheduleShift,
    plan_no_collection_shift,
)


class ManagementNoCollectionError(RuntimeError):
    code = "no_collection_error"


class ManagementNoCollectionNotFound(ManagementNoCollectionError):
    code = "no_collection_not_found"


class ManagementNoCollectionConflict(ManagementNoCollectionError):
    code = "no_collection_conflict"


class ManagementNoCollectionInvalid(ManagementNoCollectionError):
    code = "no_collection_invalid"


@dataclass(frozen=True, slots=True)
class NoCollectionSelection:
    loan_id: UUID
    expected_operational_version: int


@dataclass(frozen=True, slots=True)
class NoCollectionShiftRecord:
    installment_id: int
    installment_number: int
    contractual_due_date: date
    prior_effective_due_date: date
    new_effective_due_date: date
    contractual_amount: Decimal


@dataclass(frozen=True, slots=True)
class NoCollectionAdjustmentRecord:
    adjustment_id: UUID
    loan_id: UUID
    schedule_id: UUID
    schedule_version: int
    payment_frequency: str
    no_collection_date: date
    reason: str
    adjustment_type: str
    expected_operational_version: int
    resulting_operational_version: int
    reverses_adjustment_id: UUID | None
    created_at: datetime
    shifts: tuple[NoCollectionShiftRecord, ...]


class PostgresManagementNoCollectionRepository:
    def declare_many(
        self,
        *,
        actor_user_id: UUID,
        selections: Iterable[NoCollectionSelection],
        no_collection_date: date,
        reason: str,
    ) -> tuple[NoCollectionAdjustmentRecord, ...]:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ManagementNoCollectionInvalid("A Management reason is required.")
        requested = tuple(sorted(selections, key=lambda item: str(item.loan_id)))
        if not requested:
            raise ManagementNoCollectionInvalid("Select at least one loan.")
        if len({item.loan_id for item in requested}) != len(requested):
            raise ManagementNoCollectionInvalid("A loan may be selected only once.")
        if any(item.expected_operational_version < 0 for item in requested):
            raise ManagementNoCollectionInvalid(
                "Operational schedule version cannot be negative."
            )

        with open_connection() as connection:
            records = tuple(
                self._declare_one(
                    connection,
                    actor_user_id=actor_user_id,
                    selection=selection,
                    no_collection_date=no_collection_date,
                    reason=normalized_reason,
                )
                for selection in requested
            )
        return records

    def reverse(
        self,
        *,
        actor_user_id: UUID,
        adjustment_id: UUID,
        expected_operational_version: int,
        reason: str,
    ) -> NoCollectionAdjustmentRecord:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ManagementNoCollectionInvalid("A reversal reason is required.")
        if expected_operational_version < 0:
            raise ManagementNoCollectionInvalid(
                "Operational schedule version cannot be negative."
            )

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select loan_id
                    from lending.loan_schedule_adjustments
                    where id = %s
                      and adjustment_type = 'no_collection'
                    """,
                    (adjustment_id,),
                )
                target = cursor.fetchone()
                if target is None:
                    raise ManagementNoCollectionNotFound(
                        "The No Collection adjustment was not found."
                    )
                self._lock_loan(cursor, loan_id=target["loan_id"])

                cursor.execute(
                    """
                    select
                        adjustment.id,
                        adjustment.loan_id,
                        adjustment.schedule_id,
                        adjustment.no_collection_date,
                        adjustment.resulting_operational_version,
                        schedule.schedule_version,
                        schedule.payment_frequency,
                        schedule.status,
                        registration.id as registration_id
                    from lending.loan_schedule_adjustments adjustment
                    join lending.loan_contract_schedules schedule
                      on schedule.id = adjustment.schedule_id
                    left join lending.loan_contract_schedule_registrations registration
                      on registration.schedule_id = schedule.id
                    where adjustment.id = %s
                      and adjustment.adjustment_type = 'no_collection'
                    for update of adjustment, schedule
                    """,
                    (adjustment_id,),
                )
                original = cursor.fetchone()
                if original is None:
                    raise ManagementNoCollectionNotFound(
                        "The No Collection adjustment was not found."
                    )
                if original["status"] != "active" or original["registration_id"] is None:
                    raise ManagementNoCollectionConflict(
                        "Only the current verified active schedule can be adjusted."
                    )
                if original["loan_id"] != target["loan_id"]:
                    raise ManagementNoCollectionConflict(
                        "The No Collection adjustment changed while it was being locked."
                    )

                state_version = self._lock_operational_state(
                    cursor,
                    schedule_id=original["schedule_id"],
                )
                if state_version != expected_operational_version:
                    raise ManagementNoCollectionConflict(
                        "The operational schedule changed. Refresh before reversing No Collection."
                    )
                if state_version != int(original["resulting_operational_version"]):
                    raise ManagementNoCollectionConflict(
                        "A later schedule adjustment exists. Reverse or review the latest adjustment first."
                    )

                cursor.execute(
                    """
                    select id
                    from lending.loan_schedule_adjustments
                    where reverses_adjustment_id = %s
                    """,
                    (adjustment_id,),
                )
                if cursor.fetchone() is not None:
                    raise ManagementNoCollectionConflict(
                        "This No Collection adjustment has already been reversed."
                    )

                cursor.execute(
                    """
                    select
                        item.installment_id,
                        item.installment_number,
                        item.contractual_due_date,
                        item.prior_effective_due_date,
                        item.new_effective_due_date,
                        item.contractual_amount,
                        operational.effective_due_date,
                        coalesce(sum(allocation.amount_applied) filter (
                            where transaction.is_voided = false
                        ), 0)::numeric(18,2) as allocated_amount
                    from lending.loan_schedule_adjustment_items item
                    left join lending.loan_installment_operational_dates operational
                      on operational.installment_id = item.installment_id
                    left join lending.loan_installment_payment_allocations allocation
                      on allocation.installment_id = item.installment_id
                    left join lending.collection_transactions transaction
                      on transaction.id = allocation.transaction_id
                    where item.adjustment_id = %s
                    group by
                        item.installment_id,
                        item.installment_number,
                        item.contractual_due_date,
                        item.prior_effective_due_date,
                        item.new_effective_due_date,
                        item.contractual_amount,
                        operational.effective_due_date
                    order by item.installment_number
                    """,
                    (adjustment_id,),
                )
                items = cursor.fetchall()
                if not items:
                    raise ManagementNoCollectionConflict(
                        "The No Collection adjustment has no audit items."
                    )
                for item in items:
                    if Decimal(item["allocated_amount"]) > Decimal("0.00"):
                        raise ManagementNoCollectionConflict(
                            "No Collection cannot be reversed after an affected installment received payment."
                        )
                    if item["effective_due_date"] != item["new_effective_due_date"]:
                        raise ManagementNoCollectionConflict(
                            "The effective schedule no longer matches this adjustment. Refresh and review the latest schedule."
                        )

                resulting_version = state_version + 1
                cursor.execute(
                    """
                    insert into lending.loan_schedule_adjustments (
                        loan_id,
                        schedule_id,
                        adjustment_type,
                        no_collection_date,
                        reason,
                        expected_operational_version,
                        resulting_operational_version,
                        reverses_adjustment_id,
                        actor_user_id
                    )
                    values (%s, %s, 'reversal', %s, %s, %s, %s, %s, %s)
                    returning id, created_at
                    """,
                    (
                        original["loan_id"],
                        original["schedule_id"],
                        original["no_collection_date"],
                        normalized_reason,
                        state_version,
                        resulting_version,
                        adjustment_id,
                        actor_user_id,
                    ),
                )
                created = cursor.fetchone()
                reversal_id = created["id"]
                shifts: list[NoCollectionShiftRecord] = []
                for item in items:
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
                        )
                        values (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            reversal_id,
                            item["installment_id"],
                            item["installment_number"],
                            item["contractual_due_date"],
                            item["new_effective_due_date"],
                            item["prior_effective_due_date"],
                            item["contractual_amount"],
                        ),
                    )
                    self._write_effective_date(
                        cursor,
                        installment_id=int(item["installment_id"]),
                        effective_due_date=item["prior_effective_due_date"],
                        adjustment_id=reversal_id,
                        actor_user_id=actor_user_id,
                    )
                    shifts.append(
                        NoCollectionShiftRecord(
                            installment_id=int(item["installment_id"]),
                            installment_number=int(item["installment_number"]),
                            contractual_due_date=item["contractual_due_date"],
                            prior_effective_due_date=item["new_effective_due_date"],
                            new_effective_due_date=item["prior_effective_due_date"],
                            contractual_amount=Decimal(item["contractual_amount"]),
                        )
                    )
                self._set_operational_version(
                    cursor,
                    schedule_id=original["schedule_id"],
                    expected_version=state_version,
                    resulting_version=resulting_version,
                    actor_user_id=actor_user_id,
                )
                self._invalidate_mobile_route_revision(
                    cursor,
                    loan_id=original["loan_id"],
                )

                return NoCollectionAdjustmentRecord(
                    adjustment_id=reversal_id,
                    loan_id=original["loan_id"],
                    schedule_id=original["schedule_id"],
                    schedule_version=int(original["schedule_version"]),
                    payment_frequency=str(original["payment_frequency"]),
                    no_collection_date=original["no_collection_date"],
                    reason=normalized_reason,
                    adjustment_type="reversal",
                    expected_operational_version=state_version,
                    resulting_operational_version=resulting_version,
                    reverses_adjustment_id=adjustment_id,
                    created_at=created["created_at"],
                    shifts=tuple(shifts),
                )

    def _declare_one(
        self,
        connection: Any,
        *,
        actor_user_id: UUID,
        selection: NoCollectionSelection,
        no_collection_date: date,
        reason: str,
    ) -> NoCollectionAdjustmentRecord:
        with connection.cursor(row_factory=dict_row) as cursor:
            self._lock_loan(cursor, loan_id=selection.loan_id)
            cursor.execute(
                """
                select
                    schedule.id as schedule_id,
                    schedule.schedule_version,
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
                (selection.loan_id,),
            )
            schedule = cursor.fetchone()
            if schedule is None:
                raise ManagementNoCollectionNotFound(
                    "The selected loan has no active contractual schedule."
                )
            if schedule["registration_id"] is None:
                raise ManagementNoCollectionConflict(
                    "No Collection requires a verified registered contractual schedule."
                )

            state_version = self._lock_operational_state(
                cursor,
                schedule_id=schedule["schedule_id"],
            )
            if state_version != selection.expected_operational_version:
                raise ManagementNoCollectionConflict(
                    "The operational schedule changed. Refresh before declaring No Collection."
                )

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
                    installment.installment_number
                """,
                (schedule["schedule_id"],),
            )
            installment_rows = cursor.fetchall()
            installments = tuple(
                OperationalInstallment(
                    installment_id=int(row["id"]),
                    installment_number=int(row["installment_number"]),
                    contractual_due_date=row["contractual_due_date"],
                    effective_due_date=row["effective_due_date"],
                    contractual_amount=Decimal(row["contractual_amount"]),
                    allocated_amount=Decimal(row["allocated_amount"]),
                )
                for row in installment_rows
            )

            blocked_dates = self._active_no_collection_dates(
                cursor,
                schedule_id=schedule["schedule_id"],
            )
            try:
                planned = plan_no_collection_shift(
                    installments=installments,
                    no_collection_date=no_collection_date,
                    payment_frequency=str(schedule["payment_frequency"]),
                    blocked_dates=blocked_dates,
                    semi_monthly_days=self._semi_monthly_days(schedule["settings"]),
                )
            except NoCollectionScheduleError as error:
                raise ManagementNoCollectionConflict(str(error)) from error

            resulting_version = state_version + 1
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
                values (%s, %s, 'no_collection', %s, %s, %s, %s, %s, %s)
                returning id, created_at
                """,
                (
                    selection.loan_id,
                    schedule["schedule_id"],
                    no_collection_date,
                    no_collection_date,
                    reason,
                    state_version,
                    resulting_version,
                    actor_user_id,
                ),
            )
            created = cursor.fetchone()
            adjustment_id = created["id"]
            for shift in planned:
                self._insert_shift_item(
                    cursor,
                    adjustment_id=adjustment_id,
                    shift=shift,
                )
                self._write_effective_date(
                    cursor,
                    installment_id=shift.installment_id,
                    effective_due_date=shift.new_effective_due_date,
                    adjustment_id=adjustment_id,
                    actor_user_id=actor_user_id,
                )
            self._set_operational_version(
                cursor,
                schedule_id=schedule["schedule_id"],
                expected_version=state_version,
                resulting_version=resulting_version,
                actor_user_id=actor_user_id,
            )
            self._invalidate_mobile_route_revision(
                cursor,
                loan_id=selection.loan_id,
            )

            return NoCollectionAdjustmentRecord(
                adjustment_id=adjustment_id,
                loan_id=selection.loan_id,
                schedule_id=schedule["schedule_id"],
                schedule_version=int(schedule["schedule_version"]),
                payment_frequency=str(schedule["payment_frequency"]),
                no_collection_date=no_collection_date,
                reason=reason,
                adjustment_type="no_collection",
                expected_operational_version=state_version,
                resulting_operational_version=resulting_version,
                reverses_adjustment_id=None,
                created_at=created["created_at"],
                shifts=tuple(self._shift_record(item) for item in planned),
            )

    @staticmethod
    def _lock_loan(cursor: Any, *, loan_id: UUID) -> None:
        cursor.execute(
            "select id from lending.loans where id = %s for update",
            (loan_id,),
        )
        if cursor.fetchone() is None:
            raise ManagementNoCollectionNotFound(
                "The selected loan no longer exists."
            )

    @staticmethod
    def _invalidate_mobile_route_revision(cursor: Any, *, loan_id: UUID) -> None:
        cursor.execute(
            """
            update lending.loan_collection_state
            set state_version = state_version + 1,
                updated_at = now()
            where loan_id = %s
            """,
            (loan_id,),
        )

    @staticmethod
    def _lock_operational_state(cursor: Any, *, schedule_id: UUID) -> int:
        cursor.execute(
            """
            insert into lending.loan_schedule_operational_state (
                schedule_id, operational_version
            ) values (%s, 0)
            on conflict (schedule_id) do nothing
            """,
            (schedule_id,),
        )
        cursor.execute(
            """
            select operational_version
            from lending.loan_schedule_operational_state
            where schedule_id = %s
            for update
            """,
            (schedule_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ManagementNoCollectionConflict(
                "Operational schedule state could not be locked."
            )
        return int(row["operational_version"])

    @staticmethod
    def _set_operational_version(
        cursor: Any,
        *,
        schedule_id: UUID,
        expected_version: int,
        resulting_version: int,
        actor_user_id: UUID,
    ) -> None:
        cursor.execute(
            """
            update lending.loan_schedule_operational_state
            set operational_version = %s,
                updated_by_user_id = %s,
                updated_at = now()
            where schedule_id = %s
              and operational_version = %s
            """,
            (
                resulting_version,
                actor_user_id,
                schedule_id,
                expected_version,
            ),
        )
        if cursor.rowcount != 1:
            raise ManagementNoCollectionConflict(
                "The operational schedule changed while No Collection was being saved."
            )

    @staticmethod
    def _insert_shift_item(
        cursor: Any,
        *,
        adjustment_id: UUID,
        shift: ScheduleShift,
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
                shift.contractual_amount,
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
    def _shift_record(shift: ScheduleShift) -> NoCollectionShiftRecord:
        return NoCollectionShiftRecord(
            installment_id=shift.installment_id,
            installment_number=shift.installment_number,
            contractual_due_date=shift.contractual_due_date,
            prior_effective_due_date=shift.prior_effective_due_date,
            new_effective_due_date=shift.new_effective_due_date,
            contractual_amount=shift.contractual_amount,
        )
