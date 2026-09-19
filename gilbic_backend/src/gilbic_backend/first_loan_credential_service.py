"""Resume the existing managed Client lifecycle after committed office release.

Reserve one Auth UUID before making any external request. A retry reconciles that
exact identity and server-owned intent marker; it never guesses by email or stores
a password. The financial release has already committed before this module runs.
"""

from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

from psycopg.rows import dict_row

from .account_repository import AccountConflict
from .auth_client import SupabaseAuthError
from .client_credentials import generate_password
from .database import open_connection


class FirstLoanCredentialAccessDenied(RuntimeError):
    pass


class PostgresFirstLoanCredentialRepository:
    @staticmethod
    def _require_actor(
        cursor, *, actor_user_id: UUID, registered_device_id: UUID
    ) -> None:
        allowed = cursor.execute(
            """select 1 from core.users actor
            join core.devices device on device.user_id = actor.id
            where actor.id = %s and actor.status = 'active'
              and device.id = %s and device.status = 'active'
              and exists (
                select 1 from core.user_roles ur
                join core.roles r on r.id = ur.role_id
                join core.role_permissions rp on rp.role_id = r.id
                where ur.user_id = actor.id and r.code in ('employee', 'management')
                  and rp.permission_code = 'client.credential.manage'
              ) for share of actor, device""",
            (actor_user_id, registered_device_id),
        ).fetchone()
        if allowed is None:
            raise FirstLoanCredentialAccessDenied(
                "An authorized office account and active device are required."
            )

    @staticmethod
    def _load(cursor, loan_id: UUID):
        row = cursor.execute(
            """select intent.* from lending.first_loan_credential_intents intent
            join lending.first_loan_releases release on release.id = intent.release_id
              and release.loan_id = intent.loan_id
            join lending.loans loan on loan.id = intent.loan_id
              and loan.client_id = intent.client_id
            where intent.loan_id = %s and loan.date_released is not null
              and loan.status in ('active', 'paid', 'closed', 'defaulted')
            for update of intent""",
            (loan_id,),
        ).fetchone()
        if row is None:
            raise AccountConflict(
                "No committed release credential request is available."
            )
        return row

    def prepare(
        self, *, loan_id: UUID, actor_user_id: UUID, registered_device_id: UUID
    ) -> None:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._require_actor(
                    cursor,
                    actor_user_id=actor_user_id,
                    registered_device_id=registered_device_id,
                )
                row = self._load(cursor, loan_id)
                if row["status"] == "completed":
                    return
                cursor.execute(
                    """update lending.first_loan_credential_intents
                    set auth_user_id = coalesce(auth_user_id, %s), status = 'processing',
                        updated_at = now() where id = %s""",
                    (uuid4(), row["id"]),
                )

    @contextmanager
    def locked(self, *, loan_id: UUID, actor_user_id: UUID, registered_device_id: UUID):
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("set local lock_timeout = '5s'")
                self._require_actor(
                    cursor,
                    actor_user_id=actor_user_id,
                    registered_device_id=registered_device_id,
                )
                row = self._load(cursor, loan_id)
                yield row, cursor

    @staticmethod
    def linked_account(cursor, row):
        account = cursor.execute(
            """select u.id, u.external_auth_id, u.email, u.username
            from lending.clients c join core.users u on u.id = c.user_id
            where c.id = %s""",
            (row["client_id"],),
        ).fetchone()
        if account is not None and (
            account["external_auth_id"] != row["auth_user_id"]
            or str(account["email"]).lower() != str(row["email"]).lower()
        ):
            raise AccountConflict(
                "The Client is linked to a different authentication identity."
            )
        return account

    @staticmethod
    def complete(cursor, row, *, user_id: UUID, username: str) -> None:
        cursor.execute(
            """update lending.first_loan_credential_intents
            set status = 'completed', linked_user_id = %s, username = %s,
                completed_at = now(), updated_at = now(), last_error_code = null
            where id = %s""",
            (user_id, username, row["id"]),
        )

    @staticmethod
    def attempt(cursor, row, *, username: str) -> None:
        cursor.execute(
            """update lending.first_loan_credential_intents
            set attempt_count = attempt_count + 1, username = %s, updated_at = now()
            where id = %s""",
            (username, row["id"]),
        )

    @staticmethod
    def uncertain(cursor, row, *, code: str) -> None:
        cursor.execute(
            """update lending.first_loan_credential_intents
            set status = 'reconciliation_required', last_error_code = %s,
                updated_at = now() where id = %s""",
            (code, row["id"]),
        )


