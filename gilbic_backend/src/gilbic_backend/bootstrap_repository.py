from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from psycopg import errors
from psycopg.types.json import Jsonb

from .account_repository import AccountConflict
from .database import open_connection


class ManagementBootstrapUnavailable(RuntimeError):
    """Raised when Gilbic already has a Management account."""


@dataclass(frozen=True, slots=True)
class BootstrapManagementRecord:
    user_id: UUID
    auth_user_id: UUID
    username: str
    email: str
    full_name: str
    status: str


class PostgresManagementBootstrapRepository:
    """One-time database boundary for creating Gilbic's first manager.

    This repository is intentionally separate from the normal management API.
    It is called only by a trusted local/server CLI and automatically becomes
    unavailable as soon as any account owns the ``management`` role.
    """

    # Transaction-scoped lock preventing two bootstrap processes from winning
    # the first-management race at the same time.
    _ADVISORY_LOCK_ID = 724_512_260_731

    def is_available(self) -> bool:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select not exists (
                        select 1
                        from core.user_roles ur
                        join core.roles r on r.id = ur.role_id
                        where r.code = 'management'
                    )
                    """
                )
                row = cursor.fetchone()
        return bool(row and row[0])

    def create_initial_management(
        self,
        *,
        auth_user_id: UUID,
        username: str,
        email: str,
        full_name: str,
    ) -> BootstrapManagementRecord:
        normalized_username = username.strip()
        normalized_email = email.strip().lower()
        normalized_full_name = " ".join(full_name.split())

        if not normalized_username or any(ch.isspace() for ch in normalized_username):
            raise AccountConflict("Username cannot be empty or contain spaces.")
        if "@" not in normalized_email:
            raise AccountConflict("Enter a valid email address.")
        if not normalized_full_name:
            raise AccountConflict("Full name is required.")

        try:
            with open_connection() as connection:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "select pg_advisory_xact_lock(%s)",
                            (self._ADVISORY_LOCK_ID,),
                        )
                        cursor.execute(
                            """
                            select 1
                            from core.user_roles ur
                            join core.roles r on r.id = ur.role_id
                            where r.code = 'management'
                            limit 1
                            """
                        )
                        if cursor.fetchone() is not None:
                            raise ManagementBootstrapUnavailable(
                                "A Gilbic Management account already exists. "
                                "Use the authenticated management API for additional staff."
                            )

                        cursor.execute(
                            "select id from core.roles where code = 'management'"
                        )
                        role_row = cursor.fetchone()
                        if not role_row:
                            raise AccountConflict("Management role is not configured.")
                        role_id = role_row[0]

                        cursor.execute(
                            """
                            insert into core.users (
                                username, email, full_name, external_auth_id, status
                            ) values (%s, %s, %s, %s, 'pending')
                            returning id
                            """,
                            (
                                normalized_username,
                                normalized_email,
                                normalized_full_name,
                                auth_user_id,
                            ),
                        )
                        user_id = cursor.fetchone()[0]
                        cursor.execute(
                            """
                            insert into core.user_roles (user_id, role_id)
                            values (%s, %s)
                            """,
                            (user_id, role_id),
                        )
                        cursor.execute(
                            """
                            insert into core.audit_logs (
                                actor_user_id, action, target_type, target_id, details
                            ) values (null, 'account.bootstrap_management', 'user', %s, %s)
                            """,
                            (
                                user_id,
                                Jsonb(
                                    {
                                        "role": "management",
                                        "bootstrap": True,
                                    }
                                ),
                            ),
                        )
        except errors.UniqueViolation as exc:
            raise AccountConflict(
                "Username, email, or authentication identity is already in use."
            ) from exc

        return BootstrapManagementRecord(
            user_id=user_id,
            auth_user_id=auth_user_id,
            username=normalized_username,
            email=normalized_email,
            full_name=normalized_full_name,
            status="pending",
        )
