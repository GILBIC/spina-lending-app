"""Exercise login SQL with an in-memory store; PostgreSQL tests cover locking."""

import sqlite3
from contextlib import contextmanager
from uuid import UUID

import pytest
from gilbic_backend.account_repository import (
    AccountContext,
    DeviceApprovalRequired,
    DeviceRevoked,
    PostgresAccountRepository,
)

from gilbic_backend import account_repository as module

USER_ID = UUID(int=1)
AUTH_ID = UUID(int=2)
DEVICE_ID = "existing-device"
INSTALLATION = "collector-installation"


@pytest.fixture
def device_store(monkeypatch):
    database = sqlite3.connect(":memory:")
    database.executescript("""
        attach database ':memory:' as core;
        create table core.users (id text, external_auth_id text, status text);
        create table core.roles (id integer, code text);
        create table core.user_roles (user_id text, role_id integer);
        create table core.client_registration_requests (user_id text, status text);
        create table core.devices (
            id text default 'new-device', user_id text, device_identifier_hash text,
            platform text, app_version text, status text, last_seen_at text
        );
    """)
    database.execute(
        "insert into core.users values (?, ?, 'active')", (str(USER_ID), str(AUTH_ID))
    )
    database.execute("insert into core.roles values (1, 'collector')")
    database.execute("insert into core.user_roles values (?, 1)", (str(USER_ID),))
    database.commit()

    class Cursor:
        @contextmanager
        def cursor(self, **kwargs):
            yield self

        def execute(self, sql, params=()):
            # SQLite executes the repository's reads/writes, without PG row locks.
            sql = sql.replace("for update", "").replace("now()", "current_timestamp")
            self.result = database.execute(
                sql.replace("%s", "?"),
                tuple(
                    str(value) if isinstance(value, UUID) else value for value in params
                ),
            )

        def fetchone(self):
            return self.result.fetchone()

        def transaction(self):
            return database

    @contextmanager
    def connect():
        yield Cursor()

    monkeypatch.setattr(module, "open_connection", connect)
    monkeypatch.setattr(
        PostgresAccountRepository,
        "_load_context",
        staticmethod(
            lambda *args: AccountContext(
                USER_ID,
                AUTH_ID,
                "collector",
                None,
                "Collector",
                "active",
                ("collector",),
                ("collection.create",),
            )
        ),
    )
    yield database
    database.close()


def seed_device(database, platform, status):
    database.execute(
        "insert into core.devices (id, user_id, device_identifier_hash, platform, status) values (?, ?, ?, ?, ?)",
        (
            DEVICE_ID,
            str(USER_ID),
            PostgresAccountRepository.device_hash(INSTALLATION),
            platform,
            status,
        ),
    )
    database.commit()


def login(platform):
    return PostgresAccountRepository().activate_and_register_device(
        auth_user_id=AUTH_ID,
        device_identifier=INSTALLATION,
        platform=platform,
        app_version="test-build",
    )


@pytest.mark.parametrize("claimed_platform", ["web", "desktop"])
def test_pending_native_identity_cannot_escape_approval_by_relabeling(
    device_store, claimed_platform
):
    seed_device(device_store, "android", "pending")
    for platform in (claimed_platform, "android"):
        with pytest.raises(DeviceApprovalRequired):
            login(platform)
        assert device_store.execute(
            "select platform, status from core.devices"
        ).fetchone() == ("android", "pending")
        with pytest.raises(DeviceApprovalRequired):
            PostgresAccountRepository().get_context_for_device(
                auth_user_id=AUTH_ID,
                device_identifier=INSTALLATION,
            )


@pytest.mark.parametrize("previous_platform", ["web", "desktop"])
@pytest.mark.parametrize("native_platform", ["android", "ios"])
def test_active_non_native_identity_requires_approval_before_native_use(
    device_store, previous_platform, native_platform
):
    seed_device(device_store, previous_platform, "active")
    with pytest.raises(DeviceApprovalRequired):
        login(native_platform)
    assert device_store.execute(
        "select platform, status from core.devices"
    ).fetchone() == (native_platform, "pending")
    with pytest.raises(DeviceApprovalRequired):
        login(previous_platform)
    assert device_store.execute(
        "select platform, status from core.devices"
    ).fetchone() == (native_platform, "pending")


def test_approved_native_identity_keeps_native_provenance_when_claiming_web(
    device_store,
):
    seed_device(device_store, "ios", "active")
    assert login("web").device_registered is True
    assert device_store.execute(
        "select platform, status from core.devices"
    ).fetchone() == ("ios", "active")


@pytest.mark.parametrize("platform", ["web", "desktop"])
def test_fresh_non_native_collector_login_remains_exempt(device_store, platform):
    assert login(platform).device_registered is True
    assert device_store.execute(
        "select platform, status from core.devices"
    ).fetchone() == (platform, "active")


@pytest.mark.parametrize("platform", ["web", "desktop", "android", "ios"])
def test_revoked_identity_cannot_be_reactivated_by_a_platform_claim(
    device_store, platform
):
    seed_device(device_store, "android", "revoked")
    with pytest.raises(DeviceRevoked):
        login(platform)
    assert device_store.execute(
        "select platform, status from core.devices"
    ).fetchone() == ("android", "revoked")