class FirstLoanCredentialService:
    def __init__(self, *, intents, accounts, auth_admin, mailer) -> None:
        self.intents = intents
        self.accounts = accounts
        self.auth_admin = auth_admin
        self.mailer = mailer

    def provision(
        self, *, loan_id: UUID, actor_user_id: UUID, registered_device_id: UUID
    ) -> dict[str, object]:
        arguments = dict(
            loan_id=loan_id,
            actor_user_id=actor_user_id,
            registered_device_id=registered_device_id,
        )
        self.intents.prepare(**arguments)
        with self.intents.locked(**arguments) as (row, cursor):
            if row["status"] == "completed":
                return self._completed(row["linked_user_id"], row["username"])
            linked = self.intents.linked_account(cursor, row)
            if linked is not None:
                self.intents.complete(
                    cursor, row, user_id=linked["id"], username=linked["username"]
                )
                return self._completed(linked["id"], linked["username"])
            username = self.accounts.next_client_username(
                client_id=row["client_id"],
                provisioning_intent_id=row["id"],
            )
            self.intents.attempt(cursor, row, username=username)
            password = generate_password()
            try:
                exists = self.auth_admin.get_provisioned_user(
                    auth_user_id=row["auth_user_id"],
                    email=row["email"],
                    provisioning_intent_id=row["id"],
                )
                if exists:
                    # An interrupted first attempt never retained its password.
                    self.auth_admin.update_user_password(
                        auth_user_id=row["auth_user_id"], password=password
                    )
                else:
                    created = self.auth_admin.create_user(
                        auth_user_id=row["auth_user_id"],
                        email=row["email"],
                        password=password,
                        email_confirm=True,
                        provisioning_intent_id=row["id"],
                    )
                    if created != row["auth_user_id"]:
                        raise SupabaseAuthError(
                            "Reserved identity mismatch.",
                            status_code=409,
                            code="provisioning_identity_mismatch",
                        )
                record = self.accounts.create_client_account_profile(
                    actor_user_id=actor_user_id,
                    auth_user_id=row["auth_user_id"],
                    username=username,
                    email=row["email"],
                    client_id=row["client_id"],
                    provisioning_intent_id=row["id"],
                )
            except Exception:
                # Persist only a stable operational code. Provider errors may contain PII.
                # Do not delete an identity after an uncertain local commit.
                self.intents.uncertain(
                    cursor, row, code="credential_reconciliation_required"
                )
                return {
                    "status": "reconciliation_required",
                    "detail": "Cash release is complete. Retry credential reconciliation; no financial release will be repeated.",
                }
            self.intents.complete(cursor, row, user_id=record.id, username=username)
            try:
                delivery = self.mailer.send_client_credentials(
                    email=row["email"],
                    full_name=record.full_name,
                    username=username,
                    password=password,
                )
                sent = delivery.sent
            except Exception:
                sent = False
            return {
                "status": "completed",
                "user_id": str(record.id),
                "username": username,
                "credentials": {"username": username, "password": password},
                "delivery": {
                    "sent": sent,
                    "detail": "Credentials sent."
                    if sent
                    else "Provide these one-time credentials to the borrower in the office.",
                },
            }

    @staticmethod
    def _completed(user_id, username) -> dict[str, object]:
        return {
            "status": "completed",
            "user_id": str(user_id),
            "username": username,
            "detail": "Client account already linked. Use the existing password-reset workflow if a replacement password is needed.",
        }
