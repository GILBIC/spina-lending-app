from __future__ import annotations

import inspect
import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import psycopg
import pytest

import gilbic_backend.area_management_repository as repository_module
from gilbic_backend.area_management_repository import PostgresAreaManagementRepository

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")


@contextmanager
def _same_connection(connection):
    yield connection


def _insert_user(
    connection,
    *,
    suffix: str,
    label: str,
    role: str | None,
    status: str = "active",
) -> UUID:
    user_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, %s)
        returning id
        """,
        (f"area-owner-{label}-{suffix}-{uuid4().hex[:6]}", f"Area Owner {label} {suffix}", status),
    ).fetchone()[0]
    if role is not None:
        connection.execute(
            """
            insert into core.user_roles (user_id, role_id)
            select %s, id from core.roles where code = %s
            """,
            (user_id, role),
        )
    return user_id


def _area_uid(connection, full_path: str) -> UUID:
    row = connection.execute(
        "select area_uid from lending.area_nodes where full_path = %s",
        (full_path,),
    ).fetchone()
    assert row is not None
    return row[0]


def _protected_fingerprint(connection, table: str) -> tuple[int, str]:
    return connection.execute(
        f"""
        select
            count(*)::integer,
            md5(coalesce(string_agg(md5(row_to_json(record)::text), '' order by record.id), ''))
        from {table} record
        """
    ).fetchone()


def test_collector_assignment_interfaces_are_present() -> None:
    repository = PostgresAreaManagementRepository()

    assert callable(getattr(repository, "assign_collector"))
    assert callable(getattr(repository, "remove_collector_assignment"))


def test_collector_assignment_source_preserves_existing_ownership_and_history_contract() -> None:
    source = inspect.getsource(repository_module).lower()

    assert "def assign_collector" in source
    assert "def remove_collector_assignment" in source
    assert "lending.collector_area_assignments" in source
    assert "insert into core.audit_logs" in source

    for forbidden in (
        "update lending.collection_transactions",
        "delete from lending.collection_transactions",
        "truncate lending.collection_transactions",
        "update lending.collection_remittances",
        "delete from lending.collection_remittances",
        "truncate lending.collection_remittances",
        "update accounting.",
        "delete from accounting.",
        "truncate accounting.",
    ):
        assert forbidden not in source


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)
def test_permanent_collector_assignment_inherits_overrides_falls_back_and_invalidates_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    connection = psycopg.connect(DATABASE_URL)
    try:
        if connection.execute(
            "select to_regclass('lending.area_nodes')"
        ).fetchone()[0] is None:
            pytest.skip("Area Management migration 0113 is not installed")

        monkeypatch.setattr(
            repository_module,
            "open_connection",
            lambda: _same_connection(connection),
        )
        repository = PostgresAreaManagementRepository()
        suffix = uuid4().hex[:8]

        actor_id = _insert_user(
            connection,
            suffix=suffix,
            label="actor",
            role="management",
        )
        collector_a = _insert_user(
            connection,
            suffix=suffix,
            label="a",
            role="collector",
        )
        collector_b = _insert_user(
            connection,
            suffix=suffix,
            label="b",
            role="collector",
        )
        collector_c = _insert_user(
            connection,
            suffix=suffix,
            label="c",
            role="collector",
        )
        visitor = _insert_user(
            connection,
            suffix=suffix,
            label="visitor",
            role="collector",
        )
        inactive_collector = _insert_user(
            connection,
            suffix=suffix,
            label="inactive",
            role="collector",
            status="inactive",
        )
        non_collector = _insert_user(
            connection,
            suffix=suffix,
            label="employee",
            role="employee",
        )

        root_name = f"Ownership Cardona {suffix}"
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=None,
            name=root_name,
        )
        root_uid = _area_uid(connection, root_name)
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=root_uid,
            name="Calahan",
        )
        calahan_path = f"{root_name} › Calahan"
        calahan_uid = _area_uid(connection, calahan_path)
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=calahan_uid,
            name="Balayong",
        )
        balayong_path = f"{calahan_path} › Balayong"
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=calahan_uid,
            name="NIA",
        )
        nia_path = f"{calahan_path} › NIA"
        nia_uid = _area_uid(connection, nia_path)

        protected_before = {
            table: _protected_fingerprint(connection, table)
            for table in (
                "lending.collection_transactions",
                "lending.collection_remittances",
            )
        }

        repository.assign_collector(
            actor_user_id=actor_id,
            area_uid=calahan_uid,
            collector_user_id=collector_a,
        )
        parent_assignment = connection.execute(
            """
            select id
            from lending.collector_area_assignments
            where area_uid = %s and collector_user_id = %s and is_active = true
            """,
            (calahan_uid, collector_a),
        ).fetchone()[0]

        assert connection.execute(
            "select lending.collector_area_owner(%s)",
            (balayong_path,),
        ).fetchone()[0] == collector_a
        assert connection.execute(
            "select lending.collector_area_owner(%s)",
            (nia_path,),
        ).fetchone()[0] == collector_a

        grant_id = connection.execute(
            """
            insert into lending.collector_area_access_grants (
                grantor_user_id,
                visiting_collector_user_id,
                effective_at,
                expires_at
            ) values (%s, %s, now() - interval '1 hour', now() + interval '1 hour')
            returning id
            """,
            (collector_a, visitor),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.collector_area_access_grant_scopes (
                grant_id,
                source_assignment_id,
                area_path,
                include_descendants
            ) values (%s, %s, %s, true)
            """,
            (grant_id, parent_assignment, calahan_path),
        )
        assert connection.execute(
            "select lending.collector_has_active_delegated_area_access(%s, %s, now())",
            (visitor, nia_path),
        ).fetchone()[0] is True

        repository.assign_collector(
            actor_user_id=actor_id,
            area_uid=nia_uid,
            collector_user_id=collector_b,
        )
        assert connection.execute(
            "select lending.collector_area_owner(%s)",
            (nia_path,),
        ).fetchone()[0] == collector_b
        assert connection.execute(
            "select lending.collector_owns_area_path(%s, %s)",
            (collector_a, nia_path),
        ).fetchone()[0] is False
        assert connection.execute(
            "select is_active from lending.collector_area_assignments where id = %s",
            (parent_assignment,),
        ).fetchone()[0] is True
        assert connection.execute(
            "select lending.collector_has_active_delegated_area_access(%s, %s, now())",
            (visitor, nia_path),
        ).fetchone()[0] is False

        repository.assign_collector(
            actor_user_id=actor_id,
            area_uid=nia_uid,
            collector_user_id=collector_c,
        )
        exact_rows = connection.execute(
            """
            select collector_user_id, is_active
            from lending.collector_area_assignments
            where area_uid = %s
            order by created_at, id
            """,
            (nia_uid,),
        ).fetchall()
        assert sum(1 for _collector, is_active in exact_rows if is_active) == 1
        assert any(
            collector == collector_b and is_active is False
            for collector, is_active in exact_rows
        )
        assert any(
            collector == collector_c and is_active is True
            for collector, is_active in exact_rows
        )
        assert connection.execute(
            "select lending.collector_area_owner(%s)",
            (nia_path,),
        ).fetchone()[0] == collector_c

        repository.remove_collector_assignment(
            actor_user_id=actor_id,
            area_uid=nia_uid,
        )
        assert connection.execute(
            "select lending.collector_area_owner(%s)",
            (nia_path,),
        ).fetchone()[0] == collector_a
        assert connection.execute(
            "select lending.collector_has_active_delegated_area_access(%s, %s, now())",
            (visitor, nia_path),
        ).fetchone()[0] is True

        with pytest.raises(ValueError):
            repository.assign_collector(
                actor_user_id=actor_id,
                area_uid=nia_uid,
                collector_user_id=inactive_collector,
            )
        with pytest.raises(ValueError):
            repository.assign_collector(
                actor_user_id=actor_id,
                area_uid=nia_uid,
                collector_user_id=non_collector,
            )

        audit_actions = connection.execute(
            """
            select action
            from core.audit_logs
            where actor_user_id = %s
              and action in ('area.collector.assign', 'area.collector.remove')
            order by created_at, id
            """,
            (actor_id,),
        ).fetchall()
        assert [row[0] for row in audit_actions] == [
            "area.collector.assign",
            "area.collector.assign",
            "area.collector.assign",
            "area.collector.remove",
        ]

        protected_after = {
            table: _protected_fingerprint(connection, table)
            for table in protected_before
        }
        assert protected_after == protected_before
    finally:
        connection.rollback()
        connection.close()
