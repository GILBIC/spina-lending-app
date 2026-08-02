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
    processed_today: bool = False
    today_entry_type: str = ""
    today_collector_name: str = ""
    today_transaction_id: UUID | None = None
    today_collector_user_id: UUID | None = None
    today_is_locked: bool = False
    can_edit_today: bool = False
    covered_dates: tuple[date, ...] = ()

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
        if self.processed_today:
            if self.today_is_locked:
                return "Today's collection is already included in a remittance and is locked."
            return "Today's collection has already been recorded."
        if not self.is_reconciled:
            return "Checking this loan against SPINA records."
        if not self.mobile_collections_enabled:
            return "Use the SPINA desktop app for this loan type."
        if not self.can_enter_payment:
            return "Unable-to-pay is available, but payments still use SPINA desktop."
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
    Balance, missed-payment count, exact covered dates, and notes are read from
    the authoritative lending tables. Imported loans must remain reconciled with
    the desktop source of truth before mobile collection is enabled.
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
                            when today.entry_type = 'pass'
                                then 'Unable to pay'
                            when today.entry_type is not null
                                then 'Recorded today'
                            when coalesce(s.is_reconciled, false) = false
                                then 'Needs review'
                            when lower(coalesce(lt.settings->>'mobile_collections_enabled', ''))
                                 not in ('true', '1', 'yes', 'on')
                                then 'Desktop only'
                            when coalesce(coverage.covered_today, false)
                                then 'Covered'
                            when coalesce(s.pass_count, 0) > 0
                                then 'Missed payment'
                            else 'Pending'
                        end as collection_status,
                        coalesce(s.note, '') as note,
                        coalesce(s.state_version, 0) as state_version,
                        coalesce(s.is_reconciled, false) as is_reconciled,
                        lower(coalesce(lt.settings->>'mobile_collections_enabled', ''))
                            in ('true', '1', 'yes', 'on') as mobile_collections_enabled,
                        coalesce(lt.settings->>'mobile_balance_mode', '') as mobile_balance_mode,
                        today.entry_type is not null as processed_today,
                        coalesce(today.entry_type, '') as today_entry_type,
                        coalesce(today.collector_name, '') as today_collector_name,
                        today.transaction_id as today_transaction_id,
                        today.collector_user_id as today_collector_user_id,
                        coalesce(today.is_locked, false) as today_is_locked,
                        coalesce(coverage.covered_dates, ARRAY[]::date[]) as covered_dates
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
                    left join lateral (
                        select
                            coalesce(bool_or(cd.covered_date = %s), false) as covered_today,
                            coalesce(
                                array_agg(cd.covered_date order by cd.covered_date)
                                    filter (where cd.covered_date >= %s),
                                ARRAY[]::date[]
                            ) as covered_dates
                        from lending.collection_covered_dates cd
                        where cd.loan_id = l.id
                    ) coverage on true
                    left join lateral (
                        select
                            t.id as transaction_id,
                            t.entry_type,
                            t.collector_user_id,
                            t.is_locked,
                            coalesce(
                                nullif(btrim(u.full_name), ''),
                                nullif(btrim(u.username), ''),
                                'Collector'
                            ) as collector_name
                        from lending.collection_transactions t
                        left join core.users u
                          on u.id = t.collector_user_id
                        where t.loan_id = l.id
                          and t.collection_date = %s
                        order by t.accepted_at desc, t.id desc
                        limit 1
                    ) today on true
                    where a.collector_user_id = %s
                      and a.is_active = true
                      and coalesce(s.remaining_balance, l.principal) > 0
                    order by
                        a.sort_order,
                        lower(c.full_name),
                        l.date_released,
                        l.id
                    """,
                    (route_date, route_date, route_date, collector_user_id),
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
                processed_today=bool(row["processed_today"]),
                today_entry_type=str(row["today_entry_type"] or ""),
                today_collector_name=str(row["today_collector_name"] or ""),
                today_transaction_id=row["today_transaction_id"],
                today_collector_user_id=row["today_collector_user_id"],
                today_is_locked=bool(row["today_is_locked"]),
                can_edit_today=(
                    row["today_transaction_id"] is not None
                    and row["today_collector_user_id"] == collector_user_id
                    and not bool(row["today_is_locked"])
                ),
                covered_dates=tuple(row["covered_dates"] or ()),
            )
            for row in rows
        )
        return CollectorRouteRecord(
            route_date=route_date,
            collector_name=collector_name,
            areas=areas,
            entries=entries,
        )
