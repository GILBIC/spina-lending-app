from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .account_repository import AccountConflict, AccountNotFound
from .database import open_connection


STAFF_ROLE_CODES = frozenset({"collector", "employee", "management"})
ACCOUNT_STATUS_CODES = frozenset({"active", "inactive", "locked"})
DEVICE_STATUS_CODES = frozenset({"active", "revoked"})
CLIENT_REGISTRATION_STATUS_CODES = frozenset({"pending", "approved", "rejected"})


@dataclass(frozen=True, slots=True)
class AccountAdminRecord:
    id: UUID
    auth_user_id: UUID | None
    username: str
    email: str | None
    full_name: str
    status: str
    roles: tuple[str, ...]
    device_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DeviceAdminRecord:
    id: UUID
    user_id: UUID
    platform: str
    app_version: str | None
    status: str
    registered_at: datetime
    last_seen_at: datetime | None


@dataclass(frozen=True, slots=True)
class ClientRegistrationRecord:
    user_id: UUID
    username: str
    email: str | None
    full_name: str
    account_status: str
    claimed_client_code: str
    claimed_phone_number: str | None
    registration_status: str
    linked_client_id: UUID | None
    linked_client_code: str | None
    linked_client_name: str | None
    review_note: str
    submitted_at: datetime
    reviewed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ClientLinkCandidate:
    id: UUID
    client_code: str
    full_name: str
    phone_number: str | None
    area: str | None
    status: str


