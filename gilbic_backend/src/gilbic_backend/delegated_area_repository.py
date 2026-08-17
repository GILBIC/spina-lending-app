from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection


class DelegatedAreaError(RuntimeError):
    code = "delegated_area_error"


class DelegatedAreaNotFound(DelegatedAreaError):
    code = "delegated_area_not_found"


class DelegatedAreaForbidden(DelegatedAreaError):
    code = "delegated_area_forbidden"


class DelegatedAreaInvalid(DelegatedAreaError):
    code = "delegated_area_invalid"


class DelegatedAreaConflict(DelegatedAreaError):
    code = "delegated_area_conflict"


@dataclass(frozen=True, slots=True)
class DelegatedAreaScopeRecord:
    assignment_id: UUID
    owner_user_id: UUID
    owner_name: str
    area_path: str
    sort_order: int
    include_descendants: bool = False


@dataclass(frozen=True, slots=True)
class DelegatedAreaRequestRecord:
    request_id: UUID
    requester_user_id: UUID
    requester_name: str
    requested_owner_user_id: UUID
    requested_owner_name: str
    scope_mode: str
    reason: str
    requested_expires_at: datetime
    status: str
    decision_reason: str
    created_at: datetime
    scopes: tuple[DelegatedAreaScopeRecord, ...]


@dataclass(frozen=True, slots=True)
class DelegatedAreaGrantRecord:
    grant_id: UUID
    source_request_id: UUID | None
    grantor_user_id: UUID
    grantor_name: str
    visiting_collector_user_id: UUID
    visiting_collector_name: str
    effective_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revocation_reason: str
    scopes: tuple[DelegatedAreaScopeRecord, ...]


