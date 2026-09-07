from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection


_AREA_SEPARATOR = " › "


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


@dataclass(frozen=True, slots=True)
class AreaMovePreview:
    area_uid: UUID
    old_parent_area_uid: UUID | None
    new_parent_area_uid: UUID | None
    old_path: str
    new_path: str
    affected_node_count: int


@dataclass(frozen=True, slots=True)
class ClientAreaTransferPreview:
    client_id: UUID
    old_area_uid: UUID | None
    old_area_path: str
    new_area_uid: UUID
    new_area_path: str
    old_effective_collector_user_id: UUID | None
    new_effective_collector_user_id: UUID
    effective_date: date
    timing: str


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


def _normalize_area_name(name: str) -> str:
    normalized = " ".join(name.strip().split())
    if not normalized or "›" in normalized:
        raise ValueError("Area name must be nonblank and cannot contain the hierarchy separator.")
    return normalized


def _node_by_uid(cursor, area_uid: UUID, *, for_update: bool = False):
    lock_clause = " for update" if for_update else ""
    cursor.execute(
        f"""
        select
            area_uid,
            parent_area_uid,
            name,
            full_path,
            depth,
            sort_order,
            is_active,
            is_legacy_unmapped
        from lending.area_nodes
        where area_uid = %s{lock_clause}
        """,
        (area_uid,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("The selected Area does not exist.")
    return row


def _subtree_rows(cursor, area_uid: UUID, *, for_update: bool = False):
    lock_clause = "for update of node" if for_update else ""
    cursor.execute(
        f"""
        with recursive subtree as (
            select root.area_uid
            from lending.area_nodes root
            where root.area_uid = %s

            union all

            select child.area_uid
            from lending.area_nodes child
            join subtree parent
              on child.parent_area_uid = parent.area_uid
        )
        select
            node.area_uid,
            node.parent_area_uid,
            node.name,
            node.full_path,
            node.depth,
            node.sort_order,
            node.is_active,
            node.is_legacy_unmapped
        from lending.area_nodes node
        join subtree on subtree.area_uid = node.area_uid
        order by node.depth, node.area_uid
        {lock_clause}
        """,
        (area_uid,),
    )
    rows = cursor.fetchall()
    if not rows:
        raise ValueError("The selected Area does not exist.")
    return rows


def _assert_path_available(
    cursor,
    full_path: str,
    *,
    excluded_area_uids: tuple[UUID, ...] = (),
) -> None:
    if excluded_area_uids:
        cursor.execute(
            """
            select 1
            from lending.area_nodes
            where lower(lending.normalize_area_path(full_path)) =
                  lower(lending.normalize_area_path(%s))
              and not (area_uid = any(%s::uuid[]))
            limit 1
            """,
            (full_path, list(excluded_area_uids)),
        )
    else:
        cursor.execute(
            """
            select 1
            from lending.area_nodes
            where lower(lending.normalize_area_path(full_path)) =
                  lower(lending.normalize_area_path(%s))
            limit 1
            """,
            (full_path,),
        )
    if cursor.fetchone() is not None:
        raise ValueError("An Area with that path already exists.")


def _sync_current_area_paths(cursor, path_by_uid: Mapping[UUID, str]) -> None:
    for area_uid, full_path in path_by_uid.items():
        cursor.execute(
            """
            update lending.clients
            set area = %s, updated_at = now()
            where area_uid = %s
            """,
            (full_path, area_uid),
        )
        cursor.execute(
            """
            update lending.collector_area_assignments
            set area = %s, updated_at = now()
            where area_uid = %s
            """,
            (full_path, area_uid),
        )
        cursor.execute(
            """
            update lending.client_area_pending_transfers
            set current_area_path_snapshot = %s
            where current_area_uid = %s
              and applied_at is null
              and cancelled_at is null
            """,
            (full_path, area_uid),
        )
        cursor.execute(
            """
            update lending.client_area_pending_transfers
            set target_area_path_snapshot = %s
            where target_area_uid = %s
              and applied_at is null
              and cancelled_at is null
            """,
            (full_path, area_uid),
        )


def _write_area_audit(
    cursor,
    *,
    actor_user_id: UUID,
    action: str,
    target_type: str,
    target_id: UUID | None,
    details: Mapping[str, Any],
) -> None:
    cursor.execute(
        """
        insert into core.audit_logs (
            actor_user_id,
            action,
            target_type,
            target_id,
            details
        ) values (%s, %s, %s, %s, %s)
        """,
        (actor_user_id, action, target_type, target_id, Jsonb(dict(details))),
    )


def _planned_subtree_paths(
    rows,
    *,
    old_prefix: str,
    new_prefix: str,
) -> dict[UUID, str]:
    planned: dict[UUID, str] = {}
    for row in rows:
        old_path = row["full_path"]
        if old_path == old_prefix:
            suffix = ""
        elif old_path.startswith(old_prefix + _AREA_SEPARATOR):
            suffix = old_path[len(old_prefix) :]
        else:
            raise ValueError("The Area subtree contains an inconsistent path.")
        planned[row["area_uid"]] = new_prefix + suffix
    return planned


def _client_transfer_decision(
    cursor,
    *,
    client_id: UUID,
    target_area_uid: UUID,
    as_of_date: date,
    for_update: bool,
) -> ClientAreaTransferPreview:
    lock_clause = " for update of client" if for_update else ""
    cursor.execute(
        f"""
        select
            client.id,
            client.area_uid,
            coalesce(
                node.full_path,
                nullif(lending.normalize_area_path(client.area), ''),
                ''
            ) as area_path,
            client.status
        from lending.clients client
        left join lending.area_nodes node
          on node.area_uid = client.area_uid
        where client.id = %s{lock_clause}
        """,
        (client_id,),
    )
    client = cursor.fetchone()
    if client is None:
        raise ValueError("The selected Client does not exist.")
    if client["status"] != "active":
        raise ValueError("Only an active Client can be transferred between Areas.")

    target = _node_by_uid(cursor, target_area_uid, for_update=for_update)
    if not target["is_active"]:
        raise ValueError("The target Area is retired.")
    if client["area_uid"] == target_area_uid:
        raise ValueError("The Client is already assigned to the target Area.")

    old_path = str(client["area_path"] or "")
    new_path = str(target["full_path"])
    cursor.execute(
        """
        select
            lending.collector_area_owner(%s) as old_collector_user_id,
            lending.collector_area_owner(%s) as new_collector_user_id
        """,
        (old_path, new_path),
    )
    owners = cursor.fetchone()
    new_owner = owners["new_collector_user_id"]
    if new_owner is None:
        raise ValueError("client_transfer_target_collector_unavailable")

    cursor.execute(
        """
        select exists (
            select 1
            from lending.collection_transactions transaction
            where transaction.client_id = %s
              and transaction.collection_date = %s
              and transaction.is_voided = false
        ) as collected_today
        """,
        (client_id, as_of_date),
    )
    collected_today = bool(cursor.fetchone()["collected_today"])

    if not collected_today:
        effective_date = as_of_date
        timing = "immediate"
    else:
        cursor.execute(
            """
            select min(installment.effective_due_date) as next_collection_date
            from lending.loans loan
            join lending.loan_contract_schedules schedule
              on schedule.loan_id = loan.id
             and schedule.status = 'active'
            join lending.loan_contract_schedule_registrations registration
              on registration.schedule_id = schedule.id
            join lending.loan_contract_installments_operational installment
              on installment.schedule_id = schedule.id
            where loan.client_id = %s
              and loan.status = 'active'
              and installment.effective_due_date > %s
              and coalesce(installment.removed_from_operational_schedule, false) = false
              and coalesce(
                    installment.operational_amount,
                    installment.contractual_amount
                  ) > 0
            """,
            (client_id, as_of_date),
        )
        next_row = cursor.fetchone()
        effective_date = next_row["next_collection_date"] if next_row else None
        if effective_date is None:
            raise ValueError("client_transfer_next_collection_day_unavailable")
        timing = "next_collection_day"

    return ClientAreaTransferPreview(
        client_id=client_id,
        old_area_uid=client["area_uid"],
        old_area_path=old_path,
        new_area_uid=target_area_uid,
        new_area_path=new_path,
        old_effective_collector_user_id=owners["old_collector_user_id"],
        new_effective_collector_user_id=new_owner,
        effective_date=effective_date,
        timing=timing,
    )


def apply_due_client_area_transfers(
    connection,
    *,
    as_of_date: date,
    client_id: UUID | None = None,
) -> int:
    """Apply due deferred transfers inside the caller's existing transaction."""

    applied_count = 0
    with connection.cursor(row_factory=dict_row) as pending_cursor:
        pending_cursor.execute(
            """
            select
                pending.id,
                pending.client_id,
                pending.current_area_uid,
                pending.current_area_path_snapshot,
                pending.target_area_uid,
                pending.target_area_path_snapshot,
                pending.effective_date,
                pending.scheduled_by_user_id,
                pending.scheduled_at
            from lending.client_area_pending_transfers pending
            where pending.applied_at is null
              and pending.cancelled_at is null
              and pending.effective_date <= %s
              and (%s::uuid is null or pending.client_id = %s)
            order by pending.effective_date, pending.scheduled_at, pending.id
            for update
            """,
            (as_of_date, client_id, client_id),
        )
        pending = pending_cursor.fetchone()
        while pending is not None:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        client.id,
                        client.area_uid,
                        coalesce(
                            node.full_path,
                            nullif(lending.normalize_area_path(client.area), ''),
                            ''
                        ) as area_path,
                        client.status
                    from lending.clients client
                    left join lending.area_nodes node
                      on node.area_uid = client.area_uid
                    where client.id = %s
                    for update of client
                    """,
                    (pending["client_id"],),
                )
                current = cursor.fetchone()
                if current is None or current["status"] != "active":
                    raise ValueError("client_transfer_client_unavailable")
                if current["area_uid"] != pending["current_area_uid"]:
                    raise ValueError("client_transfer_current_area_changed")

                target = _node_by_uid(cursor, pending["target_area_uid"], for_update=True)
                if not target["is_active"]:
                    raise ValueError("client_transfer_target_area_inactive")
                cursor.execute(
                    "select lending.collector_area_owner(%s) as collector_user_id",
                    (target["full_path"],),
                )
                if cursor.fetchone()["collector_user_id"] is None:
                    raise ValueError("client_transfer_target_collector_unavailable")

                cursor.execute(
                    """
                    update lending.clients
                    set area_uid = %s, area = %s, updated_at = now()
                    where id = %s
                    """,
                    (
                        pending["target_area_uid"],
                        target["full_path"],
                        pending["client_id"],
                    ),
                )
                cursor.execute(
                    """
                    update lending.client_area_pending_transfers
                    set applied_at = now()
                    where id = %s
                      and applied_at is null
                      and cancelled_at is null
                    """,
                    (pending["id"],),
                )
                cursor.execute(
                    """
                    insert into lending.client_area_transfer_history (
                        pending_transfer_id,
                        client_id,
                        old_area_uid,
                        old_area_path_snapshot,
                        new_area_uid,
                        new_area_path_snapshot,
                        effective_date,
                        timing,
                        scheduled_by_user_id,
                        scheduled_at,
                        applied_at
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s,
                        'next_collection_day', %s, %s, now()
                    )
                    """,
                    (
                        pending["id"],
                        pending["client_id"],
                        pending["current_area_uid"],
                        pending["current_area_path_snapshot"],
                        pending["target_area_uid"],
                        target["full_path"],
                        pending["effective_date"],
                        pending["scheduled_by_user_id"],
                        pending["scheduled_at"],
                    ),
                )
                _write_area_audit(
                    cursor,
                    actor_user_id=pending["scheduled_by_user_id"],
                    action="area.client.transfer.applied",
                    target_type="client",
                    target_id=pending["client_id"],
                    details={
                        "old_area_uid": str(pending["current_area_uid"])
                        if pending["current_area_uid"] is not None
                        else None,
                        "old_area_path": pending["current_area_path_snapshot"],
                        "new_area_uid": str(pending["target_area_uid"]),
                        "new_area_path": target["full_path"],
                        "effective_date": pending["effective_date"].isoformat(),
                        "timing": "next_collection_day",
                    },
                )
                applied_count += 1

            pending = pending_cursor.fetchone()

    return applied_count


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

    def create_area(
        self,
        *,
        actor_user_id: UUID,
        parent_area_uid: UUID | None,
        name: str,
    ) -> UUID:
        normalized_name = _normalize_area_name(name)

        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                if parent_area_uid is None:
                    full_path = normalized_name
                    depth = 0
                else:
                    parent = _node_by_uid(cursor, parent_area_uid, for_update=True)
                    if not parent["is_active"]:
                        raise ValueError("A new Area cannot be added under a retired Area.")
                    full_path = f'{parent["full_path"]}{_AREA_SEPARATOR}{normalized_name}'
                    depth = parent["depth"] + 1

                _assert_path_available(cursor, full_path)
                cursor.execute(
                    """
                    select coalesce(max(sort_order) + 1, 0)::integer as next_sort_order
                    from lending.area_nodes
                    where parent_area_uid is not distinct from %s
                    """,
                    (parent_area_uid,),
                )
                next_sort_order = cursor.fetchone()["next_sort_order"]
                cursor.execute(
                    """
                    insert into lending.area_nodes (
                        parent_area_uid,
                        name,
                        full_path,
                        depth,
                        sort_order,
                        is_active,
                        is_legacy_unmapped
                    ) values (%s, %s, %s, %s, %s, true, false)
                    returning area_uid
                    """,
                    (
                        parent_area_uid,
                        normalized_name,
                        full_path,
                        depth,
                        next_sort_order,
                    ),
                )
                area_uid = cursor.fetchone()["area_uid"]
                _write_area_audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="area.create",
                    target_type="area",
                    target_id=area_uid,
                    details={
                        "path": full_path,
                        "parent_area_uid": str(parent_area_uid)
                        if parent_area_uid is not None
                        else None,
                    },
                )
                return area_uid

    def rename_area(
        self,
        *,
        actor_user_id: UUID,
        area_uid: UUID,
        name: str,
    ) -> UUID:
        normalized_name = _normalize_area_name(name)

        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                rows = _subtree_rows(cursor, area_uid, for_update=True)
                target = next(row for row in rows if row["area_uid"] == area_uid)
                if not target["is_active"]:
                    raise ValueError("A retired Area cannot be renamed.")

                old_prefix = target["full_path"]
                if target["parent_area_uid"] is None:
                    new_prefix = normalized_name
                else:
                    parent = _node_by_uid(
                        cursor,
                        target["parent_area_uid"],
                        for_update=True,
                    )
                    new_prefix = (
                        f'{parent["full_path"]}{_AREA_SEPARATOR}{normalized_name}'
                    )

                subtree_uids = tuple(row["area_uid"] for row in rows)
                planned_paths = _planned_subtree_paths(
                    rows,
                    old_prefix=old_prefix,
                    new_prefix=new_prefix,
                )
                for planned_path in planned_paths.values():
                    _assert_path_available(
                        cursor,
                        planned_path,
                        excluded_area_uids=subtree_uids,
                    )

                for row in rows:
                    current_uid = row["area_uid"]
                    if current_uid == area_uid:
                        cursor.execute(
                            """
                            update lending.area_nodes
                            set name = %s, full_path = %s, updated_at = now()
                            where area_uid = %s
                            """,
                            (normalized_name, planned_paths[current_uid], current_uid),
                        )
                    else:
                        cursor.execute(
                            """
                            update lending.area_nodes
                            set full_path = %s, updated_at = now()
                            where area_uid = %s
                            """,
                            (planned_paths[current_uid], current_uid),
                        )

                _sync_current_area_paths(cursor, planned_paths)
                _write_area_audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="area.rename",
                    target_type="area",
                    target_id=area_uid,
                    details={"old_path": old_prefix, "new_path": new_prefix},
                )
                return area_uid

    def preview_move(
        self,
        *,
        area_uid: UUID,
        new_parent_area_uid: UUID | None,
    ) -> AreaMovePreview:
        if new_parent_area_uid == area_uid:
            raise ValueError("An Area cannot be moved under itself.")

        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                rows = _subtree_rows(cursor, area_uid, for_update=False)
                target = next(row for row in rows if row["area_uid"] == area_uid)
                if not target["is_active"]:
                    raise ValueError("A retired Area cannot be moved.")
                subtree_uids = tuple(row["area_uid"] for row in rows)
                if new_parent_area_uid in subtree_uids:
                    raise ValueError("An Area cannot be moved under one of its descendants.")
                if target["parent_area_uid"] == new_parent_area_uid:
                    raise ValueError("The Area is already under that parent.")

                if new_parent_area_uid is None:
                    new_prefix = target["name"]
                else:
                    parent = _node_by_uid(cursor, new_parent_area_uid)
                    if not parent["is_active"]:
                        raise ValueError("An Area cannot be moved under a retired Area.")
                    new_prefix = (
                        f'{parent["full_path"]}{_AREA_SEPARATOR}{target["name"]}'
                    )

                planned_paths = _planned_subtree_paths(
                    rows,
                    old_prefix=target["full_path"],
                    new_prefix=new_prefix,
                )
                for planned_path in planned_paths.values():
                    _assert_path_available(
                        cursor,
                        planned_path,
                        excluded_area_uids=subtree_uids,
                    )

                return AreaMovePreview(
                    area_uid=area_uid,
                    old_parent_area_uid=target["parent_area_uid"],
                    new_parent_area_uid=new_parent_area_uid,
                    old_path=target["full_path"],
                    new_path=new_prefix,
                    affected_node_count=len(rows),
                )

    def move_area(
        self,
        *,
        actor_user_id: UUID,
        area_uid: UUID,
        new_parent_area_uid: UUID | None,
    ) -> AreaMovePreview:
        if new_parent_area_uid == area_uid:
            raise ValueError("An Area cannot be moved under itself.")

        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                rows = _subtree_rows(cursor, area_uid, for_update=True)
                target = next(row for row in rows if row["area_uid"] == area_uid)
                if not target["is_active"]:
                    raise ValueError("A retired Area cannot be moved.")
                subtree_uids = tuple(row["area_uid"] for row in rows)
                if new_parent_area_uid in subtree_uids:
                    raise ValueError("An Area cannot be moved under one of its descendants.")
                old_parent_area_uid = target["parent_area_uid"]
                if old_parent_area_uid == new_parent_area_uid:
                    raise ValueError("The Area is already under that parent.")

                if new_parent_area_uid is None:
                    new_prefix = target["name"]
                    new_depth = 0
                else:
                    parent = _node_by_uid(cursor, new_parent_area_uid, for_update=True)
                    if not parent["is_active"]:
                        raise ValueError("An Area cannot be moved under a retired Area.")
                    new_prefix = (
                        f'{parent["full_path"]}{_AREA_SEPARATOR}{target["name"]}'
                    )
                    new_depth = parent["depth"] + 1

                planned_paths = _planned_subtree_paths(
                    rows,
                    old_prefix=target["full_path"],
                    new_prefix=new_prefix,
                )
                for planned_path in planned_paths.values():
                    _assert_path_available(
                        cursor,
                        planned_path,
                        excluded_area_uids=subtree_uids,
                    )

                cursor.execute(
                    """
                    select coalesce(max(sort_order) + 1, 0)::integer as next_sort_order
                    from lending.area_nodes
                    where parent_area_uid is not distinct from %s
                      and area_uid <> %s
                    """,
                    (new_parent_area_uid, area_uid),
                )
                next_sort_order = cursor.fetchone()["next_sort_order"]
                depth_delta = new_depth - target["depth"]

                for row in rows:
                    current_uid = row["area_uid"]
                    if current_uid == area_uid:
                        cursor.execute(
                            """
                            update lending.area_nodes
                            set
                                parent_area_uid = %s,
                                full_path = %s,
                                depth = %s,
                                sort_order = %s,
                                is_legacy_unmapped = case
                                    when %s::uuid is not null then false
                                    else is_legacy_unmapped
                                end,
                                updated_at = now()
                            where area_uid = %s
                            """,
                            (
                                new_parent_area_uid,
                                planned_paths[current_uid],
                                new_depth,
                                next_sort_order,
                                new_parent_area_uid,
                                current_uid,
                            ),
                        )
                    else:
                        cursor.execute(
                            """
                            update lending.area_nodes
                            set
                                full_path = %s,
                                depth = %s,
                                updated_at = now()
                            where area_uid = %s
                            """,
                            (
                                planned_paths[current_uid],
                                row["depth"] + depth_delta,
                                current_uid,
                            ),
                        )

                if old_parent_area_uid != new_parent_area_uid:
                    cursor.execute(
                        """
                        select area_uid
                        from lending.area_nodes
                        where parent_area_uid is not distinct from %s
                          and area_uid <> %s
                        order by sort_order, area_uid
                        for update
                        """,
                        (old_parent_area_uid, area_uid),
                    )
                    for sort_order, sibling in enumerate(cursor.fetchall()):
                        cursor.execute(
                            """
                            update lending.area_nodes
                            set sort_order = %s, updated_at = now()
                            where area_uid = %s
                            """,
                            (sort_order, sibling["area_uid"]),
                        )

                _sync_current_area_paths(cursor, planned_paths)
                _write_area_audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="area.move",
                    target_type="area",
                    target_id=area_uid,
                    details={
                        "old_path": target["full_path"],
                        "new_path": new_prefix,
                        "old_parent_area_uid": str(old_parent_area_uid)
                        if old_parent_area_uid is not None
                        else None,
                        "new_parent_area_uid": str(new_parent_area_uid)
                        if new_parent_area_uid is not None
                        else None,
                        "affected_node_count": len(rows),
                    },
                )
                return AreaMovePreview(
                    area_uid=area_uid,
                    old_parent_area_uid=old_parent_area_uid,
                    new_parent_area_uid=new_parent_area_uid,
                    old_path=target["full_path"],
                    new_path=new_prefix,
                    affected_node_count=len(rows),
                )

    def reorder_siblings(
        self,
        *,
        actor_user_id: UUID,
        parent_area_uid: UUID | None,
        ordered_area_uids: tuple[UUID, ...],
    ) -> tuple[UUID, ...]:
        if not ordered_area_uids:
            raise ValueError("At least one Area is required for reordering.")
        if len(set(ordered_area_uids)) != len(ordered_area_uids):
            raise ValueError("Each Area may appear only once in the new order.")

        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                if parent_area_uid is not None:
                    parent = _node_by_uid(cursor, parent_area_uid, for_update=True)
                    if not parent["is_active"]:
                        raise ValueError("Areas under a retired parent cannot be reordered.")
                cursor.execute(
                    """
                    select area_uid, sort_order
                    from lending.area_nodes
                    where parent_area_uid is not distinct from %s
                    order by sort_order, area_uid
                    for update
                    """,
                    (parent_area_uid,),
                )
                siblings = cursor.fetchall()
                sibling_uids = tuple(row["area_uid"] for row in siblings)
                if len(sibling_uids) != len(ordered_area_uids) or set(
                    sibling_uids
                ) != set(ordered_area_uids):
                    raise ValueError("The reorder must include the complete sibling set exactly once.")

                for sort_order, sibling_uid in enumerate(ordered_area_uids):
                    cursor.execute(
                        """
                        update lending.area_nodes
                        set sort_order = %s, updated_at = now()
                        where area_uid = %s
                        """,
                        (sort_order, sibling_uid),
                    )

                _write_area_audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="area.reorder",
                    target_type="area_siblings",
                    target_id=parent_area_uid,
                    details={
                        "parent_area_uid": str(parent_area_uid)
                        if parent_area_uid is not None
                        else None,
                        "ordered_area_uids": [str(value) for value in ordered_area_uids],
                    },
                )
                return ordered_area_uids

    def assign_collector(
        self,
        *,
        actor_user_id: UUID,
        area_uid: UUID,
        collector_user_id: UUID,
    ) -> UUID:
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                node = _node_by_uid(cursor, area_uid, for_update=True)
                if not node["is_active"]:
                    raise ValueError("A Collector cannot be assigned to a retired Area.")

                cursor.execute(
                    """
                    select exists (
                        select 1
                        from core.users account
                        join core.user_roles user_role
                          on user_role.user_id = account.id
                        join core.roles role
                          on role.id = user_role.role_id
                        where account.id = %s
                          and account.status = 'active'
                          and role.code = 'collector'
                    ) as is_active_collector
                    """,
                    (collector_user_id,),
                )
                if not cursor.fetchone()["is_active_collector"]:
                    raise ValueError("Only an active Collector account may own an Area.")

                cursor.execute(
                    """
                    select
                        id,
                        collector_user_id,
                        area,
                        sort_order,
                        is_active
                    from lending.collector_area_assignments
                    where area_uid = %s
                    order by created_at, id
                    for update
                    """,
                    (area_uid,),
                )
                assignments = cursor.fetchall()
                active_assignment = next(
                    (row for row in assignments if row["is_active"]),
                    None,
                )
                if (
                    active_assignment is not None
                    and active_assignment["collector_user_id"] == collector_user_id
                ):
                    return active_assignment["id"]

                previous_collector_user_id = (
                    active_assignment["collector_user_id"]
                    if active_assignment is not None
                    else None
                )
                if active_assignment is not None:
                    cursor.execute(
                        """
                        update lending.collector_area_assignments
                        set is_active = false, updated_at = now()
                        where id = %s
                        """,
                        (active_assignment["id"],),
                    )

                reusable_assignment = next(
                    (
                        row
                        for row in assignments
                        if row["collector_user_id"] == collector_user_id
                    ),
                    None,
                )
                if reusable_assignment is None:
                    cursor.execute(
                        """
                        insert into lending.collector_area_assignments (
                            collector_user_id,
                            area,
                            area_uid,
                            sort_order,
                            is_active
                        ) values (%s, %s, %s, %s, true)
                        returning id
                        """,
                        (
                            collector_user_id,
                            node["full_path"],
                            area_uid,
                            node["sort_order"],
                        ),
                    )
                    assignment_id = cursor.fetchone()["id"]
                else:
                    cursor.execute(
                        """
                        update lending.collector_area_assignments
                        set
                            area = %s,
                            area_uid = %s,
                            sort_order = %s,
                            is_active = true,
                            updated_at = now()
                        where id = %s
                        returning id
                        """,
                        (
                            node["full_path"],
                            area_uid,
                            node["sort_order"],
                            reusable_assignment["id"],
                        ),
                    )
                    assignment_id = cursor.fetchone()["id"]

                _write_area_audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="area.collector.assign",
                    target_type="area",
                    target_id=area_uid,
                    details={
                        "area_path": node["full_path"],
                        "previous_collector_user_id": str(previous_collector_user_id)
                        if previous_collector_user_id is not None
                        else None,
                        "collector_user_id": str(collector_user_id),
                    },
                )
                return assignment_id

    def remove_collector_assignment(
        self,
        *,
        actor_user_id: UUID,
        area_uid: UUID,
    ) -> UUID:
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                node = _node_by_uid(cursor, area_uid, for_update=True)
                if not node["is_active"]:
                    raise ValueError("A retired Area cannot change its Collector assignment.")

                cursor.execute(
                    """
                    select id, collector_user_id
                    from lending.collector_area_assignments
                    where area_uid = %s
                      and is_active = true
                    for update
                    """,
                    (area_uid,),
                )
                assignment = cursor.fetchone()
                if assignment is None:
                    raise ValueError("This Area does not have a direct Collector assignment to remove.")

                cursor.execute(
                    """
                    update lending.collector_area_assignments
                    set is_active = false, updated_at = now()
                    where id = %s
                    """,
                    (assignment["id"],),
                )
                _write_area_audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="area.collector.remove",
                    target_type="area",
                    target_id=area_uid,
                    details={
                        "area_path": node["full_path"],
                        "collector_user_id": str(assignment["collector_user_id"]),
                    },
                )
                return assignment["collector_user_id"]

    def preview_client_transfer(
        self,
        *,
        client_id: UUID,
        target_area_uid: UUID,
        as_of_date: date,
    ) -> ClientAreaTransferPreview:
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                return _client_transfer_decision(
                    cursor,
                    client_id=client_id,
                    target_area_uid=target_area_uid,
                    as_of_date=as_of_date,
                    for_update=False,
                )

    def schedule_client_transfer(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        target_area_uid: UUID,
        as_of_date: date,
    ) -> ClientAreaTransferPreview:
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                preview = _client_transfer_decision(
                    cursor,
                    client_id=client_id,
                    target_area_uid=target_area_uid,
                    as_of_date=as_of_date,
                    for_update=True,
                )

                cursor.execute(
                    """
                    select id, target_area_uid, effective_date
                    from lending.client_area_pending_transfers
                    where client_id = %s
                      and applied_at is null
                      and cancelled_at is null
                    for update
                    """,
                    (client_id,),
                )
                prior_pending = cursor.fetchone()
                if prior_pending is not None:
                    cursor.execute(
                        """
                        update lending.client_area_pending_transfers
                        set
                            cancelled_at = now(),
                            cancelled_by_user_id = %s,
                            cancellation_reason = %s
                        where id = %s
                        """,
                        (
                            actor_user_id,
                            "Replaced by a newer Client Area transfer request.",
                            prior_pending["id"],
                        ),
                    )
                    _write_area_audit(
                        cursor,
                        actor_user_id=actor_user_id,
                        action="area.client.transfer.cancelled",
                        target_type="client",
                        target_id=client_id,
                        details={
                            "pending_transfer_id": str(prior_pending["id"]),
                            "target_area_uid": str(prior_pending["target_area_uid"]),
                            "effective_date": prior_pending["effective_date"].isoformat(),
                            "reason": "replaced",
                        },
                    )

                if preview.timing == "immediate":
                    cursor.execute(
                        """
                        update lending.clients
                        set area_uid = %s, area = %s, updated_at = now()
                        where id = %s
                        """,
                        (preview.new_area_uid, preview.new_area_path, client_id),
                    )
                    cursor.execute(
                        """
                        insert into lending.client_area_transfer_history (
                            pending_transfer_id,
                            client_id,
                            old_area_uid,
                            old_area_path_snapshot,
                            new_area_uid,
                            new_area_path_snapshot,
                            effective_date,
                            timing,
                            scheduled_by_user_id,
                            scheduled_at,
                            applied_at
                        ) values (
                            null, %s, %s, %s, %s, %s, %s,
                            'immediate', %s, now(), now()
                        )
                        """,
                        (
                            client_id,
                            preview.old_area_uid,
                            preview.old_area_path,
                            preview.new_area_uid,
                            preview.new_area_path,
                            preview.effective_date,
                            actor_user_id,
                        ),
                    )
                    action = "area.client.transfer"
                else:
                    cursor.execute(
                        """
                        insert into lending.client_area_pending_transfers (
                            client_id,
                            current_area_uid,
                            current_area_path_snapshot,
                            target_area_uid,
                            target_area_path_snapshot,
                            effective_date,
                            scheduled_by_user_id,
                            scheduled_at
                        ) values (%s, %s, %s, %s, %s, %s, %s, now())
                        """,
                        (
                            client_id,
                            preview.old_area_uid,
                            preview.old_area_path,
                            preview.new_area_uid,
                            preview.new_area_path,
                            preview.effective_date,
                            actor_user_id,
                        ),
                    )
                    action = "area.client.transfer.scheduled"

                _write_area_audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action=action,
                    target_type="client",
                    target_id=client_id,
                    details={
                        "old_area_uid": str(preview.old_area_uid)
                        if preview.old_area_uid is not None
                        else None,
                        "old_area_path": preview.old_area_path,
                        "new_area_uid": str(preview.new_area_uid),
                        "new_area_path": preview.new_area_path,
                        "effective_date": preview.effective_date.isoformat(),
                        "timing": preview.timing,
                    },
                )
                return preview
