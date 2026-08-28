from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Barrier
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
class DeviceAdministrationCase:
    collector_user_id: UUID
    employee_user_id: UUID
    actor_user_id: UUID
    active_collector_device_ids: tuple[UUID, UUID]
    pending_collector_device_id: UUID
    employee_device_id: UUID
    actor_device_id: UUID

    @property
    def device_ids(self) -> tuple[UUID, ...]:
        return (
            *self.active_collector_device_ids,
            self.pending_collector_device_id,
            self.employee_device_id,
            self.actor_device_id,
        )

    @property
    def user_ids(self) -> tuple[UUID, ...]:
        return (self.collector_user_id, self.employee_user_id, self.actor_user_id)


def _insert_user(connection, *, role: str, label: str) -> UUID:
    user_id = uuid4()
    username = f"ca2-device-{label}-{uuid4().hex}"
    connection.execute(
        """
        insert into core.users (id, username, email, full_name, status)
        values (%s, %s, %s, %s, 'active')
        """,
        (user_id, username, f"{username}@example.com", f"CA2 {label.title()}"),
    )
    connection.execute(
        """
        insert into core.user_roles (user_id, role_id)
        select %s, id from core.roles where code = %s
        """,
        (user_id, role),
    )
    return user_id


def _insert_device(
    connection,
    *,
    user_id: UUID,
    platform: str,
    status: str,
    app_version: str,
) -> UUID:
    return connection.execute(
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
        (user_id, uuid4().hex, platform, app_version, status),
    ).fetchone()[0]


def _seed_case() -> DeviceAdministrationCase:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        collector_user_id = _insert_user(
            connection,
            role="collector",
            label="collector",
        )
        employee_user_id = _insert_user(
            connection,
            role="employee",
            label="employee",
        )
        actor_user_id = _insert_user(
            connection,
            role="management",
            label="manager",
        )
        active_android_id = _insert_device(
            connection,
            user_id=collector_user_id,
            platform="android",
            status="active",
            app_version="0.3.0+3",
        )
        active_ios_id = _insert_device(
            connection,
            user_id=collector_user_id,
            platform="ios",
            status="active",
            app_version="0.3.1+4",
        )
        pending_android_id = _insert_device(
            connection,
            user_id=collector_user_id,
            platform="android",
            status="pending",
            app_version="0.4.0+5",
        )
        employee_device_id = _insert_device(
            connection,
            user_id=employee_user_id,
            platform="android",
            status="active",
            app_version="employee-build",
        )
        actor_device_id = _insert_device(
            connection,
            user_id=actor_user_id,
            platform="web",
            status="active",
            app_version="management-build",
        )
    return DeviceAdministrationCase(
        collector_user_id=collector_user_id,
        employee_user_id=employee_user_id,
        actor_user_id=actor_user_id,
        active_collector_device_ids=(active_android_id, active_ios_id),
        pending_collector_device_id=pending_android_id,
        employee_device_id=employee_device_id,
        actor_device_id=actor_device_id,
    )


def _delete_case(case: DeviceAdministrationCase) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            """
            delete from core.audit_logs
            where actor_user_id = any(%s) or target_id = any(%s)
            """,
            (list(case.user_ids), list(case.device_ids)),
        )
        connection.execute(
            "delete from core.users where id = any(%s)",
            (list(case.user_ids),),
        )


@pytest.fixture
def device_case() -> DeviceAdministrationCase:
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


def test_approving_collector_mobile_replaces_active_devices_and_audits(
    device_case: DeviceAdministrationCase,
) -> None:
    selected = PostgresManagementRepository().set_device_status(
        actor_user_id=device_case.actor_user_id,
        device_id=device_case.pending_collector_device_id,
        device_status="active",
    )

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        active_collector_mobile_count = connection.execute(
            """
            select count(*) as device_count
            from core.devices
            where user_id = %s
              and platform in ('android', 'ios')
              and status = 'active'
            """,
            (device_case.collector_user_id,),
        ).fetchone()["device_count"]
        selected_status = connection.execute(
            "select status from core.devices where id = %s",
            (device_case.pending_collector_device_id,),
        ).fetchone()["status"]
        displaced_statuses = [
            row["status"]
            for row in connection.execute(
                """
                select status
                from core.devices
                where id = any(%s)
                order by id
                """,
                (list(device_case.active_collector_device_ids),),
            ).fetchall()
        ]
        employee_status = connection.execute(
            "select status from core.devices where id = %s",
            (device_case.employee_device_id,),
        ).fetchone()["status"]
        audits = connection.execute(
            """
            select actor_user_id, action, target_type, target_id, details
            from core.audit_logs
            where actor_user_id = %s and target_type = 'device'
            order by created_at, id
            """,
            (device_case.actor_user_id,),
        ).fetchall()

    assert selected.status == "active"
    assert active_collector_mobile_count == 1
    assert selected_status == "active"
    assert displaced_statuses == ["revoked", "revoked"]
    assert employee_status == "active"

    selected_audit = next(
        audit for audit in audits if audit["target_id"] == selected.id
    )
    assert selected_audit["actor_user_id"] == device_case.actor_user_id
    assert selected_audit["action"] == "device.status_change"
    assert selected_audit["details"] == {
        "user_id": str(device_case.collector_user_id),
        "platform": "android",
        "previous_status": "pending",
        "new_status": "active",
    }
    assert all("device_identifier_hash" not in audit["details"] for audit in audits)

    displaced_audits = [
        audit for audit in audits if audit["action"] == "device.replacement_auto_revoke"
    ]
    assert len(audits) == 3
    assert len(displaced_audits) == 2
    assert {audit["target_id"]: audit["details"] for audit in displaced_audits} == {
        device_case.active_collector_device_ids[0]: {
            "user_id": str(device_case.collector_user_id),
            "platform": "android",
            "previous_status": "active",
            "new_status": "revoked",
        },
        device_case.active_collector_device_ids[1]: {
            "user_id": str(device_case.collector_user_id),
            "platform": "ios",
            "previous_status": "active",
            "new_status": "revoked",
        },
    }


