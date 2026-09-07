from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class AreaCollector:
    user_id: UUID
    username: str
    full_name: str


@dataclass(frozen=True, slots=True)
class AreaTreeNode:
    area_uid: UUID
    parent_area_uid: UUID | None
    name: str
    full_path: str
    depth: int
    sort_order: int
    is_active: bool
    is_legacy_unmapped: bool
    explicit_collector: AreaCollector | None
    effective_collector: AreaCollector | None
    effective_collector_source_area_uid: UUID | None
    direct_client_count: int
    subtree_client_count: int
    child_count: int


@dataclass(frozen=True, slots=True)
class AreaClientSearchResult:
    client_id: UUID
    client_code: str
    full_name: str
    area_uid: UUID | None
    area_path: str | None
    effective_collector: AreaCollector | None


def _collector_from_row(
    row: Mapping[str, Any],
    *,
    id_key: str,
    username_key: str,
    full_name_key: str,
) -> AreaCollector | None:
    user_id = row[id_key]
    if user_id is None:
        return None
    return AreaCollector(
        user_id=user_id,
        username=row[username_key],
        full_name=row[full_name_key],
    )


class PostgresAreaManagementRepository:
    def list_tree(self, *, include_inactive: bool = False) -> tuple[AreaTreeNode, ...]:
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    with recursive area_walk as (
                        select
                            node.area_uid,
                            node.parent_area_uid,
                            node.name,
                            node.full_path,
                            node.depth,
                            node.sort_order,
                            node.is_active,
                            node.is_legacy_unmapped,
                            array[node.sort_order]::integer[] as order_path
                        from lending.area_nodes node
                        where node.parent_area_uid is null

                        union all

                        select
                            child.area_uid,
                            child.parent_area_uid,
                            child.name,
                            child.full_path,
                            child.depth,
                            child.sort_order,
                            child.is_active,
                            child.is_legacy_unmapped,
                            parent.order_path || child.sort_order
                        from lending.area_nodes child
                        join area_walk parent
                          on parent.area_uid = child.parent_area_uid
                    ),
                    ancestry as (
                        select
                            node.area_uid as descendant_area_uid,
                            node.area_uid as ancestor_area_uid,
                            node.depth as ancestor_depth
                        from lending.area_nodes node

                        union all

                        select
                            ancestry.descendant_area_uid,
                            parent.area_uid,
                            parent.depth
                        from ancestry
                        join lending.area_nodes current
                          on current.area_uid = ancestry.ancestor_area_uid
                        join lending.area_nodes parent
                          on parent.area_uid = current.parent_area_uid
                    ),
                    descendants as (
                        select
                            node.area_uid as ancestor_area_uid,
                            node.area_uid as descendant_area_uid
                        from lending.area_nodes node

                        union all

                        select
                            descendants.ancestor_area_uid,
                            child.area_uid
                        from descendants
                        join lending.area_nodes child
                          on child.parent_area_uid = descendants.descendant_area_uid
                    ),
                    direct_client_counts as (
                        select
                            client.area_uid,
                            count(*)::integer as client_count
                        from lending.clients client
                        where client.area_uid is not null
                        group by client.area_uid
                    ),
                    subtree_client_counts as (
                        select
                            descendants.ancestor_area_uid as area_uid,
                            count(client.id)::integer as client_count
                        from descendants
                        left join lending.clients client
                          on client.area_uid = descendants.descendant_area_uid
                        group by descendants.ancestor_area_uid
                    ),
                    child_counts as (
                        select
                            child.parent_area_uid as area_uid,
                            count(*)::integer as child_count
                        from lending.area_nodes child
                        where child.parent_area_uid is not null
                        group by child.parent_area_uid
                    )
                    select
                        node.area_uid,
                        node.parent_area_uid,
                        node.name,
                        node.full_path,
                        node.depth,
                        node.sort_order,
                        node.is_active,
                        node.is_legacy_unmapped,
                        explicit_assignment.collector_user_id
                            as explicit_collector_user_id,
                        explicit_account.username
                            as explicit_collector_username,
                        explicit_account.full_name
                            as explicit_collector_full_name,
                        effective_owner.collector_user_id
                            as effective_collector_user_id,
                        effective_account.username
                            as effective_collector_username,
                        effective_account.full_name
                            as effective_collector_full_name,
                        effective_source.ancestor_area_uid
                            as effective_collector_source_area_uid,
                        coalesce(direct_counts.client_count, 0)
                            as direct_client_count,
                        coalesce(subtree_counts.client_count, 0)
                            as subtree_client_count,
                        coalesce(children.child_count, 0)
                            as child_count
                    from area_walk node
                    left join lending.collector_area_assignments explicit_assignment
                      on explicit_assignment.area_uid = node.area_uid
                     and explicit_assignment.is_active = true
                    left join core.users explicit_account
                      on explicit_account.id = explicit_assignment.collector_user_id
                    left join lateral (
                        select lending.collector_area_owner(node.full_path)
                            as collector_user_id
                    ) effective_owner on true
                    left join core.users effective_account
                      on effective_account.id = effective_owner.collector_user_id
                    left join lateral (
                        select ancestry.ancestor_area_uid
                        from ancestry
                        join lending.collector_area_assignments assignment
                          on assignment.area_uid = ancestry.ancestor_area_uid
                         and assignment.is_active = true
                        where ancestry.descendant_area_uid = node.area_uid
                          and assignment.collector_user_id =
                              effective_owner.collector_user_id
                        order by ancestry.ancestor_depth desc
                        limit 1
                    ) effective_source on true
                    left join direct_client_counts direct_counts
                      on direct_counts.area_uid = node.area_uid
                    left join subtree_client_counts subtree_counts
                      on subtree_counts.area_uid = node.area_uid
                    left join child_counts children
                      on children.area_uid = node.area_uid
                    where (%s or node.is_active = true)
                    order by node.order_path, node.depth, node.area_uid
                    """,
                    (include_inactive,),
                )
                rows = cursor.fetchall()

        return tuple(
            AreaTreeNode(
                area_uid=row["area_uid"],
                parent_area_uid=row["parent_area_uid"],
                name=row["name"],
                full_path=row["full_path"],
                depth=row["depth"],
                sort_order=row["sort_order"],
                is_active=row["is_active"],
                is_legacy_unmapped=row["is_legacy_unmapped"],
                explicit_collector=_collector_from_row(
                    row,
                    id_key="explicit_collector_user_id",
                    username_key="explicit_collector_username",
                    full_name_key="explicit_collector_full_name",
                ),
                effective_collector=_collector_from_row(
                    row,
                    id_key="effective_collector_user_id",
                    username_key="effective_collector_username",
                    full_name_key="effective_collector_full_name",
                ),
                effective_collector_source_area_uid=row[
                    "effective_collector_source_area_uid"
                ],
                direct_client_count=row["direct_client_count"],
                subtree_client_count=row["subtree_client_count"],
                child_count=row["child_count"],
            )
            for row in rows
        )

    def list_collectors(self) -> tuple[AreaCollector, ...]:
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select distinct
                        account.id as collector_user_id,
                        account.username as collector_username,
                        account.full_name as collector_full_name
                    from core.users account
                    join core.user_roles user_role
                      on user_role.user_id = account.id
                    join core.roles role
                      on role.id = user_role.role_id
                    where role.code = 'collector'
                      and account.status = 'active'
                    order by
                        account.full_name,
                        account.username,
                        account.id
                    """
                )
                rows = cursor.fetchall()

        return tuple(
            AreaCollector(
                user_id=row["collector_user_id"],
                username=row["collector_username"],
                full_name=row["collector_full_name"],
            )
            for row in rows
        )

    def search_clients(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> tuple[AreaClientSearchResult, ...]:
        normalized_query = query.strip()
        if not normalized_query or limit <= 0:
            return ()

        pattern = f"%{normalized_query}%"
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        client.id as client_id,
                        client.client_code,
                        client.full_name,
                        client.area_uid,
                        coalesce(
                            node.full_path,
                            nullif(lending.normalize_area_path(client.area), '')
                        ) as area_path,
                        effective_owner.collector_user_id
                            as effective_collector_user_id,
                        effective_account.username
                            as effective_collector_username,
                        effective_account.full_name
                            as effective_collector_full_name
                    from lending.clients client
                    left join lending.area_nodes node
                      on node.area_uid = client.area_uid
                    left join lateral (
                        select lending.collector_area_owner(
                            coalesce(node.full_path, client.area, '')
                        ) as collector_user_id
                    ) effective_owner on true
                    left join core.users effective_account
                      on effective_account.id = effective_owner.collector_user_id
                    where client.client_code ilike %s
                       or client.full_name ilike %s
                    order by client.full_name, client.client_code, client.id
                    limit %s
                    """,
                    (pattern, pattern, limit),
                )
                rows = cursor.fetchall()

        return tuple(
            AreaClientSearchResult(
                client_id=row["client_id"],
                client_code=row["client_code"],
                full_name=row["full_name"],
                area_uid=row["area_uid"],
                area_path=row["area_path"],
                effective_collector=_collector_from_row(
                    row,
                    id_key="effective_collector_user_id",
                    username_key="effective_collector_username",
                    full_name_key="effective_collector_full_name",
                ),
            )
            for row in rows
        )

    def effective_collector(self, area_path: str) -> UUID | None:
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select lending.collector_area_owner(%s)
                        as collector_user_id
                    """,
                    (area_path,),
                )
                row = cursor.fetchone()

        if row is None:
            return None
        return row["collector_user_id"]
