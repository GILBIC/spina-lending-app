from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .collector_schedule_repository import (
    CollectorScheduleRecord,
    CollectorScheduleRowRecord,
    _build_installment_row,
    _money,
)
from .database import open_connection


ZERO = Decimal("0.00")


class ClientLoanError(RuntimeError):
    code = "client_loan_error"


class ClientBorrowerNotLinked(ClientLoanError):
    code = "client_borrower_not_linked"


class ClientLoanNotFound(ClientLoanError):
    code = "client_loan_not_found"


class ClientLoanScheduleUnavailable(ClientLoanError):
    code = "client_loan_schedule_unavailable"


@dataclass(frozen=True, slots=True)
class ClientLoanRecord:
    loan_id: UUID
    loan_number: str
    loan_type_code: str | None
    loan_type_name: str
    principal: Decimal
    daily_amount: Decimal
    interest_rate: Decimal | None
    date_released: date | None
    due_date: date | None
    status: str
    remaining_balance: Decimal
    pass_count: int
    last_payment_date: date | None
    advance_until: date | None
    state_version: int
    payment_count: int

    @property
    def paid_amount(self) -> Decimal:
        paid = self.principal - self.remaining_balance
        return paid if paid > 0 else Decimal("0.00")


@dataclass(frozen=True, slots=True)
class ClientLoanPortfolio:
    client_id: UUID
    client_code: str
    client_name: str
    area: str | None
    client_status: str
    loans: tuple[ClientLoanRecord, ...]


