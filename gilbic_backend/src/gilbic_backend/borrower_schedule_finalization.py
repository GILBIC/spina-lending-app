from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .borrower_schedule_adjustment_repository import (
    BorrowerScheduleAdjustmentRecord,
    PostgresBorrowerScheduleAdjustmentRepository,
)
from .database import open_connection


class PostgresBorrowerScheduleFinalizer:
    """Finalize elapsed borrower obligations before today's operational route is read."""

    def finalize_elapsed_for_loans(
        self,
        *,
        actor_user_id: UUID,
        loan_ids: tuple[UUID, ...],
        business_date: date,
    ) -> tuple[BorrowerScheduleAdjustmentRecord, ...]:
        requested = tuple(sorted(dict.fromkeys(loan_ids), key=str))
        if not requested:
            return ()

        repository = PostgresBorrowerScheduleAdjustmentRepository()
        records: list[BorrowerScheduleAdjustmentRecord] = []
        for loan_id in requested:
            while True:
                pending = self._next_elapsed_shortfall(
                    loan_id=loan_id,
                    business_date=business_date,
                )
                if pending is None:
                    break
                event_date, operational_version = pending
                records.append(
                    repository.record_shortfall(
                        actor_user_id=actor_user_id,
                        loan_id=loan_id,
                        event_date=event_date,
                        expected_operational_version=operational_version,
                    )
                )
        return tuple(records)

    @staticmethod
    def _next_elapsed_shortfall(
        *,
        loan_id: UUID,
        business_date: date,
    ) -> tuple[date, int] | None:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        installment.effective_due_date,
                        coalesce(state.operational_version, 0) as operational_version,
                        greatest(
                            installment.contractual_amount
                            - coalesce(sum(allocation.amount_applied) filter (
                                where transaction.is_voided = false
                            ), 0),
                            0
                        )::numeric(18,2) as remaining_amount
                    from lending.loan_contract_schedules schedule
                    join lending.loan_contract_schedule_registrations registration
                      on registration.schedule_id = schedule.id
                    join lending.loan_contract_installments_operational installment
                      on installment.schedule_id = schedule.id
                    left join lending.loan_schedule_operational_state state
                      on state.schedule_id = schedule.id
                    left join lending.loan_installment_payment_allocations allocation
                      on allocation.installment_id = installment.id
                    left join lending.collection_transactions transaction
                      on transaction.id = allocation.transaction_id
                    where schedule.loan_id = %s
                      and schedule.status = 'active'
                      and installment.effective_due_date < %s
                    group by
                        installment.id,
                        installment.installment_number,
                        installment.effective_due_date,
                        installment.contractual_amount,
                        state.operational_version
                    having greatest(
                        installment.contractual_amount
                        - coalesce(sum(allocation.amount_applied) filter (
                            where transaction.is_voided = false
                        ), 0),
                        0
                    ) > 0
                    order by
                        installment.effective_due_date,
                        installment.installment_number,
                        installment.id
                    limit 1
                    """,
                    (loan_id, business_date),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                if Decimal(row["remaining_amount"]) <= Decimal("0.00"):
                    return None
                return row["effective_due_date"], int(row["operational_version"])
