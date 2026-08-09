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

    Loans with no activation history keep their established route behavior. A loan
    that was explicitly deactivated, or whose activation belongs to an older
    schedule, is conservatively blocked from mobile collection rather than falling
    back to legacy date-based collection. Actual posting rechecks the same state.
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
                        activation.event_action,
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

        states = {row["loan_id"]: row for row in activation_rows}
        entries = []
        for entry in route.entries:
            state = states.get(entry.loan_id)
            if state is None:
                # Never activated: preserve the established official collection path.
                entries.append(
                    replace(
                        entry,
                        contract_allocation_enabled=False,
                        contract_collection_ready=False,
                    )
                )
                continue

            action = str(state["event_action"] or "")
            active_current = (
                action == "activate"
                and state["schedule_id"] is not None
                and state["schedule_id"] == state["current_schedule_id"]
            )
            if active_current:
                entries.append(
                    replace(
                        entry,
                        contract_allocation_enabled=True,
                        contract_collection_ready=entry.contract_schedule_ready,
                    )
                )
                continue

            # A deactivated or stale activation must not reopen the legacy mobile
            # path. Desktop/Management intervention is required first.
            entries.append(
                replace(
                    entry,
                    mobile_collections_enabled=False,
                    contract_allocation_enabled=False,
                    contract_collection_ready=False,
                )
            )

        return replace(route, entries=tuple(entries))
