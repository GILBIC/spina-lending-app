from __future__ import annotations

from dataclasses import replace
from datetime import date
from uuid import UUID

from psycopg.rows import dict_row

from .collector_route_repository import (
    CollectorRouteRecord,
    PostgresCollectorRouteRepository,
)
from .database import open_connection


class PerLoanPostgresCollectorRouteRepository(PostgresCollectorRouteRepository):
    """Overlay immutable Stage 5E.4.6A activation on the existing route record.

    The Stage 5E.4.5 route SQL remains the authoritative schedule/readiness source.
    This wrapper replaces only the old broad loan-type activation indicator with
    the latest explicit state for each individual loan.
    """

    def get_today_route(
        self,
        *,
        collector_user_id: UUID,
        collector_name: str,
        route_date: date,
    ) -> CollectorRouteRecord:
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
                    select
                        activation.loan_id,
                        activation.is_active,
                        activation.schedule_id,
                        assessment.schedule_id as current_schedule_id
                    from lending.loan_contract_collection_activation_state activation
                    left join accounting.loan_contract_dpd_assessment assessment
                      on assessment.loan_id = activation.loan_id
                    where activation.loan_id = any(%s)
                    """,
                    (loan_ids,),
                )
                activation_rows = cursor.fetchall()

        active_current = {
            row["loan_id"]: (
                bool(row["is_active"])
                and row["schedule_id"] is not None
                and row["schedule_id"] == row["current_schedule_id"]
            )
            for row in activation_rows
        }

        entries = tuple(
            replace(
                entry,
                contract_allocation_enabled=active_current.get(entry.loan_id, False),
                contract_collection_ready=(
                    active_current.get(entry.loan_id, False)
                    and entry.contract_schedule_ready
                ),
            )
            for entry in route.entries
        )
        return replace(route, entries=entries)
