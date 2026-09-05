from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PostedCollection,
)

from .borrower_schedule_adjustment_repository import (
    BorrowerScheduleAdjustmentConflict,
    PostgresBorrowerScheduleAdjustmentRepository,
)
from .collection_past_due_capture import CollectionPastDueCapture
from .past_due_promise_progress import PastDuePromiseProgress
from .voluntary_extra_collection_posting import (
    VoluntaryExtraAwareCollectionPostingBridge,
)


class ConcurrentReceiptSafeCollectionPostingBridge(
    VoluntaryExtraAwareCollectionPostingBridge
):
    """Allow a narrowly proven stale route revision for a real same-day receipt.

    Distinct physical receipts are different transactions, even when two collectors
    started from the same route snapshot. The first accepted receipt increments the
    loan state version, so the second request may arrive with a now-stale revision.

    We never ignore stale revisions generally. Before delegating to the existing
    posting bridge, a normal PAYMENT may be rebased only when every intervening
    state-version increment is proven by an accepted, non-voided PAYMENT receipt for
    this exact loan and collection date. Any gap preserves the normal stale-route
    conflict, which keeps schedule changes, No Collection changes, PASS entries,
    corrections, reversals and unknown state changes fail-closed.

    After the protected product allocator succeeds, a fully completed normal
    borrower catch-up allocation contracts the remaining operational schedule in
    this same PostgreSQL transaction. Existing Past Due/promise progress is then
    reconciled from the allocator's actual installment rows, followed by capture of
    any new Past Due remainder. Any failure rolls the receipt, allocations, schedule
    contraction, and follow-up evidence back together.
    """

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        prepared = self._prepare_same_day_payment_revision(
            connection,
            actor=actor,
            command=command,
        )
        posted = super().post_collection(connection, actor, prepared)
        self._apply_followup_layers(
            connection,
            actor=actor,
            command=prepared,
            posted=posted,
        )
        return posted

    def _apply_followup_layers(
        self,
        connection: Connection[Any],
        *,
        actor: ActorContext,
        command: CollectionCommand,
        posted: PostedCollection,
    ) -> None:
        """Contract completed catch-up, then reconcile existing Past Due evidence."""

        self._apply_borrower_catchup_contraction(
            connection,
            actor=actor,
            command=command,
            posted=posted,
        )
        PastDuePromiseProgress().apply(
            connection,
            transaction_id=self._uuid(
                posted.server_transaction_id,
                "collection transaction",
            ),
            collection_date=command.collection_date,
        )
        CollectionPastDueCapture().apply(
            connection,
            actor=actor,
            command=command,
            posted=posted,
        )

    def _apply_borrower_catchup_contraction(
        self,
        connection: Connection[Any],
        *,
        actor: ActorContext,
        command: CollectionCommand,
        posted: PostedCollection,
    ) -> None:
        if command.entry_type is not CollectionEntryType.PAYMENT:
            return

        transaction_id = self._uuid(
            posted.server_transaction_id,
            "collection transaction",
        )
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select
                    installment.schedule_id,
                    installment.id as installment_id,
                    installment.installment_number,
                    greatest(
                        installment.contractual_amount
                        - coalesce(sum(allocation_all.amount_applied) filter (
                            where allocation_transaction.is_voided = false
                        ), 0),
                        0
                    )::numeric(18,2) as remaining_amount
                from lending.loan_installment_payment_allocations catchup
                join lending.loan_contract_installments installment
                  on installment.id = catchup.installment_id
                left join lending.loan_installment_payment_allocations allocation_all
                  on allocation_all.installment_id = installment.id
                left join lending.collection_transactions allocation_transaction
                  on allocation_transaction.id = allocation_all.transaction_id
                where catchup.transaction_id = %s
                  and catchup.allocation_basis = 'borrower_catch_up_oldest_first'
                group by
                    installment.schedule_id,
                    installment.id,
                    installment.installment_number,
                    installment.contractual_amount
                having greatest(
                    installment.contractual_amount
                    - coalesce(sum(allocation_all.amount_applied) filter (
                        where allocation_transaction.is_voided = false
                    ), 0),
                    0
                ) = 0
                order by installment.installment_number, installment.id
                """,
                (transaction_id,),
            )
            completed = cursor.fetchall()
            if not completed:
                return

            schedule_ids = {row["schedule_id"] for row in completed}
            if len(schedule_ids) != 1:
                raise BorrowerScheduleAdjustmentConflict(
                    "Borrower catch-up allocations must belong to one active schedule."
                )
            schedule_id = next(iter(schedule_ids))
            cursor.execute(
                """
                select operational_version
                from lending.loan_schedule_operational_state
                where schedule_id = %s
                for update
                """,
                (schedule_id,),
            )
            state = cursor.fetchone()
            if state is None:
                raise BorrowerScheduleAdjustmentConflict(
                    "Borrower catch-up requires operational schedule state."
                )
            operational_version = int(state["operational_version"])

        PostgresBorrowerScheduleAdjustmentRepository().record_catchup_in_transaction(
            connection,
            actor_user_id=self._uuid(actor.account_id, "authenticated collector"),
            loan_id=self._uuid(command.loan_id, "loan"),
            event_date=command.collection_date,
            expected_operational_version=operational_version,
            completed_catchup_installment_ids=tuple(
                int(row["installment_id"]) for row in completed
            ),
            # The official payment already advances loan_collection_state once;
            # keep that one revision as the identity of this atomic receipt +
            # schedule mutation so the returned route_revision remains current.
            invalidate_collection_state=False,
        )

    def _prepare_same_day_payment_revision(
        self,
        connection: Connection[Any],
        *,
        actor: ActorContext,
        command: CollectionCommand,
    ) -> CollectionCommand:
        if command.entry_type is not CollectionEntryType.PAYMENT:
            return command

        loan_id = self._uuid(command.loan_id, "loan")
        expected_version = self._route_revision_state_version(
            route_revision=command.route_revision,
            loan_id=loan_id,
        )
        if expected_version is None:
            return command

        registered_device_id = self._uuid(
            actor.storage_device_id,
            "registered device",
        )

        # Match the existing mobile posting lock order before reading the state:
        # device-sequence advisory lock -> loan/date advisory lock -> loan/state
        # row lock. The locks remain transaction-scoped while super() performs
        # the official write, so a third receipt cannot slip into the proof gap.
        with connection.cursor(row_factory=dict_row) as cursor:
            self._lock_device_sequence(
                cursor,
                registered_device_id=registered_device_id,
                device_sequence=command.device_sequence,
            )
            self._lock_loan_date(
                cursor,
                loan_id=loan_id,
                collection_date=command.collection_date,
            )
            cursor.execute(
                """
                select state.state_version
                from lending.loans loan
                join lending.loan_collection_state state
                  on state.loan_id = loan.id
                where loan.id = %s
                for update of loan, state
                """,
                (loan_id,),
            )
            row = cursor.fetchone()
            if row is None:
                # Let the authoritative base bridge create/validate missing state.
                return command

            current_version = int(row["state_version"])
            if expected_version == current_version:
                return command
            if expected_version > current_version:
                return command

            if not self._same_day_payment_revision_chain_is_safe(
                cursor,
                loan_id=loan_id,
                collection_date=command.collection_date,
                expected_version=expected_version,
                current_version=current_version,
            ):
                return command

        return replace(
            command,
            route_revision=self._route_revision(
                loan_id=loan_id,
                state_version=current_version,
            ),
        )

    @staticmethod
    def _route_revision_state_version(
        *,
        route_revision: str | None,
        loan_id: UUID,
    ) -> int | None:
        value = str(route_revision or "").strip()
        prefix = f"loan:{loan_id}:v"
        if not value.startswith(prefix):
            return None
        suffix = value[len(prefix) :]
        if not suffix.isdigit():
            return None
        return int(suffix)

    @staticmethod
    def _same_day_payment_revision_chain_is_safe(
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date,
        expected_version: int,
        current_version: int,
    ) -> bool:
        if expected_version >= current_version:
            return expected_version == current_version

        cursor.execute(
            """
            select
                (receipt.details->>'state_version_before')::integer
                    as state_version_before,
                (receipt.details->>'state_version_after')::integer
                    as state_version_after
            from lending.collection_transactions receipt
            where receipt.loan_id = %s
              and receipt.collection_date = %s
              and receipt.entry_type = 'payment'
              and receipt.is_voided = false
              and receipt.details ? 'state_version_before'
              and receipt.details ? 'state_version_after'
              and (receipt.details->>'state_version_before') ~ '^[0-9]+$'
              and (receipt.details->>'state_version_after') ~ '^[0-9]+$'
              and (receipt.details->>'state_version_before')::integer >= %s
              and (receipt.details->>'state_version_after')::integer <= %s
            order by
                (receipt.details->>'state_version_before')::integer,
                receipt.accepted_at,
                receipt.id
            """,
            (
                loan_id,
                collection_date,
                expected_version,
                current_version,
            ),
        )
        rows = cursor.fetchall()

        next_version = expected_version
        for row in rows:
            before = int(row["state_version_before"])
            after = int(row["state_version_after"])
            if before != next_version or after != before + 1:
                return False
            next_version = after

        return next_version == current_version
