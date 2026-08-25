from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


class CollectorScheduleError(RuntimeError):
    code = "collector_schedule_error"


class CollectorScheduleNotFound(CollectorScheduleError):
    code = "collector_schedule_not_found"


class CollectorScheduleUnavailable(CollectorScheduleError):
    code = "collector_schedule_unavailable"


@dataclass(frozen=True, slots=True)
class CollectorScheduleRowRecord:
    kind: str
    schedule_date: date
    status: str
    amount: Decimal
    contractual_amount: Decimal
    paid_amount: Decimal
    prepaid_amount: Decimal
    remaining_amount: Decimal
    installment_id: int | None = None
    installment_number: int | None = None
    contractual_due_date: date | None = None
    principal_component: Decimal | None = None
    interest_component: Decimal | None = None
    principal_reduction_amount: Decimal = ZERO
    past_due_reason_code: str = ""
    past_due_reason_note: str = ""
    promised_for_date: date | None = None
    promise_remaining_amount: Decimal = ZERO
    promise_status: str = ""
    no_collection_reason: str = ""


@dataclass(frozen=True, slots=True)
class CollectorScheduleRecord:
    loan_id: UUID
    loan_number: str
    client_id: UUID
    client_name: str
    loan_type: str
    calculation_mode: str
    schedule_id: UUID
    schedule_version: int
    payment_frequency: str
    contract_reference: str
    as_of_date: date
    rows: tuple[CollectorScheduleRowRecord, ...]


def _money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _schedule_status(
    *,
    schedule_date: date,
    as_of_date: date,
    amount: Decimal,
    paid_amount: Decimal,
    prepaid_amount: Decimal,
) -> str:
    if amount <= ZERO:
        return "Paid"
    remaining = max(_money(amount - paid_amount), ZERO)
    if remaining == ZERO:
        if prepaid_amount >= amount:
            return "Paid in Advance"
        return "Paid"
    if paid_amount > ZERO:
        if schedule_date > as_of_date and prepaid_amount > ZERO:
            return "Partially Paid in Advance"
        if schedule_date < as_of_date:
            return "Past Due"
        return "Partial"
    if schedule_date < as_of_date:
        return "Past Due"
    if schedule_date == as_of_date:
        return "Due Today"
    return "Scheduled"


def _build_installment_row(
    *,
    as_of_date: date,
    installment_id: int,
    installment_number: int,
    contractual_due_date: date,
    effective_due_date: date,
    contractual_amount: Decimal,
    paid_amount: Decimal,
    prepaid_amount: Decimal,
    principal_reduction_amount: Decimal,
    principal_component: Decimal | None,
    interest_component: Decimal | None,
    past_due_reason_code: str = "",
    past_due_reason_note: str = "",
    promised_for_date: date | None = None,
    promise_remaining_amount: Decimal = ZERO,
    promise_status: str = "",
) -> CollectorScheduleRowRecord | None:
    original = _money(contractual_amount)
    principal_reduction = min(_money(principal_reduction_amount), original)
    operational_amount = max(_money(original - principal_reduction), ZERO)

    # Principal Reduction changes the current operational schedule rather than
    # becoming a "Paid in Advance" state. Fully removed future tail rows disappear.
    if operational_amount == ZERO and effective_due_date > as_of_date:
        return None

    applied = min(_money(paid_amount), operational_amount)
    prepaid = min(_money(prepaid_amount), applied)
    remaining = max(_money(operational_amount - applied), ZERO)
    return CollectorScheduleRowRecord(
        kind="installment",
        schedule_date=effective_due_date,
        status=_schedule_status(
            schedule_date=effective_due_date,
            as_of_date=as_of_date,
            amount=operational_amount,
            paid_amount=applied,
            prepaid_amount=prepaid,
        ),
        amount=operational_amount,
        contractual_amount=original,
        paid_amount=applied,
        prepaid_amount=prepaid,
        remaining_amount=remaining,
        installment_id=installment_id,
        installment_number=installment_number,
        contractual_due_date=contractual_due_date,
        principal_component=(
            _money(principal_component) if principal_component is not None else None
        ),
        interest_component=(
            _money(interest_component) if interest_component is not None else None
        ),
        principal_reduction_amount=principal_reduction,
        past_due_reason_code=past_due_reason_code,
        past_due_reason_note=past_due_reason_note,
        promised_for_date=promised_for_date,
        promise_remaining_amount=_money(promise_remaining_amount),
        promise_status=promise_status,
    )


class PostgresCollectorScheduleRepository:
    """Read one Collector-owned loan's current operational schedule.

    Signed contractual due dates remain immutable evidence. Management-approved
    No Collection shifts are read through the operational overlay. Regular
    Principal Reduction is presented as the updated remaining schedule, while
    Advance remains visible as prepayment against specific future rows.
    """

    def get_schedule(
        self,
        *,
        collector_user_id: UUID,
        loan_id: UUID,
        as_of_date: date,
    ) -> CollectorScheduleRecord:
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
                        loan_type.calculation_mode,
                        schedule.id as schedule_id,
                        schedule.schedule_version,
                        schedule.payment_frequency,
                        schedule.contract_reference,
                        registration.id as registration_id
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
                    where loan.id = %s
                      and loan.status = 'active'
                      and client.status = 'active'
                      and lending.collector_area_owner(coalesce(client.area, '')) = %s
                      and exists (
                            select 1
                            from lending.collector_area_assignments assignment
                            where assignment.collector_user_id = %s
                              and assignment.is_active = true
                              and lending.area_path_contains(
                                  assignment.area,
                                  coalesce(client.area, ''),
                                  true
                              )
                      )
                    limit 1
                    """,
                    (loan_id, collector_user_id, collector_user_id),
                )
                loan = cursor.fetchone()
                if loan is None:
                    raise CollectorScheduleNotFound(
                        "The selected loan is not on this Collector's active route."
                    )
                if loan["schedule_id"] is None or loan["registration_id"] is None:
                    raise CollectorScheduleUnavailable(
                        "A verified contractual schedule is required before View Schedule is available."
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
        )
