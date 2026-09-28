from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import gilbic_backend.account_repository as account_repository_module
import gilbic_backend.management_repository as management_repository_module
import psycopg
import pytest
from gilbic_backend.account_repository import (
    DeviceApprovalRequired,
    DeviceRevoked,
    PostgresAccountRepository,
)
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
        connection.execute("insert into auth.users (id) values (%s)", (auth_user_id,))
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
        deleted = connection.execute(
            "delete from core.users where id = %s returning external_auth_id",
            (user_id,),
        ).fetchone()
        if deleted and deleted[0]:
            connection.execute("delete from auth.users where id = %s", (deleted[0],))


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


@pytest.mark.parametrize("claimed_platform", ["web", "desktop"])
def test_pending_native_platform_relabel_remains_denied_in_postgres(
    monkeypatch: pytest.MonkeyPatch,
    claimed_platform: str,
) -> None:
    user_id, auth_user_id, _ = _seed_user(
        device_identifier="pending-phone",
        device_status="pending",
    )
    monkeypatch.setattr(account_repository_module, "open_connection", _test_connection)
    repository = PostgresAccountRepository()
    try:
        for platform in (claimed_platform, "android"):
            with pytest.raises(DeviceApprovalRequired):
                repository.activate_and_register_device(
                    auth_user_id=auth_user_id,
                    device_identifier="pending-phone",
                    platform=platform,
                    app_version="test-build",
                )
            with pytest.raises(DeviceApprovalRequired):
                repository.get_context_for_device(
                    auth_user_id=auth_user_id,
                    device_identifier="pending-phone",
                )
        assert _device_rows(user_id)[0]["platform"] == "android"
        assert _device_rows(user_id)[0]["status"] == "pending"
    finally:
        _delete_user(user_id)


def test_web_to_native_transition_requires_management_replacement_approval_and_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, auth_user_id, old_device_id = _seed_user(device_identifier="old-phone")
    manager_id, _, _ = _seed_user(role="management")
    monkeypatch.setattr(account_repository_module, "open_connection", _test_connection)
    monkeypatch.setattr(
        management_repository_module, "open_connection", _test_connection
    )
    repository = PostgresAccountRepository()
    try:
        # A previously approved phone cannot hide from replacement revocation.
        repository.activate_and_register_device(
            auth_user_id=auth_user_id,
            device_identifier="old-phone",
            platform="web",
            app_version="test-build",
        )
        replacement = repository.activate_and_register_device(
            auth_user_id=auth_user_id,
            device_identifier="replacement",
            platform="web",
            app_version="test-build",
        )
        new_device_id = replacement.registered_device_id
        for platform in ("android", "web"):
            with pytest.raises(DeviceApprovalRequired):
                repository.activate_and_register_device(
                    auth_user_id=auth_user_id,
                    device_identifier="replacement",
                    platform=platform,
                    app_version="test-build",
                )
        with pytest.raises(DeviceApprovalRequired):
            repository.get_context_for_device(
                auth_user_id=auth_user_id,
                device_identifier="replacement",
            )

        approved = PostgresManagementRepository().set_device_status(
            actor_user_id=manager_id,
            device_id=new_device_id,
            device_status="active",
        )
        assert approved.status == "active"
        assert approved.platform == "android"
        assert (
            repository.get_context_for_device(
                auth_user_id=auth_user_id,
                device_identifier="replacement",
            ).registered_device_id
            == new_device_id
        )
        with pytest.raises(DeviceRevoked):
            repository.get_context_for_device(
                auth_user_id=auth_user_id,
                device_identifier="old-phone",
            )

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            devices = connection.execute(
                "select id, platform, status from core.devices where user_id = %s",
                (user_id,),
            ).fetchall()
            audits = connection.execute(
                "select action, target_id, details from core.audit_logs where actor_user_id = %s",
                (manager_id,),
            ).fetchall()
        assert {
            device["id"]: (device["platform"], device["status"]) for device in devices
        } == {
            old_device_id: ("android", "revoked"),
            new_device_id: ("android", "active"),
        }
        assert {audit["action"]: audit["target_id"] for audit in audits} == {
            "device.status_change": new_device_id,
            "device.replacement_auto_revoke": old_device_id,
        }
        approval = next(
            audit for audit in audits if audit["action"] == "device.status_change"
        )
        assert approval["details"]["previous_status"] == "pending"
        assert approval["details"]["new_status"] == "active"
        assert approval["details"]["platform"] == "android"
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "delete from core.audit_logs where actor_user_id = %s", (manager_id,)
            )
        _delete_user(user_id)
        _delete_user(manager_id)
