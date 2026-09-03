from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from spina_mobile_collections.contracts import CollectionCommand
from spina_mobile_collections.service import CollectionRejected

from .collection_posting import PostgresCollectionPostingBridge


class CrossCollectorCollectionPostingBridge(PostgresCollectionPostingBridge):
    """Use the official posting transaction for assigned and cross-route work.

    The legacy base validator recognizes the Collector's assigned route. When it
    returns ``route_not_assigned``, Gilbic may still accept a protected
    cross-route collection from another active Collector. Temporary delegated
    area grants are a route-convenience feature only; they are not a financial
    posting permission gate.

    Every other base validation remains authoritative. In particular, an active
    client/loan, reconciled collection state, feature gates, stale-route checks,
    idempotency, device authorization and chronological safeguards must still
    pass before the official transaction is written. Permanent route ownership
    and the original recorder remain separate audit facts.
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

        # ``route_not_assigned`` is the only base rejection this bridge may
        # relax. Cross-route collection is allowed without a delegated grant;
        # all validation performed before that base rejection remains intact.
        # The authoritative assigned Collector is resolved later for route
        # reflection, notifications, custody and remittance attribution.
        del cursor, collector_user_id

        last_payment_date: date | None = loan["last_payment_date"]
        if last_payment_date is not None and command.collection_date < last_payment_date:
            raise CollectionRejected(
                "This date is earlier than the latest recorded payment. Refresh the "
                "client and review the entry.",
                code="collection_date_out_of_order",
            )
