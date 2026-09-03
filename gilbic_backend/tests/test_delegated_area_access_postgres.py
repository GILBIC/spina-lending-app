from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"


def _collector(connection: psycopg.Connection, label: str):
    user_id = connection.execute(
        """
        INSERT INTO core.users(username, full_name, status)
        VALUES(%s, %s, 'active')
        RETURNING id
        """,
        (f"delegated-{label}-{uuid4().hex[:8]}", f"Delegated {label}"),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO core.user_roles(user_id, role_id)
        SELECT %s, id FROM core.roles WHERE code='collector'
        """,
        (user_id,),
    )
    return user_id


def _assignment(
    connection: psycopg.Connection,
    collector_user_id,
    area: str,
    *,
    sort_order: int = 0,
):
    return connection.execute(
        """
        INSERT INTO lending.collector_area_assignments(
            collector_user_id, area, sort_order, is_active
        )
        VALUES(%s, %s, %s, true)
        RETURNING id
        """,
        (collector_user_id, area, sort_order),
    ).fetchone()[0]


def _grant(
    connection: psycopg.Connection,
    *,
    grantor_user_id,
    visiting_user_id,
    assignment_id,
    area_path: str,
    include_descendants: bool = True,
):
    grant_id = connection.execute(
        """
        INSERT INTO lending.collector_area_access_grants(
            grantor_user_id,
            visiting_collector_user_id,
            effective_at,
            expires_at
        )
        VALUES(%s, %s, now() - interval '1 hour', now() + interval '1 hour')
        RETURNING id
        """,
        (grantor_user_id, visiting_user_id),
    ).fetchone()[0]
    scope_id = connection.execute(
        """
        INSERT INTO lending.collector_area_access_grant_scopes(
            grant_id,
            source_assignment_id,
            area_path,
            include_descendants
        )
        VALUES(%s, %s, %s, %s)
        RETURNING id
        """,
        (grant_id, assignment_id, area_path, include_descendants),
    ).fetchone()[0]
    return grant_id, scope_id


def test_delegated_permissions_and_boundary_safe_area_paths() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            permissions = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT permission.code
                    FROM core.role_permissions mapping
                    JOIN core.roles role ON role.id=mapping.role_id
                    JOIN core.permissions permission ON permission.code=mapping.permission_code
                    WHERE role.code='collector'
                      AND permission.code LIKE 'delegated_area.%'
                    """
                ).fetchall()
            }
            assert permissions == {
                "delegated_area.view",
                "delegated_area.request",
                "delegated_area.grant",
            }

            assert connection.execute(
                "SELECT lending.normalize_area_path(%s)",
                ("  CARDONA   ›  Looc  ",),
            ).fetchone()[0] == "CARDONA › Looc"

            assert connection.execute(
                "SELECT lending.area_path_contains(%s,%s,true)",
                ("CARDONA", "CARDONA › Looc"),
            ).fetchone()[0] is True
            assert connection.execute(
                "SELECT lending.area_path_contains(%s,%s,false)",
                ("CARDONA", "CARDONA › Looc"),
            ).fetchone()[0] is False
            assert connection.execute(
                "SELECT lending.area_path_contains(%s,%s,true)",
                ("CARDONA", "CARDONA EAST"),
            ).fetchone()[0] is False
            assert connection.execute(
                "SELECT lending.area_path_contains(%s,%s,true)",
                ("cardona", "CARDONA › LOOC"),
            ).fetchone()[0] is True
        finally:
            connection.rollback()


def test_most_specific_owner_and_equal_specificity_ambiguity_fail_closed() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            parent_owner = _collector(connection, "parent")
            child_owner = _collector(connection, "child")
            ambiguous_owner = _collector(connection, "ambiguous")

            _assignment(connection, parent_owner, "CARDONA", sort_order=1)
            _assignment(connection, child_owner, "CARDONA › Looc", sort_order=1)

            assert connection.execute(
                "SELECT lending.collector_area_owner(%s)",
                ("CARDONA › Calahan › Zone 1",),
            ).fetchone()[0] == parent_owner
            assert connection.execute(
                "SELECT lending.collector_area_owner(%s)",
                ("CARDONA › Looc › Zone 2",),
            ).fetchone()[0] == child_owner
            assert connection.execute(
                "SELECT lending.collector_owns_area_path(%s,%s)",
                (child_owner, "CARDONA › Looc › Zone 2"),
            ).fetchone()[0] is True
            assert connection.execute(
                "SELECT lending.collector_owns_area_path(%s,%s)",
                (parent_owner, "CARDONA › Looc › Zone 2"),
            ).fetchone()[0] is False

            _assignment(connection, ambiguous_owner, "CARDONA › Looc", sort_order=2)
            assert connection.execute(
                "SELECT lending.collector_area_owner(%s)",
                ("CARDONA › Looc › Zone 2",),
            ).fetchone()[0] is None
            assert connection.execute(
                "SELECT lending.collector_owns_area_path(%s,%s)",
                (child_owner, "CARDONA › Looc › Zone 2"),
            ).fetchone()[0] is False
        finally:
            connection.rollback()


