from __future__ import annotations

from dataclasses import replace
from datetime import date
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .per_loan_collector_route import PerLoanPostgresCollectorRouteRepository
from .seven_by_seven_collection_posting import SEVEN_BY_SEVEN_MOBILE_SETTING


class SevenBySevenGatedPostgresCollectorRouteRepository(
    PerLoanPostgresCollectorRouteRepository
):
    """Apply protected 7x7 and renewal-activation gates to Daily Collection."""

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
                    select
                        loan.id as loan_id,
                        loan_type.calculation_mode,
                        loan_type.settings,
                        exists (
                            select 1
                            from lending.client_renewal_requests request
                            where request.new_loan_id = loan.id
                              and request.activation_status <> 'active'
                        ) as renewal_activation_blocked
                    from lending.loans loan
                    join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
                    where loan.id = any(%s)
                    """,
                    (loan_ids,),
                )
                rows = cursor.fetchall()

        coordinates = {row["loan_id"]: row for row in rows}
        entries = []
        for entry in route.entries:
            row = coordinates.get(entry.loan_id)
            if row is not None and bool(row["renewal_activation_blocked"]):
                # A renewal loan can exist for accounting/disbursement evidence but is
                # not collectible until client cash confirmation, proof approval,
                # old-loan settlement and Management activation are all complete.
                continue

            if row is None or str(row["calculation_mode"] or "") != "seven_by_seven":
                entries.append(entry)
                continue

            settings = row["settings"] if isinstance(row["settings"], dict) else {}
            dedicated_enabled = _setting_enabled(
                settings.get(SEVEN_BY_SEVEN_MOBILE_SETTING)
            )
            if dedicated_enabled:
                entries.append(entry)
                continue

            entries.append(
                replace(
                    entry,
                    mobile_collections_enabled=False,
                    contract_allocation_enabled=False,
                    contract_collection_ready=False,
                )
            )

        return replace(route, entries=tuple(entries))


def _setting_enabled(value: object) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() in {"true", "1", "yes", "on"}