class PostgresClientLoanRepository:
    def list_for_user(self, *, user_id: UUID) -> ClientLoanPortfolio:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id, client_code, full_name, area, status
                    from lending.clients
                    where user_id = %s
                    limit 1
                    """,
                    (user_id,),
                )
                client = cursor.fetchone()
                if not client:
                    raise ClientBorrowerNotLinked(
                        "This client account is not linked to a borrower record."
                    )

                cursor.execute(
                    """
                    select
                        loan.id as loan_id,
                        loan.loan_number,
                        loan_type.code as loan_type_code,
                        coalesce(nullif(btrim(loan_type.name), ''), 'Loan')
                            as loan_type_name,
                        loan.principal,
                        loan.daily_amount,
                        loan.interest_rate,
                        loan.date_released,
                        loan.due_date,
                        loan.status,
                        coalesce(state.remaining_balance, loan.principal)
                            as remaining_balance,
                        coalesce(state.pass_count, 0) as pass_count,
                        state.last_payment_date,
                        state.advance_until,
                        coalesce(state.state_version, 0) as state_version,
                        coalesce(
                            (
                                select count(*)
                                from lending.collection_transactions item
                                where item.loan_id = loan.id
                                  and item.is_voided = false
                                  and item.amount > 0
                            ),
                            0
                        ) as payment_count
                    from lending.loans loan
                    left join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_collection_state state
                      on state.loan_id = loan.id
                    where loan.client_id = %s
                    order by
                        case when lower(loan.status) = 'active' then 0 else 1 end,
                        loan.date_released desc nulls last,
                        loan.created_at desc,
                        loan.id desc
                    """,
                    (client["id"],),
                )
                rows = cursor.fetchall()

        return ClientLoanPortfolio(
            client_id=client["id"],
            client_code=str(client["client_code"]),
            client_name=str(client["full_name"]),
            area=str(client["area"]) if client["area"] else None,
            client_status=str(client["status"]),
            loans=tuple(self._loan_from_row(row) for row in rows),
        )

    def get_schedule_for_user(
        self,
        *,
        user_id: UUID,
        loan_id: UUID,
        as_of_date: date,
    ) -> CollectorScheduleRecord:
        """Read the linked client's persisted operational schedule.

        This path never derives a second schedule. It reads the same
        ``loan_contract_installments_operational`` source and uses the same row
        status builder as Collector View Schedule, with client ownership replacing
        Collector-area authorization.
        """

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id
                    from lending.clients
                    where user_id = %s
                    limit 1
                    """,
                    (user_id,),
                )
                linked_client = cursor.fetchone()
                if linked_client is None:
                    raise ClientBorrowerNotLinked(
                        "This client account is not linked to a borrower record."
                    )

                cursor.execute(
                    """
                    select
                        loan.id as loan_id,
                        loan.loan_number,
                        client.id as client_id,
                        client.full_name as client_name,
                        coalesce(nullif(btrim(loan_type.name), ''), 'Loan') as loan_type,
                        loan_type.calculation_mode,
                        schedule.id as schedule_id,
                        schedule.schedule_version,
                        schedule.payment_frequency,
                        schedule.contract_reference,
                        registration.id as registration_id,
                        coalesce(
                            nullif(
                                to_jsonb(operational_state)
                                    ->> 'active_borrower_extension_slots',
                                ''
                            )::integer,
                            0
                        ) as active_borrower_extension_slots
                    from lending.clients client
                    join lending.loans loan
                      on loan.client_id = client.id
                    left join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_contract_schedules schedule
                      on schedule.loan_id = loan.id
                     and schedule.status = 'active'
                    left join lending.loan_contract_schedule_registrations registration
                      on registration.schedule_id = schedule.id
                    left join lending.loan_schedule_operational_state operational_state
                      on operational_state.schedule_id = schedule.id
                    where client.id = %s
                      and loan.id = %s
                    order by registration.verified_at desc nulls last
                    limit 1
                    """,
                    (linked_client["id"], loan_id),
                )
                loan = cursor.fetchone()
                if loan is None:
                    raise ClientLoanNotFound(
                        "This loan is not linked to the authenticated client account."
                    )
                if loan["schedule_id"] is None or loan["registration_id"] is None:
                    raise ClientLoanScheduleUnavailable(
                        "A verified contractual schedule is not yet available for this loan."
                    )

                cursor.execute(
                    """
                    select
                        installment.id,
                        installment.installment_number,
                        installment.contractual_due_date,
                        installment.effective_due_date,
                        installment.contractual_amount,
                        installment.principal_component,
                        installment.interest_component,
                        coalesce(allocation.paid_amount, 0)::numeric(18,2)
                            as paid_amount,
                        coalesce(allocation.prepaid_amount, 0)::numeric(18,2)
                            as prepaid_amount,
                        coalesce(allocation.principal_reduction_amount, 0)::numeric(18,2)
                            as principal_reduction_amount,
                        coalesce(past_due.current_reason_code, '') as past_due_reason_code,
                        coalesce(past_due.current_reason_note, '') as past_due_reason_note,
                        promise.promised_for_date,
                        coalesce(promise.remaining_promised_amount, 0)::numeric(18,2)
                            as promise_remaining_amount,
                        coalesce(promise.status, '') as promise_status
                    from lending.loan_contract_installments_operational installment
                    left join lateral (
                        select
                            coalesce(sum(item.amount_applied) filter (
                                where transaction.is_voided = false
                                  and item.allocation_basis <> 'voluntary_extra_tail'
                            ), 0)::numeric(18,2) as paid_amount,
                            coalesce(sum(item.amount_applied) filter (
                                where transaction.is_voided = false
                                  and item.allocation_basis <> 'voluntary_extra_tail'
                                  and transaction.collection_date
                                      < installment.effective_due_date
                            ), 0)::numeric(18,2) as prepaid_amount,
                            coalesce(sum(item.amount_applied) filter (
                                where transaction.is_voided = false
                                  and item.allocation_basis = 'voluntary_extra_tail'
                            ), 0)::numeric(18,2) as principal_reduction_amount
                        from lending.loan_installment_payment_allocations item
                        join lending.collection_transactions transaction
                          on transaction.id = item.transaction_id
                        where item.installment_id = installment.id
                    ) allocation on true
                    left join lateral (
                        select
                            obligation.id,
                            obligation.current_reason_code,
                            obligation.current_reason_note
                        from lending.past_due_obligations obligation
                        where obligation.installment_id = installment.id
                          and obligation.remaining_past_due_amount > 0
                        order by
                            obligation.obligation_date desc,
                            obligation.created_at desc,
                            obligation.id desc
                        limit 1
                    ) past_due on true
                    left join lateral (
                        select
                            current_promise.promised_for_date,
                            current_promise.remaining_promised_amount,
                            current_promise.status
                        from lending.payment_promises current_promise
                        join lending.payment_promise_obligations link
                          on link.promise_id = current_promise.id
                        join lending.past_due_obligations obligation
                          on obligation.id = link.past_due_obligation_id
                        where obligation.installment_id = installment.id
                          and current_promise.status = 'pending'
                          and current_promise.remaining_promised_amount > 0
                        order by
                            current_promise.created_at desc,
                            current_promise.id desc
                        limit 1
                    ) promise on true
                    where installment.schedule_id = %s
                    order by
                        installment.effective_due_date,
                        installment.installment_number,
                        installment.id
                    """,
                    (loan["schedule_id"],),
                )
                installment_rows = cursor.fetchall()

                cursor.execute(
                    """
                    select distinct on (adjustment.no_collection_date)
                        adjustment.no_collection_date,
                        adjustment.reason,
                        adjustment.created_at
                    from lending.loan_schedule_adjustments adjustment
                    where adjustment.schedule_id = %s
                      and adjustment.adjustment_type = 'no_collection'
                      and not exists (
                            select 1
                            from lending.loan_schedule_adjustments reversal
                            where reversal.reverses_adjustment_id = adjustment.id
                      )
                    order by
                        adjustment.no_collection_date,
                        adjustment.created_at desc,
                        adjustment.id desc
                    """,
                    (loan["schedule_id"],),
                )
                no_collection_rows = cursor.fetchall()

        rows: list[CollectorScheduleRowRecord] = []
        for row in installment_rows:
            installment = _build_installment_row(
                as_of_date=as_of_date,
                installment_id=int(row["id"]),
                installment_number=int(row["installment_number"]),
                contractual_due_date=row["contractual_due_date"],
                effective_due_date=row["effective_due_date"],
                contractual_amount=_money(row["contractual_amount"]),
                paid_amount=_money(row["paid_amount"]),
                prepaid_amount=_money(row["prepaid_amount"]),
                principal_reduction_amount=_money(row["principal_reduction_amount"]),
                principal_component=(
                    _money(row["principal_component"])
                    if row["principal_component"] is not None
                    else None
                ),
                interest_component=(
                    _money(row["interest_component"])
                    if row["interest_component"] is not None
                    else None
                ),
                past_due_reason_code=str(row["past_due_reason_code"] or ""),
                past_due_reason_note=str(row["past_due_reason_note"] or ""),
                promised_for_date=row["promised_for_date"],
                promise_remaining_amount=_money(row["promise_remaining_amount"]),
                promise_status=str(row["promise_status"] or ""),
            )
            if installment is not None:
                rows.append(installment)

        installment_records = tuple(item for item in rows if item.kind == "installment")
        past_due_rows = tuple(
            item
            for item in installment_records
            if item.schedule_date < as_of_date and item.remaining_amount > ZERO
        )
        past_due_amount = _money(
            sum((item.remaining_amount for item in past_due_rows), ZERO)
        )
        active_extension_slots = int(loan["active_borrower_extension_slots"] or 0)
        base_maturity = max(
            (
                item.contractual_due_date
                for item in installment_records
                if item.contractual_due_date is not None
            ),
            default=None,
        )
        updated_maturity = max(
            (item.schedule_date for item in installment_records),
            default=None,
        )
        if updated_maturity is None:
            maturity_status = "no_current_installments"
        elif active_extension_slots > 0:
            maturity_status = "extended"
        else:
            maturity_status = "on_schedule"

        for row in no_collection_rows:
            rows.append(
                CollectorScheduleRowRecord(
                    kind="no_collection",
                    schedule_date=row["no_collection_date"],
                    status="No Collection",
                    amount=ZERO,
                    contractual_amount=ZERO,
                    paid_amount=ZERO,
                    prepaid_amount=ZERO,
                    remaining_amount=ZERO,
                    no_collection_reason=str(row["reason"] or ""),
                )
            )

        rows.sort(
            key=lambda item: (
                item.schedule_date,
                0 if item.kind == "no_collection" else 1,
                item.installment_number or 0,
            )
        )
        return CollectorScheduleRecord(
            loan_id=loan["loan_id"],
            loan_number=str(loan["loan_number"]),
            client_id=loan["client_id"],
            client_name=str(loan["client_name"]),
            loan_type=str(loan["loan_type"]),
            calculation_mode=str(loan["calculation_mode"] or ""),
            schedule_id=loan["schedule_id"],
            schedule_version=int(loan["schedule_version"]),
            payment_frequency=str(loan["payment_frequency"]),
            contract_reference=str(loan["contract_reference"] or ""),
            as_of_date=as_of_date,
            rows=tuple(rows),
            past_due_amount=past_due_amount,
            past_due_count=len(past_due_rows),
            schedule_extension_slots=active_extension_slots,
            base_maturity=base_maturity,
            updated_maturity=updated_maturity,
            maturity_projection_status=maturity_status,
        )

    @staticmethod
    def _loan_from_row(row) -> ClientLoanRecord:
        return ClientLoanRecord(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_type_code=(
                str(row["loan_type_code"]) if row["loan_type_code"] else None
            ),
            loan_type_name=str(row["loan_type_name"]),
            principal=Decimal(row["principal"]),
            daily_amount=Decimal(row["daily_amount"]),
            interest_rate=(
                Decimal(row["interest_rate"])
                if row["interest_rate"] is not None
                else None
            ),
            date_released=row["date_released"],
            due_date=row["due_date"],
            status=str(row["status"]),
            remaining_balance=Decimal(row["remaining_balance"]),
            pass_count=int(row["pass_count"]),
            last_payment_date=row["last_payment_date"],
            advance_until=row["advance_until"],
            state_version=int(row["state_version"]),
            payment_count=int(row["payment_count"]),
        )
