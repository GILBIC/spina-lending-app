from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class CollectorRouteRenewalBadgeRecord:
    request_id: UUID
    client_id: UUID
    loan_id: UUID
    status: str
    loan_type: str
    is_seven_by_seven: bool
    submitted_at: object


class PostgresCollectorRouteRenewalRepository:
    """Read pending/approved renewal badges for the authoritative route owner."""

    def get_for_clients(
        self,
        *,
        collector_user_id: UUID,
        client_ids: Iterable[UUID],
    ) -> dict[UUID, tuple[CollectorRouteRenewalBadgeRecord, ...]]:
        ids = tuple(dict.fromkeys(client_ids))
        if not ids:
            return {}

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        request.id as request_id,
                        request.client_id,
                        request.loan_id,
                        request.status,
                        coalesce(nullif(btrim(loan_type.name), ''), 'Loan') as loan_type,
                        loan_type.calculation_mode,
                        request.submitted_at
                    from lending.client_renewal_requests request
                    join lending.clients client on client.id = request.client_id
                    join lending.loans loan on loan.id = request.loan_id
                    join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
                    where request.client_id = any(%s)
                      and request.status in ('pending', 'approved')
                      and lending.collector_area_owner(coalesce(client.area, '')) = %s
                    order by request.submitted_at desc, request.id desc
                    """,
                    (list(ids), collector_user_id),
                )
                rows = cursor.fetchall()

        grouped: dict[UUID, list[CollectorRouteRenewalBadgeRecord]] = {}
        for row in rows:
            grouped.setdefault(row["client_id"], []).append(
                CollectorRouteRenewalBadgeRecord(
                    request_id=row["request_id"],
                    client_id=row["client_id"],
                    loan_id=row["loan_id"],
                    status=str(row["status"]),
                    loan_type=str(row["loan_type"]),
                    is_seven_by_seven=(
                        str(row["calculation_mode"] or "").lower()
                        == "seven_by_seven"
                    ),
                    submitted_at=row["submitted_at"],
                )
            )
        return {key: tuple(value) for key, value in grouped.items()}
