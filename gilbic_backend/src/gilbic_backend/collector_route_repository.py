from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class CollectorRouteEntryRecord:
    route_entry_id: UUID
    client_id: UUID
    loan_id: UUID
    client_name: str
    area: str
    loan_type: str
    daily_amount: Decimal
    remaining_balance: Decimal
    pass_count: int
    last_payment_date: date | None
    advance_until: date | None
    status: str
    note: str
    state_version: int = 0
    is_reconciled: bool = False
    mobile_collections_enabled: bool = False
    mobile_balance_mode: str = ""

    @property
    def route_revision(self) -> str:
        return f"loan:{self.loan_id}:v{self.state_version}"

    @property
    def can_collect_mobile(self) -> bool:
        return self.is_reconciled and self.mobile_collections_enabled

    @property
    def can_enter_payment(self) -> bool:
        return self.can_collect_mobile and self.mobile_balance_mode == "direct_remaining_balance"

    @property
    def collection_message(self) -> str:
        if not self.is_reconciled:
            return "Checking this loan against SPINA records."
        if not self.mobile_collections_enabled:
            return "Use the SPINA desktop app for this loan type."
        if not self.can_enter_payment:
            return "PASS is available, but payments and ADV still use SPINA desktop."
        return "Ready for mobile collection."


@dataclass(frozen=True, slots=True)
class CollectorRouteRecord:
    route_date: date
    collector_name: str
    areas: tuple[str, ...]
    entries: tuple[CollectorRouteEntryRecord, ...]

    @property
    def expected_total(self) -> Decimal:
        return sum((entry.daily_amount for entry in self.entries), start=Decimal("0"))


class PostgresCollectorRouteRepository:
    """Read the live route for one authenticated collector.

    Area ownership is server-side in ``lending.collector_area_assignments``.
    Balance, pass, advance, and note values are read from the authoritative
    ``lending.loan_collection_state`` row. Before imported loans are exposed to
    mobile collection, that state must be reconciled with the desktop source of
    truth.
    """

    def get_today_route(
        self,
        *,
        collector_user_id: UUID,
        collector_name: str,
        route_date: date,
    ) -> CollectorRouteRecord:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select area
                    from lending.collector_area_assignments
                    where collector_user_id = %s
                      and is_active = true
                    order by sort_order, lower(area), id
                    """,
                    (collector_user_id,),
                )
                areas = tuple(str(row[0]) for row in cursor.fetchall())

            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        l.id as route_entry_id,
                        c.id as client_id,
                        l.id as loan_id,
                        c.full_name as client_name,
                        c.area,
                        lt.name as loan_type,
                        l.daily_amount,
                        coalesce(s.remaining_balance, l.principal) as remaining_balance,
                        coalesce(s.pass_count, 0) as pass_count,
                        s.last_payment_date,
                        s.advance_until,
                        case
                            when coalesce(s.is_reconciled, false) = false
                                then 'Needs review'
                            when lower(coalesce(lt.settings->>'mobile_collections_enabled', ''))
                                 not in ('true', '1', 'yes', 'on')
                                then 'Desktop only'
                            when s.advance_until is not null and s.advance_until >= %s
                                then 'Advance'
                            when coalesce(s.pass_count, 0) > 0
                                then 'Pass'
                            else 'Pending'
                        end as collection_status,
                        coalesce(s.note, '') as note,
                        coalesce(s.state_version, 0) as state_version,
                        coalesce(s.is_reconciled, false) as is_reconciled,
                        lower(coalesce(lt.settings->>'mobile_collections_enabled', ''))
                            in ('true', '1', 'yes', 'on') as mobile_collections_enabled,
                        coalesce(lt.settings->>'mobile_balance_mode', '') as mobile_balance_mode
                    from lending.collector_area_assignments a
                    join lending.clients c
                      on lower(btrim(c.area)) = lower(btrim(a.area))
                     and c.status = 'active'
                    join lending.loans l
                      on l.client_id = c.id
                     and l.status = 'active'
                    join lending.loan_types lt
                      on lt.id = l.loan_type_id
                     and lt.is_active = true
                    left join lending.loan_collection_state s
                      on s.loan_id = l.id
                    where a.collector_user_id = %s
                      and a.is_active = true
                      and coalesce(s.remaining_balance, l.principal) > 0
                    order by
                        a.sort_order,
                        lower(c.full_name),
                        l.date_released,
                        l.id
                    """,
                    (route_date, collector_user_id),
                )
                rows = cursor.fetchall()

        entries = tuple(
            CollectorRouteEntryRecord(
                route_entry_id=row["route_entry_id"],
                client_id=row["client_id"],
                loan_id=row["loan_id"],
                client_name=row["client_name"],
                area=row["area"] or "",
                loan_type=row["loan_type"],
                daily_amount=row["daily_amount"],
                remaining_balance=row["remaining_balance"],
                pass_count=row["pass_count"],
                last_payment_date=row["last_payment_date"],
                advance_until=row["advance_until"],
                status=row["collection_status"],
                note=row["note"],
                state_version=int(row["state_version"]),
                is_reconciled=bool(row["is_reconciled"]),
                mobile_collections_enabled=bool(row["mobile_collections_enabled"]),
                mobile_balance_mode=str(row["mobile_balance_mode"] or ""),
            )
            for row in rows
        )
        return CollectorRouteRecord(
            route_date=route_date,
            collector_name=collector_name,
            areas=areas,
            entries=entries,
        )
