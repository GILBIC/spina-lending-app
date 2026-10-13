"""The immutable book identity of one isolated accounting deployment."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection

BookKind = Literal["owner_operations", "corporate_legal", "synthetic"]


@dataclass(frozen=True, slots=True)
class AccountingBookIdentity:
    book_id: UUID
    kind: BookKind
    entity_label: str
    evidence_reference: str
    evidence_digest: str
    configured_by_user_id: UUID
    configured_at: datetime


class AccountingBookError(RuntimeError):
    code = "accounting_book_error"


class AccountingBookConflict(AccountingBookError):
    code = "accounting_book_conflict"


class AccountingBookDenied(AccountingBookError):
    code = "accounting_book_permission_required"


class AccountingBookUnavailable(AccountingBookError):
    code = "accounting_book_unavailable"


def _database_error(error: psycopg.Error) -> AccountingBookError:
    message = error.diag.message_primary or "Accounting book operation was rejected."
    if error.sqlstate == "42501":
        return AccountingBookDenied(
            "Current Management accounting permission is required."
        )
    if error.sqlstate in {"22023", "55000"}:
        return AccountingBookConflict(message)
    return AccountingBookUnavailable("Accounting book identity is unavailable.")


def read_book_identity(cursor: Any) -> AccountingBookIdentity | None:
    """Read through the caller's dict-row cursor, preserving its report snapshot."""
    cursor.execute(
        """SELECT id AS book_id, kind, entity_label, evidence_reference, evidence_digest,
                  configured_by_user_id, configured_at
           FROM accounting.book_identity WHERE singleton"""
    )
    row = cursor.fetchone()
    return AccountingBookIdentity(**row) if row is not None else None


def book_identity_payload(identity: AccountingBookIdentity | None) -> dict[str, object]:
    return {
        "status": "configured" if identity else "unconfigured",
        "book_id": str(identity.book_id) if identity else None,
        "kind": identity.kind if identity else None,
        "entity_label": identity.entity_label if identity else None,
        "evidence_reference": identity.evidence_reference if identity else None,
        "evidence_digest": identity.evidence_digest if identity else None,
        "configured_by_user_id": str(identity.configured_by_user_id)
        if identity
        else None,
        "configured_at": identity.configured_at.isoformat() if identity else None,
    }


def require_accounting_context(cursor: Any, context_id: UUID) -> UUID:
    """Guard a Treasury context inside the caller's existing transaction.

    This does not authorize a user or a cash account. Source adapters must also
    enforce their current actor/account permission and validate the exact wallet.
    """
    cursor.execute(
        "SELECT accounting.require_book_treasury_context(%s) AS book_id", (context_id,)
    )
    return cursor.fetchone()["book_id"]


def require_accounting_account(cursor: Any, account_id: UUID) -> UUID:
    """Guard context and ownership of a Treasury wallet in the same transaction."""
    cursor.execute(
        "SELECT accounting.require_book_treasury_account(%s) AS book_id", (account_id,)
    )
    return cursor.fetchone()["book_id"]


class PostgresAccountingBookRepository:
    def get_book_identity(self) -> AccountingBookIdentity | None:
        try:
            with (
                open_connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                return read_book_identity(cursor)
        except psycopg.Error as error:
            raise _database_error(error) from error

    def configure_book_identity(
        self,
        *,
        kind: BookKind,
        entity_label: str,
        evidence_reference: str,
        evidence_digest: str,
        actor_user_id: UUID,
    ) -> AccountingBookIdentity:
        try:
            with (
                open_connection() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute(
                    "SELECT accounting.configure_book_identity(%s,%s,%s,%s,%s)",
                    (
                        kind,
                        entity_label,
                        evidence_reference,
                        evidence_digest,
                        actor_user_id,
                    ),
                )
                identity = read_book_identity(cursor)
                if identity is None:
                    raise AccountingBookUnavailable(
                        "Accounting book identity was not retained."
                    )
                return identity
        except psycopg.Error as error:
            raise _database_error(error) from error
