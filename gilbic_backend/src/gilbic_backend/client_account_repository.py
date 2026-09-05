from __future__ import annotations

from uuid import UUID

from psycopg import errors
from psycopg.rows import dict_row

from .account_repository import AccountConflict, AccountNotFound
from .client_credentials import client_username_base
from .database import open_connection
from .management_repository import AccountAdminRecord, PostgresManagementRepository


class PostgresClientAccountRepository(PostgresManagementRepository):
    """Management repository extension for SPINA-controlled Client credentials."""

    def next_client_username(self, *, client_id: UUID) -> str:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id, client_code, status, user_id
                    from lending.clients
                    where id = %s
                    """,
                    (client_id,),
                )
                borrower = cursor.fetchone()
                if not borrower:
                    raise AccountNotFound("Borrower record was not found.")
                if borrower["status"] != "active":
                    raise AccountConflict(
                        "Only an active borrower record can receive a Client account."
                    )
                if borrower["user_id"] is not None:
                    raise AccountConflict(
                        "That borrower record is already linked to an account."
                    )

                base = client_username_base(str(borrower["client_code"]))
                candidate = base
                suffix = 2
                while True:
                    cursor.execute(
                        "select 1 from core.users where lower(username) = lower(%s)",
                        (candidate,),
                    )
                    if cursor.fetchone() is None:
                        return candidate
                    candidate = f"{base}.{suffix}"
                    suffix += 1

    def create_client_account_profile(
        self,
        *,
        actor_user_id: UUID,
        auth_user_id: UUID,
        username: str,
        email: str,
        client_id: UUID,
    ) -> AccountAdminRecord:
        try:
            with open_connection() as connection:
                with connection.transaction():
                    with connection.cursor(row_factory=dict_row) as cursor:
                        cursor.execute(
                            """
                            select id, client_code, full_name, status, user_id
                            from lending.clients
                            where id = %s
                            for update
                            """,
                            (client_id,),
                        )
                        borrower = cursor.fetchone()
                    if not borrower:
                        raise AccountNotFound("Borrower record was not found.")
                    if borrower["status"] != "active":
                        raise AccountConflict(
                            "Only an active borrower record can receive a Client account."
                        )
                    if borrower["user_id"] is not None:
                        raise AccountConflict(
                            "That borrower record is already linked to an account."
                        )

                    role_id = self._role_id(connection, "client")
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            insert into core.users (
                                username,
                                email,
                                full_name,
                                external_auth_id,
                                status
                            ) values (%s, %s, %s, %s, 'active')
                            returning id
                            """,
                            (
                                username.strip(),
                                email.strip().lower(),
                                str(borrower["full_name"]).strip(),
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
                            update lending.clients
                            set user_id = %s, updated_at = now()
                            where id = %s
                            """,
                            (user_id, client_id),
                        )

                    self._audit(
                        connection,
                        actor_user_id=actor_user_id,
                        action="client_account.create",
                        target_type="user",
                        target_id=user_id,
                        details={
                            "client_id": str(client_id),
                            "role": "client",
                        },
                    )
                    return self._load_account(connection, user_id)
        except errors.UniqueViolation as exc:
            raise AccountConflict(
                "Username, email, or authentication identity is already in use."
            ) from exc

    def get_account(self, *, target_user_id: UUID) -> AccountAdminRecord:
        with open_connection() as connection:
            return self._load_account(connection, target_user_id)

    def record_password_reset(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        delivery_sent: bool,
    ) -> None:
        with open_connection() as connection:
            with connection.transaction():
                self._lock_user(connection, target_user_id)
                account = self._load_account(connection, target_user_id)
                self._audit(
                    connection,
                    actor_user_id=actor_user_id,
                    action="account.password_reset",
                    target_type="user",
                    target_id=target_user_id,
                    details={
                        "roles": list(account.roles),
                        "delivery_sent": bool(delivery_sent),
                    },
                )
