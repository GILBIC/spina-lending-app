from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class OtherAreaLoanRecord:
    route_entry_id: UUID
    client_id: UUID
    loan_id: UUID
    client_name: str
    client_code: str
    phone_number: str
    area: str
    loan_type: str
    daily_amount: Decimal
    remaining_balance: Decimal
    pass_count: int
    status: str
    route_revision: str
    can_collect_mobile: bool
    can_enter_payment: bool
    collection_message: str
    assigned_collector_user_id: UUID | None
    assigned_collector_name: str
    processed_today: bool = False
    today_entry_type: str = ""
    today_collector_user_id: UUID | None = None
    today_collector_name: str = ""
    today_amount: Decimal = Decimal("0.00")
    today_is_locked: bool = False


class PostgresOtherAreaRepository:
    def search(
        self,
        *,
        collector_user_id: UUID,
        query: str,
        limit: int = 25,
    ) -> tuple[OtherAreaLoanRecord, ...]:
        """Search active clients outside the Collector's permanent route.

        Cross-route collection is a normal protected Collector capability.
        Delegated grants only make approved work convenient to browse in the
        separate Other-Area Work list; they are not required for search/posting.
        """
        return self._search_active_loans(
            actor_user_id=collector_user_id,
            query=query,
            limit=limit,
            exclude_actor_owned=True,
        )

    def search_management_direct(
        self,
        *,
        management_user_id: UUID,
        query: str,
        limit: int = 25,
    ) -> tuple[OtherAreaLoanRecord, ...]:
        """Search active loans for the distinct Management direct-payment path."""
        return self._search_active_loans(
            actor_user_id=management_user_id,
            query=query,
            limit=limit,
            exclude_actor_owned=False,
        )

    def _search_active_loans(
        self,
        *,
        actor_user_id: UUID,
        query: str,
        limit: int,
        exclude_actor_owned: bool,
    ) -> tuple[OtherAreaLoanRecord, ...]:
        normalized = " ".join(query.split()).strip()
        if len(normalized) < 2:
            return ()
        pattern = f"%{normalized}%"
        safe_limit = max(1, min(limit, 50))
        actor_scope_clause = (
            """
                      and lending.collector_area_owner(coalesce(client.area, ''))
                          is distinct from %s
            """
            if exclude_actor_owned
            else ""
        )
        params: list[object] = []
        if exclude_actor_owned:
            params.append(actor_user_id)
        params.extend((pattern, pattern, pattern, pattern, safe_limit))

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    select
                        loan.id as route_entry_id,
                        client.id as client_id,
                        loan.id as loan_id,
                        client.full_name as client_name,
                        client.client_code,
                        coalesce(client.phone_number, '') as phone_number,
                        coalesce(client.area, '') as area,
                        loan_type.name as loan_type,
                        loan.daily_amount,
                        coalesce(state.remaining_balance, loan.principal) as remaining_balance,
                        coalesce(state.pass_count, 0) as pass_count,
                        case
                            when coalesce(state.is_reconciled, false) = false
                                then 'Needs review'
                            when lower(coalesce(loan_type.settings->>'mobile_collections_enabled', ''))
                                 not in ('true', '1', 'yes', 'on')
                                then 'Desktop only'
                            else 'Other area'
                        end as collection_status,
                        coalesce(state.state_version, 0) as state_version,
                        coalesce(state.is_reconciled, false) as is_reconciled,
                        lower(coalesce(loan_type.settings->>'mobile_collections_enabled', ''))
                            in ('true', '1', 'yes', 'on') as mobile_collections_enabled,
                        coalesce(loan_type.settings->>'mobile_balance_mode', '')
                            as mobile_balance_mode,
                        assigned.id as assigned_collector_user_id,
                        coalesce(assigned.full_name, 'Unassigned') as assigned_collector_name,
                        false as processed_today,
                        ''::text as today_entry_type,
                        null::uuid as today_collector_user_id,
                        ''::text as today_collector_name,
                        0::numeric(18,2) as today_amount,
                        false as today_is_locked
                    from lending.clients client
                    join lending.loans loan
                      on loan.client_id = client.id
                     and loan.status = 'active'
                    join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                     and loan_type.is_active = true
                    left join lending.loan_collection_state state
                      on state.loan_id = loan.id
                    left join core.users assigned
                      on assigned.id = lending.collector_area_owner(
                          coalesce(client.area, '')
                      )
                    where client.status = 'active'
                      and coalesce(state.remaining_balance, loan.principal) > 0
                      {actor_scope_clause}
                      and (
                          client.full_name ilike %s
                          or client.client_code ilike %s
                          or coalesce(client.phone_number, '') ilike %s
                          or coalesce(client.area, '') ilike %s
                      )
                    order by
                        lower(client.full_name),
                        loan.date_released desc,
                        loan.id
                    limit %s
                    """,
                    tuple(params),
                )
                rows = cursor.fetchall()

        return tuple(self._from_row(row) for row in rows)

    def list_work(
        self,
        *,
        collector_user_id: UUID,
        collection_date: date,
        assigned_collector_user_id: UUID | None = None,
        limit: int = 500,
    ) -> tuple[OtherAreaLoanRecord, ...]:
        """List convenience work explicitly surfaced by active delegated grants.

        This list remains separate from the Collector's permanent Daily Route.
        Grants control only which cross-route clients are proactively surfaced
        here. A Collector may still search and collect another-route client
        through the protected cross-route search even without a grant.
        """

        safe_limit = max(1, min(limit, 1000))
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        loan.id as route_entry_id,
                        client.id as client_id,
                        loan.id as loan_id,
                        client.full_name as client_name,
                        client.client_code,
                        coalesce(client.phone_number, '') as phone_number,
                        coalesce(client.area, '') as area,
                        loan_type.name as loan_type,
                        loan.daily_amount,
                        coalesce(state.remaining_balance, loan.principal) as remaining_balance,
                        coalesce(state.pass_count, 0) as pass_count,
                        case
                            when today.entry_type = 'pass'
                                then 'Unable to pay'
                            when today.entry_type is not null
                                then 'Recorded today'
                            when coalesce(state.is_reconciled, false) = false
                                then 'Needs review'
                            when lower(coalesce(loan_type.settings->>'mobile_collections_enabled', ''))
                                 not in ('true', '1', 'yes', 'on')
                                then 'Desktop only'
                            else 'Pending'
                        end as collection_status,
                        coalesce(state.state_version, 0) as state_version,
                        coalesce(state.is_reconciled, false) as is_reconciled,
                        lower(coalesce(loan_type.settings->>'mobile_collections_enabled', ''))
                            in ('true', '1', 'yes', 'on') as mobile_collections_enabled,
                        coalesce(loan_type.settings->>'mobile_balance_mode', '')
                            as mobile_balance_mode,
                        assigned.id as assigned_collector_user_id,
                        coalesce(assigned.full_name, 'Unassigned') as assigned_collector_name,
                        today.entry_type is not null as processed_today,
                        coalesce(today.entry_type, '') as today_entry_type,
                        today.collector_user_id as today_collector_user_id,
                        coalesce(today.collector_name, '') as today_collector_name,
                        coalesce(today.amount, 0)::numeric(18,2) as today_amount,
                        coalesce(today.is_locked, false) as today_is_locked
                    from lending.clients client
                    join lending.loans loan
                      on loan.client_id = client.id
                     and loan.status = 'active'
                    join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                     and loan_type.is_active = true
                    left join lending.loan_collection_state state
                      on state.loan_id = loan.id
                    left join core.users assigned
                      on assigned.id = lending.collector_area_owner(
                          coalesce(client.area, '')
                      )
                    left join lateral (
                        select
                            transaction.entry_type,
                            transaction.amount,
                            transaction.collector_user_id,
                            transaction.is_locked,
                            coalesce(
                                nullif(btrim(recorder.full_name), ''),
                                nullif(btrim(recorder.username), ''),
                                'Collector'
                            ) as collector_name
                        from lending.collection_transactions transaction
                        left join core.users recorder
                          on recorder.id = transaction.collector_user_id
                        where transaction.loan_id = loan.id
                          and transaction.collection_date = %s
                          and transaction.is_voided = false
                        order by transaction.accepted_at desc, transaction.id desc
                        limit 1
                    ) today on true
                    where client.status = 'active'
                      and coalesce(state.remaining_balance, loan.principal) > 0
                      and lending.collector_area_owner(coalesce(client.area, ''))
                          is distinct from %s
                      and lending.collector_has_active_delegated_area_access(
                          %s,
                          coalesce(client.area, ''),
                          now()
                      )
                      and (
                          %s::uuid is null
                          or lending.collector_area_owner(coalesce(client.area, '')) = %s
                      )
                    order by
                        lower(coalesce(assigned.full_name, '')),
                        lower(lending.normalize_area_path(coalesce(client.area, ''))),
                        lower(client.full_name),
                        loan.date_released,
                        loan.id
                    limit %s
                    """,
                    (
                        collection_date,
                        collector_user_id,
                        collector_user_id,
                        assigned_collector_user_id,
                        assigned_collector_user_id,
                        safe_limit,
                    ),
                )
                rows = cursor.fetchall()

        return tuple(self._from_row(row) for row in rows)

    @staticmethod
    def _from_row(row) -> OtherAreaLoanRecord:
        is_reconciled = bool(row["is_reconciled"])
        mobile_enabled = bool(row["mobile_collections_enabled"])
        balance_mode = str(row["mobile_balance_mode"] or "")
        can_collect_mobile = is_reconciled and mobile_enabled
        can_enter_payment = (
            can_collect_mobile and balance_mode == "direct_remaining_balance"
        )
        processed_today = bool(row.get("processed_today", False))
        if processed_today:
            recorder = str(row.get("today_collector_name") or "Collector")
            message = f"Already recorded today by {recorder}."
        elif not is_reconciled:
            message = "Checking this loan against SPINA records."
        elif not mobile_enabled:
            message = "Use the SPINA desktop app for this loan type."
        elif not can_enter_payment:
            message = "This loan's payment calculation still uses SPINA desktop."
        else:
            message = (
                "Cross-route collection. The assigned collector and linked client "
                "will be notified after posting."
            )

        loan_id = row["loan_id"]
        state_version = int(row["state_version"])
        return OtherAreaLoanRecord(
            route_entry_id=row["route_entry_id"],
            client_id=row["client_id"],
            loan_id=loan_id,
            client_name=str(row["client_name"]),
            client_code=str(row["client_code"]),
            phone_number=str(row["phone_number"] or ""),
            area=str(row["area"] or ""),
            loan_type=str(row["loan_type"]),
            daily_amount=Decimal(row["daily_amount"]),
            remaining_balance=Decimal(row["remaining_balance"]),
            pass_count=int(row["pass_count"]),
            status=str(row["collection_status"]),
            route_revision=f"loan:{loan_id}:v{state_version}",
            can_collect_mobile=can_collect_mobile,
            can_enter_payment=can_enter_payment and not processed_today,
            collection_message=message,
            assigned_collector_user_id=row["assigned_collector_user_id"],
            assigned_collector_name=str(row["assigned_collector_name"]),
            processed_today=processed_today,
            today_entry_type=str(row.get("today_entry_type") or ""),
            today_collector_user_id=row.get("today_collector_user_id"),
            today_collector_name=str(row.get("today_collector_name") or ""),
            today_amount=Decimal(row.get("today_amount") or 0),
            today_is_locked=bool(row.get("today_is_locked", False)),
        )
