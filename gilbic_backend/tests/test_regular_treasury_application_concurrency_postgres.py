"""First Regular application rechecks committed prefix/source state after a lock wait."""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from test_regular_treasury_application_boundaries_postgres import append_collection
from test_regular_treasury_application_postgres import (
    actual_regular_source,
    posted,
    retained,
)


@pytest.fixture
def regular_race_database():
    url = os.getenv("GILBIC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit disposable loopback PostgreSQL URL required")
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    params = conninfo_to_dict(url)
    assert params.get("host") in {"127.0.0.1", "localhost", "::1"}
    assert params.get("hostaddr", params["host"]) in {"127.0.0.1", "localhost", "::1"}
    assert not {"options", "passfile", "service", "servicefile"}.intersection(params)
    assert re.fullmatch(r"spina_treasury_validation_[a-f0-9]{24}", params["dbname"])
    name = "spina_treasury_validation_" + uuid4().hex[:24]
    with psycopg.connect(
        make_conninfo(**(params | {"dbname": "postgres"})), autocommit=True
    ) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(name), sql.Identifier(params["dbname"])
            )
        )
        try:
            yield make_conninfo(**(params | {"dbname": name}))
        finally:
            assert re.fullmatch(r"spina_treasury_validation_[a-f0-9]{24}", name)
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.mark.parametrize("winner", ["post", "earlier_cash", "private_authority"])
def test_waiting_regular_prefix_post_rechecks_committed_evidence(
    regular_race_database, monkeypatch, tmp_path, winner
):
    url = regular_race_database
    with psycopg.connect(url) as setup:
        f = actual_regular_source(setup, monkeypatch, tmp_path, with_prefix=True)
        preparation = retained(f)
    waiting = Event()
    waiter_pid = []

    def waiting_post():
        with psycopg.connect(url, row_factory=dict_row) as connection:
            connection.execute("SET statement_timeout='30s'")
            waiter_pid.append(connection.info.backend_pid)
            waiting.set()
            return posted(f | {"conn": connection}, preparation)

    with (
        psycopg.connect(url, row_factory=dict_row) as first,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as workers,
    ):
        first.execute(
            "SELECT id FROM treasury.accounts WHERE id=%s FOR UPDATE", (f["wallet"],)
        )
        current = f | {"conn": first}
        if winner == "post":
            expected = posted(current, preparation)
        elif winner == "earlier_cash":
            append_collection(current, f["day"] - timedelta(days=1))
        else:
            first.execute(
                "UPDATE treasury.account_access SET private_history=false "
                "WHERE account_id=%s AND user_id=%s",
                (f["wallet"], f["actor_id"]),
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
        assert blocked, "Regular application did not wait on its retained wallet lock"
        first.commit()
        if winner == "post":
            assert future.result(timeout=35) == expected
        else:
            with pytest.raises(psycopg.Error, match="prior cash|first cash|permission"):
                future.result(timeout=35)
    with psycopg.connect(url) as check:
        assert check.execute(
            "SELECT count(*) FROM accounting.treasury_application_postings WHERE application_id=%s",
            (f["application"],),
        ).fetchone()[0] == (1 if winner == "post" else 0)
