"""Committed wallet changes are rechecked after a transfer posting lock wait."""

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
from test_treasury_receipt_accounting_postgres import install, mapping
from test_treasury_transfer_accounting_postgres import (
    MIGRATION,
    post,
    prepare,
    record_leg,
    seed_transfer,
)

isolated_statement_database = _isolated_statement_database


@pytest.mark.parametrize("winner", ["post", "correction", "mapping"])
def test_waiting_transfer_post_rechecks_committed_evidence(
    isolated_statement_database, tmp_path, winner
):
    url = isolated_statement_database
    with psycopg.connect(url, row_factory=dict_row) as setup:
        f = seed_transfer(setup, tmp_path)
        install(setup, MIGRATION)
        record_leg(f, "source", fee="2.00")
        prepared = prepare(f, "source")
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
            "SELECT id FROM treasury.accounts WHERE id IN(%s,%s) ORDER BY id FOR UPDATE",
            (f["wallet"], f["destination"]),
        )
        if winner == "post":
            expected = post(f | {"conn": winner_connection}, prepared)
        elif winner == "mapping":
            mapping(
                f | {"conn": winner_connection, "wallet": f["destination"]},
                version=1,
                reference="test:racing-destination-mapping",
            )
        else:
            winner_connection.execute(
                "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) SELECT %s,source_event_id,2,'correct','Synthetic racing correction',%s FROM treasury.transfers WHERE id=%s",
                (uuid4(), f["actor"].user_id, f["transfer"]),
            )
        future = workers.submit(waiting_post)
        assert waiting.wait(timeout=5)
        deadline = time.monotonic() + 5
        blocked = False
        while time.monotonic() < deadline:
            blocked = observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (waiter_pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            time.sleep(0.01)
        assert blocked, (
            "Concurrent transfer posting did not wait on the owned-wallet lock"
        )
        winner_connection.commit()
        if winner == "post":
            assert future.result(timeout=10) == expected
        else:
            with pytest.raises(psycopg.Error, match="corrected|mapping"):
                future.result(timeout=10)
    with psycopg.connect(url) as check:
        assert check.execute(
            "SELECT count(*) FROM accounting.treasury_transfer_postings WHERE transfer_id=%s",
            (f["transfer"],),
        ).fetchone()[0] == (1 if winner == "post" else 0)
