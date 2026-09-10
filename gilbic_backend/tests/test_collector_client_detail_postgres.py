from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest

import gilbic_backend.collector_client_detail_repository as client_detail_repository_module
from gilbic_backend.collector_client_detail_repository import (
    CollectorClientDetailRecord,
    PostgresCollectorClientDetailRepository,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


@contextmanager
def _same_connection(connection: psycopg.Connection):
    yield connection


def test_collection_location_repository_uses_owner_or_current_delegation_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    connection = psycopg.connect(DATABASE_URL)
    try:
        if connection.execute(
            "select to_regclass('lending.area_nodes')"
        ).fetchone()[0] is None:
            pytest.skip("Area Management migration 0113 is not installed")

        suffix = uuid4().hex[:10]
        owner = connection.execute(
            """
            insert into core.users(username, full_name, status)
            values (%s, %s, 'active')
            returning id
            """,
            (f"detail-owner-{suffix}", f"Detail Owner {suffix}"),
        ).fetchone()[0]
        child_owner = connection.execute(
            """
            insert into core.users(username, full_name, status)
            values (%s, %s, 'active')
            returning id
            """,
            (f"detail-child-{suffix}", f"Detail Child {suffix}"),
        ).fetchone()[0]
        visitor = connection.execute(
            """
            insert into core.users(username, full_name, status)
            values (%s, %s, 'active')
            returning id
            """,
            (f"detail-visitor-{suffix}", f"Detail Visitor {suffix}"),
        ).fetchone()[0]
        unrelated = connection.execute(
            """
            insert into core.users(username, full_name, status)
            values (%s, %s, 'active')
            returning id
            """,
            (f"detail-unrelated-{suffix}", f"Detail Unrelated {suffix}"),
        ).fetchone()[0]

        root_path = f"DETAIL-{suffix}"
        owned_path = f"{root_path} › Owned"
        override_path = f"{root_path} › Override"
        override_client_path = f"{override_path} › Block"

        root_uid = uuid4()
        owned_uid = uuid4()
        override_uid = uuid4()
        override_block_uid = uuid4()
        connection.execute(
            """
            insert into lending.area_nodes(
                area_uid,
                parent_area_uid,
                name,
                full_path,
                depth,
                sort_order,
                is_active,
                is_legacy_unmapped
            )
            values
                (%s, null, %s, %s, 0, 0, true, false),
                (%s, %s, 'Owned', %s, 1, 0, true, false),
                (%s, %s, 'Override', %s, 1, 1, true, false),
                (%s, %s, 'Block', %s, 2, 0, true, false)
            """,
            (
                root_uid,
                root_path,
                root_path,
                owned_uid,
                root_uid,
                owned_path,
                override_uid,
                root_uid,
                override_path,
                override_block_uid,
                override_uid,
                override_client_path,
            ),
        )

        root_assignment = connection.execute(
            """
            insert into lending.collector_area_assignments(
                collector_user_id, area, area_uid, sort_order, is_active
            )
            values (%s, %s, %s, 0, true)
            returning id
            """,
            (owner, root_path, root_uid),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.collector_area_assignments(
                collector_user_id, area, area_uid, sort_order, is_active
            )
            values (%s, %s, %s, 0, true)
            """,
            (child_owner, override_path, override_uid),
        )

        grant_id = connection.execute(
            """
            insert into lending.collector_area_access_grants(
                grantor_user_id,
                visiting_collector_user_id,
                effective_at,
                expires_at
            )
            values (%s, %s, now() - interval '1 hour', now() + interval '1 hour')
            returning id
            """,
            (owner, visitor),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.collector_area_access_grant_scopes(
                grant_id,
                source_assignment_id,
                area_path,
                include_descendants
            )
            values (%s, %s, %s, true)
            """,
            (grant_id, root_assignment, root_path),
        )

        owned_client = uuid4()
        overridden_client = uuid4()
        connection.execute(
            """
            insert into lending.clients(
                id, client_code, full_name, area, area_uid, status
            )
            values
                (%s, %s, %s, %s, %s, 'active'),
                (%s, %s, %s, %s, %s, 'active')
            """,
            (
                owned_client,
                f"DETAIL-O-{suffix}",
                f"Detail Owned {suffix}",
                owned_path,
                owned_uid,
                overridden_client,
                f"DETAIL-X-{suffix}",
                f"Detail Override {suffix}",
                override_client_path,
                override_block_uid,
            ),
        )

        monkeypatch.setattr(
            client_detail_repository_module,
            "open_connection",
            lambda: _same_connection(connection),
        )
        repository = PostgresCollectorClientDetailRepository()

        expected_owned = CollectorClientDetailRecord(
            client_id=owned_client,
            collection_location_status="not_verified",
            display_address=None,
            landmark=None,
            photo_url=None,
            verified_at=None,
        )
        expected_override = CollectorClientDetailRecord(
            client_id=overridden_client,
            collection_location_status="not_verified",
            display_address=None,
            landmark=None,
            photo_url=None,
            verified_at=None,
        )

        assert repository.get_collection_location(
            collector_user_id=owner,
            client_id=owned_client,
        ) == expected_owned
        assert repository.get_collection_location(
            collector_user_id=visitor,
            client_id=owned_client,
        ) == expected_owned
        assert (
            repository.get_collection_location(
                collector_user_id=unrelated,
                client_id=owned_client,
            )
            is None
        )

        assert (
            repository.get_collection_location(
                collector_user_id=owner,
                client_id=overridden_client,
            )
            is None
        )
        assert (
            repository.get_collection_location(
                collector_user_id=visitor,
                client_id=overridden_client,
            )
            is None
        )
        assert repository.get_collection_location(
            collector_user_id=child_owner,
            client_id=overridden_client,
        ) == expected_override
    finally:
        connection.rollback()
        connection.close()
