from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from .seven_by_seven_operational_allocator import (
    ZERO,
    SevenBySevenAllocationError,
    SevenBySevenAllocationResult,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
    money,
)


FUTURE_ADVANCE_BASIS = "future_advance_oldest_first"


class SevenBySevenAdvanceActivationError(RuntimeError):
    code = "seven_by_seven_advance_activation_conflict"


@dataclass(frozen=True, slots=True)
class SevenBySevenAdvanceFinancialReplay:
    historical_events: tuple[SevenBySevenCashEvent, ...]
    result: SevenBySevenAllocationResult
    matured_advance_row_count: int
    interest_holiday_dates: tuple[date, ...]


def _financial_transaction_watermark(cursor: Any, *, loan_id: UUID) -> date | None:
    cursor.execute(
        """
        select max(transaction.collection_date)
        from lending.collection_transactions transaction
        where transaction.loan_id = %s
          and transaction.is_voided = false
          and transaction.amount > 0
          and transaction.entry_type in ('payment', 'advance')
        """,
        (loan_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return next(iter(row.values()))
    return row[0]


def _active_no_collection_interest_holidays(
    cursor: Any,
    *,
    loan_id: UUID,
    through_date: date,
) -> tuple[date, ...]:
    """Return active Management NC dates that still carry zero 7x7 interest.

    A Management declaration remains immutable history after a borrower later
    completes that affected installment voluntarily. The separate completion
    evidence changes only the operational/financial effect for that loan/date,
    so that date is no longer supplied to the allocator as an interest holiday.
    A voided completion receipt does not suppress the original holiday.
    """

    cursor.execute(
        """
        select distinct adjustment.no_collection_date
        from lending.loan_schedule_adjustments adjustment
        where adjustment.loan_id = %s
          and adjustment.adjustment_type = 'no_collection'
          and adjustment.no_collection_date <= %s
          and not exists (
                select 1
                from lending.loan_schedule_adjustments reversal
                where reversal.reverses_adjustment_id = adjustment.id
          )
          and not exists (
                select 1
                from lending.loan_no_collection_voluntary_completions completion
                join lending.collection_transactions completion_transaction
                  on completion_transaction.id = completion.transaction_id
                where completion.no_collection_adjustment_id = adjustment.id
                  and completion_transaction.is_voided = false
          )
        order by adjustment.no_collection_date
        """,
        (loan_id, through_date),
    )
    rows = cursor.fetchall()
    holidays: list[date] = []
    for row in rows:
        if isinstance(row, dict):
            holidays.append(row["no_collection_date"])
        else:
            holidays.append(row[0])
    return tuple(holidays)


def _immediate_financial_receipt_amount(
    *,
    receipt_amount: Decimal | int | str,
    deferred_amount: Decimal | int | str,
) -> Decimal:
    """Return cash that is financially active on the physical receipt date.

    ``future_advance_oldest_first`` is also the protected evidence basis for a
    partial voluntary payment toward a shifted No Collection installment. That
    part of a PAYMENT remains custody cash today but must not reduce principal or
    earn the shifted row's interest until the row becomes financially effective.
    """

    receipt = money(receipt_amount)
    deferred = money(deferred_amount)
    if deferred < ZERO or deferred > receipt:
        raise SevenBySevenAdvanceActivationError(
            "Deferred 7x7 prepayment evidence does not reconcile to its source receipt."
        )
    return money(receipt - deferred)


def replay_verified_seven_by_seven_financial_state(
    cursor: Any,
    *,
    loan_id: UUID,
    original_principal: Decimal | int | str,
    daily_interest_per_1000: Decimal | int | str,
    payment_start: date,
    through_date: date,
) -> SevenBySevenAdvanceFinancialReplay:
    """Replay immediate cash plus matured verified prepayment as cash events.

    A verified Advance receipt is deliberately excluded on its receipt date.
    The same deferred basis may also represent the affected portion of a partial
    voluntary PAYMENT on a Management No Collection day. For PAYMENT, only the
    receipt amount not attached to deferred future-row evidence is financially
    active immediately; the deferred portion later activates with its signed row.

    Each signed future row becomes a synthetic operational cash event only on
    that row's effective due date. Multiple partial prepayments attached to the
    same signed row are aggregated into one due-date activation event.

    Management No Collection dates remain zero-interest holidays unless immutable
    voluntary-completion evidence exists for that exact declaration and its source
    receipt is still non-voided. Because prepayment stays attached to installment
    id while operational dates move, financial activation follows the authoritative
    effective date automatically.
    """

    cursor.execute(
        """
        select
            transaction.id,
            transaction.collection_date,
            transaction.entry_type,
            transaction.amount as receipt_amount,
            coalesce(sum(allocation.amount_applied) filter (
                where allocation.allocation_basis = %s
            ), 0)::numeric(18,2) as deferred_amount,
            transaction.accepted_at
        from lending.collection_transactions transaction
        left join lending.loan_installment_payment_allocations allocation
          on allocation.transaction_id = transaction.id
        where transaction.loan_id = %s
          and transaction.is_voided = false
          and transaction.amount > 0
          and transaction.collection_date <= %s
          and transaction.entry_type in ('payment', 'advance')
        group by
            transaction.id,
            transaction.collection_date,
            transaction.entry_type,
            transaction.amount,
            transaction.accepted_at
        order by transaction.collection_date, transaction.accepted_at, transaction.id
        """,
        (FUTURE_ADVANCE_BASIS, loan_id, through_date),
    )
    actual_rows = cursor.fetchall()

    cursor.execute(
        """
        select
            installment.id as installment_id,
            installment.installment_number,
            installment.effective_due_date,
            sum(allocation.amount_applied)::numeric(18,2) as amount_applied,
            min(prepayment_transaction.accepted_at) as first_accepted_at
        from lending.loan_installment_payment_allocations allocation
        join lending.collection_transactions prepayment_transaction
          on prepayment_transaction.id = allocation.transaction_id
        join lending.loan_contract_installments_operational installment
          on installment.id = allocation.installment_id
        where prepayment_transaction.loan_id = %s
          and prepayment_transaction.is_voided = false
          and allocation.allocation_basis = %s
          and installment.effective_due_date <= %s
        group by
            installment.id,
            installment.installment_number,
            installment.effective_due_date
        order by installment.effective_due_date, installment.installment_number
        """,
        (loan_id, FUTURE_ADVANCE_BASIS, through_date),
    )
    matured_rows = cursor.fetchall()

    ordered: list[tuple[date, int, object, str, SevenBySevenCashEvent]] = []
    for row in actual_rows:
        if isinstance(row, dict):
            transaction_id = row["id"]
            collection_date = row["collection_date"]
            entry_type = str(row["entry_type"])
            receipt_amount = money(row["receipt_amount"])
            deferred_amount = money(row["deferred_amount"])
            accepted_at = row["accepted_at"]
        else:
            (
                transaction_id,
                collection_date,
                entry_type,
                receipt_value,
                deferred_value,
                accepted_at,
            ) = row
            entry_type = str(entry_type)
            receipt_amount = money(receipt_value)
            deferred_amount = money(deferred_value)

        immediate_amount = _immediate_financial_receipt_amount(
            receipt_amount=receipt_amount,
            deferred_amount=deferred_amount,
        )
        if entry_type == "advance" and deferred_amount not in {ZERO, receipt_amount}:
            raise SevenBySevenAdvanceActivationError(
                "A verified 7x7 Advance receipt is only partly attached to future signed rows. Management reconciliation is required."
            )
        if immediate_amount <= ZERO:
            continue

        ordered.append(
            (
                collection_date,
                1,
                accepted_at,
                str(transaction_id),
                SevenBySevenCashEvent(
                    event_id=str(transaction_id),
                    collection_date=collection_date,
                    amount=immediate_amount,
                ),
            )
        )

    for row in matured_rows:
        if isinstance(row, dict):
            installment_id = row["installment_id"]
            installment_number = int(row["installment_number"])
            effective_due_date = row["effective_due_date"]
            amount_applied = row["amount_applied"]
            first_accepted_at = row["first_accepted_at"]
        else:
            (
                installment_id,
                installment_number,
                effective_due_date,
                amount_applied,
                first_accepted_at,
            ) = row
        ordered.append(
            (
                effective_due_date,
                0,
                first_accepted_at,
                f"{installment_number:09d}:{installment_id}",
                SevenBySevenCashEvent(
                    event_id=f"advance-activation:{installment_id}",
                    collection_date=effective_due_date,
                    amount=money(amount_applied),
                ),
            )
        )

    ordered.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    events = tuple(item[4] for item in ordered)
    holidays = _active_no_collection_interest_holidays(
        cursor,
        loan_id=loan_id,
        through_date=through_date,
    )
    try:
        result = allocate_seven_by_seven_payments(
            original_principal=original_principal,
            daily_interest_per_1000=daily_interest_per_1000,
            payment_start=payment_start,
            events=events,
            interest_holiday_dates=holidays,
        )
    except SevenBySevenAllocationError as error:
        raise SevenBySevenAdvanceActivationError(
            "Verified 7x7 prepayment cannot be activated against the protected financial history."
        ) from error

    if result.total_unallocated_cash > ZERO:
        raise SevenBySevenAdvanceActivationError(
            "A matured 7x7 prepayment would leave unapplied cash. Management must review "
            "the unused Advance/prepayment before financial activation continues."
        )

    return SevenBySevenAdvanceFinancialReplay(
        historical_events=events,
        result=result,
        matured_advance_row_count=len(matured_rows),
        interest_holiday_dates=holidays,
    )


def reconcile_verified_seven_by_seven_advance_before_collection(
    cursor: Any,
    *,
    loan: dict[str, Any],
    through_date: date,
) -> SevenBySevenAdvanceFinancialReplay:
    """Bring principal state forward through matured prepayment before new cash.

    The last accepted financial receipt is the reconciliation watermark: every
    accepted PAYMENT/ADVANCE on this protected path leaves state equal to the
    replay through that receipt date. New matured prepayment rows between that
    watermark and ``through_date`` may then reduce principal, while original
    receipt evidence remains immutable and no future interest is recognized
    before the effective due date.
    """

    loan_id = loan["loan_id"]
    payment_start = loan["date_released"] + timedelta(days=1)
    watermark = _financial_transaction_watermark(cursor, loan_id=loan_id)
    if watermark is not None and through_date < watermark:
        raise SevenBySevenAdvanceActivationError(
            "A 7x7 collection cannot be financially activated before the latest accepted receipt date."
        )

    baseline_date = watermark if watermark is not None else payment_start - timedelta(days=1)
    baseline = replay_verified_seven_by_seven_financial_state(
        cursor,
        loan_id=loan_id,
        original_principal=money(loan["principal"]),
        daily_interest_per_1000=money(loan["daily_interest_per_1000"]),
        payment_start=payment_start,
        through_date=baseline_date,
    )
    stored_balance = money(loan["remaining_balance"])
    if baseline.result.closing_remaining_principal != stored_balance:
        raise SevenBySevenAdvanceActivationError(
            "The 7x7 balance no longer matches the protected financial replay at the "
            "last accepted receipt. Management reconciliation is required."
        )

    current = replay_verified_seven_by_seven_financial_state(
        cursor,
        loan_id=loan_id,
        original_principal=money(loan["principal"]),
        daily_interest_per_1000=money(loan["daily_interest_per_1000"]),
        payment_start=payment_start,
        through_date=through_date,
    )
    activated_balance = current.result.closing_remaining_principal
    if activated_balance > stored_balance:
        raise SevenBySevenAdvanceActivationError(
            "7x7 prepayment activation would increase principal. Management review is required."
        )

    if activated_balance != stored_balance:
        cursor.execute(
            """
            update lending.loan_collection_state
            set remaining_balance = %s,
                updated_at = now()
            where loan_id = %s
            """,
            (activated_balance, loan_id),
        )
        if cursor.rowcount != 1:
            raise SevenBySevenAdvanceActivationError(
                "The 7x7 collection state could not be activated exactly once."
            )
        loan["remaining_balance"] = activated_balance

    return current
