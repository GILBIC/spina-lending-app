from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from spina_mobile_collections.contracts import CollectionCommand
from spina_mobile_collections.service import CollectionRejected

from .collection_posting import PostgresCollectionPostingBridge


class CrossCollectorCollectionPostingBridge(PostgresCollectionPostingBridge):
    """Use the official posting transaction for assigned and other-area payments.

    The base bridge performs every balance, date, device, receipt, idempotency,
    and loan-state validation. This override changes only the route-ownership
    rejection: an authenticated collector may explicitly post a payment for an
    active client outside their route. The database assignment trigger preserves
    both the recorder and the actual assigned collector.
    """

    @staticmethod
    def _validate_loan_and_route(
        cursor: Any,
        *,
        loan: dict[str, Any],
        collector_user_id: UUID,
        command: CollectionCommand,
    ) -> None:
        try:
            PostgresCollectionPostingBridge._validate_loan_and_route(
                cursor,
                loan=loan,
                collector_user_id=collector_user_id,
                command=command,
            )
            return
        except CollectionRejected as error:
            if error.code != "route_not_assigned":
                raise

        # The base method already validated the active client, active loan,
        # reconciled state, and route revision before checking assignment.
        # Preserve its final chronological safeguard for the explicit
        # other-area flow.
        last_payment_date: date | None = loan["last_payment_date"]
        if last_payment_date is not None and command.collection_date < last_payment_date:
            raise CollectionRejected(
                "This date is earlier than the latest recorded payment. Refresh the "
                "client and review the entry.",
                code="collection_date_out_of_order",
            )
