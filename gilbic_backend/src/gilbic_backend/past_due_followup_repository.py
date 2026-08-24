from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from psycopg import errors
from psycopg.rows import dict_row

from .database import open_connection
from .past_due_followup_contracts import (
    PastDueEventKind,
    PastDueReasonBody,
    PastDueReasonCode,
)


MONEY = Decimal("0.01")


class PastDueFollowupError(RuntimeError):
    code = "past_due_followup_error"


class PastDueFollowupNotFound(PastDueFollowupError):
    code = "past_due_followup_not_found"


class PastDueFollowupForbidden(PastDueFollowupError):
    code = "past_due_followup_forbidden"


class PastDueFollowupInvalid(PastDueFollowupError):
    code = "past_due_followup_invalid"


class PastDueFollowupConflict(PastDueFollowupError):
    code = "past_due_followup_conflict"


@dataclass(frozen=True)
class PastDueFollowupRecord:
    id: UUID
    client_id: UUID
    loan_id: UUID
    installment_id: int | None
    obligation_date: date
    original_past_due_amount: Decimal
    remaining_past_due_amount: Decimal
    event_kind: str
    reason_code: str
    reason_note: str
    status: str
    promise_id: UUID | None = None
    promised_payment_date: date | None = None
    initial_promised_amount: Decimal | None = None
    promised_amount: Decimal | None = None
    remaining_promised_amount: Decimal | None = None
    promise_status: str | None = None
    promise_version: int | None = None


