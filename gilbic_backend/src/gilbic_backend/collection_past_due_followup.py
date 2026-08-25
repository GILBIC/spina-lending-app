from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PastDueFollowupInput,
    PastDueReasonCode,
    PostedCollection,
)
from spina_mobile_collections.service import CollectionRejected


MONEY = Decimal("0.01")
CONTRACT_ALLOCATION_SETTING = "mobile_contract_schedule_allocation_enabled"


@dataclass(frozen=True, slots=True)
class CurrentPastDueObligation:
    installment_id: int | None
    obligation_date: date
    remaining_amount: Decimal
    order_key: tuple[date, int]


class CollectionPastDueFollowupWriter:
    """Bind Past Due reason/promise evidence to the real collection transaction.

    This writer is called by the outer collection posting bridge *inside* the
    idempotency executor's PostgreSQL transaction. If required reason evidence is
    missing or invalid, raising ``CollectionRejected`` rolls back the cash receipt,
    balance change, contractual allocation, and follow-up together.

    Regular contractual schedules use exact installment truth after protected
    allocation. Legacy Regular falls back to the remaining daily amount for the
    collection date. 7x7 Unable-to-pay reasons are preserved on the transaction,
    but 7x7 promise/partial-Past-Due amount semantics remain fail-closed until the
    separate 7x7 product rules are finalized.
    """

    def apply(
        self,
        connection: Connection[Any],
        *,
        actor: ActorContext,
        command: CollectionCommand,
        posted: PostedCollection,
    ) -> None:
        if command.entry_type is CollectionEntryType.ADVANCE:
            return

        actor_user_id = self._uuid(actor.account_id, "authenticated collector")
        loan_id = self._uuid(command.loan_id, "loan")
        client_id = self._uuid(command.client_id, "client")
        transaction_id = self._uuid(
            posted.server_transaction_id,
            "collection transaction",
        )

        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select
                    loan.daily_amount,
                    loan_type.calculation_mode,
                    loan_type.settings
                from lending.loans loan
                join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
                where loan.id = %s and loan.client_id = %s
                """,
                (loan_id, client_id),
            )
            loan = cursor.fetchone()
            if loan is None:
                raise CollectionRejected(
                    "The loan changed before Past Due follow-up could be saved. Refresh the route.",
                    code="past_due_followup_loan_changed",
                )

            calculation_mode = str(loan["calculation_mode"] or "").strip()
            if calculation_mode == "seven_by_seven":
                self._apply_seven_by_seven_reason_only(
                    cursor,
                    command=command,
                    transaction_id=transaction_id,
                )
                return

            self._close_expired_pending_promises(
                cursor,
                client_id=client_id,
                collection_date=command.collection_date,
            )
            if command.entry_type is CollectionEntryType.PAYMENT:
                self._sync_contract_past_due_balances(
                    cursor,
                    loan_id=loan_id,
                    collection_date=command.collection_date,
                )
                self._sync_pending_promise_balances(
                    cursor,
                    client_id=client_id,
                    collection_date=command.collection_date,
                )

            settings = loan["settings"] if isinstance(loan["settings"], dict) else {}
            contract_mode = self._setting_enabled(
                settings.get(CONTRACT_ALLOCATION_SETTING)
            )
            obligations = (
                self._contract_current_past_due(
                    cursor,
                    loan_id=loan_id,
                    collection_date=command.collection_date,
                )
                if contract_mode
                else self._legacy_current_past_due(
                    cursor,
                    loan_id=loan_id,
                    collection_date=command.collection_date,
                    daily_amount=self._money(loan["daily_amount"]),
                )
            )

            followup = command.past_due_followup
            if obligations and followup is None:
                raise CollectionRejected(
                    "This collection leaves an unpaid amount for today. Choose a Past Due reason before saving.",
                    code="past_due_reason_required",
                )
            if not obligations:
                if followup is not None:
                    raise CollectionRejected(
                        "No new Past Due amount remains for this collection, so a Past Due reason is not needed.",
                        code="past_due_reason_not_needed",
                    )
                return

            assert followup is not None
            total_past_due = self._money(
                sum((item.remaining_amount for item in obligations), Decimal("0.00"))
            )
            self._validate_followup_amounts(
                followup,
                collection_date=command.collection_date,
                total_past_due=total_past_due,
            )

            event_kind = (
                "unable_to_pay"
                if command.entry_type is CollectionEntryType.PASS
                else "partial_payment"
            )
            created: list[tuple[UUID, Decimal, tuple[date, int]]] = []
            for obligation in obligations:
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
                        client_id,
                        loan_id,
                        obligation.installment_id,
                        obligation.obligation_date,
                        obligation.remaining_amount,
                        obligation.remaining_amount,
                        event_kind,
                        transaction_id,
                        followup.reason_code.value,
                        followup.note.strip(),
                        actor_user_id,
                    ),
                )
                created.append(
                    (
                        cursor.fetchone()["id"],
                        obligation.remaining_amount,
                        obligation.order_key,
                    )
                )

            promise_id: UUID | None = None
            if followup.reason_code is PastDueReasonCode.PROMISED_TO_PAY_LATER:
                promise_id = self._create_promise(
                    cursor,
                    actor_user_id=actor_user_id,
                    client_id=client_id,
                    loan_id=loan_id,
                    followup=followup,
                    obligations=created,
                )

            payload = {
                "event_kind": event_kind,
                "reason_code": followup.reason_code.value,
                "reason_note": followup.note.strip(),
                "past_due_amount": str(total_past_due),
                "past_due_obligation_ids": [str(item[0]) for item in created],
                "promise_id": str(promise_id) if promise_id is not None else None,
                "promised_payment_date": (
                    followup.promised_payment_date.isoformat()
                    if followup.promised_payment_date is not None
                    else None
                ),
                "promised_amount": (
                    str(self._money(followup.promised_amount))
                    if followup.promised_amount is not None
                    else None
                ),
            }
            cursor.execute(
                """
                update lending.collection_transactions
                set details = coalesce(details, '{}'::jsonb) || %s
                where id = %s and is_locked = false
                """,
                (Jsonb({"past_due_followup": payload}), transaction_id),
            )
            cursor.execute(
                """
                insert into core.audit_logs (
                    actor_user_id,
                    action,
                    target_type,
                    target_id,
                    details,
                    created_at
                ) values (
                    %s,
                    'collection.past_due_followup.recorded',
                    'collection_transaction',
                    %s,
                    %s,
                    now()
                )
                """,
                (actor_user_id, transaction_id, Jsonb(payload)),
            )

    def _apply_seven_by_seven_reason_only(
        self,
        cursor: Any,
        *,
        command: CollectionCommand,
        transaction_id: UUID,
    ) -> None:
        followup = command.past_due_followup
        if command.entry_type is CollectionEntryType.PAYMENT:
            if followup is not None:
                raise CollectionRejected(
                    "7x7 partial-payment Past Due follow-up is not enabled yet. The protected 7x7 allocation must remain unchanged.",
                    code="seven_by_seven_partial_followup_not_ready",
                )
            return
        if followup is None:
            raise CollectionRejected(
                "Choose a Past Due reason before saving Unable to pay.",
                code="past_due_reason_required",
            )
        if followup.reason_code is PastDueReasonCode.PROMISED_TO_PAY_LATER:
            raise CollectionRejected(
                "7x7 promise-to-pay amount tracking is not enabled yet. Choose another Past Due reason for now.",
                code="seven_by_seven_promise_not_ready",
            )
        payload = {
            "scope": "seven_by_seven_reason_only",
            "event_kind": "unable_to_pay",
            "reason_code": followup.reason_code.value,
            "reason_note": followup.note.strip(),
        }
        cursor.execute(
            """
            update lending.collection_transactions
            set details = coalesce(details, '{}'::jsonb) || %s
            where id = %s and is_locked = false
            """,
            (Jsonb({"past_due_followup": payload}), transaction_id),
        )

    def _contract_current_past_due(
        self,
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date: date,
    ) -> tuple[CurrentPastDueObligation, ...]:
        cursor.execute(
            """
            select assessment.schedule_id, assessment.dpd_data_status
            from accounting.loan_contract_dpd_assessment assessment
            where assessment.loan_id = %s
            """,
            (loan_id,),
        )
        assessment = cursor.fetchone()
        if (
            assessment is None
            or assessment["schedule_id"] is None
            or str(assessment["dpd_data_status"] or "") != "ready"
        ):
            raise CollectionRejected(
                "The contractual schedule is not ready to determine the exact Past Due remainder.",
                code="past_due_contract_not_ready",
            )

        cursor.execute(
            """
            select
                installment.id,
                installment.installment_number,
                installment.effective_due_date,
                installment.contractual_amount,
                coalesce(sum(allocation.amount_applied) filter (
                    where allocation_transaction.is_voided = false
                ), 0)::numeric(18,2) as allocated_amount
            from lending.loan_contract_installments_operational installment
            left join lending.loan_installment_payment_allocations allocation
              on allocation.installment_id = installment.id
            left join lending.collection_transactions allocation_transaction
              on allocation_transaction.id = allocation.transaction_id
            where installment.schedule_id = %s
              and installment.effective_due_date = %s
            group by
                installment.id,
                installment.installment_number,
                installment.effective_due_date,
                installment.contractual_amount
            order by installment.installment_number, installment.id
            """,
            (assessment["schedule_id"], collection_date),
        )
        result: list[CurrentPastDueObligation] = []
        for row in cursor.fetchall():
            remaining = self._money(
                max(
                    Decimal("0.00"),
                    Decimal(row["contractual_amount"]) - Decimal(row["allocated_amount"]),
                )
            )
            if remaining <= Decimal("0.00"):
                continue
            result.append(
                CurrentPastDueObligation(
                    installment_id=int(row["id"]),
                    obligation_date=row["effective_due_date"],
                    remaining_amount=remaining,
                    order_key=(row["effective_due_date"], int(row["installment_number"])),
                )
            )
        return tuple(result)

    def _legacy_current_past_due(
        self,
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date: date,
        daily_amount: Decimal,
    ) -> tuple[CurrentPastDueObligation, ...]:
        cursor.execute(
            """
            select coalesce(sum(applied_amount), 0)::numeric(18,2) as applied_amount
            from lending.collection_transactions
            where loan_id = %s
              and collection_date = %s
              and entry_type = 'payment'
              and is_voided = false
            """,
            (loan_id, collection_date),
        )
        row = cursor.fetchone()
        applied = self._money(row["applied_amount"] if row else Decimal("0.00"))
        remaining = self._money(max(Decimal("0.00"), daily_amount - applied))
        if remaining <= Decimal("0.00"):
            return ()
        return (
            CurrentPastDueObligation(
                installment_id=None,
                obligation_date=collection_date,
                remaining_amount=remaining,
                order_key=(collection_date, 0),
            ),
        )

    def _create_promise(
        self,
        cursor: Any,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        loan_id: UUID,
        followup: PastDueFollowupInput,
        obligations: list[tuple[UUID, Decimal, tuple[date, int]]],
    ) -> UUID:
        assert followup.promised_payment_date is not None
        assert followup.promised_amount is not None
        promised_amount = self._money(followup.promised_amount)

        cursor.execute(
            """
            select id
            from lending.payment_promises
            where client_id = %s and status = 'pending'
            for update
            """,
            (client_id,),
        )
        if cursor.fetchone() is not None:
            raise CollectionRejected(
                "This client already has an active Pending promise. Update that promise instead of creating another one.",
                code="active_payment_promise_exists",
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
            returning id
            """,
            (
                client_id,
                loan_id,
                followup.promised_payment_date,
                promised_amount,
                promised_amount,
                promised_amount,
                actor_user_id,
            ),
        )
        promise_id = cursor.fetchone()["id"]

        remaining_target = promised_amount
        for obligation_id, obligation_amount, _ in sorted(
            obligations,
            key=lambda item: item[2],
        ):
            if remaining_target <= Decimal("0.00"):
                break
            target = min(obligation_amount, remaining_target)
            cursor.execute(
                """
                insert into lending.payment_promise_obligations (
                    promise_id,
                    past_due_obligation_id,
                    target_amount
                ) values (%s, %s, %s)
                """,
                (promise_id, obligation_id, target),
            )
            remaining_target = self._money(remaining_target - target)

        if remaining_target != Decimal("0.00"):
            raise CollectionRejected(
                "The promised amount could not be mapped to the new Past Due remainder.",
                code="promised_amount_mapping_failed",
            )
        return promise_id

    def _close_expired_pending_promises(
        self,
        cursor: Any,
        *,
        client_id: UUID,
        collection_date: date,
    ) -> None:
        cursor.execute(
            """
            select id, promised_amount, remaining_promised_amount
            from lending.payment_promises
            where client_id = %s
              and status = 'pending'
              and promised_for_date < %s
            for update
            """,
            (client_id, collection_date),
        )
        for row in cursor.fetchall():
            promised = self._money(row["promised_amount"])
            remaining = self._money(row["remaining_promised_amount"])
            status = "not_kept" if remaining >= promised else "partially_kept"
            if remaining <= Decimal("0.00"):
                status = "kept"
            cursor.execute(
                """
                update lending.payment_promises
                set status = %s,
                    closed_at = now(),
                    updated_at = now()
                where id = %s and status = 'pending'
                """,
                (status, row["id"]),
            )

    def _sync_contract_past_due_balances(
        self,
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date: date,
    ) -> None:
        cursor.execute(
            """
            select
                obligation.id,
                obligation.original_past_due_amount,
                installment.contractual_amount,
                coalesce(sum(allocation.amount_applied) filter (
                    where allocation_transaction.is_voided = false
                ), 0)::numeric(18,2) as allocated_amount
            from lending.past_due_obligations obligation
            join lending.loan_contract_installments_operational installment
              on installment.id = obligation.installment_id
            left join lending.loan_installment_payment_allocations allocation
              on allocation.installment_id = installment.id
            left join lending.collection_transactions allocation_transaction
              on allocation_transaction.id = allocation.transaction_id
            where obligation.loan_id = %s
              and obligation.status = 'open'
              and obligation.installment_id is not null
              and obligation.obligation_date < %s
            group by obligation.id, installment.id, installment.contractual_amount
            for update of obligation
            """,
            (loan_id, collection_date),
        )
        for row in cursor.fetchall():
            actual_remaining = self._money(
                max(
                    Decimal("0.00"),
                    Decimal(row["contractual_amount"]) - Decimal(row["allocated_amount"]),
                )
            )
            remaining = min(
                self._money(row["original_past_due_amount"]),
                actual_remaining,
            )
            if remaining <= Decimal("0.00"):
                cursor.execute(
                    """
                    update lending.past_due_obligations
                    set remaining_past_due_amount = 0,
                        status = 'paid',
                        resolved_at = now(),
                        updated_at = now()
                    where id = %s and status = 'open'
                    """,
                    (row["id"],),
                )
            else:
                cursor.execute(
                    """
                    update lending.past_due_obligations
                    set remaining_past_due_amount = %s,
                        updated_at = now()
                    where id = %s and status = 'open'
                    """,
                    (remaining, row["id"]),
                )

    def _sync_pending_promise_balances(
        self,
        cursor: Any,
        *,
        client_id: UUID,
        collection_date: date,
    ) -> None:
        cursor.execute(
            """
            select
                promise.id,
                promise.promised_for_date,
                promise.promised_amount,
                coalesce(sum(
                    greatest(
                        link.target_amount - greatest(
                            obligation.original_past_due_amount
                            - obligation.remaining_past_due_amount,
                            0
                        ),
                        0
                    )
                ), 0)::numeric(18,2) as remaining_target
            from lending.payment_promises promise
            join lending.payment_promise_obligations link
              on link.promise_id = promise.id
            join lending.past_due_obligations obligation
              on obligation.id = link.past_due_obligation_id
            where promise.client_id = %s
              and promise.status = 'pending'
            group by promise.id
            for update of promise
            """,
            (client_id,),
        )
        for row in cursor.fetchall():
            remaining = self._money(row["remaining_target"])
            if remaining <= Decimal("0.00"):
                # Expired promises were closed before this payment was applied, so
                # only an on-time/early pending promise can become Kept here.
                cursor.execute(
                    """
                    update lending.payment_promises
                    set remaining_promised_amount = 0,
                        status = 'kept',
                        closed_at = now(),
                        updated_at = now()
                    where id = %s and status = 'pending'
                    """,
                    (row["id"],),
                )
            else:
                cursor.execute(
                    """
                    update lending.payment_promises
                    set remaining_promised_amount = %s,
                        updated_at = now()
                    where id = %s and status = 'pending'
                    """,
                    (remaining, row["id"]),
                )

    def _validate_followup_amounts(
        self,
        followup: PastDueFollowupInput,
        *,
        collection_date: date,
        total_past_due: Decimal,
    ) -> None:
        if followup.reason_code is PastDueReasonCode.OTHER and not followup.note.strip():
            raise CollectionRejected(
                "Other Past Due reason requires a short explanation.",
                code="past_due_other_note_required",
            )
        if followup.reason_code is not PastDueReasonCode.PROMISED_TO_PAY_LATER:
            return
        if followup.promised_payment_date is None or followup.promised_amount is None:
            raise CollectionRejected(
                "Promised to pay later requires a date and promised amount.",
                code="promise_details_required",
            )
        if followup.promised_payment_date < collection_date:
            raise CollectionRejected(
                "Promised payment date cannot be before the collection date.",
                code="promised_payment_date_invalid",
            )
        promised = self._money(followup.promised_amount)
        if promised <= Decimal("0.00") or promised > total_past_due:
            raise CollectionRejected(
                "Promised amount must be greater than zero and cannot exceed the new Past Due amount.",
                code="promised_amount_invalid",
            )

    @staticmethod
    def _setting_enabled(value: object) -> bool:
        if value is True:
            return True
        return str(value or "").strip().lower() in {"true", "1", "yes", "on"}

    @staticmethod
    def _money(value: Decimal | int | str | None) -> Decimal:
        return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)

    @staticmethod
    def _uuid(value: str, label: str) -> UUID:
        try:
            return UUID(str(value).strip())
        except (ValueError, AttributeError) as error:
            raise CollectionRejected(
                f"The {label} information is invalid. Refresh and try again.",
                code="invalid_collection_reference",
            ) from error
