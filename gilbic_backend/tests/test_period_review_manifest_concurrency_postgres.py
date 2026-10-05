"""Retained review cannot race chart changes or commit a stale source identity."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

import psycopg
import pytest
from psycopg.rows import dict_row
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_period_review_manifest_postgres import (
    MIGRATION,
    _manual,
    _review,
    _state,
    install_composition,
)
from test_period_review_manifest_postgres import reviewed_source as _reviewed_source
from test_treasury_receipt_accounting_postgres import (
    install,
    mapping,
    post,
    prepare,
    seed,
)
from test_treasury_receipt_accounting_postgres import receipt_db as _receipt_db

isolated_statement_database = _isolated_statement_database
receipt_db = _receipt_db
reviewed_source = _reviewed_source


def _prepare(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_period_close(%s,%s) AS id",
            (f["period"], f["actor"].user_id),
        )
        .fetchone()["id"]
    )


def _change(conn):
    conn.execute(
        "UPDATE accounting.accounts SET name='Concurrent revised cash label' WHERE code='1010'"
    )


@pytest.mark.parametrize("winner", ["chart", "prepare"])
def test_manifest_preparation_rechecks_after_concurrent_chart_change(
    isolated_statement_database, winner
):
    url = isolated_statement_database
    with psycopg.connect(url, row_factory=dict_row) as setup:
        case = seed(setup)
        install_composition(setup)
        install(setup, MIGRATION)
        post(case, prepare(case, mapping(case)))
        _manual(case, income=True)
        _review(case)
    started, pid = Event(), []

    def waiting():
        with psycopg.connect(url, row_factory=dict_row) as conn:
            conn.execute("SET statement_timeout='20s'")
            pid.append(conn.info.backend_pid)
            started.set()
            if winner == "chart":
                return _prepare(case | {"conn": conn})
            _change(conn)

    with (
        psycopg.connect(url, row_factory=dict_row) as first,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        first.execute("SET statement_timeout='20s'")
        if winner == "chart":
            _change(first)
        else:
            _prepare(case | {"conn": first})
        future = pool.submit(waiting)
        assert started.wait(timeout=5)
        deadline = monotonic() + 5
        blocked = False
        while monotonic() < deadline:
            blocked = observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            sleep(0.01)
        assert blocked, "Review manifest must serialize against chart mutations"
        first.commit()
        if winner == "chart":
            with pytest.raises(psycopg.Error, match="manifest.*changed"):
                future.result(timeout=20)
        else:
            future.result(timeout=20)
    with psycopg.connect(url, row_factory=dict_row) as check:
        f = case | {"conn": check}
        assert _state(f)["current"] is False
        with pytest.raises(psycopg.Error, match="manifest.*changed"):
            _prepare(f)


def test_deferred_review_rejects_change_after_manifest_capture(reviewed_source):
    f = reviewed_source
    _manual(f)
    with (
        pytest.raises(psycopg.Error, match="manifest.*changed|unreconciled source"),
        f["conn"].transaction(),
    ):
        _review(f)
        _change(f["conn"])
        assert _state(f)["current"] is False
        assert (
            f["conn"]
            .execute(
                "SELECT count(*) AS n FROM accounting.period_source_blockers(%s) WHERE source_type='period_review_manifest'",
                (f["period"],),
            )
            .fetchone()["n"]
            == 1
        )
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert (
        f["conn"]
        .execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        )
        .fetchone()["status"]
        == "open"
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.period_review_manifests WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()["n"]
        == 0
    )
