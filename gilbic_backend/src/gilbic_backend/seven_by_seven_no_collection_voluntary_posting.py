from __future__ import annotations

from typing import Any

from psycopg import Connection

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


class NoCollectionVoluntarySevenBySevenCollectionPostingBridge(
    MaturingVerifiedAdvanceSevenBySevenCollectionPostingBridge
):
    """Fail closed until the protected 7x7 No Collection cash path is complete.

    The wire contract already distinguishes a borrower-requested voluntary
    payment on a Management No Collection date from an ordinary scheduled
    payment. Until the dedicated immutable posting transaction is wired, that
    explicit intent must never fall through to Regular or ordinary 7x7 posting.
    All established intents continue through the existing bridge unchanged.
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

        raise CollectionRejected(
            "7x7 No Collection voluntary payment posting is not enabled yet. "
            "Refresh the route and use the protected flow when Management enables it.",
            code="seven_by_seven_no_collection_voluntary_posting_required",
        )
