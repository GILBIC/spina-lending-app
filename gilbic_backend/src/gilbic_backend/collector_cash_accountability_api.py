from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Header
from psycopg.rows import dict_row

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .database import open_connection
from .request_auth import authenticated_device_context


ZERO = Decimal("0.00")


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def create_collector_cash_accountability_router() -> APIRouter:
    router = APIRouter(tags=["collector cash accountability"])

    @router.get("/api/v1/collector/cash-accountability")
    @router.get(
        "/api/mobile/v1/collector/cash-accountability",
        include_in_schema=False,
    )
    def cash_accountability(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.view",
            permission_error="Remittance view permission is required.",
        )

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    with actor as (
                        select %s::uuid as user_id
                    ),
                    ready as (
                        select
                            transaction.amount,
                            transaction.assigned_collector_user_id,
                            transaction.collection_origin = 'cross_collector'
                                and transaction.assigned_collector_user_id is not null
                                and transaction.assigned_collector_user_id <> actor.user_id
                                as is_other_area
                        from lending.collection_transactions transaction
                        cross join actor
                        where transaction.collector_user_id = actor.user_id
                          and transaction.entry_type <> 'pass'
                          and transaction.remittance_id is null
                          and transaction.is_locked = false
                          and transaction.is_voided = false
                    ),
                    awaiting as (
                        select
                            remittance.id as remittance_id,
                            item.amount,
                            transaction.assigned_collector_user_id,
                            transaction.collection_origin = 'cross_collector'
                                and transaction.assigned_collector_user_id is not null
                                and transaction.assigned_collector_user_id <> actor.user_id
                                as is_other_area
                        from lending.collection_remittances remittance
                        join lending.collection_remittance_items item
                          on item.remittance_id = remittance.id
                        join lending.collection_transactions transaction
                          on transaction.id = item.transaction_id
                        cross join actor
                        where remittance.collector_user_id = actor.user_id
                          and remittance.status = 'submitted'
                          and not exists (
                              select 1
                              from lending.collection_remittance_rejections rejection
                              where rejection.remittance_id = remittance.id
                          )
                    ),
                    all_cash as (
                        select
                            amount,
                            assigned_collector_user_id,
                            is_other_area
                        from ready
                        union all
                        select
                            amount,
                            assigned_collector_user_id,
                            is_other_area
                        from awaiting
                    ),
                    other_by_collector as (
                        select
                            cash.assigned_collector_user_id,
                            coalesce(
                                nullif(btrim(user_account.full_name), ''),
                                user_account.username
                            ) as collector_name,
                            sum(cash.amount)::numeric(18,2) as amount
                        from all_cash cash
                        join core.users user_account
                          on user_account.id = cash.assigned_collector_user_id
                        where cash.is_other_area
                        group by
                            cash.assigned_collector_user_id,
                            user_account.full_name,
                            user_account.username
                    )
                    select
                        coalesce((select sum(amount) from ready), 0)::numeric(18,2)
                            as ready_to_remit_amount,
                        coalesce((select count(*) from ready), 0)::integer
                            as ready_to_remit_count,
                        coalesce((select sum(amount) from awaiting), 0)::numeric(18,2)
                            as awaiting_acceptance_amount,
                        coalesce((
                            select count(distinct remittance_id) from awaiting
                        ), 0)::integer as awaiting_acceptance_count,
                        coalesce((
                            select sum(amount) from all_cash where not is_other_area
                        ), 0)::numeric(18,2) as assigned_area_cash_held,
                        coalesce((
                            select sum(amount) from all_cash where is_other_area
                        ), 0)::numeric(18,2) as other_area_cash_held,
                        coalesce((
                            select jsonb_agg(
                                jsonb_build_object(
                                    'collector_user_id', assigned_collector_user_id,
                                    'collector_name', collector_name,
                                    'amount', amount
                                )
                                order by lower(collector_name), assigned_collector_user_id
                            )
                            from other_by_collector
                        ), '[]'::jsonb) as other_area_by_collector
                    """,
                    (actor.user_id,),
                )
                row = cursor.fetchone()

        ready = Decimal(row["ready_to_remit_amount"] or ZERO)
        awaiting = Decimal(row["awaiting_acceptance_amount"] or ZERO)
        total = ready + awaiting
        assigned_area = Decimal(row["assigned_area_cash_held"] or ZERO)
        other_area = Decimal(row["other_area_cash_held"] or ZERO)
        other_area_by_collector = []
        for item in row["other_area_by_collector"] or []:
            other_area_by_collector.append(
                {
                    "collector_user_id": str(item["collector_user_id"]),
                    "collector_name": str(item["collector_name"]),
                    "amount": _money(Decimal(item["amount"])),
                }
            )

        return {
            "success": True,
            "data": {
                "total_cash_held": _money(total),
                "assigned_area_cash_held": _money(assigned_area),
                "other_area_cash_held": _money(other_area),
                "other_area_by_collector": other_area_by_collector,
                "ready_to_remit_amount": _money(ready),
                "ready_to_remit_count": int(row["ready_to_remit_count"] or 0),
                "awaiting_acceptance_amount": _money(awaiting),
                "awaiting_acceptance_count": int(
                    row["awaiting_acceptance_count"] or 0
                ),
            },
        }

    return router
