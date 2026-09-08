from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import psycopg
import pytest

import gilbic_backend.area_management_move_preview as move_preview_module
import gilbic_backend.area_management_repository as repository_module
from gilbic_backend.area_management_repository import PostgresAreaManagementRepository


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


@contextmanager
def _same_connection(connection):
    yield connection


def _insert_user(connection, *, suffix: str, label: str, collector: bool = False) -> UUID:
    user_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"move-preview-{label}-{suffix}", f"Move Preview {label} {suffix}"),
    ).fetchone()[0]
    if collector:
        connection.execute(
            """
            insert into core.user_roles (user_id, role_id)
            select %s, id from core.roles where code = 'collector'
            """,
            (user_id,),
        )
    return user_id


def _area_uid_by_path(connection, full_path: str) -> UUID:
    row = connection.execute(
        "select area_uid from lending.area_nodes where full_path = %s",
        (full_path,),
    ).fetchone()
    assert row is not None
    return row[0]


def _assign_collector(connection, *, collector_user_id: UUID, area_uid: UUID, area_path: str) -> UUID:
    return connection.execute(
        """
        insert into lending.collector_area_assignments (
            collector_user_id, area, area_uid, sort_order, is_active
        ) values (%s, %s, %s, 0, true)
        returning id
        """,
        (collector_user_id, area_path, area_uid),
    ).fetchone()[0]


def test_move_preview_reports_clients_descendants_owner_change_and_stale_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    connection = psycopg.connect(DATABASE_URL)
    try:
        if connection.execute(
            "select to_regclass('lending.area_nodes')"
        ).fetchone()[0] is None:
            pytest.skip("Area Management migration 0113 is not installed")

        same_connection = lambda: _same_connection(connection)  # noqa: E731
        monkeypatch.setattr(repository_module, "open_connection", same_connection)
        monkeypatch.setattr(move_preview_module, "open_connection", same_connection)
        repository = PostgresAreaManagementRepository()
        suffix = uuid4().hex[:8]
        actor_id = _insert_user(connection, suffix=suffix, label="actor")
        collector_a = _insert_user(connection, suffix=suffix, label="collector-a", collector=True)
        collector_c = _insert_user(connection, suffix=suffix, label="collector-c", collector=True)
        visitor = _insert_user(connection, suffix=suffix, label="visitor", collector=True)

        cardona_name = f"Preview Cardona {suffix}"
        other_city_name = f"Preview Other {suffix}"
        repository.create_area(actor_user_id=actor_id, parent_area_uid=None, name=cardona_name)
        repository.create_area(actor_user_id=actor_id, parent_area_uid=None, name=other_city_name)
        cardona_uid = _area_uid_by_path(connection, cardona_name)
        other_city_uid = _area_uid_by_path(connection, other_city_name)

        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=cardona_uid,
            name="Calahan",
        )
        calahan_path = f"{cardona_name} › Calahan"
        calahan_uid = _area_uid_by_path(connection, calahan_path)
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=calahan_uid,
            name="Balayong",
        )
        balayong_path = f"{calahan_path} › Balayong"
        balayong_uid = _area_uid_by_path(connection, balayong_path)

        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=other_city_uid,
            name="Destination",
        )
        destination_path = f"{other_city_name} › Destination"
        destination_uid = _area_uid_by_path(connection, destination_path)

        cardona_assignment = _assign_collector(
            connection,
            collector_user_id=collector_a,
            area_uid=cardona_uid,
            area_path=cardona_name,
        )
        _assign_collector(
            connection,
            collector_user_id=collector_c,
            area_uid=destination_uid,
            area_path=destination_path,
        )

        connection.execute(
            """
            insert into lending.clients (client_code, full_name, area, area_uid, status)
            values (%s, %s, %s, %s, 'active')
            """,
            (
                f"MOVE-PREVIEW-{suffix}",
                f"Move Preview Client {suffix}",
                balayong_path,
                balayong_uid,
            ),
        )

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
            (grant_id, cardona_assignment, cardona_name),
        )
        assert connection.execute(
            "select lending.collector_has_active_delegated_area_access(%s, %s, now())",
            (visitor, calahan_path),
        ).fetchone()[0] is True

        preview = move_preview_module.preview_move_with_operational_impact(
            repository,
            area_uid=calahan_uid,
            new_parent_area_uid=destination_uid,
        )

        assert preview.clients_affected == 1
        assert preview.descendant_areas_affected == 1
        assert preview.effective_collector_before is not None
        assert preview.effective_collector_before.user_id == collector_a
        assert preview.effective_collector_after is not None
        assert preview.effective_collector_after.user_id == collector_c
        assert preview.stale_delegated_access_count == 1
        assert preview.affected_node_count == 2
    finally:
        connection.rollback()
        connection.close()