class PostgresManagementRepository:
    def create_staff_profile(
        self,
        *,
        actor_user_id: UUID,
        auth_user_id: UUID,
        username: str,
        email: str,
        full_name: str,
        role_code: str,
    ) -> AccountAdminRecord:
        normalized_role = self._validate_staff_role(role_code)
        try:
            with open_connection() as connection:
                with connection.transaction():
                    role_id = self._role_id(connection, normalized_role)
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            insert into core.users (
                                username, email, full_name, external_auth_id, status
                            ) values (%s, %s, %s, %s, 'pending')
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
                            values (%s, %s)
                            """,
                            (user_id, role_id),
                        )
                    self._audit(
                        connection,
                        actor_user_id=actor_user_id,
                        action="account.invite",
                        target_type="user",
                        target_id=user_id,
                        details={"role": normalized_role},
                    )
                    return self._load_account(connection, user_id)
        except errors.UniqueViolation as exc:
            raise AccountConflict("Username, email, or authentication identity is already in use.") from exc

    def list_accounts(self, *, limit: int = 100, offset: int = 0) -> list[AccountAdminRecord]:
        safe_limit = min(max(limit, 1), 200)
        safe_offset = max(offset, 0)
        with open_connection() as connection:
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
                        u.created_at,
                        u.updated_at,
                        coalesce(
                            array_agg(distinct r.code) filter (where r.code is not null),
                            '{}'::text[]
                        ) as roles,
                        count(distinct d.id) as device_count
                    from core.users u
                    left join core.user_roles ur on ur.user_id = u.id
                    left join core.roles r on r.id = ur.role_id
                    left join core.devices d on d.user_id = u.id
                    group by u.id
                    order by u.created_at desc, u.username
                    limit %s offset %s
                    """,
                    (safe_limit, safe_offset),
                )
                rows = cursor.fetchall()
        return [self._account_from_row(row) for row in rows]

    def list_client_registrations(
        self,
        *,
        registration_status: str = "pending",
        limit: int = 100,
        offset: int = 0,
    ) -> list[ClientRegistrationRecord]:
        normalized_status = self._validate_registration_status(registration_status)
        safe_limit = min(max(limit, 1), 200)
        safe_offset = max(offset, 0)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        crr.user_id,
                        u.username,
                        u.email,
                        u.full_name,
                        u.status as account_status,
                        crr.claimed_client_code,
                        crr.claimed_phone_number,
                        crr.status as registration_status,
                        crr.linked_client_id,
                        linked.client_code as linked_client_code,
                        linked.full_name as linked_client_name,
                        crr.review_note,
                        crr.submitted_at,
                        crr.reviewed_at
                    from core.client_registration_requests crr
                    join core.users u on u.id = crr.user_id
                    left join lending.clients linked on linked.id = crr.linked_client_id
                    where crr.status = %s
                    order by crr.submitted_at asc, u.full_name, u.username
                    limit %s offset %s
                    """,
                    (normalized_status, safe_limit, safe_offset),
                )
                rows = cursor.fetchall()
        return [self._client_registration_from_row(row) for row in rows]

    def search_client_link_candidates(
        self,
        *,
        query: str,
        limit: int = 25,
    ) -> list[ClientLinkCandidate]:
        normalized_query = query.strip()
        if len(normalized_query) < 2:
            return []
        safe_limit = min(max(limit, 1), 50)
        pattern = f"%{normalized_query}%"
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id, client_code, full_name, phone_number, area, status
                    from lending.clients
                    where user_id is null
                      and status = 'active'
                      and (
                          client_code ilike %s
                          or full_name ilike %s
                          or coalesce(phone_number, '') ilike %s
                          or coalesce(gcash_number, '') ilike %s
                      )
                    order by
                        case when lower(client_code) = lower(%s) then 0 else 1 end,
                        case when lower(full_name) = lower(%s) then 0 else 1 end,
                        full_name,
                        client_code
                    limit %s
                    """,
                    (
                        pattern,
                        pattern,
                        pattern,
                        pattern,
                        normalized_query,
                        normalized_query,
                        safe_limit,
                    ),
                )
                rows = cursor.fetchall()
        return [self._client_candidate_from_row(row) for row in rows]

    def approve_client_registration(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        client_id: UUID,
        review_note: str = "",
    ) -> ClientRegistrationRecord:
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select crr.status, u.status as account_status
                        from core.client_registration_requests crr
                        join core.users u on u.id = crr.user_id
                        where crr.user_id = %s
                        for update of crr, u
                        """,
                        (target_user_id,),
                    )
                    registration = cursor.fetchone()
                    if not registration:
                        raise AccountNotFound("Client registration request was not found.")
                    if registration["status"] != "pending":
                        raise AccountConflict("Only a pending client registration can be approved.")

                    cursor.execute(
                        """
                        select 1
                        from core.user_roles ur
                        join core.roles r on r.id = ur.role_id
                        where ur.user_id = %s and r.code = 'client'
                        """,
                        (target_user_id,),
                    )
                    if cursor.fetchone() is None:
                        raise AccountConflict("The selected account is not a client account.")

                    cursor.execute(
                        """
                        select id, user_id, status
                        from lending.clients
                        where id = %s
                        for update
                        """,
                        (client_id,),
                    )
                    client = cursor.fetchone()
                    if not client:
                        raise AccountNotFound("Borrower record was not found.")
                    if client["status"] != "active":
                        raise AccountConflict("Only an active borrower record can be linked.")
                    if client["user_id"] not in {None, target_user_id}:
                        raise AccountConflict("That borrower record is already linked to another account.")

                    cursor.execute(
                        """
                        update lending.clients
                        set user_id = %s, updated_at = now()
                        where id = %s
                        """,
                        (target_user_id, client_id),
                    )
                    cursor.execute(
                        """
                        update core.users
                        set status = 'active', updated_at = now()
                        where id = %s
                        """,
                        (target_user_id,),
                    )
                    cursor.execute(
                        """
                        update core.client_registration_requests
                        set status = 'approved',
                            linked_client_id = %s,
                            reviewed_by_user_id = %s,
                            review_note = %s,
                            reviewed_at = now(),
                            updated_at = now()
                        where user_id = %s
                        """,
                        (
                            client_id,
                            actor_user_id,
                            review_note.strip(),
                            target_user_id,
                        ),
                    )

                self._audit(
                    connection,
                    actor_user_id=actor_user_id,
                    action="client_registration.approve",
                    target_type="user",
                    target_id=target_user_id,
                    details={
                        "client_id": str(client_id),
                        "review_note": review_note.strip(),
                    },
                )
                return self._load_client_registration(connection, target_user_id)

    def reject_client_registration(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        review_note: str,
    ) -> ClientRegistrationRecord:
        normalized_note = review_note.strip()
        if not normalized_note:
            raise AccountConflict("A rejection reason is required.")
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select crr.status
                        from core.client_registration_requests crr
                        join core.users u on u.id = crr.user_id
                        where crr.user_id = %s
                        for update of crr, u
                        """,
                        (target_user_id,),
                    )
                    registration = cursor.fetchone()
                    if not registration:
                        raise AccountNotFound("Client registration request was not found.")
                    if registration["status"] != "pending":
                        raise AccountConflict("Only a pending client registration can be rejected.")

                    cursor.execute(
                        """
                        update core.users
                        set status = 'inactive', updated_at = now()
                        where id = %s
                        """,
                        (target_user_id,),
                    )
                    cursor.execute(
                        """
                        update core.client_registration_requests
                        set status = 'rejected',
                            linked_client_id = null,
                            reviewed_by_user_id = %s,
                            review_note = %s,
                            reviewed_at = now(),
                            updated_at = now()
                        where user_id = %s
                        """,
                        (actor_user_id, normalized_note, target_user_id),
                    )

                self._audit(
                    connection,
                    actor_user_id=actor_user_id,
                    action="client_registration.reject",
                    target_type="user",
                    target_id=target_user_id,
                    details={"review_note": normalized_note},
                )
                return self._load_client_registration(connection, target_user_id)

    def set_role(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        role_code: str,
    ) -> AccountAdminRecord:
        if actor_user_id == target_user_id:
            raise AccountConflict("You cannot change your own management role.")
        normalized_role = self._validate_staff_role(role_code)
        with open_connection() as connection:
            with connection.transaction():
                self._lock_user(connection, target_user_id)
                role_id = self._role_id(connection, normalized_role)
                with connection.cursor() as cursor:
                    cursor.execute(
                        "delete from core.user_roles where user_id = %s",
                        (target_user_id,),
                    )
                    cursor.execute(
                        "insert into core.user_roles (user_id, role_id) values (%s, %s)",
                        (target_user_id, role_id),
                    )
                self._audit(
                    connection,
                    actor_user_id=actor_user_id,
                    action="account.role_change",
                    target_type="user",
                    target_id=target_user_id,
                    details={"role": normalized_role},
                )
                return self._load_account(connection, target_user_id)

    def set_status(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        account_status: str,
    ) -> AccountAdminRecord:
        normalized_status = account_status.strip().lower()
        if normalized_status not in ACCOUNT_STATUS_CODES:
            raise AccountConflict("Unsupported account status.")
        if actor_user_id == target_user_id and normalized_status != "active":
            raise AccountConflict("You cannot lock or disable your own management account.")
        with open_connection() as connection:
            with connection.transaction():
                self._lock_user(connection, target_user_id)
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        update core.users
                        set status = %s, updated_at = now()
                        where id = %s
                        """,
                        (normalized_status, target_user_id),
                    )
                self._audit(
                    connection,
                    actor_user_id=actor_user_id,
                    action="account.status_change",
                    target_type="user",
                    target_id=target_user_id,
                    details={"status": normalized_status},
                )
                return self._load_account(connection, target_user_id)

    def list_devices(self, *, target_user_id: UUID) -> list[DeviceAdminRecord]:
        with open_connection() as connection:
            self._ensure_user(connection, target_user_id)
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id, user_id, platform, app_version, status,
                           registered_at, last_seen_at
                    from core.devices
                    where user_id = %s
                    order by last_seen_at desc nulls last, registered_at desc
                    """,
                    (target_user_id,),
                )
                rows = cursor.fetchall()
        return [self._device_from_row(row) for row in rows]

    def set_device_status(
        self,
        *,
        actor_user_id: UUID,
        device_id: UUID,
        device_status: str,
    ) -> DeviceAdminRecord:
        normalized_status = device_status.strip().lower()
        if normalized_status not in DEVICE_STATUS_CODES:
            raise AccountConflict("Unsupported device status.")
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select id, user_id, platform, app_version, status,
                               registered_at, last_seen_at
                        from core.devices
                        where id = %s
                        for update
                        """,
                        (device_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise AccountNotFound("Registered device was not found.")
                    if actor_user_id == row["user_id"] and normalized_status == "revoked":
                        raise AccountConflict("You cannot revoke your own current account's device.")
                    cursor.execute(
                        "update core.devices set status = %s where id = %s",
                        (normalized_status, device_id),
                    )
                self._audit(
                    connection,
                    actor_user_id=actor_user_id,
                    action="device.status_change",
                    target_type="device",
                    target_id=device_id,
                    details={"status": normalized_status, "user_id": str(row["user_id"])},
                )
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select id, user_id, platform, app_version, status,
                               registered_at, last_seen_at
                        from core.devices where id = %s
                        """,
                        (device_id,),
                    )
                    updated = cursor.fetchone()
                return self._device_from_row(updated)

    @staticmethod
    def _validate_staff_role(role_code: str) -> str:
        normalized = role_code.strip().lower()
        if normalized not in STAFF_ROLE_CODES:
            raise AccountConflict("Only Collector, Employee, or Management staff roles are allowed.")
        return normalized

    @staticmethod
    def _validate_registration_status(value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in CLIENT_REGISTRATION_STATUS_CODES:
            raise AccountConflict("Unsupported client registration status.")
        return normalized

    @staticmethod
    def _role_id(connection, role_code: str) -> UUID:
        with connection.cursor() as cursor:
            cursor.execute("select id from core.roles where code = %s", (role_code,))
            row = cursor.fetchone()
        if not row:
            raise AccountConflict(f"Role '{role_code}' is not configured.")
        return row[0]

    @staticmethod
    def _ensure_user(connection, user_id: UUID) -> None:
        with connection.cursor() as cursor:
            cursor.execute("select 1 from core.users where id = %s", (user_id,))
            if cursor.fetchone() is None:
                raise AccountNotFound("Gilbic account was not found.")

    @staticmethod
    def _lock_user(connection, user_id: UUID) -> None:
        with connection.cursor() as cursor:
            cursor.execute("select id from core.users where id = %s for update", (user_id,))
            if cursor.fetchone() is None:
                raise AccountNotFound("Gilbic account was not found.")

    def _load_account(self, connection, user_id: UUID) -> AccountAdminRecord:
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
                    u.created_at,
                    u.updated_at,
                    coalesce(
                        array_agg(distinct r.code) filter (where r.code is not null),
                        '{}'::text[]
                    ) as roles,
                    count(distinct d.id) as device_count
                from core.users u
                left join core.user_roles ur on ur.user_id = u.id
                left join core.roles r on r.id = ur.role_id
                left join core.devices d on d.user_id = u.id
                where u.id = %s
                group by u.id
                """,
                (user_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise AccountNotFound("Gilbic account was not found.")
        return self._account_from_row(row)

    def _load_client_registration(
        self,
        connection,
        user_id: UUID,
    ) -> ClientRegistrationRecord:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select
                    crr.user_id,
                    u.username,
                    u.email,
                    u.full_name,
                    u.status as account_status,
                    crr.claimed_client_code,
                    crr.claimed_phone_number,
                    crr.status as registration_status,
                    crr.linked_client_id,
                    linked.client_code as linked_client_code,
                    linked.full_name as linked_client_name,
                    crr.review_note,
                    crr.submitted_at,
                    crr.reviewed_at
                from core.client_registration_requests crr
                join core.users u on u.id = crr.user_id
                left join lending.clients linked on linked.id = crr.linked_client_id
                where crr.user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise AccountNotFound("Client registration request was not found.")
        return self._client_registration_from_row(row)

    @staticmethod
    def _audit(
        connection,
        *,
        actor_user_id: UUID,
        action: str,
        target_type: str,
        target_id: UUID | None,
        details: dict[str, object],
    ) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into core.audit_logs (
                    actor_user_id, action, target_type, target_id, details
                ) values (%s, %s, %s, %s, %s)
                """,
                (actor_user_id, action, target_type, target_id, Jsonb(details)),
            )

    @staticmethod
    def _account_from_row(row) -> AccountAdminRecord:
        return AccountAdminRecord(
            id=row["id"],
            auth_user_id=row["external_auth_id"],
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            status=row["status"],
            roles=tuple(sorted(row["roles"] or ())),
            device_count=int(row["device_count"] or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _device_from_row(row) -> DeviceAdminRecord:
        return DeviceAdminRecord(
            id=row["id"],
            user_id=row["user_id"],
            platform=row["platform"],
            app_version=row["app_version"],
            status=row["status"],
            registered_at=row["registered_at"],
            last_seen_at=row["last_seen_at"],
        )

    @staticmethod
    def _client_registration_from_row(row) -> ClientRegistrationRecord:
        return ClientRegistrationRecord(
            user_id=row["user_id"],
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            account_status=row["account_status"],
            claimed_client_code=row["claimed_client_code"],
            claimed_phone_number=row["claimed_phone_number"],
            registration_status=row["registration_status"],
            linked_client_id=row["linked_client_id"],
            linked_client_code=row["linked_client_code"],
            linked_client_name=row["linked_client_name"],
            review_note=row["review_note"] or "",
            submitted_at=row["submitted_at"],
            reviewed_at=row["reviewed_at"],
        )

    @staticmethod
    def _client_candidate_from_row(row) -> ClientLinkCandidate:
        return ClientLinkCandidate(
            id=row["id"],
            client_code=row["client_code"],
            full_name=row["full_name"],
            phone_number=row["phone_number"],
            area=row["area"],
            status=row["status"],
        )
