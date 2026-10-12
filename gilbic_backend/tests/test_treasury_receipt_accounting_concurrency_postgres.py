"""Committed races must yield one cash journal or a fresh source rejection."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_treasury_receipt_accounting_postgres import mapping, post, prepare, seed

isolated_statement_database = _isolated_statement_database


@pytest.mark.parametrize("winner", ["post", "correction"])
def test_waiting_post_rechecks_committed_source_or_returns_one_audit(
    isolated_statement_database, winner
):
    url = isolated_statement_database
    with psycopg.connect(url, row_factory=dict_row) as setup:
        f = seed(setup)
        prepared = prepare(f, mapping(f))
    waiting = Event()
    waiter_pid = []

    def waiting_post():
        with psycopg.connect(url, row_factory=dict_row) as connection:
            connection.execute("SET statement_timeout='10s'")
            waiter_pid.append(connection.info.backend_pid)
            waiting.set()
            return post(f | {"conn": connection}, prepared)

    with (
        psycopg.connect(url, row_factory=dict_row) as winner_connection,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as workers,
    ):
        winner_connection.execute(
            "SELECT id FROM treasury.accounts WHERE id=%s FOR UPDATE", (f["wallet"],)
        )
        if winner == "post":
            expected = post(f | {"conn": winner_connection}, prepared)
        else:
            winner_connection.execute(
                "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) VALUES(%s,%s,2,'correct','Synthetic racing correction',%s)",
                (uuid4(), f["event"], f["actor"].user_id),
            )
        future = workers.submit(waiting_post)
        assert waiting.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            blocked = observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (waiter_pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            time.sleep(0.01)
        assert blocked, "Concurrent posting did not wait on the source account lock"
        winner_connection.commit()
        if winner == "post":
            assert future.result(timeout=10) == expected
        else:
            with pytest.raises(psycopg.Error, match="uncorrected"):
                future.result(timeout=10)
    with psycopg.connect(url) as check:
        assert check.execute(
            "SELECT count(*) FROM accounting.treasury_receipt_postings WHERE event_id=%s",
            (f["event"],),
        ).fetchone()[0] == (1 if winner == "post" else 0)
