from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .management_no_collection_repository import (
    ManagementNoCollectionConflict,
    ManagementNoCollectionNotFound,
)


MONEY = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class NoCollectionInstallmentState:
    installment_id: int
    installment_number: int
    contractual_due_date: date
    effective_due_date: date
    contractual_amount: Decimal
    allocated_amount: Decimal
    last_adjustment_id: UUID | None

    @property
    def remaining_amount(self) -> Decimal:
        return max(
            (self.contractual_amount - self.allocated_amount).quantize(MONEY),
            Decimal("0.00"),
        )


@dataclass(frozen=True, slots=True)
class ActiveNoCollectionState:
    adjustment_id: UUID
    no_collection_date: date
    reason: str
    resulting_operational_version: int
    actor_name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NoCollectionLoanState:
    loan_id: UUID
    loan_number: str
    client_id: UUID
    client_name: str
    loan_type: str
    schedule_id: UUID
    schedule_version: int
    payment_frequency: str
    contract_reference: str
    operational_version: int
    semi_monthly_days: tuple[int, int]
    installments: tuple[NoCollectionInstallmentState, ...]
    active_no_collection: tuple[ActiveNoCollectionState, ...]


class PostgresManagementNoCollectionQueryRepository:
    """Read the exact operational schedule Management must review before writing."""

    def get_loan_state(self, *, loan_id: UUID) -> NoCollectionLoanState:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        loan.id as loan_id,
                        loan.loan_number,
                        client.id as client_id,
                        client.full_name as client_name,
                        loan_type.name as loan_type,
                        schedule.id as schedule_id,
                        schedule.schedule_version,
                        schedule.payment_frequency,
                        schedule.contract_reference,
                        schedule.settings,
                        registration.id as registration_id,
                        coalesce(state.operational_version, 0) as operational_version
                    from lending.loans loan
                    join lending.clients client
                      on client.id = loan.client_id
                    join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_contract_schedules schedule
                      on schedule.loan_id = loan.id
                     and schedule.status = 'active'
                    left join lending.loan_contract_schedule_registrations registration
                      on registration.schedule_id = schedule.id
                    left join lending.loan_schedule_operational_state state
                      on state.schedule_id = schedule.id
                    where loan.id = %s
                    """,
                    (loan_id,),
                )
                loan = cursor.fetchone()
                if loan is None:
                    raise ManagementNoCollectionNotFound(
                        "The selected loan was not found."
                    )
                if loan["schedule_id"] is None:
                    raise ManagementNoCollectionConflict(
                        "No Collection requires an active contractual schedule."
                    )
                if loan["registration_id"] is None:
                    raise ManagementNoCollectionConflict(
                        "No Collection requires a verified registered contractual schedule."
                    )

                cursor.execute(
                    """
                    select
                        installment.id,
                        installment.installment_number,
                        installment.contractual_due_date,
                        installment.effective_due_date,
                        installment.contractual_amount,
                        installment.last_adjustment_id,
                        coalesce(sum(allocation.amount_applied) filter (
                            where transaction.is_voided = false
                        ), 0)::numeric(18,2) as allocated_amount
                    from lending.loan_contract_installments_operational installment
                    left join lending.loan_installment_payment_allocations allocation
                      on allocation.installment_id = installment.id
                    left join lending.collection_transactions transaction
                      on transaction.id = allocation.transaction_id
                    where installment.schedule_id = %s
                    group by
                        installment.id,
                        installment.installment_number,
                        installment.contractual_due_date,
                        installment.effective_due_date,
                        installment.contractual_amount,
                        installment.last_adjustment_id
                    order by installment.installment_number
                    """,
                    (loan["schedule_id"],),
                )
                installments = tuple(
                    NoCollectionInstallmentState(
                        installment_id=int(row["id"]),
                        installment_number=int(row["installment_number"]),
                        contractual_due_date=row["contractual_due_date"],
                        effective_due_date=row["effective_due_date"],
                        contractual_amount=Decimal(row["contractual_amount"]).quantize(MONEY),
                        allocated_amount=Decimal(row["allocated_amount"]).quantize(MONEY),
                        last_adjustment_id=row["last_adjustment_id"],
                    )
                    for row in cursor.fetchall()
                )
                if not installments:
                    raise ManagementNoCollectionConflict(
                        "The verified schedule has no installments to adjust."
                    )

                cursor.execute(
                    """
                    select
                        adjustment.id,
                        adjustment.no_collection_date,
                        adjustment.reason,
                        adjustment.resulting_operational_version,
                        coalesce(
                            nullif(btrim(actor.full_name), ''),
                            nullif(btrim(actor.username), ''),
                            'Management'
                        ) as actor_name,
                        adjustment.created_at
                    from lending.loan_schedule_adjustments adjustment
                    left join core.users actor
                      on actor.id = adjustment.actor_user_id
                    where adjustment.schedule_id = %s
                      and adjustment.adjustment_type = 'no_collection'
                      and not exists (
                            select 1
                            from lending.loan_schedule_adjustments reversal
                            where reversal.reverses_adjustment_id = adjustment.id
                      )
                    order by adjustment.created_at, adjustment.id
                    """,
                    (loan["schedule_id"],),
                )
                active_no_collection = tuple(
                    ActiveNoCollectionState(
                        adjustment_id=row["id"],
                        no_collection_date=row["no_collection_date"],
                        reason=str(row["reason"]),
                        resulting_operational_version=int(
                            row["resulting_operational_version"]
                        ),
                        actor_name=str(row["actor_name"]),
                        created_at=row["created_at"],
                    )
                    for row in cursor.fetchall()
                )

        return NoCollectionLoanState(
            loan_id=loan["loan_id"],
            loan_number=str(loan["loan_number"]),
            client_id=loan["client_id"],
            client_name=str(loan["client_name"]),
            loan_type=str(loan["loan_type"]),
            schedule_id=loan["schedule_id"],
            schedule_version=int(loan["schedule_version"]),
            payment_frequency=str(loan["payment_frequency"]),
            contract_reference=str(loan["contract_reference"]),
            operational_version=int(loan["operational_version"]),
            semi_monthly_days=self._semi_monthly_days(loan["settings"]),
            installments=installments,
            active_no_collection=active_no_collection,
        )

    @staticmethod
    def _semi_monthly_days(settings: object) -> tuple[int, int]:
        if not isinstance(settings, dict):
            return (15, 30)
        value = settings.get("semi_monthly_days")
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return (15, 30)
        try:
            first = int(value[0])
            second = int(value[1])
        except (TypeError, ValueError):
            return (15, 30)
        if first < 1 or first > 31 or second < 1 or second > 31 or first == second:
            return (15, 30)
        return tuple(sorted((first, second)))
