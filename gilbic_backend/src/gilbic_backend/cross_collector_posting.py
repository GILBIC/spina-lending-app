from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from spina_mobile_collections.contracts import CollectionCommand
from spina_mobile_collections.service import CollectionRejected

from .collection_posting import PostgresCollectionPostingBridge


class CrossCollectorCollectionPostingBridge(PostgresCollectionPostingBridge):
    """Use the official posting transaction for delegated other-area work.

    The base bridge performs every balance, date, device, receipt, idempotency,
    and loan-state validation. This override changes only the route-ownership
    rejection, and only when the signed-in Collector has an active delegated
    grant for the client's current area path. The database assignment trigger
    continues to preserve both the recorder and the authoritative assigned
    Collector.
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

        area_path = str(loan.get("area") or "").strip()
        cursor.execute(
            """
            select lending.collector_has_active_delegated_area_access(
                %s,
                %s,
                now()
            ) as allowed
            """,
            (collector_user_id, area_path),
        )
        access_row = cursor.fetchone()
        access_allowed = False
        if access_row is not None:
            try:
                access_allowed = bool(access_row["allowed"])
            except (KeyError, TypeError):
                try:
                    access_allowed = bool(access_row[0])
                except (IndexError, KeyError, TypeError):
                    access_allowed = False
        if not access_allowed:
            raise CollectionRejected(
                "You do not have active access to this assigned area. Ask the "
                "assigned Collector to grant access, then refresh Other-Area Work.",
                code="delegated_area_access_required",
            )

        # The base method already validated the active client, active loan,
        # reconciled state, and route revision before checking assignment.
        # Preserve its final chronological safeguard after delegated access is
        # revalidated inside the same official posting transaction.
        last_payment_date: date | None = loan["last_payment_date"]
        if last_payment_date is not None and command.collection_date < last_payment_date:
            raise CollectionRejected(
                "This date is earlier than the latest recorded payment. Refresh the "
                "client and review the entry.",
                code="collection_date_out_of_order",
            )
