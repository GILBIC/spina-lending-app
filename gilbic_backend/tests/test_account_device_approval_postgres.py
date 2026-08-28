from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import gilbic_backend.account_repository as account_repository_module
import psycopg
import pytest
from gilbic_backend.account_repository import (
    DeviceApprovalRequired,
    DeviceRevoked,
    PostgresAccountRepository,
)
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


def _seed_user(
    *,
    role: str = "collector",
    device_identifier: str | None = None,
    device_platform: str = "android",
    device_status: str = "active",
    app_version: str | None = "0.3.0+3",
) -> tuple[UUID, UUID, UUID | None]:
    assert DATABASE_URL is not None
    user_id = uuid4()
    auth_user_id = uuid4()
    username = f"ca2-device-{uuid4().hex}"
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            """
            insert into core.users (
                id, username, email, full_name, external_auth_id, status
            ) values (%s, %s, %s, %s, %s, 'active')
            """,
            (
                user_id,
                username,
                f"{username}@example.com",
                "CA2 Device Test User",
                auth_user_id,
            ),
        )
        connection.execute(
            """
            insert into core.user_roles (user_id, role_id)
            select %s, id from core.roles where code = %s
            """,
            (user_id, role),
        )
        device_id = None
        if device_identifier is not None:
            device_id = connection.execute(
                """
                insert into core.devices (
                    user_id,
                    device_identifier_hash,
                    platform,
                    app_version,
                    status,
                    last_seen_at
                ) values (%s, %s, %s, %s, %s, now())
                returning id
                """,
                (
                    user_id,
                    PostgresAccountRepository.device_hash(device_identifier),
                    device_platform,
                    app_version,
                    device_status,
                ),
            ).fetchone()[0]
    return user_id, auth_user_id, device_id


def _delete_user(user_id: UUID) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("delete from core.users where id = %s", (user_id,))


def _device_rows(user_id: UUID) -> list[dict[str, object]]:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        return connection.execute(
            """
            select platform, status, device_identifier_hash
            from core.devices
            where user_id = %s
            order by id
            """,
            (user_id,),
        ).fetchall()


def test_first_collector_android_login_persists_pending_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, auth_user_id, _ = _seed_user()
    monkeypatch.setattr(account_repository_module, "open_connection", _test_connection)
    try:
        with pytest.raises(
            DeviceApprovalRequired,
            match="This Collector device is awaiting Management approval.",
        ):
            PostgresAccountRepository().activate_and_register_device(
                auth_user_id=auth_user_id,
                device_identifier="collector-phone-b",
                platform="android",
                app_version="0.3.0+3",
            )

        pending_rows = _device_rows(user_id)
        assert pending_rows == [
            {
                "platform": "android",
                "status": "pending",
                "device_identifier_hash": PostgresAccountRepository.device_hash(
                    "collector-phone-b"
                ),
            }
        ]
    finally:
        _delete_user(user_id)


def test_repeated_collector_mobile_login_keeps_one_pending_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, auth_user_id, _ = _seed_user()
    monkeypatch.setattr(account_repository_module, "open_connection", _test_connection)
    repository = PostgresAccountRepository()
    try:
        for app_version in ("0.3.0+3", "0.3.1+4"):
            with pytest.raises(DeviceApprovalRequired):
                repository.activate_and_register_device(
                    auth_user_id=auth_user_id,
                    device_identifier="collector-phone-b",
                    platform="android",
                    app_version=app_version,
                )

        assert _device_rows(user_id) == [
            {
                "platform": "android",
                "status": "pending",
                "device_identifier_hash": PostgresAccountRepository.device_hash(
                    "collector-phone-b"
                ),
            }
        ]
        assert DATABASE_URL is not None
        with psycopg.connect(DATABASE_URL) as connection:
            app_version = connection.execute(
                "select app_version from core.devices where user_id = %s",
                (user_id,),
            ).fetchone()[0]
        assert app_version == "0.3.1+4"
    finally:
        _delete_user(user_id)


def test_existing_pending_collector_mobile_login_updates_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, auth_user_id, device_id = _seed_user(
        device_identifier="collector-phone-b",
        device_platform="android",
        device_status="pending",
        app_version="0.2.0+2",
    )
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        registered_at = connection.execute(
            "select registered_at from core.devices where id = %s",
            (device_id,),
        ).fetchone()[0]
    monkeypatch.setattr(account_repository_module, "open_connection", _test_connection)
    repository = PostgresAccountRepository()
    try:
        with pytest.raises(DeviceApprovalRequired):
            repository.get_context_for_device(
                auth_user_id=auth_user_id,
                device_identifier="collector-phone-b",
            )

        with pytest.raises(DeviceApprovalRequired):
            repository.activate_and_register_device(
                auth_user_id=auth_user_id,
                device_identifier="collector-phone-b",
                platform="ios",
                app_version="0.3.1+4",
            )

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            device = connection.execute(
                """
                select id, platform, app_version, status, registered_at,
                       last_seen_at is not null as was_seen
                from core.devices
                where user_id = %s
                """,
                (user_id,),
            ).fetchone()
        assert device == {
            "id": device_id,
            "platform": "ios",
            "app_version": "0.3.1+4",
            "status": "pending",
            "registered_at": registered_at,
            "was_seen": True,
        }
    finally:
        _delete_user(user_id)


def test_approved_collector_mobile_login_remains_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, auth_user_id, device_id = _seed_user(
        device_identifier="collector-phone-b",
        device_status="active",
    )
    monkeypatch.setattr(account_repository_module, "open_connection", _test_connection)
    try:
        context = PostgresAccountRepository().activate_and_register_device(
            auth_user_id=auth_user_id,
            device_identifier="collector-phone-b",
            platform="android",
            app_version="0.3.1+4",
        )

        assert context.device_registered is True
        assert context.registered_device_id == device_id
        assert _device_rows(user_id)[0]["status"] == "active"
    finally:
        _delete_user(user_id)


def test_revoked_collector_mobile_login_retains_revoked_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, auth_user_id, _ = _seed_user(
        device_identifier="collector-phone-b",
        device_status="revoked",
        app_version="0.2.0+2",
    )
    monkeypatch.setattr(account_repository_module, "open_connection", _test_connection)
    try:
        with pytest.raises(DeviceRevoked, match="This device has been revoked."):
            PostgresAccountRepository().activate_and_register_device(
                auth_user_id=auth_user_id,
                device_identifier="collector-phone-b",
                platform="android",
                app_version="0.3.1+4",
            )

        assert DATABASE_URL is not None
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            device = connection.execute(
                """
                select status, app_version
                from core.devices
                where user_id = %s
                """,
                (user_id,),
            ).fetchone()
        assert device == {"status": "revoked", "app_version": "0.2.0+2"}
    finally:
        _delete_user(user_id)
