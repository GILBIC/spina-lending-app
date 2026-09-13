from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from psycopg.rows import dict_row

from .area_management_repository import AreaCollector, PostgresAreaManagementRepository
from .database import open_connection


_AREA_SEPARATOR = " › "


@dataclass(frozen=True, slots=True)
class AreaMoveImpactPreview:
    area_uid: UUID
    old_parent_area_uid: UUID | None
    new_parent_area_uid: UUID | None
    old_path: str
    new_path: str
    affected_node_count: int
    clients_affected: int
    descendant_areas_affected: int
    effective_collector_before: AreaCollector | None
    effective_collector_after: AreaCollector | None
    stale_delegated_access_count: int


def _collector_from_row(row) -> AreaCollector | None:
    if row is None or row["collector_user_id"] is None:
        return None
    return AreaCollector(
        user_id=row["collector_user_id"],
        username=row["collector_username"],
        full_name=row["collector_full_name"],
    )


def _current_collector(cursor, area_path: str) -> AreaCollector | None:
    cursor.execute(
        """
        select
            owner.collector_user_id,
            account.username as collector_username,
            account.full_name as collector_full_name
        from (
            select lending.collector_area_owner(%s) as collector_user_id
        ) owner
        left join core.users account
          on account.id = owner.collector_user_id
        """,
        (area_path,),
    )
    return _collector_from_row(cursor.fetchone())


def _planned_collector(
    cursor,
    area_path: str,
    planned_paths: Mapping[UUID, str],
) -> AreaCollector | None:
    planned_uids = list(planned_paths)
    planned_values = [planned_paths[area_uid] for area_uid in planned_uids]
    cursor.execute(
        """
        with planned(area_uid, full_path) as (
            select *
            from unnest(%s::uuid[], %s::text[])
        ),
        matching as (
            select
                assignment.collector_user_id,
                char_length(
                    lending.normalize_area_path(
                        coalesce(planned.full_path, assignment.area)
                    )
                ) as specificity
            from lending.collector_area_assignments assignment
            left join planned
              on planned.area_uid = assignment.area_uid
            where assignment.is_active = true
              and lending.area_path_contains(
                    coalesce(planned.full_path, assignment.area),
                    %s,
                    true
                  )
        ),
        most_specific as (
            select matching.collector_user_id
            from matching
            where matching.specificity = (
                select max(other.specificity)
                from matching other
            )
        ),
        resolved as (
            select case
                when count(distinct most_specific.collector_user_id) = 1
                    then max(most_specific.collector_user_id::text)::uuid
                else null
            end as collector_user_id
            from most_specific
        )
        select
            resolved.collector_user_id,
            account.username as collector_username,
            account.full_name as collector_full_name
        from resolved
        left join core.users account
          on account.id = resolved.collector_user_id
        """,
        (planned_uids, planned_values, area_path),
    )
    return _collector_from_row(cursor.fetchone())


def _stale_delegated_access_count(
    cursor,
    rows,
    planned_paths: Mapping[UUID, str],
) -> int:
    area_uids = [row["area_uid"] for row in rows]
    old_paths = [row["full_path"] for row in rows]
    new_paths = [planned_paths[area_uid] for area_uid in area_uids]
    cursor.execute(
        """
        with moved_paths(area_uid, old_path, new_path) as (
            select *
            from unnest(%s::uuid[], %s::text[], %s::text[])
        ),
        planned_nodes(area_uid, new_path) as (
            select *
            from unnest(%s::uuid[], %s::text[])
        ),
        assignment_paths as (
            select
                assignment.id,
                assignment.collector_user_id,
                assignment.area_uid,
                assignment.area as current_path,
                coalesce(planned.new_path, assignment.area) as planned_path
            from lending.collector_area_assignments assignment
            left join planned_nodes planned
              on planned.area_uid = assignment.area_uid
            where assignment.is_active = true
        ),
        new_owners as (
            select
                moved.area_uid,
                resolved.collector_user_id
            from moved_paths moved
            left join lateral (
                select case
                    when count(distinct most_specific.collector_user_id) = 1
                        then max(most_specific.collector_user_id::text)::uuid
                    else null
                end as collector_user_id
                from (
                    select candidate.collector_user_id
                    from assignment_paths candidate
                    where lending.area_path_contains(
                              candidate.planned_path,
                              moved.new_path,
                              true
                          )
                      and char_length(
                              lending.normalize_area_path(candidate.planned_path)
                          ) = (
                              select max(
                                  char_length(
                                      lending.normalize_area_path(other.planned_path)
                                  )
                              )
                              from assignment_paths other
                              where lending.area_path_contains(
                                  other.planned_path,
                                  moved.new_path,
                                  true
                              )
                          )
                ) most_specific
            ) resolved on true
        ),
        current_scopes as (
            select
                grant_scope.id as scope_id,
                grant_record.grantor_user_id,
                grant_scope.area_path,
                grant_scope.include_descendants,
                source_assignment.planned_path
            from lending.collector_area_access_grants grant_record
            join lending.collector_area_access_grant_scopes grant_scope
              on grant_scope.grant_id = grant_record.id
            join assignment_paths source_assignment
              on source_assignment.id = grant_scope.source_assignment_id
             and source_assignment.collector_user_id = grant_record.grantor_user_id
            where grant_record.revoked_at is null
              and grant_record.effective_at <= now()
              and grant_record.expires_at > now()
              and lower(
                    lending.normalize_area_path(source_assignment.current_path)
                  ) = lower(lending.normalize_area_path(grant_scope.area_path))
        ),
        stale_scopes as (
            select distinct current_scope.scope_id
            from current_scopes current_scope
            join moved_paths moved
              on lending.area_path_contains(
                    current_scope.area_path,
                    moved.old_path,
                    current_scope.include_descendants
                 )
            join new_owners new_owner
              on new_owner.area_uid = moved.area_uid
            where lending.collector_area_owner(moved.old_path) =
                  current_scope.grantor_user_id
              and not (
                    lower(
                        lending.normalize_area_path(current_scope.planned_path)
                    ) = lower(
                        lending.normalize_area_path(current_scope.area_path)
                    )
                    and new_owner.collector_user_id =
                        current_scope.grantor_user_id
                    and lending.area_path_contains(
                        current_scope.area_path,
                        moved.new_path,
                        current_scope.include_descendants
                    )
                  )
        )
        select count(*)::integer as stale_delegated_access_count
        from stale_scopes
        """,
        (area_uids, old_paths, new_paths, area_uids, new_paths),
    )
    row = cursor.fetchone()
    return int(row["stale_delegated_access_count"] if row else 0)


