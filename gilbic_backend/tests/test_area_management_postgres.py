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


def _unexpected_connection():
    raise AssertionError("Invalid structural input must fail before opening PostgreSQL.")


def _area_row(connection, area_uid: UUID):
    return connection.execute(
        """
        select area_uid, parent_area_uid, name, full_path, depth, sort_order,
               is_active, is_legacy_unmapped
        from lending.area_nodes
        where area_uid = %s
        """,
        (area_uid,),
    ).fetchone()


def _area_uid_by_path(connection, full_path: str) -> UUID:
    row = connection.execute(
        "select area_uid from lending.area_nodes where full_path = %s",
        (full_path,),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_user(connection, *, suffix: str, label: str) -> UUID:
    return connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"area-{label}-{suffix}-{uuid4().hex[:6]}", f"Area {label} {suffix}"),
    ).fetchone()[0]


def _protected_table_fingerprint(connection, table: str) -> tuple[int, str]:
    count, digest = connection.execute(
        f"""
        select
            count(*)::integer,
            md5(coalesce(string_agg(md5(row_to_json(record)::text), '' order by record.id), ''))
        from {table} record
        """
    ).fetchone()
    return count, digest


def test_structural_mutation_interfaces_are_present() -> None:
    repository = PostgresAreaManagementRepository()

    for method_name in (
        "create_area",
        "rename_area",
        "preview_move",
        "move_area",
        "reorder_siblings",
    ):
        assert callable(getattr(repository, method_name))


def test_structural_input_validation_fails_before_database(monkeypatch) -> None:
    monkeypatch.setattr(repository_module, "open_connection", _unexpected_connection)
    repository = PostgresAreaManagementRepository()
    actor_id = UUID("00000000-0000-0000-0000-0000000000a1")
    area_a = UUID("00000000-0000-0000-0000-0000000000b1")
    area_b = UUID("00000000-0000-0000-0000-0000000000b2")

    for invalid_name in ("", "   ", "Calahan › Balayong"):
        with pytest.raises(ValueError):
            repository.create_area(
                actor_user_id=actor_id,
                parent_area_uid=None,
                name=invalid_name,
            )

    with pytest.raises(ValueError):
        repository.reorder_siblings(
            actor_user_id=actor_id,
            parent_area_uid=None,
            ordered_area_uids=(area_a, area_a, area_b),
        )


