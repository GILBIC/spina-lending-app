from __future__ import annotations

from uuid import UUID

import pytest

from gilbic_backend.account_repository import AccountConflict
from gilbic_backend.bootstrap_management import (
    ManagementBootstrapCleanupError,
    bootstrap_first_management,
)
from gilbic_backend.bootstrap_repository import (
    BootstrapManagementRecord,
    ManagementBootstrapUnavailable,
)


AUTH_USER_ID = UUID("55555555-5555-4555-8555-555555555555")
GILBIC_USER_ID = UUID("66666666-6666-4666-8666-666666666666")


class FakeAuthAdmin:
    def __init__(self) -> None:
        self.invited: list[str] = []
        self.deleted: list[UUID] = []
        self.delete_error: Exception | None = None

    def invite_user(self, *, email: str) -> UUID:
        self.invited.append(email)
        return AUTH_USER_ID

    def delete_user(self, *, auth_user_id: UUID) -> None:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(auth_user_id)


class FakeBootstrapRepository:
    def __init__(self) -> None:
        self.available = True
        self.create_error: Exception | None = None
        self.created: tuple[UUID, str, str, str] | None = None

    def is_available(self) -> bool:
        return self.available

    def create_initial_management(
        self,
        *,
        auth_user_id: UUID,
        username: str,
        email: str,
        full_name: str,
    ) -> BootstrapManagementRecord:
        if self.create_error is not None:
            raise self.create_error
        self.created = (auth_user_id, username, email, full_name)
        return BootstrapManagementRecord(
            user_id=GILBIC_USER_ID,
            auth_user_id=auth_user_id,
            username=username.strip(),
            email=email.strip().lower(),
            full_name=" ".join(full_name.split()),
            status="pending",
        )


def test_bootstrap_invites_and_creates_first_management() -> None:
    auth = FakeAuthAdmin()
    repository = FakeBootstrapRepository()

    record = bootstrap_first_management(
        auth=auth,
        repository=repository,
        username="manager.one",
        email="Manager@Example.com",
        full_name="  Manager   One  ",
    )

    assert auth.invited == ["manager@example.com"]
    assert auth.deleted == []
    assert repository.created == (
        AUTH_USER_ID,
        "manager.one",
        "Manager@Example.com",
        "  Manager   One  ",
    )
    assert record.auth_user_id == AUTH_USER_ID
    assert record.status == "pending"


def test_bootstrap_stops_before_invite_when_management_exists() -> None:
    auth = FakeAuthAdmin()
    repository = FakeBootstrapRepository()
    repository.available = False

    with pytest.raises(ManagementBootstrapUnavailable):
        bootstrap_first_management(
            auth=auth,
            repository=repository,
            username="manager.one",
            email="manager@example.com",
            full_name="Manager One",
        )

    assert auth.invited == []


def test_bootstrap_removes_invited_auth_user_when_database_write_fails() -> None:
    auth = FakeAuthAdmin()
    repository = FakeBootstrapRepository()
    repository.create_error = AccountConflict("username already exists")

    with pytest.raises(AccountConflict):
        bootstrap_first_management(
            auth=auth,
            repository=repository,
            username="manager.one",
            email="manager@example.com",
            full_name="Manager One",
        )

    assert auth.invited == ["manager@example.com"]
    assert auth.deleted == [AUTH_USER_ID]


def test_bootstrap_reports_cleanup_failure_instead_of_silently_orphaning_auth_user() -> None:
    auth = FakeAuthAdmin()
    auth.delete_error = RuntimeError("auth unavailable")
    repository = FakeBootstrapRepository()
    repository.create_error = AccountConflict("username already exists")

    with pytest.raises(ManagementBootstrapCleanupError):
        bootstrap_first_management(
            auth=auth,
            repository=repository,
            username="manager.one",
            email="manager@example.com",
            full_name="Manager One",
        )
