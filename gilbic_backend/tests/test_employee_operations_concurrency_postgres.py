"""Concurrent employee writes on an isolated, freshly migrated loopback database."""

from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

import test_employee_operations_postgres as employee_proofs
from gilbic_backend.employee_operations import EmployeeConflict
from gilbic_backend.employee_operations_models import ACTION_ADAPTER
from gilbic_backend.employee_operations_repository import (
    PostgresEmployeeOperationsRepository,
)
from tools import run_stage5d17_disposable_postgres_validation as disposable


BASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not BASE_URL, reason="Guarded disposable PostgreSQL is not configured"
)


@pytest.fixture(scope="module")
def isolated_database_url():
    """Committed race fixtures never touch the caller's rollback-only database."""
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError("Concurrency proofs require explicit disposable permission")
    params = disposable._safe_local_connection_params(BASE_URL)
    if not re.fullmatch(r"spina_onboarding_[0-9a-f]{12}", params["dbname"]):
        raise RuntimeError("Concurrency proofs require a generated onboarding database")
    name = "spina_onboarding_" + uuid4().hex[:12]
    assert name != params["dbname"]
    admin_url = disposable._conninfo_for_database(params, "postgres")
    test_url = disposable._conninfo_for_database(params, name)
    created = False
    with pytest.MonkeyPatch.context() as environment:
        for key in disposable.ENDPOINT_ENV_KEYS:
            environment.delenv(key, raising=False)
        try:
            with psycopg.connect(admin_url, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                        sql.Identifier(name)
                    )
                )
            created = True
            disposable._install_supabase_auth_prerequisite(test_url)
            with pytest.MonkeyPatch.context() as bootstrap:
                bootstrap.setattr(disposable, "BOOTSTRAP_THROUGH", 128)
                disposable._bootstrap_database(test_url)
            yield test_url
        finally:
            if created:
                # Only this exact generated database is eligible for cleanup.
                if not re.fullmatch(r"spina_onboarding_[0-9a-f]{12}", name):
                    raise RuntimeError("Unsafe generated cleanup target")
                with psycopg.connect(admin_url, autocommit=True) as admin:
                    disposable._drop_database(admin, name)


@pytest.fixture
def committed_case(isolated_database_url, monkeypatch):
    monkeypatch.setattr(employee_proofs, "URL", isolated_database_url)
    fixture = employee_proofs.database.__wrapped__(monkeypatch)
    case = next(fixture)
    try:
        case.connection.commit()
        yield case
    finally:
        fixture.close()


def _payment_command(case, payroll):
    employee_id = case.users["one"].user_id
    approved = case.call(
        "owner",
        "payroll_approve",
        id=payroll["id"],
        employee_id=employee_id,
        expected_version=payroll["version"],
        decision="approved",
        reason="Synthetic concurrency approval",
    )
    amount = case.record("payroll", payroll["id"])["payload"]["net_pay"]
    case.connection.commit()
    return ACTION_ADAPTER.validate_python(
        {
            "action": "payroll_payment",
            "request_id": str(uuid4()),
            "id": payroll["id"],
            "expected_version": approved["version"],
            "employee_id": str(employee_id),
            "amount": amount,
            "occurred_at": "2026-09-19T18:00:00+08:00",
            "payment_method": "cash",
            "employee_acknowledgment": "Synthetic employee acknowledgment",
            "result": "completed",
        }
    )


def _concurrent_commands(case, database_url, commands):
    """Queue both actual sessions behind a gate, then release them together.

    The first request is queued first so the profile/attendance lock-order proof
    deterministically exercises an owner update followed by the target's write.
    """
    names = ["employee-race-" + uuid4().hex for _ in commands]

    def execute(name, actor_name, command):
        try:
            with psycopg.connect(
                database_url, row_factory=dict_row, application_name=name
            ) as connection:
                connection.execute("set statement_timeout='12s'")
                connection.execute("set lock_timeout='10s'")
                with connection.cursor() as cursor:
                    result = (
                        PostgresEmployeeOperationsRepository.execute_in_transaction(
                            cursor, actor=case.users[actor_name], command=command
                        )
                    )
            return "success", result
        except EmployeeConflict as error:
            return "conflict", str(error)

    def wait_until_blocked(expected):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            # Each observation must refresh PostgreSQL's transaction-local view.
            case.connection.execute("select pg_stat_clear_snapshot()")
            count = case.connection.execute(
                """select count(*) as count from pg_stat_activity
                where datname=current_database() and application_name=any(%s)
                and wait_event_type='Lock' and wait_event='advisory'""",
                (names,),
            ).fetchone()["count"]
            if count == expected:
                return
            time.sleep(0.02)
        raise AssertionError(f"Expected {expected} concurrent advisory-lock waiters")

    case.connection.commit()
    futures = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        with case.connection.transaction():
            case.connection.execute(
                "select pg_advisory_xact_lock(hashtext('spina.employee_operations'))"
            )
            for position, (actor_name, command) in enumerate(commands):
                futures.append(
                    pool.submit(execute, names[position], actor_name, command)
                )
                wait_until_blocked(position + 1)
        return [future.result(timeout=15) for future in futures]


