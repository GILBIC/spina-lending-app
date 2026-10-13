"""Liability claims serialize competing settlements and reports use one snapshot."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from test_accounting_book_postgres import configure
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_liability_control_postgres import line, movement, register
from test_period_close_postgres import _body, _management_actor

from gilbic_backend import liability_control_repository as repository

isolated_statement_database = _isolated_statement_database


def seed(url):
    with psycopg.connect(url) as conn:
        for name in (
            "0144_add_accounting_book_identity.sql",
            "0147_add_liability_control_schedule.sql",
        ):
            conn.execute(
                _body(
                    (Path(__file__).resolve().parents[1] / "sql" / name).read_text(
                        encoding="utf-8"
                    )
                )
            )
        actor = _management_actor(conn, uuid4().hex)
        book = configure(conn, actor, "owner_operations")
        day = conn.execute(
            "SELECT greatest(current_date,coalesce(max(end_date)+1,current_date)) FROM accounting.fiscal_periods"
        ).fetchone()[0]
        conn.execute(
            "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
            (uuid4().hex, day, day + timedelta(days=12), actor),
        )
        f = {"conn": conn, "actor": actor, "book": book, "day": day}
        obligation = register(f, line(f))
        first = line(f, "70.00", debit=True)
        second = line(f, "70.00", debit=True)
        return f, obligation, first, second


@pytest.mark.parametrize("exact_retry", [False, True])
def test_competing_claims_see_committed_balance(
    isolated_statement_database, exact_retry
):
    url = isolated_statement_database
    f, obligation, first, second = seed(url)
    request = uuid4()
    waiting = Event()
    pid = []

    def waiting_claim():
        with psycopg.connect(url) as conn:
            conn.execute("SET statement_timeout='10s'")
            pid.append(conn.info.backend_pid)
            waiting.set()
            return movement(
                f | {"conn": conn},
                obligation,
                first if exact_retry else second,
                request=request if exact_retry else uuid4(),
            )

    with (
        psycopg.connect(url) as winner,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as workers,
    ):
        claim = movement(f | {"conn": winner}, obligation, first, request=request)
        future = workers.submit(waiting_claim)
        assert waiting.wait(timeout=5)
        blocked = False
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            blocked = observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            time.sleep(0.01)
        assert blocked, "The competing claim must wait for the first transaction"
        winner.commit()
        if exact_retry:
            assert future.result(timeout=10) == claim
        else:
            with pytest.raises(psycopg.Error, match="exceed|negative"):
                future.result(timeout=10)
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT sum(signed_amount),count(*) FROM accounting.liability_line_claims WHERE obligation_id=%s",
            (obligation,),
        ).fetchone() == (30, 2)


def test_schedule_and_reconciliation_keep_one_snapshot(
    isolated_statement_database, monkeypatch
):
    url = isolated_statement_database
    f, obligation, first, _ = seed(url)
    real_read = repository.read_book_identity
    wrote = False

    def interleave(cursor):
        nonlocal wrote
        book = real_read(cursor)
        if not wrote:
            with psycopg.connect(url) as conn:
                movement(f | {"conn": conn}, obligation, first)
            wrote = True
        return book

    monkeypatch.setattr(repository, "open_connection", lambda: psycopg.connect(url))
    monkeypatch.setattr(repository, "read_book_identity", interleave)
    repo = repository.PostgresLiabilityControlRepository()
    result = repo.load_schedule(actor_user_id=f["actor"], as_of=f["day"])
    assert result["obligations"][0]["outstanding_amount"] == "100.00"
    assert len(result["movements"]) == 1
    assert len(result["unregistered_lines"]) == 2
    fresh = repo.load_schedule(actor_user_id=f["actor"], as_of=f["day"])
    assert fresh["obligations"][0]["outstanding_amount"] == "30.00"
    assert len(fresh["movements"]) == 2
    assert len(fresh["unregistered_lines"]) == 1