def test_delegated_grant_follows_current_authoritative_owner_only() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            grantor = _collector(connection, "grantor")
            visitor = _collector(connection, "visitor")
            child_owner = _collector(connection, "override")
            parent_assignment = _assignment(connection, grantor, "CARDONA")
            _grant(
                connection,
                grantor_user_id=grantor,
                visiting_user_id=visitor,
                assignment_id=parent_assignment,
                area_path="CARDONA",
            )

            assert connection.execute(
                "SELECT lending.collector_has_active_delegated_area_access(%s,%s,now())",
                (visitor, "CARDONA › Calahan"),
            ).fetchone()[0] is True

            _assignment(connection, child_owner, "CARDONA › Looc")
            assert connection.execute(
                "SELECT lending.collector_has_active_delegated_area_access(%s,%s,now())",
                (visitor, "CARDONA › Looc › Zone 1"),
            ).fetchone()[0] is False
            assert connection.execute(
                "SELECT lending.collector_has_active_delegated_area_access(%s,%s,now())",
                (visitor, "CARDONA › Calahan"),
            ).fetchone()[0] is True

            connection.execute(
                "UPDATE lending.collector_area_assignments SET is_active=false WHERE id=%s",
                (parent_assignment,),
            )
            assert connection.execute(
                "SELECT lending.collector_has_active_delegated_area_access(%s,%s,now())",
                (visitor, "CARDONA › Calahan"),
            ).fetchone()[0] is False
        finally:
            connection.rollback()


def test_delegated_grant_expiry_and_revocation_fail_closed() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            grantor = _collector(connection, "expiry-owner")
            visitor = _collector(connection, "expiry-visitor")
            assignment_id = _assignment(connection, grantor, "MORONG")
            grant_id, _ = _grant(
                connection,
                grantor_user_id=grantor,
                visiting_user_id=visitor,
                assignment_id=assignment_id,
                area_path="MORONG",
            )

            assert connection.execute(
                "SELECT lending.collector_has_active_delegated_area_access(%s,%s,now())",
                (visitor, "MORONG › Bombongan"),
            ).fetchone()[0] is True
            assert connection.execute(
                """
                SELECT lending.collector_has_active_delegated_area_access(
                    %s,%s,now() + interval '2 hours'
                )
                """,
                (visitor, "MORONG › Bombongan"),
            ).fetchone()[0] is False

            connection.execute(
                """
                UPDATE lending.collector_area_access_grants
                SET revoked_at=now(),
                    revoked_by_user_id=%s,
                    revocation_reason='Route coverage ended',
                    updated_at=now()
                WHERE id=%s
                """,
                (grantor, grant_id),
            )
            assert connection.execute(
                "SELECT lending.collector_has_active_delegated_area_access(%s,%s,now())",
                (visitor, "MORONG › Bombongan"),
            ).fetchone()[0] is False
        finally:
            connection.rollback()


def test_request_grant_scope_and_event_evidence_are_immutable() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            owner = _collector(connection, "immutable-owner")
            visitor = _collector(connection, "immutable-visitor")
            assignment_id = _assignment(connection, owner, "TAYTAY")
            request_id = connection.execute(
                """
                INSERT INTO lending.collector_area_access_requests(
                    requester_user_id,
                    requested_owner_user_id,
                    scope_mode,
                    reason,
                    requested_expires_at
                )
                VALUES(%s,%s,'selected_paths','Temporary route assistance',now()+interval '1 day')
                RETURNING id
                """,
                (visitor, owner),
            ).fetchone()[0]
            request_scope_id = connection.execute(
                """
                INSERT INTO lending.collector_area_access_request_scopes(
                    request_id, source_assignment_id, area_path, include_descendants
                )
                VALUES(%s,%s,'TAYTAY',true)
                RETURNING id
                """,
                (request_id, assignment_id),
            ).fetchone()[0]
            event_id = connection.execute(
                """
                INSERT INTO lending.collector_area_access_events(
                    request_id, actor_user_id, event_type, details
                )
                VALUES(%s,%s,'requested','{}'::jsonb)
                RETURNING id
                """,
                (request_id, visitor),
            ).fetchone()[0]
            grant_id, grant_scope_id = _grant(
                connection,
                grantor_user_id=owner,
                visiting_user_id=visitor,
                assignment_id=assignment_id,
                area_path="TAYTAY",
            )

            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE lending.collector_area_access_requests SET reason='tampered' WHERE id=%s",
                        (request_id,),
                    )
            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE lending.collector_area_access_request_scopes SET area_path='OTHER' WHERE id=%s",
                        (request_scope_id,),
                    )
            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE lending.collector_area_access_grant_scopes SET area_path='OTHER' WHERE id=%s",
                        (grant_scope_id,),
                    )
            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE lending.collector_area_access_events SET details='{\"tampered\":true}'::jsonb WHERE id=%s",
                        (event_id,),
                    )
            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE lending.collector_area_access_grants SET visiting_collector_user_id=%s WHERE id=%s",
                        (owner, grant_id),
                    )
        finally:
            connection.rollback()


def test_0097_0098_do_not_rewrite_existing_collection_history_and_capture_is_hierarchical() -> None:
    migration_0097 = (SQL_ROOT / "0097_add_delegated_collector_area_access.sql").read_text(
        encoding="utf-8"
    ).lower()
    migration_0098 = (
        SQL_ROOT / "0098_harden_hierarchical_collector_area_ownership.sql"
    ).read_text(encoding="utf-8").lower()

    for source in (migration_0097, migration_0098):
        assert "update lending.collection_transactions" not in source
        assert "delete from lending.collection_transactions" not in source
        assert "insert into lending.collection_transactions" not in source

    assert "new.assigned_collector_user_id := route_owner" in migration_0098
    assert "new.assignment_area := client_area" in migration_0098
    assert "new.collection_origin := 'assigned_route'" in migration_0098
    assert "new.collection_origin := 'cross_collector'" in migration_0098
    assert "route_owner := lending.collector_area_owner(client_area)" in migration_0098
