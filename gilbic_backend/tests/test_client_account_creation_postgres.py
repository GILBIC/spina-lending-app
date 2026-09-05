from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

import gilbic_backend.management_repository as management_repository_module
import psycopg
import pytest
from gilbic_backend.account_repository import AccountConflict
from gilbic_backend.management_repository import PostgresManagementRepository
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


@contextmanager
def _test_connection():
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        yield connection


@dataclass(frozen=True, slots=True)
class ClientAccountCase:
    actor_user_id: UUID
    active_client_id: UUID
    inactive_client_id: UUID
    linked_client_id: UUID
    linked_user_id: UUID

    @property
    def client_ids(self) -> tuple[UUID, ...]:
        return (self.active_client_id, self.inactive_client_id, self.linked_client_id)


def _insert_user(connection, *, role: str, label: str) -> UUID:
    user_id = uuid4()
    username = f"priority3-{label}-{uuid4().hex}"
    connection.execute(
        """
        insert into core.users (id, username, email, full_name, status)
        values (%s, %s, %s, %s, 'active')
        """,
        (user_id, username, f"{username}@example.com", f"Priority 3 {label}"),
    )
    connection.execute(
        """
        insert into core.user_roles (user_id, role_id)
        select %s, id from core.roles where code = %s
        """,
        (user_id, role),
    )
    return user_id


def _insert_client(
    connection,
    *,
    client_code: str,
    full_name: str,
    status: str = "active",
    user_id: UUID | None = None,
) -> UUID:
    return connection.execute(
        """
        insert into lending.clients (
            client_code, full_name, phone_number, area, status, user_id
        ) values (%s, %s, '09171234567', 'Priority 3', %s, %s)
        returning id
        """,
        (client_code, full_name, status, user_id),
    ).fetchone()[0]


def _seed_case() -> ClientAccountCase:
    assert DATABASE_URL is not None
    token = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        actor_user_id = _insert_user(connection, role="management", label=f"manager-{token}")
        linked_user_id = _insert_user(connection, role="client", label=f"linked-{token}")
        active_client_id = _insert_client(
            connection,
            client_code=f"C-{token}",
            full_name="Maria Santos",
        )
        inactive_client_id = _insert_client(
            connection,
            client_code=f"INACTIVE-{token}",
            full_name="Inactive Borrower",
            status="inactive",
        )
        linked_client_id = _insert_client(
            connection,
            client_code=f"LINKED-{token}",
            full_name="Linked Borrower",
            user_id=linked_user_id,
        )
    return ClientAccountCase(
        actor_user_id=actor_user_id,
        active_client_id=active_client_id,
        inactive_client_id=inactive_client_id,
        linked_client_id=linked_client_id,
        linked_user_id=linked_user_id,
    )


def _delete_case(case: ClientAccountCase) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        rows = connection.execute(
            "select user_id from lending.clients where id = any(%s)",
            (list(case.client_ids),),
        ).fetchall()
        target_user_ids = [row[0] for row in rows if row[0] is not None]
        audit_targets = [case.actor_user_id, *target_user_ids]
        connection.execute(
            "delete from core.audit_logs where actor_user_id = %s or target_id = any(%s)",
            (case.actor_user_id, audit_targets),
        )
        connection.execute(
            "delete from lending.clients where id = any(%s)",
            (list(case.client_ids),),
        )
        connection.execute(
            "delete from core.users where id = any(%s)",
            (audit_targets,),
        )


@pytest.fixture
def client_account_case() -> ClientAccountCase:
    case = _seed_case()
    try:
        yield case
    finally:
        _delete_case(case)


@pytest.fixture(autouse=True)
def use_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        management_repository_module,
        "open_connection",
        _test_connection,
    )


def test_next_client_username_uses_client_code_and_suffixes_case_insensitive_collision(
    client_account_case: ClientAccountCase,
) -> None:
    repository = PostgresManagementRepository()
    expected_base = repository.next_client_username(
        client_id=client_account_case.active_client_id,
    )
    assert expected_base.startswith("spina.c.")

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            """
            insert into core.users (username, email, full_name, status)
            values (%s, %s, 'Collision User', 'active')
            """,
            (expected_base.upper(), f"collision-{uuid4().hex}@example.com"),
        )

    try:
        assert repository.next_client_username(
            client_id=client_account_case.active_client_id,
        ) == f"{expected_base}.2"
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "delete from core.users where lower(username) = lower(%s)",
                (expected_base,),
            )


def test_create_client_account_profile_links_active_borrower_assigns_client_only_and_audits_without_password(
    client_account_case: ClientAccountCase,
) -> None:
    repository = PostgresManagementRepository()
    username = repository.next_client_username(client_id=client_account_case.active_client_id)
    auth_user_id = uuid4()

    record = repository.create_client_account_profile(
        actor_user_id=client_account_case.actor_user_id,
        auth_user_id=auth_user_id,
        username=username,
        email=f"client-{uuid4().hex}@example.com",
        client_id=client_account_case.active_client_id,
    )

    assert record.status == "active"
    assert record.roles == ("client",)
    assert record.auth_user_id == auth_user_id
    assert record.full_name == "Maria Santos"

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        linked = connection.execute(
            "select user_id from lending.clients where id = %s",
            (client_account_case.active_client_id,),
        ).fetchone()
        roles = connection.execute(
            """
            select r.code
            from core.user_roles ur
            join core.roles r on r.id = ur.role_id
            where ur.user_id = %s
            order by r.code
            """,
            (record.id,),
        ).fetchall()
        audit = connection.execute(
            """
            select action, target_type, target_id, details
            from core.audit_logs
            where actor_user_id = %s and target_id = %s
            order by created_at desc
            limit 1
            """,
            (client_account_case.actor_user_id, record.id),
        ).fetchone()

    assert linked["user_id"] == record.id
    assert [row["code"] for row in roles] == ["client"]
    assert audit["action"] == "client_account.create"
    assert audit["target_type"] == "user"
    assert audit["target_id"] == record.id
    assert audit["details"]["client_id"] == str(client_account_case.active_client_id)
    assert "password" not in json.dumps(audit["details"]).lower()


def test_client_account_creation_rejects_inactive_or_already_linked_borrower(
    client_account_case: ClientAccountCase,
) -> None:
    repository = PostgresManagementRepository()

    with pytest.raises(AccountConflict, match="active"):
        repository.next_client_username(client_id=client_account_case.inactive_client_id)

    with pytest.raises(AccountConflict, match="linked"):
        repository.next_client_username(client_id=client_account_case.linked_client_id)