def test_non_collector_status_changes_audit_previous_and_new_status(
    device_case: DeviceAdministrationCase,
) -> None:
    repository = PostgresManagementRepository()

    repository.set_device_status(
        actor_user_id=device_case.actor_user_id,
        device_id=device_case.employee_device_id,
        device_status="revoked",
    )
    repository.set_device_status(
        actor_user_id=device_case.actor_user_id,
        device_id=device_case.employee_device_id,
        device_status="active",
    )

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        audits = connection.execute(
            """
            select action, details
            from core.audit_logs
            where actor_user_id = %s and target_id = %s
            order by created_at, id
            """,
            (device_case.actor_user_id, device_case.employee_device_id),
        ).fetchall()
    assert audits == [
        {
            "action": "device.status_change",
            "details": {
                "user_id": str(device_case.employee_user_id),
                "platform": "android",
                "previous_status": "active",
                "new_status": "revoked",
            },
        },
        {
            "action": "device.status_change",
            "details": {
                "user_id": str(device_case.employee_user_id),
                "platform": "android",
                "previous_status": "revoked",
                "new_status": "active",
            },
        },
    ]


def test_repeating_device_status_does_not_update_or_audit(
    device_case: DeviceAdministrationCase,
) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        original_xmin = connection.execute(
            "select xmin::text from core.devices where id = %s",
            (device_case.employee_device_id,),
        ).fetchone()[0]

    selected = PostgresManagementRepository().set_device_status(
        actor_user_id=device_case.actor_user_id,
        device_id=device_case.employee_device_id,
        device_status="active",
    )

    with psycopg.connect(DATABASE_URL) as connection:
        persisted = connection.execute(
            "select status, xmin::text from core.devices where id = %s",
            (device_case.employee_device_id,),
        ).fetchone()
        audit_count = connection.execute(
            """
            select count(*)
            from core.audit_logs
            where actor_user_id = %s and target_id = %s
            """,
            (device_case.actor_user_id, device_case.employee_device_id),
        ).fetchone()[0]

    assert selected.status == "active"
    assert persisted == ("active", original_xmin)
    assert audit_count == 0


class AuditFailureManagementRepository(PostgresManagementRepository):
    def _audit(self, connection, **kwargs) -> None:
        raise RuntimeError("forced audit failure")


def test_audit_failure_rolls_back_selected_and_displaced_statuses(
    device_case: DeviceAdministrationCase,
) -> None:
    with pytest.raises(RuntimeError, match="forced audit failure"):
        AuditFailureManagementRepository().set_device_status(
            actor_user_id=device_case.actor_user_id,
            device_id=device_case.pending_collector_device_id,
            device_status="active",
        )

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        selected_status = connection.execute(
            "select status from core.devices where id = %s",
            (device_case.pending_collector_device_id,),
        ).fetchone()["status"]
        displaced_statuses = [
            row["status"]
            for row in connection.execute(
                """
                select status
                from core.devices
                where id = any(%s)
                order by id
                """,
                (list(device_case.active_collector_device_ids),),
            ).fetchall()
        ]
    assert selected_status == "pending"
    assert displaced_statuses == ["active", "active"]


def test_concurrent_collector_mobile_approvals_leave_at_most_one_active(
    device_case: DeviceAdministrationCase,
) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        second_pending_device_id = _insert_device(
            connection,
            user_id=device_case.collector_user_id,
            platform="ios",
            status="pending",
            app_version="0.4.1+6",
        )
    start = Barrier(2)

    def approve(device_id: UUID):
        start.wait()
        return PostgresManagementRepository().set_device_status(
            actor_user_id=device_case.actor_user_id,
            device_id=device_id,
            device_status="active",
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = (
                executor.submit(approve, device_case.pending_collector_device_id),
                executor.submit(approve, second_pending_device_id),
            )
            results = tuple(future.result() for future in futures)

        assert [result.status for result in results] == ["active", "active"]
        with psycopg.connect(DATABASE_URL) as connection:
            active_mobile_count = connection.execute(
                """
                select count(*)
                from core.devices
                where user_id = %s
                  and platform in ('android', 'ios')
                  and status = 'active'
                """,
                (device_case.collector_user_id,),
            ).fetchone()[0]
        assert active_mobile_count <= 1
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "delete from core.audit_logs where target_id = %s",
                (second_pending_device_id,),
            )
            connection.execute(
                "delete from core.devices where id = %s",
                (second_pending_device_id,),
            )


def test_management_actor_cannot_revoke_own_device(
    device_case: DeviceAdministrationCase,
) -> None:
    with pytest.raises(
        AccountConflict,
        match="You cannot revoke your own current account's device.",
    ):
        PostgresManagementRepository().set_device_status(
            actor_user_id=device_case.actor_user_id,
            device_id=device_case.actor_device_id,
            device_status="revoked",
        )

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        status = connection.execute(
            "select status from core.devices where id = %s",
            (device_case.actor_device_id,),
        ).fetchone()[0]
        audit_count = connection.execute(
            "select count(*) from core.audit_logs where target_id = %s",
            (device_case.actor_device_id,),
        ).fetchone()[0]
    assert status == "active"
    assert audit_count == 0
