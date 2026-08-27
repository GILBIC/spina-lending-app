from __future__ import annotations

from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PaymentAllocationIntent,
    PostedCollection,
)
from spina_mobile_collections.service import CollectionRejected

from .seven_by_seven_advance_activation_posting import (
    MaturingVerifiedAdvanceSevenBySevenCollectionPostingBridge,
)
from .seven_by_seven_no_collection_voluntary import (
    SevenBySevenNoCollectionVoluntaryError,
)
from .seven_by_seven_no_collection_voluntary_context import (
    SevenBySevenNoCollectionVoluntaryContextError,
    load_no_collection_voluntary_posting_context,
)


class NoCollectionVoluntarySevenBySevenCollectionPostingBridge(
    MaturingVerifiedAdvanceSevenBySevenCollectionPostingBridge
):
    """Verify the protected NC voluntary context and fail closed at the write boundary.

    The wire contract distinguishes a borrower-requested voluntary payment on a
    Management No Collection date from an ordinary scheduled payment. This bridge
    now proves the exact active 7x7 schedule, source Management declaration,
    affected signed installment, Past Due priority, and existing prepayment
    evidence before the request can reach the still-pending atomic write slice.

    No verified NC request is allowed to fall through to Regular or ordinary 7x7
    posting. Established non-NC intents continue through the existing bridge.
    """

    def post_collection(
        self,
        connection: Connection[Any],
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        if (
            command.payment_allocation_intent
            is not PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY
        ):
            return super().post_collection(connection, actor, command)

        if command.entry_type is not CollectionEntryType.PAYMENT:
            raise CollectionRejected(
                "No Collection voluntary intent is valid only for a Payment receipt.",
                code="seven_by_seven_no_collection_voluntary_payment_required",
            )

        if not self._requires_seven_by_seven_path(connection, command=command):
            raise CollectionRejected(
                "No Collection voluntary intent is valid only for a protected 7x7 loan.",
                code="seven_by_seven_no_collection_voluntary_loan_required",
            )

        loan_id = self._uuid(command.loan_id, "loan")
        try:
            with connection.cursor(row_factory=dict_row) as cursor:
                context = load_no_collection_voluntary_posting_context(
                    cursor,
                    loan_id=loan_id,
                    collection_date=command.collection_date,
                    transaction_amount=command.amount or 0,
                )
        except (
            SevenBySevenNoCollectionVoluntaryContextError,
            SevenBySevenNoCollectionVoluntaryError,
        ) as error:
            raise CollectionRejected(str(error), code=error.code) from error

        raise CollectionRejected(
            "The 7x7 No Collection voluntary payment is verified and planned, "
            f"but the atomic receipt/evidence write is not enabled yet ({context.plan.status}).",
            code="seven_by_seven_no_collection_voluntary_posting_required",
        )
