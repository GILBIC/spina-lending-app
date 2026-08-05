from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from psycopg import errors
from psycopg.rows import dict_row

from .database import open_connection


class AccountError(RuntimeError):
    code = "account_error"


class AccountNotFound(AccountError):
    code = "account_not_found"


class AccountConflict(AccountError):
    code = "account_conflict"


class AccountDisabled(AccountError):
    code = "account_disabled"


class DeviceRequired(AccountError):
    code = "device_required"


class DeviceNotRegistered(AccountError):
    code = "device_not_registered"


class DeviceRevoked(AccountError):
    code = "device_revoked"


@dataclass(frozen=True, slots=True)
class AccountContext:
    user_id: UUID
    auth_user_id: UUID
    username: str
    email: str | None
    full_name: str
    status: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    device_registered: bool = False
    registered_device_id: UUID | None = None

    @property
    def primary_role_code(self) -> str:
        for code in ("management", "employee", "collector", "client"):
            if code in self.roles:
                return code
        return self.roles[0] if self.roles else "client"

    @property
    def primary_role_name(self) -> str:
        return {
            "management": "Management",
            "employee": "Employee",
            "collector": "Collector",
            "client": "Client",
        }.get(self.primary_role_code, self.primary_role_code.title())


class PostgresAccountRepository:
    @staticmethod
    def device_hash(device_identifier: str) -> str:
        return sha256(device_identifier.strip().encode("utf-8")).hexdigest()

    def username_exists(self, username: str) -> bool:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select 1 from core.users where lower(username) = lower(%s) limit 1",
                    (username.strip(),),
                )
                return cursor.fetchone() is not None

    def resolve_email(self, identifier: str) -> str:
        normalized = identifier.strip()
        if "@" in normalized:
            return normalized.lower()
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select email from core.users where lower(username) = lower(%s) limit 1",
                    (normalized,),
                )
                row = cursor.fetchone()
        if not row or not row[0]:
            raise AccountNotFound("Account was not found.")
        return str(row[0]).lower()

    def create_client_profile(
        self,
        *,
        auth_user_id: UUID,
        username: str,
        email: str,
        full_name: str,
        claimed_client_code: str,
        claimed_phone_number: str | None,
    ) -> AccountContext:
        try:
            with open_connection() as connection:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            insert into core.users (
                                username, email, full_name, external_auth_id, status
                            ) values (%s, %s, %s, %s, 'pending')
                            on conflict (external_auth_id) do update
                            set username = excluded.username,
                                email = excluded.email,
                                full_name = excluded.full_name,
                                status = 'pending',
                                updated_at = now()
                            returning id
                            """,
                            (
                                username.strip(),
                                email.strip().lower(),
                                full_name.strip(),
                                auth_user_id,
                            ),
                        )
                        user_id = cursor.fetchone()[0]
                        cursor.execute(
                            """
                            insert into core.user_roles (user_id, role_id)
                            select %s, id from core.roles where code = 'client'
                            on conflict do nothing
                            """,
                            (user_id,),
                        )
                        cursor.execute(
                            """
                            insert into core.client_registration_requests (
                                user_id,
                                claimed_client_code,
                                claimed_phone_number,
                                status,
                                linked_client_id,
                                reviewed_by_user_id,
                                review_note,
                                submitted_at,
                                reviewed_at,
                                updated_at
                            ) values (%s, %s, %s, 'pending', null, null, '', now(), null, now())
                            on conflict (user_id) do update
                            set claimed_client_code = excluded.claimed_client_code,
                                claimed_phone_number = excluded.claimed_phone_number,
                                status = 'pending',
                                linked_client_id = null,
                                reviewed_by_user_id = null,
                                review_note = '',
                                submitted_at = now(),
                                reviewed_at = null,
                                updated_at = now()
                            """,
                            (
                                user_id,
                                claimed_client_code.strip(),
                                (claimed_phone_number or "").strip() or None,
                            ),
                        )
                    return self._load_context(connection, auth_user_id)
        except errors.UniqueViolation as exc:
            raise AccountConflict("Username or email is already in use.") from exc

    def activate_and_register_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
        platform: str | None,
        app_version: str | None,
    ) -> AccountContext:
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select
                            u.id,
                            u.status,
                            exists (
                                select 1
                                from core.user_roles ur
                                join core.roles r on r.id = ur.role_id
                                where ur.user_id = u.id and r.code = 'client'
                            ) as is_client,
                            coalesce((
                                select crr.status
                                from core.client_registration_requests crr
                                where crr.user_id = u.id
                            ), '') as registration_status
                        from core.users u
                        where u.external_auth_id = %s
                        for update
                        """,
                        (auth_user_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise AccountNotFound("Gilbic profile is not linked to this login.")
                    user_id, account_status, is_client, registration_status = row
                    if account_status in {"inactive", "locked"}:
                        raise AccountDisabled("This Gilbic account is not active.")
                    if (
                        account_status == "pending"
                        and is_client
                        and registration_status == "pending"
                    ):
                        raise AccountDisabled(
                            "Your client account is awaiting Management approval and borrower linking."
                        )
                    if account_status == "pending":
                        cursor.execute(
                            "update core.users set status = 'active', updated_at = now() where id = %s",
                            (user_id,),
                        )

                    registered = False
                    registered_device_id: UUID | None = None
                    if device_identifier:
                        normalized_platform = (platform or "").strip().lower()
                        if normalized_platform not in {"android", "ios", "web", "desktop"}:
                            raise AccountConflict("A valid device platform is required.")
                        identifier_hash = self.device_hash(device_identifier)
                        cursor.execute(
                            """
                            select id, status
                            from core.devices
                            where user_id = %s and device_identifier_hash = %s
                            for update
                            """,
                            (user_id, identifier_hash),
                        )
                        device = cursor.fetchone()
                        if device and device[1] == "revoked":
                            raise DeviceRevoked("This device has been revoked.")
                        if device:
                            registered_device_id = device[0]
                            cursor.execute(
                                """
                                update core.devices
                                set platform = %s,
                                    app_version = %s,
                                    status = 'active',
                                    last_seen_at = now()
                                where id = %s
                                """,
                                (normalized_platform, app_version, registered_device_id),
                            )
                        else:
                            cursor.execute(
                                """
                                insert into core.devices (
                                    user_id, device_identifier_hash, platform,
                                    app_version, status, last_seen_at
                                ) values (%s, %s, %s, %s, 'active', now())
                                returning id
                                """,
                                (
                                    user_id,
                                    identifier_hash,
                                    normalized_platform,
                                    app_version,
                                ),
                            )
                            registered_device_id = cursor.fetchone()[0]
                        registered = True

                context = self._load_context(connection, auth_user_id)
                return AccountContext(
                    user_id=context.user_id,
                    auth_user_id=context.auth_user_id,
                    username=context.username,
                    email=context.email,
                    full_name=context.full_name,
                    status=context.status,
                    roles=context.roles,
                    permissions=context.permissions,
                    device_registered=registered,
                    registered_device_id=registered_device_id,
                )

    def get_context(self, auth_user_id: UUID) -> AccountContext:
        with open_connection() as connection:
            return self._load_context(connection, auth_user_id)

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        normalized_device = (device_identifier or "").strip()
        if not normalized_device:
            raise DeviceRequired("X-Device-Id is required.")
        if len(normalized_device) > 300:
            raise DeviceRequired("X-Device-Id is invalid.")

        with open_connection() as connection:
            with connection.transaction():
                context = self._load_context(connection, auth_user_id)
                if context.status != "active":
                    raise AccountDisabled("This Gilbic account is not active.")

                identifier_hash = self.device_hash(normalized_device)
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select id, status
                        from core.devices
                        where user_id = %s and device_identifier_hash = %s
                        for update
                        """,
                        (context.user_id, identifier_hash),
                    )
                    device = cursor.fetchone()
                    if not device:
                        raise DeviceNotRegistered(
                            "This device is not registered. Sign in again on this device."
                        )
                    if device[1] != "active":
                        raise DeviceRevoked("This device has been revoked.")
                    cursor.execute(
                        "update core.devices set last_seen_at = now() where id = %s",
                        (device[0],),
                    )

                return AccountContext(
                    user_id=context.user_id,
                    auth_user_id=context.auth_user_id,
                    username=context.username,
                    email=context.email,
                    full_name=context.full_name,
                    status=context.status,
                    roles=context.roles,
                    permissions=context.permissions,
                    device_registered=True,
                    registered_device_id=device[0],
                )

    @staticmethod
    def _load_context(connection, auth_user_id: UUID) -> AccountContext:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select
                    u.id,
                    u.external_auth_id,
                    u.username,
                    u.email,
                    u.full_name,
                    u.status,
                    coalesce(
                        array_agg(distinct r.code) filter (where r.code is not null),
                        '{}'::text[]
                    ) as roles,
                    coalesce(
                        array_agg(distinct rp.permission_code)
                            filter (where rp.permission_code is not null),
                        '{}'::text[]
                    ) as permissions
                from core.users u
                left join core.user_roles ur on ur.user_id = u.id
                left join core.roles r on r.id = ur.role_id
                left join core.role_permissions rp on rp.role_id = r.id
                where u.external_auth_id = %s
                group by u.id
                """,
                (auth_user_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise AccountNotFound("Gilbic profile is not linked to this login.")
        if not row["external_auth_id"]:
            raise AccountNotFound("Gilbic profile has no authentication identity.")
        return AccountContext(
            user_id=row["id"],
            auth_user_id=row["external_auth_id"],
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            status=row["status"],
            roles=tuple(sorted(row["roles"] or ())),
            permissions=tuple(sorted(row["permissions"] or ())),
        )