class PostgresDelegatedAreaRepository:
    def list_available_owner_scopes(
        self,
        *,
        requester_user_id: UUID,
    ) -> tuple[DelegatedAreaScopeRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        assignment.id as assignment_id,
                        assignment.collector_user_id as owner_user_id,
                        owner.full_name as owner_name,
                        assignment.area as area_path,
                        assignment.sort_order
                    from lending.collector_area_assignments assignment
                    join core.users owner
                      on owner.id = assignment.collector_user_id
                     and owner.status = 'active'
                    where assignment.is_active = true
                      and assignment.collector_user_id <> %s
                    order by
                        lower(owner.full_name),
                        assignment.sort_order,
                        lower(lending.normalize_area_path(assignment.area)),
                        assignment.id
                    """,
                    (requester_user_id,),
                )
                rows = cursor.fetchall()
        return tuple(self._scope_from_row(row) for row in rows)

    def list_owned_scopes(
        self,
        *,
        owner_user_id: UUID,
    ) -> tuple[DelegatedAreaScopeRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        assignment.id as assignment_id,
                        assignment.collector_user_id as owner_user_id,
                        owner.full_name as owner_name,
                        assignment.area as area_path,
                        assignment.sort_order
                    from lending.collector_area_assignments assignment
                    join core.users owner
                      on owner.id = assignment.collector_user_id
                     and owner.status = 'active'
                    where assignment.is_active = true
                      and assignment.collector_user_id = %s
                    order by
                        assignment.sort_order,
                        lower(lending.normalize_area_path(assignment.area)),
                        assignment.id
                    """,
                    (owner_user_id,),
                )
                rows = cursor.fetchall()
        return tuple(self._scope_from_row(row) for row in rows)

    def create_request(
        self,
        *,
        requester_user_id: UUID,
        requested_owner_user_id: UUID,
        assignment_scopes: tuple[tuple[UUID, bool], ...],
        scope_mode: str,
        reason: str,
        requested_expires_at: datetime,
    ) -> DelegatedAreaRequestRecord:
        now = datetime.now(timezone.utc)
        if requester_user_id == requested_owner_user_id:
            raise DelegatedAreaInvalid("A Collector cannot request delegated access from themselves.")
        if requested_expires_at.tzinfo is None:
            raise DelegatedAreaInvalid("Delegated access expiry must include a timezone.")
        requested_expires_at = requested_expires_at.astimezone(timezone.utc)
        if requested_expires_at <= now:
            raise DelegatedAreaInvalid("Delegated access expiry must be in the future.")
        if scope_mode not in {"selected_paths", "all_owner_areas"}:
            raise DelegatedAreaInvalid("Unsupported delegated area scope mode.")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise DelegatedAreaInvalid("A reason is required for delegated area access.")

        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._advisory_lock(
                        cursor,
                        f"delegated-area-request:{requester_user_id}:{requested_owner_user_id}",
                    )
                    self._require_active_collector(cursor, requester_user_id)
                    self._require_active_collector(cursor, requested_owner_user_id)

                    if scope_mode == "all_owner_areas":
                        scopes = self._owned_scope_rows_for_update(
                            cursor,
                            owner_user_id=requested_owner_user_id,
                        )
                    else:
                        scopes = self._selected_scope_rows_for_update(
                            cursor,
                            owner_user_id=requested_owner_user_id,
                            assignment_scopes=assignment_scopes,
                        )
                    if not scopes:
                        raise DelegatedAreaInvalid("At least one currently assigned area is required.")

                    cursor.execute(
                        """
                        select 1
                        from lending.collector_area_access_requests request
                        where request.requester_user_id = %s
                          and request.requested_owner_user_id = %s
                          and request.status = 'pending'
                          and request.requested_expires_at > %s
                        limit 1
                        """,
                        (requester_user_id, requested_owner_user_id, now),
                    )
                    if cursor.fetchone() is not None:
                        raise DelegatedAreaConflict(
                            "There is already a pending delegated-area request for this Collector."
                        )

                    request_id = uuid4()
                    cursor.execute(
                        """
                        insert into lending.collector_area_access_requests (
                            id,
                            requester_user_id,
                            requested_owner_user_id,
                            scope_mode,
                            reason,
                            requested_expires_at,
                            status,
                            created_at,
                            updated_at
                        ) values (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                        """,
                        (
                            request_id,
                            requester_user_id,
                            requested_owner_user_id,
                            scope_mode,
                            normalized_reason,
                            requested_expires_at,
                            now,
                            now,
                        ),
                    )
                    selected_flags = {assignment_id: include for assignment_id, include in assignment_scopes}
                    for row in scopes:
                        include_descendants = (
                            True
                            if scope_mode == "all_owner_areas"
                            else bool(selected_flags.get(row["assignment_id"], False))
                        )
                        cursor.execute(
                            """
                            insert into lending.collector_area_access_request_scopes (
                                request_id,
                                source_assignment_id,
                                area_path,
                                include_descendants
                            ) values (%s, %s, %s, %s)
                            """,
                            (
                                request_id,
                                row["assignment_id"],
                                row["area_path"],
                                include_descendants,
                            ),
                        )
                    self._insert_event(
                        cursor,
                        request_id=request_id,
                        grant_id=None,
                        actor_user_id=requester_user_id,
                        event_type="request_created",
                        details={
                            "scope_mode": scope_mode,
                            "requested_owner_user_id": str(requested_owner_user_id),
                            "requested_expires_at": requested_expires_at.isoformat(),
                            "scope_count": len(scopes),
                        },
                    )
        return self.get_request(request_id=request_id, actor_user_id=requester_user_id)

    def list_incoming_requests(
        self,
        *,
        owner_user_id: UUID,
    ) -> tuple[DelegatedAreaRequestRecord, ...]:
        return self._list_requests(
            where_sql="request.requested_owner_user_id = %s",
            params=(owner_user_id,),
        )

    def list_outgoing_requests(
        self,
        *,
        requester_user_id: UUID,
    ) -> tuple[DelegatedAreaRequestRecord, ...]:
        return self._list_requests(
            where_sql="request.requester_user_id = %s",
            params=(requester_user_id,),
        )

    def get_request(
        self,
        *,
        request_id: UUID,
        actor_user_id: UUID,
    ) -> DelegatedAreaRequestRecord:
        requests = self._list_requests(
            where_sql=(
                "request.id = %s and "
                "(request.requester_user_id = %s or request.requested_owner_user_id = %s)"
            ),
            params=(request_id, actor_user_id, actor_user_id),
        )
        if not requests:
            raise DelegatedAreaNotFound("Delegated area request was not found.")
        return requests[0]

    def approve_request(
        self,
        *,
        owner_user_id: UUID,
        request_id: UUID,
        decision_reason: str,
    ) -> DelegatedAreaGrantRecord:
        now = datetime.now(timezone.utc)
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    request = self._request_for_update(cursor, request_id=request_id)
                    self._require_request_owner(request, owner_user_id)
                    self._require_request_pending(request)
                    if request["requested_expires_at"] <= now:
                        raise DelegatedAreaConflict(
                            "This delegated-area request has already reached its requested expiry."
                        )
                    scopes = self._request_scope_rows(cursor, request_id=request_id, for_update=True)
                    if not scopes:
                        raise DelegatedAreaConflict("The delegated-area request has no scope.")
                    self._assert_owner_still_owns_scopes(
                        cursor,
                        owner_user_id=owner_user_id,
                        scopes=scopes,
                    )
                    self._require_active_collector(cursor, request["requester_user_id"])
                    self._require_active_collector(cursor, owner_user_id)

                    grant_id = uuid4()
                    cursor.execute(
                        """
                        insert into lending.collector_area_access_grants (
                            id,
                            source_request_id,
                            grantor_user_id,
                            visiting_collector_user_id,
                            effective_at,
                            expires_at,
                            created_at,
                            updated_at
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            grant_id,
                            request_id,
                            owner_user_id,
                            request["requester_user_id"],
                            now,
                            request["requested_expires_at"],
                            now,
                            now,
                        ),
                    )
                    for scope in scopes:
                        cursor.execute(
                            """
                            insert into lending.collector_area_access_grant_scopes (
                                grant_id,
                                source_assignment_id,
                                area_path,
                                include_descendants
                            ) values (%s, %s, %s, %s)
                            """,
                            (
                                grant_id,
                                scope["source_assignment_id"],
                                scope["area_path"],
                                scope["include_descendants"],
                            ),
                        )
                    cursor.execute(
                        """
                        update lending.collector_area_access_requests
                        set status = 'approved',
                            decided_by_user_id = %s,
                            decided_at = %s,
                            decision_reason = %s,
                            updated_at = %s
                        where id = %s
                        """,
                        (owner_user_id, now, decision_reason.strip(), now, request_id),
                    )
                    self._insert_event(
                        cursor,
                        request_id=request_id,
                        grant_id=grant_id,
                        actor_user_id=owner_user_id,
                        event_type="request_approved",
                        details={"scope_count": len(scopes)},
                    )
        return self.get_grant(grant_id=grant_id, actor_user_id=owner_user_id)

    def decline_request(
        self,
        *,
        owner_user_id: UUID,
        request_id: UUID,
        decision_reason: str,
    ) -> DelegatedAreaRequestRecord:
        return self._decide_request(
            actor_user_id=owner_user_id,
            request_id=request_id,
            status="declined",
            decision_reason=decision_reason,
            require_owner=True,
        )

    def cancel_request(
        self,
        *,
        requester_user_id: UUID,
        request_id: UUID,
        decision_reason: str,
    ) -> DelegatedAreaRequestRecord:
        return self._decide_request(
            actor_user_id=requester_user_id,
            request_id=request_id,
            status="cancelled",
            decision_reason=decision_reason,
            require_owner=False,
        )

    def list_active_grants(
        self,
        *,
        actor_user_id: UUID,
    ) -> tuple[DelegatedAreaGrantRecord, ...]:
        now = datetime.now(timezone.utc)
        return self._list_grants(
            where_sql=(
                "(grant_record.grantor_user_id = %s or "
                "grant_record.visiting_collector_user_id = %s) "
                "and grant_record.revoked_at is null "
                "and grant_record.expires_at > %s"
            ),
            params=(actor_user_id, actor_user_id, now),
        )

    def get_grant(
        self,
        *,
        grant_id: UUID,
        actor_user_id: UUID,
    ) -> DelegatedAreaGrantRecord:
        grants = self._list_grants(
            where_sql=(
                "grant_record.id = %s and "
                "(grant_record.grantor_user_id = %s or "
                "grant_record.visiting_collector_user_id = %s)"
            ),
            params=(grant_id, actor_user_id, actor_user_id),
        )
        if not grants:
            raise DelegatedAreaNotFound("Delegated area grant was not found.")
        return grants[0]

    def revoke_grant(
        self,
        *,
        grantor_user_id: UUID,
        grant_id: UUID,
        reason: str,
    ) -> DelegatedAreaGrantRecord:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise DelegatedAreaInvalid("A revocation reason is required.")
        now = datetime.now(timezone.utc)
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select * from lending.collector_area_access_grants where id = %s for update",
                        (grant_id,),
                    )
                    grant = cursor.fetchone()
                    if grant is None:
                        raise DelegatedAreaNotFound("Delegated area grant was not found.")
                    if grant["grantor_user_id"] != grantor_user_id:
                        raise DelegatedAreaForbidden(
                            "Only the Collector who granted this area access may revoke it."
                        )
                    if grant["revoked_at"] is not None:
                        raise DelegatedAreaConflict("This delegated area grant is already revoked.")
                    cursor.execute(
                        """
                        update lending.collector_area_access_grants
                        set revoked_at = %s,
                            revoked_by_user_id = %s,
                            revocation_reason = %s,
                            updated_at = %s
                        where id = %s
                        """,
                        (now, grantor_user_id, normalized_reason, now, grant_id),
                    )
                    self._insert_event(
                        cursor,
                        request_id=grant["source_request_id"],
                        grant_id=grant_id,
                        actor_user_id=grantor_user_id,
                        event_type="grant_revoked",
                        details={"reason": normalized_reason},
                    )
        return self.get_grant(grant_id=grant_id, actor_user_id=grantor_user_id)

    def has_active_access(
        self,
        *,
        visiting_collector_user_id: UUID,
        area_path: str,
    ) -> bool:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select lending.collector_has_active_delegated_area_access(%s, %s, now())",
                    (visiting_collector_user_id, area_path),
                )
                row = cursor.fetchone()
        return bool(row and row[0])

    def _decide_request(
        self,
        *,
        actor_user_id: UUID,
        request_id: UUID,
        status: str,
        decision_reason: str,
        require_owner: bool,
    ) -> DelegatedAreaRequestRecord:
        normalized_reason = decision_reason.strip()
        now = datetime.now(timezone.utc)
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    request = self._request_for_update(cursor, request_id=request_id)
                    if require_owner:
                        self._require_request_owner(request, actor_user_id)
                    elif request["requester_user_id"] != actor_user_id:
                        raise DelegatedAreaForbidden(
                            "Only the requesting Collector may cancel this request."
                        )
                    self._require_request_pending(request)
                    cursor.execute(
                        """
                        update lending.collector_area_access_requests
                        set status = %s,
                            decided_by_user_id = %s,
                            decided_at = %s,
                            decision_reason = %s,
                            updated_at = %s
                        where id = %s
                        """,
                        (status, actor_user_id, now, normalized_reason, now, request_id),
                    )
                    self._insert_event(
                        cursor,
                        request_id=request_id,
                        grant_id=None,
                        actor_user_id=actor_user_id,
                        event_type=f"request_{status}",
                        details={"reason": normalized_reason},
                    )
        return self.get_request(request_id=request_id, actor_user_id=actor_user_id)

    def _list_requests(self, *, where_sql: str, params: tuple[object, ...]) -> tuple[DelegatedAreaRequestRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    select
                        request.*,
                        requester.full_name as requester_name,
                        owner.full_name as requested_owner_name
                    from lending.collector_area_access_requests request
                    join core.users requester on requester.id = request.requester_user_id
                    join core.users owner on owner.id = request.requested_owner_user_id
                    where {where_sql}
                    order by request.created_at desc, request.id
                    """,
                    params,
                )
                rows = cursor.fetchall()
                return tuple(
                    self._request_record(cursor, row)
                    for row in rows
                )

    def _list_grants(self, *, where_sql: str, params: tuple[object, ...]) -> tuple[DelegatedAreaGrantRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    select
                        grant_record.*,
                        grantor.full_name as grantor_name,
                        visitor.full_name as visiting_collector_name
                    from lending.collector_area_access_grants grant_record
                    join core.users grantor on grantor.id = grant_record.grantor_user_id
                    join core.users visitor on visitor.id = grant_record.visiting_collector_user_id
                    where {where_sql}
                    order by grant_record.created_at desc, grant_record.id
                    """,
                    params,
                )
                rows = cursor.fetchall()
                return tuple(self._grant_record(cursor, row) for row in rows)

    def _request_record(self, cursor, row) -> DelegatedAreaRequestRecord:
        scopes = self._request_scope_rows(cursor, request_id=row["id"], for_update=False)
        return DelegatedAreaRequestRecord(
            request_id=row["id"],
            requester_user_id=row["requester_user_id"],
            requester_name=str(row["requester_name"]),
            requested_owner_user_id=row["requested_owner_user_id"],
            requested_owner_name=str(row["requested_owner_name"]),
            scope_mode=str(row["scope_mode"]),
            reason=str(row["reason"]),
            requested_expires_at=row["requested_expires_at"],
            status=str(row["status"]),
            decision_reason=str(row["decision_reason"] or ""),
            created_at=row["created_at"],
            scopes=tuple(
                DelegatedAreaScopeRecord(
                    assignment_id=scope["source_assignment_id"],
                    owner_user_id=row["requested_owner_user_id"],
                    owner_name=str(row["requested_owner_name"]),
                    area_path=str(scope["area_path"]),
                    sort_order=int(scope["sort_order"]),
                    include_descendants=bool(scope["include_descendants"]),
                )
                for scope in scopes
            ),
        )

    def _grant_record(self, cursor, row) -> DelegatedAreaGrantRecord:
        cursor.execute(
            """
            select
                scope.source_assignment_id,
                scope.area_path,
                scope.include_descendants,
                assignment.sort_order
            from lending.collector_area_access_grant_scopes scope
            join lending.collector_area_assignments assignment
              on assignment.id = scope.source_assignment_id
            where scope.grant_id = %s
            order by assignment.sort_order, lower(lending.normalize_area_path(scope.area_path)), scope.id
            """,
            (row["id"],),
        )
        scopes = cursor.fetchall()
        return DelegatedAreaGrantRecord(
            grant_id=row["id"],
            source_request_id=row["source_request_id"],
            grantor_user_id=row["grantor_user_id"],
            grantor_name=str(row["grantor_name"]),
            visiting_collector_user_id=row["visiting_collector_user_id"],
            visiting_collector_name=str(row["visiting_collector_name"]),
            effective_at=row["effective_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            revocation_reason=str(row["revocation_reason"] or ""),
            scopes=tuple(
                DelegatedAreaScopeRecord(
                    assignment_id=scope["source_assignment_id"],
                    owner_user_id=row["grantor_user_id"],
                    owner_name=str(row["grantor_name"]),
                    area_path=str(scope["area_path"]),
                    sort_order=int(scope["sort_order"]),
                    include_descendants=bool(scope["include_descendants"]),
                )
                for scope in scopes
            ),
        )

    @staticmethod
    def _scope_from_row(row) -> DelegatedAreaScopeRecord:
        return DelegatedAreaScopeRecord(
            assignment_id=row["assignment_id"],
            owner_user_id=row["owner_user_id"],
            owner_name=str(row["owner_name"]),
            area_path=str(row["area_path"]),
            sort_order=int(row["sort_order"]),
        )

    @staticmethod
    def _advisory_lock(cursor, key: str) -> None:
        cursor.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (key,))

    @staticmethod
    def _require_active_collector(cursor, user_id: UUID) -> None:
        cursor.execute(
            """
            select 1
            from core.users user_account
            join core.user_roles user_role on user_role.user_id = user_account.id
            join core.roles role on role.id = user_role.role_id
            where user_account.id = %s
              and user_account.status = 'active'
              and role.code = 'collector'
            limit 1
            """,
            (user_id,),
        )
        if cursor.fetchone() is None:
            raise DelegatedAreaInvalid("Delegated area access is available only between active Collectors.")

    @staticmethod
    def _owned_scope_rows_for_update(cursor, *, owner_user_id: UUID):
        cursor.execute(
            """
            select id as assignment_id, area as area_path, sort_order
            from lending.collector_area_assignments
            where collector_user_id = %s
              and is_active = true
            order by sort_order, lower(lending.normalize_area_path(area)), id
            for update
            """,
            (owner_user_id,),
        )
        return cursor.fetchall()

    @staticmethod
    def _selected_scope_rows_for_update(
        cursor,
        *,
        owner_user_id: UUID,
        assignment_scopes: tuple[tuple[UUID, bool], ...],
    ):
        assignment_ids = tuple(dict.fromkeys(assignment_id for assignment_id, _ in assignment_scopes))
        if not assignment_ids:
            return []
        cursor.execute(
            """
            select id as assignment_id, area as area_path, sort_order
            from lending.collector_area_assignments
            where collector_user_id = %s
              and is_active = true
              and id = any(%s)
            order by sort_order, lower(lending.normalize_area_path(area)), id
            for update
            """,
            (owner_user_id, list(assignment_ids)),
        )
        rows = cursor.fetchall()
        if len(rows) != len(assignment_ids):
            raise DelegatedAreaForbidden(
                "One or more requested areas are not currently assigned to that Collector."
            )
        return rows

    @staticmethod
    def _request_for_update(cursor, *, request_id: UUID):
        cursor.execute(
            "select * from lending.collector_area_access_requests where id = %s for update",
            (request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise DelegatedAreaNotFound("Delegated area request was not found.")
        return row

    @staticmethod
    def _request_scope_rows(cursor, *, request_id: UUID, for_update: bool):
        sql = """
            select
                scope.source_assignment_id,
                scope.area_path,
                scope.include_descendants,
                assignment.sort_order
            from lending.collector_area_access_request_scopes scope
            join lending.collector_area_assignments assignment
              on assignment.id = scope.source_assignment_id
            where scope.request_id = %s
            order by assignment.sort_order, lower(lending.normalize_area_path(scope.area_path)), scope.id
        """
        if for_update:
            sql += " for update of scope"
        cursor.execute(sql, (request_id,))
        return cursor.fetchall()

    @staticmethod
    def _assert_owner_still_owns_scopes(cursor, *, owner_user_id: UUID, scopes) -> None:
        assignment_ids = [scope["source_assignment_id"] for scope in scopes]
        cursor.execute(
            """
            select id, area
            from lending.collector_area_assignments
            where id = any(%s)
              and collector_user_id = %s
              and is_active = true
            for update
            """,
            (assignment_ids, owner_user_id),
        )
        current = {row["id"]: str(row["area"]) for row in cursor.fetchall()}
        if len(current) != len(assignment_ids):
            raise DelegatedAreaConflict(
                "Area ownership changed after this request. A new owner must explicitly grant access."
            )
        for scope in scopes:
            assignment_id = scope["source_assignment_id"]
            if current[assignment_id].strip().casefold() != str(scope["area_path"]).strip().casefold():
                raise DelegatedAreaConflict(
                    "Area ownership/path changed after this request. Create a new delegated-area request."
                )

    @staticmethod
    def _require_request_owner(request, owner_user_id: UUID) -> None:
        if request["requested_owner_user_id"] != owner_user_id:
            raise DelegatedAreaForbidden(
                "Only the Collector who owns the requested area scope may decide this request."
            )

    @staticmethod
    def _require_request_pending(request) -> None:
        if request["status"] != "pending":
            raise DelegatedAreaConflict("This delegated-area request is no longer pending.")

    @staticmethod
    def _insert_event(
        cursor,
        *,
        request_id: UUID | None,
        grant_id: UUID | None,
        actor_user_id: UUID,
        event_type: str,
        details: dict[str, object],
    ) -> None:
        cursor.execute(
            """
            insert into lending.collector_area_access_events (
                request_id,
                grant_id,
                actor_user_id,
                event_type,
                details
            ) values (%s, %s, %s, %s, %s)
            """,
            (request_id, grant_id, actor_user_id, event_type, Jsonb(details)),
        )