def _subtree_rows(cursor, area_uid: UUID):
    cursor.execute(
        """
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
            node.depth
        from lending.area_nodes node
        join subtree
          on subtree.area_uid = node.area_uid
        order by node.depth, node.area_uid
        """,
        (area_uid,),
    )
    rows = cursor.fetchall()
    if not rows:
        raise ValueError("The selected Area does not exist.")
    return rows


def preview_move_with_operational_impact(
    repository: PostgresAreaManagementRepository,
    *,
    area_uid: UUID,
    new_parent_area_uid: UUID | None,
) -> AreaMoveImpactPreview:
    structural = repository.preview_move(
        area_uid=area_uid,
        new_parent_area_uid=new_parent_area_uid,
    )

    with open_connection() as connection:  # noqa: SIM117
        with connection.cursor(row_factory=dict_row) as cursor:
            rows = _subtree_rows(cursor, area_uid)
            target = next(row for row in rows if row["area_uid"] == area_uid)
            if (
                target["full_path"] != structural.old_path
                or target["parent_area_uid"] != structural.old_parent_area_uid
            ):
                raise ValueError("The Area changed while the move preview was being prepared.")

            if new_parent_area_uid is None:
                expected_new_path = target["name"]
            else:
                cursor.execute(
                    """
                    select full_path, is_active
                    from lending.area_nodes
                    where area_uid = %s
                    """,
                    (new_parent_area_uid,),
                )
                new_parent = cursor.fetchone()
                if new_parent is None or not new_parent["is_active"]:
                    raise ValueError("The target parent changed while the preview was prepared.")
                expected_new_path = (
                    f'{new_parent["full_path"]}{_AREA_SEPARATOR}{target["name"]}'
                )
            if expected_new_path != structural.new_path:
                raise ValueError("The target parent changed while the preview was prepared.")

            planned_paths: dict[UUID, str] = {}
            for row in rows:
                old_path = row["full_path"]
                if old_path == structural.old_path:
                    suffix = ""
                elif old_path.startswith(structural.old_path + _AREA_SEPARATOR):
                    suffix = old_path[len(structural.old_path) :]
                else:
                    raise ValueError("The Area subtree contains an inconsistent path.")
                planned_paths[row["area_uid"]] = structural.new_path + suffix

            subtree_uids = [row["area_uid"] for row in rows]
            cursor.execute(
                """
                select count(*)::integer as clients_affected
                from lending.clients client
                where client.area_uid = any(%s::uuid[])
                """,
                (subtree_uids,),
            )
            client_row = cursor.fetchone()
            clients_affected = int(client_row["clients_affected"] if client_row else 0)

            effective_collector_before = _current_collector(
                cursor,
                structural.old_path,
            )
            effective_collector_after = _planned_collector(
                cursor,
                structural.new_path,
                planned_paths,
            )
            stale_delegated_access_count = _stale_delegated_access_count(
                cursor,
                rows,
                planned_paths,
            )

    return AreaMoveImpactPreview(
        area_uid=structural.area_uid,
        old_parent_area_uid=structural.old_parent_area_uid,
        new_parent_area_uid=structural.new_parent_area_uid,
        old_path=structural.old_path,
        new_path=structural.new_path,
        affected_node_count=structural.affected_node_count,
        clients_affected=clients_affected,
        descendant_areas_affected=max(len(rows) - 1, 0),
        effective_collector_before=effective_collector_before,
        effective_collector_after=effective_collector_after,
        stale_delegated_access_count=stale_delegated_access_count,
    )
