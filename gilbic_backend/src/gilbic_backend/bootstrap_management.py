from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from .account_repository import AccountConflict
from .auth_admin_client import SupabaseAuthAdminClient
from .auth_client import SupabaseAuthError
from .bootstrap_repository import (
    BootstrapManagementRecord,
    ManagementBootstrapUnavailable,
    PostgresManagementBootstrapRepository,
)


class BootstrapAuthAdmin(Protocol):
    def invite_user(self, *, email: str) -> UUID: ...

    def delete_user(self, *, auth_user_id: UUID) -> None: ...


class BootstrapRepository(Protocol):
    def is_available(self) -> bool: ...

    def create_initial_management(
        self,
        *,
        auth_user_id: UUID,
        username: str,
        email: str,
        full_name: str,
    ) -> BootstrapManagementRecord: ...


class ManagementBootstrapCleanupError(RuntimeError):
    """Bootstrap failed and the newly invited Auth identity could not be removed."""


def bootstrap_first_management(
    *,
    auth: BootstrapAuthAdmin,
    repository: BootstrapRepository,
    username: str,
    email: str,
    full_name: str,
) -> BootstrapManagementRecord:
    """Invite and create the one permitted bootstrap Management account.

    The database repository performs the authoritative, transaction-locked
    first-management check. The early check avoids sending an unnecessary Auth
    invitation when bootstrap is already disabled. If the database write fails
    after Supabase created the invitation, the Auth identity is removed again.
    """

    if not repository.is_available():
        raise ManagementBootstrapUnavailable(
            "A Gilbic Management account already exists. Bootstrap is disabled."
        )

    auth_user_id = auth.invite_user(email=email.strip().lower())
    try:
        return repository.create_initial_management(
            auth_user_id=auth_user_id,
            username=username,
            email=email,
            full_name=full_name,
        )
    except Exception as bootstrap_error:
        try:
            auth.delete_user(auth_user_id=auth_user_id)
        except Exception as cleanup_error:
            raise ManagementBootstrapCleanupError(
                "Management bootstrap failed and the invited Supabase Auth user "
                "could not be cleaned up automatically. Review Auth users before retrying."
            ) from cleanup_error
        raise bootstrap_error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gilbic-bootstrap-management",
        description=(
            "Send the invitation for Gilbic's first Management account. "
            "This command automatically disables itself once Management exists."
        ),
    )
    parser.add_argument("--username", required=True, help="Gilbic username")
    parser.add_argument("--email", required=True, help="Invitation email address")
    parser.add_argument("--full-name", required=True, help="Administrator full name")
    parser.add_argument(
        "--confirm-first-management",
        action="store_true",
        help="Required acknowledgement that this creates the first Management account",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.confirm_first_management:
        print(
            "Refusing to bootstrap without --confirm-first-management.",
            file=sys.stderr,
        )
        return 2

    repository = PostgresManagementBootstrapRepository()
    if not repository.is_available():
        print(
            "Bootstrap is disabled because a Management account already exists.",
            file=sys.stderr,
        )
        return 1

    try:
        auth = SupabaseAuthAdminClient()
    except SupabaseAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        record = bootstrap_first_management(
            auth=auth,
            repository=repository,
            username=args.username,
            email=args.email,
            full_name=args.full_name,
        )
    except (
        AccountConflict,
        ManagementBootstrapUnavailable,
        ManagementBootstrapCleanupError,
        SupabaseAuthError,
    ) as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1
    finally:
        auth.close()

    print(
        "Management invitation created successfully. "
        f"User {record.username!r} is pending until the invited administrator "
        "finishes Supabase Auth setup and signs in."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
