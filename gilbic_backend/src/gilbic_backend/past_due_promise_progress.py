from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


MONEY = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class PastDueReduction:
    obligation_id: UUID
    installment_id: int
    amount_applied: Decimal
    remaining_after: Decimal
    status_after: str


@dataclass(frozen=True, slots=True)
class PromiseProgressChange:
    promise_id: UUID
    remaining_before: Decimal
    remaining_after: Decimal
    status_before: str
    status_after: str


def promise_deadline_status(*, promised_amount: Decimal, remaining_amount: Decimal) -> str:
    """Return the approved terminal status once a promise deadline has passed."""

    promised = _money(promised_amount)
    remaining = _money(remaining_amount)
    if remaining <= Decimal("0.00"):
        return "kept"
    if remaining < promised:
        return "partially_kept"
    return "not_kept"


class PastDuePromiseProgress:
    """Apply actual Past Due allocation to follow-up and promise progress.

    This layer runs only after the protected collection allocator has written its
    installment-allocation rows. It never guesses from receipt cash. Only an
    ``oldest_due_first`` allocation against an installment that already has an
    open Past Due record may reduce that record or a linked Pending promise.

    Pending promises whose date is already before the current collection date are
    closed *before* the new payment is applied. Therefore a late payment can pay
    the underlying Past Due balance but cannot rewrite a missed promise as Kept.
    """

    def apply(
        self,
        connection: Connection[Any],
        *,
        transaction_id: UUID,
        collection_date: date,
    ) -> None:
        reductions: list[PastDueReduction] = []
        promise_changes: list[PromiseProgressChange] = []

        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select
                    id,
                    client_id,
                    loan_id,
                    collector_user_id,
                    entry_type,
                    is_voided
                from lending.collection_transactions
                where id = %s
                for update
                """,
                (transaction_id,),
            )
            transaction = cursor.fetchone()
            if transaction is None or bool(transaction["is_voided"]):
                return

            actor_user_id: UUID = transaction["collector_user_id"]
            client_id: UUID = transaction["client_id"]
            loan_id: UUID = transaction["loan_id"]

            promise_changes.extend(
                self._close_overdue_pending_promises(
                    cursor,
                    client_id=client_id,
                    as_of_date=collection_date,
                    actor_user_id=actor_user_id,
                )
            )

            if str(transaction["entry_type"]).strip().lower() != "payment":
                self._attach_evidence(
                    cursor,
                    transaction_id=transaction_id,
                    reductions=reductions,
                    promise_changes=promise_changes,
                )
                return

            cursor.execute(
                """
                select
                    allocation.installment_id,
                    sum(allocation.amount_applied)::numeric(18,2) as amount_applied
                from lending.loan_installment_payment_allocations allocation
                where allocation.transaction_id = %s
                  and allocation.allocation_basis = 'oldest_due_first'
                group by allocation.installment_id
                order by allocation.installment_id
                """,
                (transaction_id,),
            )
            allocation_rows = cursor.fetchall()
            touched_obligation_ids: list[UUID] = []

            for allocation in allocation_rows:
                installment_id = int(allocation["installment_id"])
                amount_left = _money(allocation["amount_applied"])
                if amount_left <= Decimal("0.00"):
                    continue

                cursor.execute(
                    """
                    select
                        id,
                        remaining_past_due_amount
                    from lending.past_due_obligations
                    where loan_id = %s
                      and installment_id = %s
                      and status = 'open'
                    order by obligation_date, created_at, id
                    for update
                    """,
                    (loan_id, installment_id),
                )
                obligations = cursor.fetchall()

                for obligation in obligations:
                    if amount_left <= Decimal("0.00"):
                        break
                    before = _money(obligation["remaining_past_due_amount"])
                    reduction = _money(min(before, amount_left))
                    if reduction <= Decimal("0.00"):
                        continue
                    after = _money(before - reduction)
                    status_after = "paid" if after == Decimal("0.00") else "open"
                    cursor.execute(
                        """
                        update lending.past_due_obligations
                        set remaining_past_due_amount = %s,
                            status = %s,
                            resolved_at = case when %s = 'paid' then now() else null end,
                            updated_at = now()
                        where id = %s
                        """,
                        (after, status_after, status_after, obligation["id"]),
                    )
                    reductions.append(
                        PastDueReduction(
                            obligation_id=obligation["id"],
                            installment_id=installment_id,
                            amount_applied=reduction,
                            remaining_after=after,
                            status_after=status_after,
                        )
                    )
                    touched_obligation_ids.append(obligation["id"])
                    amount_left = _money(amount_left - reduction)

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
                            'past_due.progress.applied',
                            'past_due_obligation',
                            %s,
                            %s,
                            now()
                        )
                        """,
                        (
                            actor_user_id,
                            obligation["id"],
                            Jsonb(
                                {
                                    "source_transaction_id": str(transaction_id),
                                    "installment_id": installment_id,
                                    "amount_applied": str(reduction),
                                    "remaining_before": str(before),
                                    "remaining_after": str(after),
                                    "status_after": status_after,
                                }
                            ),
                        ),
                    )

            if touched_obligation_ids:
                promise_changes.extend(
                    self._reconcile_pending_promises(
                        cursor,
                        touched_obligation_ids=touched_obligation_ids,
                        actor_user_id=actor_user_id,
                        source_transaction_id=transaction_id,
                    )
                )

            self._attach_evidence(
                cursor,
                transaction_id=transaction_id,
                reductions=reductions,
                promise_changes=promise_changes,
            )

    def _close_overdue_pending_promises(
        self,
        cursor: Any,
        *,
        client_id: UUID,
        as_of_date: date,
        actor_user_id: UUID,
    ) -> list[PromiseProgressChange]:
        cursor.execute(
            """
            select
                id,
                promised_amount,
                remaining_promised_amount,
                status
            from lending.payment_promises
            where client_id = %s
              and status = 'pending'
              and promised_for_date < %s
            order by promised_for_date, created_at, id
            for update
            """,
            (client_id, as_of_date),
        )
        changes: list[PromiseProgressChange] = []
        for promise in cursor.fetchall():
            promised = _money(promise["promised_amount"])
            remaining = _money(promise["remaining_promised_amount"])
            status_after = promise_deadline_status(
                promised_amount=promised,
                remaining_amount=remaining,
            )
            cursor.execute(
                """
                update lending.payment_promises
                set status = %s,
                    closed_at = now(),
                    updated_at = now()
                where id = %s and status = 'pending'
                """,
                (status_after, promise["id"]),
            )
            change = PromiseProgressChange(
                promise_id=promise["id"],
                remaining_before=remaining,
                remaining_after=remaining,
                status_before="pending",
                status_after=status_after,
            )
            changes.append(change)
            self._audit_promise_change(
                cursor,
                actor_user_id=actor_user_id,
                change=change,
                source_transaction_id=None,
                reason="deadline_passed",
            )
        return changes

    def _reconcile_pending_promises(
        self,
        cursor: Any,
        *,
        touched_obligation_ids: list[UUID],
        actor_user_id: UUID,
        source_transaction_id: UUID,
    ) -> list[PromiseProgressChange]:
        cursor.execute(
            """
            select distinct link.promise_id
            from lending.payment_promise_obligations link
            join lending.payment_promises promise on promise.id = link.promise_id
            where link.past_due_obligation_id = any(%s)
              and promise.status = 'pending'
            order by link.promise_id
            """,
            (touched_obligation_ids,),
        )
        promise_ids = [row["promise_id"] for row in cursor.fetchall()]
        changes: list[PromiseProgressChange] = []

        for promise_id in promise_ids:
            cursor.execute(
                """
                select id, promised_amount, remaining_promised_amount, status
                from lending.payment_promises
                where id = %s
                for update
                """,
                (promise_id,),
            )
            promise = cursor.fetchone()
            if promise is None or str(promise["status"]) != "pending":
                continue

            cursor.execute(
                """
                select coalesce(sum(
                    greatest(
                        link.target_amount - least(
                            link.target_amount,
                            greatest(
                                obligation.original_past_due_amount
                                - obligation.remaining_past_due_amount,
                                0
                            )
                        ),
                        0
                    )
                ), 0)::numeric(18,2) as remaining_promised_amount
                from lending.payment_promise_obligations link
                join lending.past_due_obligations obligation
                  on obligation.id = link.past_due_obligation_id
                where link.promise_id = %s
                """,
                (promise_id,),
            )
            progress = cursor.fetchone()
            remaining_before = _money(promise["remaining_promised_amount"])
            remaining_after = _money(
                progress["remaining_promised_amount"]
                if progress is not None
                else remaining_before
            )
            status_after = "kept" if remaining_after == Decimal("0.00") else "pending"
            if remaining_after == remaining_before and status_after == "pending":
                continue

            cursor.execute(
                """
                update lending.payment_promises
                set remaining_promised_amount = %s,
                    status = %s,
                    closed_at = case when %s = 'kept' then now() else null end,
                    updated_at = now()
                where id = %s and status = 'pending'
                """,
                (remaining_after, status_after, status_after, promise_id),
            )
            change = PromiseProgressChange(
                promise_id=promise_id,
                remaining_before=remaining_before,
                remaining_after=remaining_after,
                status_before="pending",
                status_after=status_after,
            )
            changes.append(change)
            self._audit_promise_change(
                cursor,
                actor_user_id=actor_user_id,
                change=change,
                source_transaction_id=source_transaction_id,
                reason="covered_past_due_reduced",
            )
        return changes

    @staticmethod
    def _audit_promise_change(
        cursor: Any,
        *,
        actor_user_id: UUID,
        change: PromiseProgressChange,
        source_transaction_id: UUID | None,
        reason: str,
    ) -> None:
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
                'payment_promise.progress.updated',
                'payment_promise',
                %s,
                %s,
                now()
            )
            """,
            (
                actor_user_id,
                change.promise_id,
                Jsonb(
                    {
                        "source_transaction_id": (
                            str(source_transaction_id)
                            if source_transaction_id is not None
                            else None
                        ),
                        "reason": reason,
                        "remaining_before": str(change.remaining_before),
                        "remaining_after": str(change.remaining_after),
                        "status_before": change.status_before,
                        "status_after": change.status_after,
                    }
                ),
            ),
        )

    @staticmethod
    def _attach_evidence(
        cursor: Any,
        *,
        transaction_id: UUID,
        reductions: list[PastDueReduction],
        promise_changes: list[PromiseProgressChange],
    ) -> None:
        if not reductions and not promise_changes:
            return
        payload = {
            "past_due_reductions": [
                {
                    "obligation_id": str(item.obligation_id),
                    "installment_id": item.installment_id,
                    "amount_applied": str(item.amount_applied),
                    "remaining_after": str(item.remaining_after),
                    "status_after": item.status_after,
                }
                for item in reductions
            ],
            "promise_changes": [
                {
                    "promise_id": str(item.promise_id),
                    "remaining_before": str(item.remaining_before),
                    "remaining_after": str(item.remaining_after),
                    "status_before": item.status_before,
                    "status_after": item.status_after,
                }
                for item in promise_changes
            ],
        }
        cursor.execute(
            """
            update lending.collection_transactions
            set details = coalesce(details, '{}'::jsonb) || %s
            where id = %s and is_locked = false
            """,
            (Jsonb({"past_due_promise_progress": payload}), transaction_id),
        )


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)
