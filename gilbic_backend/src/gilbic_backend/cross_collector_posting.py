from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from spina_mobile_collections.contracts import CollectionCommand
from spina_mobile_collections.service import CollectionRejected

from .collection_posting import PostgresCollectionPostingBridge


class CrossCollectorCollectionPostingBridge(PostgresCollectionPostingBridge):
    """Use the official posting transaction for assigned and delegated work.

    The legacy base validator recognizes exact flat-area assignments. When it
    returns ``route_not_assigned``, resolve the hierarchical authoritative owner
    first: the owner may collect their own descendant sub-area without a grant.
    Only a different visiting Collector must have an active delegated grant for
    the client's current area path. Every other base validation remains intact.
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
            select
                lending.collector_area_owner(%s) as assigned_collector_user_id,
                lending.collector_has_active_delegated_area_access(
                    %s,
                    %s,
                    now()
                ) as delegated_allowed
            """,
            (area_path, collector_user_id, area_path),
        )
        access_row = cursor.fetchone()
        assigned_collector_user_id = None
        delegated_allowed = False
        if access_row is not None:
            try:
                assigned_collector_user_id = access_row["assigned_collector_user_id"]
                delegated_allowed = bool(access_row["delegated_allowed"])
            except (KeyError, TypeError):
                try:
                    assigned_collector_user_id = access_row[0]
                    delegated_allowed = bool(access_row[1])
                except (IndexError, KeyError, TypeError):
                    assigned_collector_user_id = None
                    delegated_allowed = False

        is_authoritative_owner = (
            assigned_collector_user_id is not None
            and UUID(str(assigned_collector_user_id)) == collector_user_id
        )
        if not is_authoritative_owner and not delegated_allowed:
            raise CollectionRejected(
                "You do not have active access to this assigned area. Ask the "
                "assigned Collector to grant access, then refresh Other-Area Work.",
                code="delegated_area_access_required",
            )

        # The base method already validated the active client, active loan and
        # reconciled state before checking flat assignment. Preserve its final
        # chronological safeguard after hierarchical ownership/access is
        # revalidated inside the same official posting transaction.
        last_payment_date: date | None = loan["last_payment_date"]
        if last_payment_date is not None and command.collection_date < last_payment_date:
            raise CollectionRejected(
                "This date is earlier than the latest recorded payment. Refresh the "
                "client and review the entry.",
                code="collection_date_out_of_order",
            )
