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

from .collection_past_due_capture import CollectionPastDueCapture
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

    Structured Past Due capture runs only after the protected product allocator
    succeeds, but still inside the executor's same PostgreSQL transaction. Missing
    or invalid reason evidence therefore rolls the whole collection back.
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
        CollectionPastDueCapture().apply(
            connection,
            actor=actor,
            command=prepared,
            posted=posted,
        )
        return posted

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