def _assert_single_payment(case, payroll, amount, request_ids):
    row = case.record("payroll", payroll["id"])
    assert row["status"] == "paid"
    assert row["version"] == 3
    assert row["payload"]["paid_amount"] == amount
    assert row["payload"]["balance_due"] == "0.00"
    payments = case.connection.execute(
        """select count(*) as count from core.employee_payments
        where payload->>'payroll_id'=%s and status='completed'""",
        (str(payroll["id"]),),
    ).fetchone()["count"]
    receipts = case.connection.execute(
        """select count(*) as count from core.employee_action_receipts
        where request_id=any(%s::uuid[])""",
        (request_ids,),
    ).fetchone()["count"]
    assert payments == receipts == 1


def test_simultaneous_same_key_completed_payout_replays_once(
    committed_case, isolated_database_url
):
    case = committed_case
    case.week()
    payroll = case.payroll()
    command = _payment_command(case, payroll)
    outcomes = _concurrent_commands(
        case, isolated_database_url, [("owner", command), ("owner", command)]
    )
    assert [kind for kind, _ in outcomes] == ["success", "success"]
    assert sorted(result["replayed"] for _, result in outcomes) == [False, True]
    assert outcomes[0][1]["request_id"] == outcomes[1][1]["request_id"]
    _assert_single_payment(
        case, payroll, str(command.amount), [str(command.request_id)]
    )


def test_simultaneous_different_keys_cannot_pay_the_same_version_twice(
    committed_case, isolated_database_url
):
    case = committed_case
    case.week()
    payroll = case.payroll()
    first = _payment_command(case, payroll)
    second = first.model_copy(update={"request_id": uuid4()})
    outcomes = _concurrent_commands(
        case, isolated_database_url, [("owner", first), ("owner", second)]
    )
    assert sorted(kind for kind, _ in outcomes) == ["conflict", "success"]
    assert (
        "record changed"
        in next(result for kind, result in outcomes if kind == "conflict").lower()
    )
    _assert_single_payment(
        case,
        payroll,
        str(first.amount),
        [str(first.request_id), str(second.request_id)],
    )


def test_owner_profile_update_and_target_attendance_do_not_deadlock(
    committed_case, isolated_database_url
):
    case = committed_case
    employee = case.users["one"]
    profile = case.record("profiles", employee.user_id)
    profile_fields = dict(profile["payload"])
    profile_fields.pop("full_name")
    profile_fields["daily_rate"] = "850.00"
    update = ACTION_ADAPTER.validate_python(
        dict(
            profile_fields,
            action="profile_save",
            request_id=str(uuid4()),
            id=str(employee.user_id),
            employee_id=str(employee.user_id),
            expected_version=profile["version"],
        )
    )
    attendance = ACTION_ADAPTER.validate_python(
        {
            "action": "attendance_record",
            "request_id": str(uuid4()),
            "id": str(uuid4()),
            "employee_id": str(employee.user_id),
            "expected_version": 0,
            "event_type": "clock_in",
            "captured_at": "2026-09-19T06:00:00+08:00",
            "device_id": str(employee.registered_device_id),
            "previous_event_id": None,
            "sequence": 1,
            "offline": False,
        }
    )
    outcomes = _concurrent_commands(
        case, isolated_database_url, [("owner", update), ("one", attendance)]
    )
    assert [kind for kind, _ in outcomes] == ["success", "success"]
    assert (
        case.record("profiles", employee.user_id)["payload"]["daily_rate"] == "850.00"
    )
    assert case.record("attendance", attendance.id)["status"] == "accepted"