class PostgresPastDueFollowupRepository:
    """Persist the reason/history foundation without creating new debt.

    Slice 1 deliberately derives client/loan identity from the already accepted
    collection transaction. This prevents the mobile caller from attaching a
    reason or promise to an arbitrary borrower. Posting integration will call
    the same repository after protected allocation determines the exact unpaid
    obligation and remainder.
    """

    def create_for_collection(
        self,
        *,
        actor_user_id: UUID,
        source_transaction_id: UUID,
        installment_id: int | None,
        obligation_date: date,
        past_due_amount: Decimal,
        event_kind: PastDueEventKind,
        reason: PastDueReasonBody,
    ) -> PastDueFollowupRecord:
        normalized_amount = self._money(past_due_amount)
        if normalized_amount <= Decimal("0.00"):
            raise PastDueFollowupInvalid("Past Due amount must be greater than zero.")

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select
                            transaction.id,
                            transaction.loan_id,
                            transaction.client_id,
                            transaction.collector_user_id,
                            transaction.collection_date,
                            transaction.entry_type,
                            transaction.amount,
                            transaction.is_voided,
                            transaction.is_locked,
                            transaction.remittance_id
                        from lending.collection_transactions transaction
                        where transaction.id = %s
                        for update
                        """,
                        (source_transaction_id,),
                    )
                    transaction = cursor.fetchone()
                    if transaction is None:
                        raise PastDueFollowupNotFound(
                            "The source collection transaction was not found."
                        )
                    if transaction["collector_user_id"] != actor_user_id:
                        raise PastDueFollowupForbidden(
                            "Only the collector who recorded this collection may add its initial Past Due follow-up."
                        )
                    if transaction["is_voided"]:
                        raise PastDueFollowupInvalid(
                            "A voided collection cannot create Past Due follow-up evidence."
                        )
                    if transaction["is_locked"] or transaction["remittance_id"] is not None:
                        raise PastDueFollowupConflict(
                            "This collection is already remitted and locked. Refresh before adding follow-up evidence."
                        )
                    if obligation_date > transaction["collection_date"]:
                        raise PastDueFollowupInvalid(
                            "Past Due obligation date cannot be after the collection date."
                        )

                    entry_type = str(transaction["entry_type"]).strip().lower()
                    transaction_amount = self._money(transaction["amount"])
                    if event_kind is PastDueEventKind.UNABLE_TO_PAY:
                        if entry_type != "pass" or transaction_amount != Decimal("0.00"):
                            raise PastDueFollowupInvalid(
                                "Unable to pay follow-up must come from a zero-cash Unable-to-pay collection entry."
                            )
                    elif event_kind is PastDueEventKind.PARTIAL_PAYMENT:
                        if entry_type != "payment" or transaction_amount <= Decimal("0.00"):
                            raise PastDueFollowupInvalid(
                                "Partial-payment Past Due follow-up must come from a positive payment entry."
                            )

                    if installment_id is not None:
                        cursor.execute(
                            """
                            select installment.id
                            from lending.loan_contract_installments installment
                            join lending.loan_contract_schedules schedule
                              on schedule.id = installment.schedule_id
                            where installment.id = %s
                              and schedule.loan_id = %s
                            """,
                            (installment_id, transaction["loan_id"]),
                        )
                        if cursor.fetchone() is None:
                            raise PastDueFollowupInvalid(
                                "The selected contractual obligation does not belong to this loan."
                            )

                    promise_amount = (
                        self._money(reason.promised_amount)
                        if reason.promised_amount is not None
                        else None
                    )
                    if promise_amount is not None and promise_amount > normalized_amount:
                        raise PastDueFollowupInvalid(
                            "Promised amount cannot exceed this Past Due amount in the initial follow-up record."
                        )
                    if (
                        reason.promised_payment_date is not None
                        and reason.promised_payment_date < transaction["collection_date"]
                    ):
                        raise PastDueFollowupInvalid(
                            "Promised payment date cannot be before the collection date."
                        )

                    cursor.execute(
                        """
                        insert into lending.past_due_obligations (
                            client_id,
                            loan_id,
                            installment_id,
                            obligation_date,
                            original_past_due_amount,
                            remaining_past_due_amount,
                            event_kind,
                            source_transaction_id,
                            current_reason_code,
                            current_reason_note,
                            created_by_user_id
                        )
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        returning id
                        """,
                        (
                            transaction["client_id"],
                            transaction["loan_id"],
                            installment_id,
                            obligation_date,
                            normalized_amount,
                            normalized_amount,
                            event_kind.value,
                            source_transaction_id,
                            reason.reason_code.value,
                            reason.note.strip(),
                            actor_user_id,
                        ),
                    )
                    obligation_id = cursor.fetchone()["id"]

                    promise_id: UUID | None = None
                    promised_payment_date: date | None = None
                    initial_promised_amount: Decimal | None = None
                    current_promised_amount: Decimal | None = None
                    remaining_promised_amount: Decimal | None = None
                    promise_status: str | None = None
                    promise_version: int | None = None

                    if reason.reason_code is PastDueReasonCode.PROMISED_TO_PAY_LATER:
                        assert reason.promised_payment_date is not None
                        assert promise_amount is not None
                        cursor.execute(
                            """
                            select id
                            from lending.payment_promises
                            where client_id = %s
                              and status = 'pending'
                            for update
                            """,
                            (transaction["client_id"],),
                        )
                        if cursor.fetchone() is not None:
                            raise PastDueFollowupConflict(
                                "This client already has an active Pending promise. Update that promise instead of creating another one."
                            )

                        cursor.execute(
                            """
                            insert into lending.payment_promises (
                                client_id,
                                loan_id,
                                promised_for_date,
                                initial_promised_amount,
                                promised_amount,
                                remaining_promised_amount,
                                status,
                                created_by_user_id
                            )
                            values (%s, %s, %s, %s, %s, %s, 'pending', %s)
                            returning id, promised_for_date, initial_promised_amount,
                                      promised_amount, remaining_promised_amount,
                                      status, version
                            """,
                            (
                                transaction["client_id"],
                                transaction["loan_id"],
                                reason.promised_payment_date,
                                promise_amount,
                                promise_amount,
                                promise_amount,
                                actor_user_id,
                            ),
                        )
                        promise = cursor.fetchone()
                        promise_id = promise["id"]
                        promised_payment_date = promise["promised_for_date"]
                        initial_promised_amount = self._money(
                            promise["initial_promised_amount"]
                        )
                        current_promised_amount = self._money(promise["promised_amount"])
                        remaining_promised_amount = self._money(
                            promise["remaining_promised_amount"]
                        )
                        promise_status = str(promise["status"])
                        promise_version = int(promise["version"])

                        cursor.execute(
                            """
                            insert into lending.payment_promise_obligations (
                                promise_id,
                                past_due_obligation_id,
                                target_amount
                            )
                            values (%s, %s, %s)
                            """,
                            (promise_id, obligation_id, promise_amount),
                        )

                    return PastDueFollowupRecord(
                        id=obligation_id,
                        client_id=transaction["client_id"],
                        loan_id=transaction["loan_id"],
                        installment_id=installment_id,
                        obligation_date=obligation_date,
                        original_past_due_amount=normalized_amount,
                        remaining_past_due_amount=normalized_amount,
                        event_kind=event_kind.value,
                        reason_code=reason.reason_code.value,
                        reason_note=reason.note.strip(),
                        status="open",
                        promise_id=promise_id,
                        promised_payment_date=promised_payment_date,
                        initial_promised_amount=initial_promised_amount,
                        promised_amount=current_promised_amount,
                        remaining_promised_amount=remaining_promised_amount,
                        promise_status=promise_status,
                        promise_version=promise_version,
                    )
        except errors.UniqueViolation as error:
            raise PastDueFollowupConflict(
                "This Past Due follow-up or active promise was already recorded. Refresh before retrying."
            ) from error

    @staticmethod
    def _money(value: Decimal | int | str) -> Decimal:
        return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)
