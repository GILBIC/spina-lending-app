from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


SupportCategory = Literal["payment", "loan", "renewal", "account", "other"]
SupportStatus = Literal["open", "answered", "resolved", "cancelled"]
SupportAction = Literal["answered", "resolved"]


class SupportError(RuntimeError):
    code = "support_error"


class SupportBorrowerNotLinked(SupportError):
    code = "support_borrower_not_linked"


class SupportRequestNotFound(SupportError):
    code = "support_request_not_found"


class SupportConflict(SupportError):
    code = "support_conflict"


@dataclass(frozen=True, slots=True)
class SupportRequestRecord:
    request_id: UUID
    client_id: UUID
    client_code: str
    client_name: str
    category: SupportCategory
    subject: str
    message: str
    reference_text: str
    status: SupportStatus
    created_at: datetime
    managed_by_name: str | None
    management_response: str
    responded_at: datetime | None
    resolved_at: datetime | None
    cancelled_at: datetime | None


@dataclass(frozen=True, slots=True)
class ClientSupportPortal:
    client_id: UUID
    client_code: str
    client_name: str
    requests: tuple[SupportRequestRecord, ...]


class PostgresSupportRepository:
    def portal_for_user(self, *, user_id: UUID) -> ClientSupportPortal:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                client = self._linked_client(cursor, user_id=user_id)
                requests = self._list_requests(cursor, client_id=client["id"])

        return ClientSupportPortal(
            client_id=client["id"],
            client_code=str(client["client_code"]),
            client_name=str(client["full_name"]),
            requests=requests,
        )

    def submit_for_user(
        self,
        *,
        user_id: UUID,
        category: SupportCategory,
        subject: str,
        message: str,
        reference_text: str,
    ) -> SupportRequestRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                client = self._linked_client(cursor, user_id=user_id)
                cursor.execute(
                    """
                    insert into lending.client_support_requests (
                        client_id,
                        created_by_user_id,
                        category,
                        subject,
                        message,
                        reference_text
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    returning id
                    """,
                    (
                        client["id"],
                        user_id,
                        category,
                        subject,
                        message,
                        reference_text,
                    ),
                )
                request_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id,
                        details
                    )
                    values (
                        %s,
                        'support.requested',
                        'client_support_request',
                        %s,
                        jsonb_build_object(
                            'client_id', %s::text,
                            'category', %s::text,
                            'reference_text', %s::text
                        )
                    )
                    """,
                    (
                        user_id,
                        request_id,
                        client["id"],
                        category,
                        reference_text,
                    ),
                )
                return self._fetch_request(cursor, request_id=request_id)

    def cancel_for_user(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
    ) -> SupportRequestRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                client = self._linked_client(cursor, user_id=user_id)
                cursor.execute(
                    """
                    update lending.client_support_requests
                    set
                        status = 'cancelled',
                        cancelled_at = now(),
                        updated_at = now()
                    where id = %s
                      and client_id = %s
                      and status = 'open'
                    returning id
                    """,
                    (request_id, client["id"]),
                )
                if not cursor.fetchone():
                    raise SupportConflict(
                        "Only your own open support request can be cancelled."
                    )
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id
                    )
                    values (
                        %s,
                        'support.cancelled',
                        'client_support_request',
                        %s
                    )
                    """,
                    (user_id, request_id),
                )
                return self._fetch_request(cursor, request_id=request_id)

    def list_for_management(
        self,
        *,
        status: SupportStatus,
        limit: int,
        offset: int,
    ) -> tuple[SupportRequestRecord, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return self._list_requests(
                    cursor,
                    status=status,
                    limit=limit,
                    offset=offset,
                )

    def review(
        self,
        *,
        actor_user_id: UUID,
        request_id: UUID,
        action: SupportAction,
        response: str,
    ) -> SupportRequestRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                if action == "answered":
                    cursor.execute(
                        """
                        update lending.client_support_requests
                        set
                            status = 'answered',
                            managed_by_user_id = %s,
                            management_response = %s,
                            responded_at = now(),
                            resolved_at = null,
                            updated_at = now()
                        where id = %s
                          and status = 'open'
                        returning id
                        """,
                        (actor_user_id, response, request_id),
                    )
                else:
                    cursor.execute(
                        """
                        update lending.client_support_requests
                        set
                            status = 'resolved',
                            managed_by_user_id = %s,
                            management_response = %s,
                            responded_at = coalesce(responded_at, now()),
                            resolved_at = now(),
                            updated_at = now()
                        where id = %s
                          and status in ('open', 'answered')
                        returning id
                        """,
                        (actor_user_id, response, request_id),
                    )
                if not cursor.fetchone():
                    raise SupportConflict(
                        "This support request can no longer receive that action."
                    )
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id,
                        details
                    )
                    values (
                        %s,
                        %s,
                        'client_support_request',
                        %s,
                        jsonb_build_object('response', %s::text)
                    )
                    """,
                    (
                        actor_user_id,
                        f"support.{action}",
                        request_id,
                        response,
                    ),
                )
                return self._fetch_request(cursor, request_id=request_id)

    @staticmethod
    def _linked_client(cursor, *, user_id: UUID):
        cursor.execute(
            """
            select id, client_code, full_name
            from lending.clients
            where user_id = %s
            limit 1
            """,
            (user_id,),
        )
        client = cursor.fetchone()
        if not client:
            raise SupportBorrowerNotLinked(
                "This client account is not linked to a borrower record."
            )
        return client

    def _list_requests(
        self,
        cursor,
        *,
        client_id: UUID | None = None,
        status: SupportStatus | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[SupportRequestRecord, ...]:
        filters: list[str] = []
        params: list[object] = []
        if client_id is not None:
            filters.append("request.client_id = %s")
            params.append(client_id)
        if status is not None:
            filters.append("request.status = %s")
            params.append(status)
        where = f"where {' and '.join(filters)}" if filters else ""
        params.extend([limit, offset])
        cursor.execute(
            f"""
            select
                request.id as request_id,
                request.client_id,
                client.client_code,
                client.full_name as client_name,
                request.category,
                request.subject,
                request.message,
                request.reference_text,
                request.status,
                request.created_at,
                coalesce(
                    nullif(btrim(manager.full_name), ''),
                    nullif(btrim(manager.username), '')
                ) as managed_by_name,
                request.management_response,
                request.responded_at,
                request.resolved_at,
                request.cancelled_at
            from lending.client_support_requests request
            join lending.clients client on client.id = request.client_id
            left join core.users manager on manager.id = request.managed_by_user_id
            {where}
            order by request.created_at desc, request.id desc
            limit %s offset %s
            """,
            tuple(params),
        )
        return tuple(self._record_from_row(row) for row in cursor.fetchall())

    def _fetch_request(self, cursor, *, request_id: UUID) -> SupportRequestRecord:
        cursor.execute(
            """
            select
                request.id as request_id,
                request.client_id,
                client.client_code,
                client.full_name as client_name,
                request.category,
                request.subject,
                request.message,
                request.reference_text,
                request.status,
                request.created_at,
                coalesce(
                    nullif(btrim(manager.full_name), ''),
                    nullif(btrim(manager.username), '')
                ) as managed_by_name,
                request.management_response,
                request.responded_at,
                request.resolved_at,
                request.cancelled_at
            from lending.client_support_requests request
            join lending.clients client on client.id = request.client_id
            left join core.users manager on manager.id = request.managed_by_user_id
            where request.id = %s
            """,
            (request_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise SupportRequestNotFound("Support request was not found.")
        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(row) -> SupportRequestRecord:
        return SupportRequestRecord(
            request_id=row["request_id"],
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            category=str(row["category"]),
            subject=str(row["subject"]),
            message=str(row["message"]),
            reference_text=str(row["reference_text"] or ""),
            status=str(row["status"]),
            created_at=row["created_at"],
            managed_by_name=(
                str(row["managed_by_name"]) if row["managed_by_name"] else None
            ),
            management_response=str(row["management_response"] or ""),
            responded_at=row["responded_at"],
            resolved_at=row["resolved_at"],
            cancelled_at=row["cancelled_at"],
        )
