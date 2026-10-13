"""Real concurrent transactions and populated 0157 database/evidence recovery."""

import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import psycopg
import pytest
import run_release_recovery_drill as recovery
from collector_accounting_test_support import (
    command,
    post,
    prepare,
    reserved,
    source_case,
)
from gilbic_backend.collector_settlement import source_snapshot
from gilbic_backend.collector_surplus import load
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from gilbic_backend.treasury_models import COMMAND_ADAPTER
from gilbic_backend.treasury_repository import TreasuryService
from psycopg.rows import dict_row
from test_collector_credit_application_postgres import (
    _accept,
    _approve,
    _count,
    _credit,
)
from test_collector_credit_application_postgres import (
    credit_application as _credit_application,
)
from test_current_schema_accounting_cycle_postgres import (
    fresh_current_database as _fresh_current_database,
)

fresh_current_database = _fresh_current_database
credit_application = _credit_application


@pytest.fixture
def collector_accounting(fresh_current_database, tmp_path, monkeypatch, request):
    with psycopg.connect(
        fresh_current_database["source"], row_factory=dict_row
    ) as conn:
        try:
            yield source_case(
                conn,
                tmp_path,
                monkeypatch,
                historical_days=getattr(request, "param", 0),
            )
        finally:
            conn.rollback()


def _service(f, conn):
    @contextmanager
    def borrowed():
        yield conn

    service = TreasuryService(store=f["store"])
    service.connect = borrowed
    return service


@pytest.mark.parametrize("collector_accounting", [1], indirect=True)
def test_actual_count_date_and_later_acceptance_have_distinct_journal_dates(
    credit_application,
):
    # Only synthetic collection/count observations are historical. The database
    # clock, approval, credit consumption and acceptance remain at their real time.
    f = credit_application
    action = _approve(f)
    result = _accept(f, action, _count(f, action, "96.00", counted_at=f["now"]))
    cash = prepare(f, "settlement", UUID(result["settlement"]["id"]))
    application = prepare(
        f, "credit_application", UUID(result["application_entry"]["id"])
    )
    assert cash["snapshot"]["posting_date"] == f["day"].isoformat()
    accepted_day = (
        f["conn"]
        .execute(
            "SELECT (accepted_at AT TIME ZONE 'Asia/Manila')::date AS day FROM treasury.collector_credit_applications"
        )
        .fetchone()["day"]
    )
    assert accepted_day > f["day"]
    assert application["snapshot"]["posting_date"] == accepted_day.isoformat()
    assert datetime.fromisoformat(
        result["settlement"]["accepted_at"]
    ) > datetime.fromisoformat(result["count"]["counted_at"])
    post(f, cash)
    post(f, application)


def _accept_command(f, action, count):
    account = (
        f["conn"]
        .execute("SELECT version FROM treasury.accounts WHERE id=%s", (f["wallet"],))
        .fetchone()
    )
    return COMMAND_ADAPTER.validate_python(
        {
            "action": "collector_count_accept",
            "request_id": uuid4(),
            "account_id": f["wallet"],
            "expected_version": account["version"],
            "count_id": count["id"],
            "count_version": count["version"],
            "source_digest": count["source_digest"],
            "physical_receipt_acknowledged": True,
            "credit_application_id": action["id"],
            "credit_application_version": action["version"],
        }
    )


@pytest.mark.parametrize("winner", ["accept", "cancel", "permission"])
def test_waiting_acceptance_rechecks_committed_winner(
    credit_application, fresh_current_database, monkeypatch, winner
):
    f = credit_application
    monkeypatch.setenv("SPINA_TREASURY_ENABLED", "true")
    action = _approve(f)
    count = _count(f, action, "96.00")
    model = _accept_command(f, action, count)
    f["conn"].commit()
    url = fresh_current_database["source"]
    ready, pid = Event(), []

    def waiting_accept():
        with psycopg.connect(url, row_factory=dict_row) as conn:
            conn.execute("SET statement_timeout='15s'")
            pid.append(conn.info.backend_pid)
            ready.set()
            return _service(f, conn).execute(f["actor"], model)

    with (
        psycopg.connect(url, row_factory=dict_row) as first,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        first.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,1))", (str(f["wallet"]),)
        )
        future = pool.submit(waiting_accept)
        assert ready.wait(5)
        deadline = time.monotonic() + 5
        blocked = False
        while time.monotonic() < deadline:
            blocked = observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            time.sleep(0.01)
        assert blocked, "Acceptance must wait on the actual wallet lock"
        if winner == "accept":
            # A different request cannot consume the same reviewed approval twice.
            competing = model.model_copy(update={"request_id": uuid4()})
            _service(f, first).execute(f["actor"], competing)
        elif winner == "cancel":
            command(
                f | {"conn": first},
                "collector_surplus_action_cancel",
                action_id=action["id"],
                action_version=action["version"],
                evidence_id=f["evidence"],
                reason="Cancel the exact unconsumed reservation",
            )
        else:
            first.execute(
                "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
                (f["wallet"],),
            )
        first.commit()
        with pytest.raises((TreasuryConflict, TreasuryDenied)):
            future.result(timeout=15)
    applications = (
        f["conn"]
        .execute("SELECT count(*) AS n FROM treasury.collector_credit_applications")
        .fetchone()["n"]
    )
    assert applications == (1 if winner == "accept" else 0)
    assert _credit(f)["applied_amount"] == ("4.00" if winner == "accept" else "0.00")


