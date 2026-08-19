from __future__ import annotations

from dataclasses import replace
from datetime import date
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .seven_by_seven_collector_route import (
    SevenBySevenGatedPostgresCollectorRouteRepository,
)


class RenewalActivationGatedPostgresCollectorRouteRepository(
    SevenBySevenGatedPostgresCollectorRouteRepository
):
    """Keep newly renewed loans off Daily Collection until renewal activation.

    A new loan may already exist for authoritative accounting/disbursement evidence,
    but it is not field-collectible while client cash confirmation, handover proof,
    old-loan settlement, or Management activation remains incomplete.
    """

    def get_today_route(
        self,
        *,
        collector_user_id: UUID,
        collector_name: str,
        route_date: date,
    ):
        route = super().get_today_route(
            collector_user_id=collector_user_id,
            collector_name=collector_name,
            route_date=route_date,
        )
        if not route.entries:
            return route

        loan_ids = [entry.loan_id for entry in route.entries]
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select request.new_loan_id
                    from lending.client_renewal_requests request
                    where request.new_loan_id = any(%s)
                      and request.activation_status <> 'active'
                    """,
                    (loan_ids,),
                )
                blocked = {row["new_loan_id"] for row in cursor.fetchall()}

        if not blocked:
            return route
        return replace(
            route,
            entries=tuple(
                entry for entry in route.entries if entry.loan_id not in blocked
            ),
        )
