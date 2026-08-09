from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .eir_cash_allocation import (
    EirAllocationResult,
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
)


MAX_SOURCE_EVENTS = 5000


class EirCashAllocationError(RuntimeError):
    code = "eir_cash_allocation_error"


class EirCashAllocationLoanNotFound(EirCashAllocationError):
    code = "eir_cash_allocation_loan_not_found"


@dataclass(frozen=True, slots=True)
class EirCashAllocationPack:
    loan_id: UUID
    loan_number: str
    client_name: str
    cutover_date: object | None
    opening_balance_posted: bool
    opening_balance_entry_number: str | None
    source_event_count: int
    source_history_complete: bool
    blocker_code: str | None
    blocker_message: str | None
    allocation: EirAllocationResult | None
    automatic_source_posting_enabled: bool = False


class PostgresEirCashAllocationRepository:
    def load_loan_allocation(self, *, loan_id: UUID) -> EirCashAllocationPack:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        l.loan_number,
                        c.full_name as client_name
                    from lending.loans l
                    join lending.clients c on c.id = l.client_id
                    where l.id = %s
                    """,
                    (loan_id,),
                )
                loan = cursor.fetchone()
                if loan is None:
                    raise EirCashAllocationLoanNotFound("Loan was not found.")

                cutover = self._load_current_cutover(cursor)
                if cutover is None:
                    return EirCashAllocationPack(
                        loan_id=loan_id,
                        loan_number=str(loan["loan_number"]),
                        client_name=str(loan["client_name"]),
                        cutover_date=None,
                        opening_balance_posted=False,
                        opening_balance_entry_number=None,
                        source_event_count=0,
                        source_history_complete=True,
                        blocker_code="cutover_required",
                        blocker_message="Create and verify the protected opening-balance cutover before event-date EIR allocation.",
                        allocation=None,
                    )

                cutover_date = cutover["cutover_date"]
                cursor.execute(
                    """
                    select count(*) as same_day_cash_count
                    from lending.collection_transactions t
                    where t.loan_id = %s
                      and t.collection_date = %s
                      and t.is_voided = false
                      and t.entry_type in ('payment', 'advance')
                      and t.amount > 0
                    """,
                    (loan_id, cutover_date),
                )
                same_day_cash_count = int(cursor.fetchone()["same_day_cash_count"])
                if same_day_cash_count > 0:
                    return EirCashAllocationPack(
                        loan_id=loan_id,
                        loan_number=str(loan["loan_number"]),
                        client_name=str(loan["client_name"]),
                        cutover_date=cutover_date,
                        opening_balance_posted=bool(cutover["opening_balance_posted"]),
                        opening_balance_entry_number=(
                            str(cutover["opening_balance_entry_number"])
                            if cutover["opening_balance_entry_number"]
                            else None
                        ),
                        source_event_count=0,
                        source_history_complete=False,
                        blocker_code="cutover_date_cash_review",
                        blocker_message="Cash exists on the date-only cutover boundary. Confirm whether it is included in the protected opening balance before rolling forward post-cutover EIR.",
                        allocation=None,
                    )

                measurement = self._load_measurement(
                    cursor,
                    loan_id=loan_id,
                    cutover_date=cutover_date,
                )
                events = self._load_source_events(
                    cursor,
                    loan_id=loan_id,
                    cutover_date=cutover_date,
                )

        if len(events) > MAX_SOURCE_EVENTS:
            return EirCashAllocationPack(
                loan_id=loan_id,
                loan_number=str(loan["loan_number"]),
                client_name=str(loan["client_name"]),
                cutover_date=cutover_date,
                opening_balance_posted=bool(cutover["opening_balance_posted"]),
                opening_balance_entry_number=(
                    str(cutover["opening_balance_entry_number"])
                    if cutover["opening_balance_entry_number"]
                    else None
                ),
                source_event_count=len(events),
                source_history_complete=False,
                blocker_code="source_history_too_large",
                blocker_message="More than 5,000 post-cutover source events exist for this loan. Allocation is blocked rather than silently truncating history.",
                allocation=None,
            )

        state = EirCutoverState(
            loan_id=loan_id,
            calculation_mode=str(measurement["calculation_mode"] or ""),
            cutover_date=cutover_date,
            due_date=measurement["due_date"],
            measurement_status=str(measurement["measurement_status"] or ""),
            daily_eir=(
                Decimal(measurement["daily_eir"])
                if measurement["daily_eir"] is not None
                else None
            ),
            loan_component=(
                Decimal(measurement["loan_component"])
                if measurement["loan_component"] is not None
                else None
            ),
            accrued_interest_component=(
                Decimal(measurement["accrued_interest_component"])
                if measurement["accrued_interest_component"] is not None
                else None
            ),
            gross_carrying_amount=(
                Decimal(measurement["gross_carrying_amount"])
                if measurement["gross_carrying_amount"] is not None
                else None
            ),
        )
        source_events = tuple(
            EirCashSourceEvent(
                transaction_id=UUID(str(row["transaction_id"])),
                collection_date=row["collection_date"],
                accepted_at=row["accepted_at"],
                entry_type=str(row["entry_type"]),
                amount=Decimal(row["amount"] or 0),
                is_voided=bool(row["is_voided"]),
            )
            for row in events
        )
        allocation = allocate_event_date_eir_cash(state, source_events)
        return EirCashAllocationPack(
            loan_id=loan_id,
            loan_number=str(loan["loan_number"]),
            client_name=str(loan["client_name"]),
            cutover_date=cutover_date,
            opening_balance_posted=bool(cutover["opening_balance_posted"]),
            opening_balance_entry_number=(
                str(cutover["opening_balance_entry_number"])
                if cutover["opening_balance_entry_number"]
                else None
            ),
            source_event_count=len(source_events),
            source_history_complete=True,
            blocker_code=None,
            blocker_message=None,
            allocation=allocation,
        )

    @staticmethod
    def _load_current_cutover(cursor):
        cursor.execute(
            """
            select
                workbook.id as workbook_id,
                workbook.cutover_date,
                (posting.workbook_id is not null) as opening_balance_posted,
                posting.entry_number as opening_balance_entry_number
            from accounting.opening_balance_workbooks workbook
            left join accounting.opening_balance_journal_postings posting
              on posting.workbook_id = workbook.id
            order by workbook.created_at desc
            limit 1
            """
        )
        return cursor.fetchone()

    @staticmethod
    def _load_measurement(cursor, *, loan_id: UUID, cutover_date):
        cursor.execute(
            """
            select *
            from accounting.measure_loan_at_cutover(%s, %s)
            """,
            (loan_id, cutover_date),
        )
        row = cursor.fetchone()
        if row is None:
            raise EirCashAllocationLoanNotFound("Loan measurement source was not found.")
        return row

    @staticmethod
    def _load_source_events(cursor, *, loan_id: UUID, cutover_date):
        cursor.execute(
            """
            select
                t.id as transaction_id,
                t.collection_date,
                t.accepted_at,
                t.entry_type,
                t.amount,
                t.is_voided
            from lending.collection_transactions t
            where t.loan_id = %s
              and t.collection_date > %s
            order by t.collection_date, t.accepted_at, t.id
            limit %s
            """,
            (loan_id, cutover_date, MAX_SOURCE_EVENTS + 1),
        )
        return tuple(cursor.fetchall())