def test_populated_credit_consumption_and_private_files_restore_exactly(
    credit_application, fresh_current_database, tmp_path
):
    f, case = credit_application, fresh_current_database
    action = _approve(f)
    result = _accept(f, action, _count(f, action, "98.00"))
    for kind, source in (
        ("settlement", result["settlement"]["id"]),
        ("credit_application", result["application_entry"]["id"]),
    ):
        post(f, prepare(f, kind, UUID(source)))
    f["conn"].commit()
    with psycopg.connect(case["source"]) as conn:
        expected = recovery.database_snapshot(conn)
    assert expected["treasury.collector_credit_applications"]["rows"] == 1
    files = recovery.file_manifest(f["store"].root)
    assert files
    suffix = ".exe" if os.name == "nt" else ""
    binary = Path(os.environ["SPINA_POSTGRES_BIN"]) / ("pg_dump" + suffix)
    restore = binary.with_name("pg_restore" + suffix)
    source_env = recovery.pg_environment(case["params"], case["names"][0])
    restore_env = recovery.pg_environment(case["params"], case["names"][1])
    schema = recovery.schema_snapshot(binary, source_env, case["source"])
    archive = tmp_path / "collector-applications.dump"
    recovery.run_pg(binary, ["--format=custom", "--file", str(archive)], source_env)
    restored_private = tmp_path / "restored-private"
    shutil.copytree(f["store"].root, restored_private)
    recovery.run_pg(
        restore,
        ["--exit-on-error", "--no-owner", "--dbname", case["names"][1], str(archive)],
        restore_env,
    )
    with psycopg.connect(case["restore"]) as conn:
        recovery.verify_database(conn, expected)
        conn.row_factory = dict_row
        assert conn.execute(
            "SELECT bool_and(exact_posted AND NOT correction_pending) AS valid FROM accounting.collector_liability_posting_status"
        ).fetchone()["valid"]
        assert (
            load(conn, "credits", UUID(f["credit"]["id"]))["applied_amount"] == "4.00"
        )
    recovery.verify_files(restored_private, files)
    assert recovery.schema_snapshot(binary, restore_env, case["restore"]) == schema


def test_waiting_application_reservation_cannot_spend_credit_reserved_for_return(
    credit_application, fresh_current_database, monkeypatch
):
    f = credit_application
    monkeypatch.setenv("SPINA_TREASURY_ENABLED", "true")
    digest = source_snapshot(f["conn"], f["later"])[2]
    request = command(
        f,
        "collector_surplus_application_request",
        who=f["collector"],
        credit_id=f["credit"]["id"],
        credit_version=f["credit"]["version"],
        remittance_id=f["later"],
        source_digest=digest,
        amount="6.00",
        reason="Apply my exact retained credit",
    )["request"]
    version = (
        f["conn"]
        .execute("SELECT version FROM treasury.accounts WHERE id=%s", (f["wallet"],))
        .fetchone()["version"]
    )
    model = COMMAND_ADAPTER.validate_python(
        {
            "action": "collector_surplus_application_prepare",
            "request_id": uuid4(),
            "account_id": f["wallet"],
            "expected_version": version,
            "credit_id": f["credit"]["id"],
            "credit_version": f["credit"]["version"],
            "collector_request_id": request["id"],
            "collector_request_version": request["version"],
            "remittance_id": f["later"],
            "source_digest": digest,
            "amount": "6.00",
            "evidence_id": f["evidence"],
            "reason": "Approve the requested exact credit application",
        }
    )
    f["conn"].commit()
    url, ready, pid = fresh_current_database["source"], Event(), []

    def waiting_reserve():
        with psycopg.connect(url, row_factory=dict_row) as conn:
            conn.execute("SET statement_timeout='15s'")
            pid.append(conn.info.backend_pid)
            ready.set()
            return _service(f, conn).execute(f["actor"], model)

    with (
        psycopg.connect(url, row_factory=dict_row) as first,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        first.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,1))", (str(f["wallet"]),)
        )
        future = pool.submit(waiting_reserve)
        assert ready.wait(5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (pid[0],)
            ).fetchone()[0]:
                break
            time.sleep(0.01)
        else:
            pytest.fail("Approval must wait for the current wallet transaction")
        reserved(f | {"conn": first}, f["credit"], "6.00")
        first.commit()
        with pytest.raises(TreasuryConflict):
            future.result(timeout=15)
    assert _credit(f)["reserved_amount"] == "6.00"
    assert _credit(f)["available_amount"] == "4.00"
    assert (
        not f["conn"]
        .execute(
            "SELECT 1 FROM treasury.collector_actions WHERE payload->>'kind'='application'"
        )
        .fetchone()
    )