def test_structural_mutation_source_preserves_financial_history_and_audits() -> None:
    source = inspect.getsource(repository_module).lower()

    for method_name in (
        "create_area",
        "rename_area",
        "preview_move",
        "move_area",
        "reorder_siblings",
    ):
        assert f"def {method_name}" in source

    assert "insert into core.audit_logs" in source
    assert "depth <=" not in source
    assert "depth<=" not in source

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
def test_structural_mutations_support_deep_hierarchy_cascade_order_and_audit(
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
        actor_id = _insert_user(connection, suffix=suffix, label="actor")
        collector_id = _insert_user(connection, suffix=suffix, label="collector")

        protected_before = {
            table: _protected_table_fingerprint(connection, table)
            for table in (
                "lending.collection_transactions",
                "lending.collection_remittances",
            )
        }
        audit_before = connection.execute(
            "select count(*) from core.audit_logs where actor_user_id = %s",
            (actor_id,),
        ).fetchone()[0]
        successful_mutations = 0

        cardona_name = f"AM Cardona {suffix}"
        other_city_name = f"AM Other City {suffix}"
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=None,
            name=cardona_name,
        )
        successful_mutations += 1
        cardona_uid = _area_uid_by_path(connection, cardona_name)
        cardona = _area_row(connection, cardona_uid)
        assert cardona[1] is None
        assert cardona[4] == 0
        assert cardona[7] is False

        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=None,
            name=other_city_name,
        )
        successful_mutations += 1
        other_city_uid = _area_uid_by_path(connection, other_city_name)

        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=other_city_uid,
            name="Destination",
        )
        successful_mutations += 1
        destination_path = f"{other_city_name} › Destination"
        destination_uid = _area_uid_by_path(connection, destination_path)

        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=cardona_uid,
            name="Calahan",
        )
        successful_mutations += 1
        calahan_path = f"{cardona_name} › Calahan"
        calahan_uid = _area_uid_by_path(connection, calahan_path)
        assert _area_row(connection, calahan_uid)[4] == 1

        parent_uid = calahan_uid
        path = calahan_path
        for name in ("Balayong", "Mabini Street", "Purok 2", "Riverside", "Block A"):
            repository.create_area(
                actor_user_id=actor_id,
                parent_area_uid=parent_uid,
                name=name,
            )
            successful_mutations += 1
            path = f"{path} › {name}"
            parent_uid = _area_uid_by_path(connection, path)

        deepest_uid = parent_uid
        deepest = _area_row(connection, deepest_uid)
        assert deepest[4] == 6

        client_id = connection.execute(
            """
            insert into lending.clients (
                client_code, full_name, area, area_uid, status
            ) values (%s, %s, %s, %s, 'active')
            returning id
            """,
            (f"AREA-C-{suffix}", f"Area Client {suffix}", path, deepest_uid),
        ).fetchone()[0]
        assignment_id = connection.execute(
            """
            insert into lending.collector_area_assignments (
                collector_user_id, area, area_uid, sort_order, is_active
            ) values (%s, %s, %s, 0, true)
            returning id
            """,
            (collector_id, path, deepest_uid),
        ).fetchone()[0]

        repository.rename_area(
            actor_user_id=actor_id,
            area_uid=calahan_uid,
            name="Calahan Renamed",
        )
        successful_mutations += 1
        renamed_prefix = f"{cardona_name} › Calahan Renamed"
        renamed_deep_path = (
            f"{renamed_prefix} › Balayong › Mabini Street › Purok 2 › Riverside › Block A"
        )
        assert _area_row(connection, deepest_uid)[3] == renamed_deep_path
        assert connection.execute(
            "select area from lending.clients where id = %s", (client_id,)
        ).fetchone()[0] == renamed_deep_path
        assert connection.execute(
            "select area from lending.collector_area_assignments where id = %s",
            (assignment_id,),
        ).fetchone()[0] == renamed_deep_path

        before_preview = _area_row(connection, calahan_uid)
        repository.preview_move(
            area_uid=calahan_uid,
            new_parent_area_uid=destination_uid,
        )
        after_preview = _area_row(connection, calahan_uid)
        assert after_preview == before_preview

        repository.move_area(
            actor_user_id=actor_id,
            area_uid=calahan_uid,
            new_parent_area_uid=destination_uid,
        )
        successful_mutations += 1
        moved_prefix = f"{destination_path} › Calahan Renamed"
        moved_deep_path = (
            f"{moved_prefix} › Balayong › Mabini Street › Purok 2 › Riverside › Block A"
        )
        assert _area_row(connection, calahan_uid)[4] == 2
        assert _area_row(connection, deepest_uid)[4] == 7
        assert _area_row(connection, deepest_uid)[3] == moved_deep_path
        assert connection.execute(
            "select area from lending.clients where id = %s", (client_id,)
        ).fetchone()[0] == moved_deep_path
        assert connection.execute(
            "select area from lending.collector_area_assignments where id = %s",
            (assignment_id,),
        ).fetchone()[0] == moved_deep_path

        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=other_city_uid,
            name="Sibling A",
        )
        successful_mutations += 1
        sibling_a = _area_uid_by_path(connection, f"{other_city_name} › Sibling A")
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=other_city_uid,
            name="Sibling B",
        )
        successful_mutations += 1
        sibling_b = _area_uid_by_path(connection, f"{other_city_name} › Sibling B")

        repository.reorder_siblings(
            actor_user_id=actor_id,
            parent_area_uid=other_city_uid,
            ordered_area_uids=(sibling_b, destination_uid, sibling_a),
        )
        successful_mutations += 1
        orders = connection.execute(
            """
            select area_uid, sort_order
            from lending.area_nodes
            where parent_area_uid = %s
            order by sort_order
            """,
            (other_city_uid,),
        ).fetchall()
        assert orders == [(sibling_b, 0), (destination_uid, 1), (sibling_a, 2)]

        with pytest.raises(ValueError):
            repository.reorder_siblings(
                actor_user_id=actor_id,
                parent_area_uid=other_city_uid,
                ordered_area_uids=(sibling_a, sibling_b),
            )
        with pytest.raises(ValueError):
            repository.reorder_siblings(
                actor_user_id=actor_id,
                parent_area_uid=other_city_uid,
                ordered_area_uids=(sibling_a, sibling_a, destination_uid),
            )
        with pytest.raises(ValueError):
            repository.create_area(
                actor_user_id=actor_id,
                parent_area_uid=other_city_uid,
                name="Sibling A",
            )
        with pytest.raises(ValueError):
            repository.move_area(
                actor_user_id=actor_id,
                area_uid=destination_uid,
                new_parent_area_uid=deepest_uid,
            )

        inactive_name = f"AM Retired {suffix}"
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=None,
            name=inactive_name,
        )
        successful_mutations += 1
        inactive_uid = _area_uid_by_path(connection, inactive_name)
        connection.execute(
            "update lending.area_nodes set is_active = false where area_uid = %s",
            (inactive_uid,),
        )
        with pytest.raises(ValueError):
            repository.move_area(
                actor_user_id=actor_id,
                area_uid=calahan_uid,
                new_parent_area_uid=inactive_uid,
            )

        audit_rows = connection.execute(
            """
            select action, target_type, details::text
            from core.audit_logs
            where actor_user_id = %s
            order by created_at, id
            """,
            (actor_id,),
        ).fetchall()
        assert len(audit_rows) - audit_before == successful_mutations
        for _action, _target_type, details in audit_rows[audit_before:]:
            lowered = details.lower()
            for forbidden in ("national_id", "meralco", "photo", "selfie", "evidence"):
                assert forbidden not in lowered

        protected_after = {
            table: _protected_table_fingerprint(connection, table)
            for table in protected_before
        }
        assert protected_after == protected_before
    finally:
        connection.rollback()
        connection.close()
