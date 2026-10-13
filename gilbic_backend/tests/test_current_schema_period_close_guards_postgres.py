"""Exercise the installed close stack without reinstalling historical SQL."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
import test_period_close_postgres as close
from test_current_schema_accounting_cycle_postgres import (
    fresh_current_database as _fresh_current_database,
)
from test_source_close_guard_postgres import _event, _instant

from gilbic_backend import period_close_repository

fresh_current_database = _fresh_current_database


def new_book(connection):
    suffix = uuid4().hex
    actor = close._management_actor(connection, suffix)
    identity = ("synthetic", "Synthetic first book", "test:first-book", "a" * 64, actor)
    query = "SELECT accounting.configure_book_identity(%s,%s,%s,%s,%s)"
    book = connection.execute(query, identity).fetchone()[0]
    assert connection.execute(query, identity).fetchone()[0] == book
    start = connection.execute(
        "SELECT least(coalesce(min(start_date)-20,DATE '2000-01-01'),DATE '2000-01-01') FROM accounting.fiscal_periods"
    ).fetchone()[0]
    end = start + timedelta(days=9)
    period = connection.execute(
        "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
        ("Synthetic first period " + suffix, start, end, actor),
    ).fetchone()[0]
    return {
        "conn": connection,
        "actor": actor,
        "book": book,
        "period": period,
        "start": start,
        "end": end,
    }


def wallet(f):
    connection, actor = f["conn"], f["actor"]
    device, context, account, evidence = (uuid4() for _ in range(4))
    connection.execute(
        "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) VALUES(%s,%s,%s,'web','active')",
        (device, actor, device.hex),
    )
    connection.execute(
        "INSERT INTO treasury.contexts(id,kind,created_by) VALUES(%s,'synthetic',%s)",
        (context, actor),
    )
    connection.execute(
        "INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) VALUES(%s,%s,'gcash','Synthetic first wallet','synthetic',%s)",
        (account, context, actor),
    )
    connection.execute(
        "INSERT INTO treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256) VALUES(%s,%s,%s,%s,'recipient','application/pdf',20,%s)",
        (evidence, account, actor, device, "1" * 64),
    )
    return f | {
        "device": device,
        "context": context,
        "account": account,
        "evidence": evidence,
    }


def prepare(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_period_close(%s,%s)", (f["period"], f["actor"])
        )
        .fetchone()[0]
    )


def post(f):
    digest, net = (
        f["conn"]
        .execute(
            "SELECT close_digest,net_income FROM accounting.period_close_preparations WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()
    )
    return close._post_close(
        f["conn"],
        period_id=f["period"],
        actor_id=f["actor"],
        token="b" * 64,
        close_digest=digest,
        net_income=str(net),
        end_date=f["end"],
    )


def test_current_schema_empty_first_book_closes_without_invented_opening(
    fresh_current_database, monkeypatch
):
    url = fresh_current_database["source"]
    monkeypatch.setattr(
        period_close_repository, "open_connection", lambda: psycopg.connect(url)
    )
    repository = period_close_repository.PostgresPeriodCloseRepository()
    with psycopg.connect(url) as connection:
        f = new_book(connection)
        assert (
            connection.execute(
                "SELECT count(*) FROM accounting.journal_entries"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM accounting.opening_balance_workbooks"
            ).fetchone()[0]
            == 0
        )
        close._move_to_review(connection, f["period"], f["actor"])
        connection.commit()
        prepared = repository.prepare(
            fiscal_period_id=f["period"], actor_user_id=f["actor"]
        )
        assert (
            repository.prepare(fiscal_period_id=f["period"], actor_user_id=f["actor"])
            == prepared
        )
        item = repository.get_item(f["period"])
        confirmation = {
            "fiscal_period_id": f["period"],
            "actor_user_id": f["actor"],
            "confirmation_token": "b" * 64,
            "expected_close_digest": item.close_digest,
            "expected_net_income": Decimal("0.00"),
            "expected_retained_earnings_account_code": "3100",
            "expected_period_end_date": f["end"],
        }
        posted = repository.post(**confirmation)
        assert repository.post(**confirmation) == posted
        connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        assert (
            connection.execute(
                "SELECT count(*) FROM accounting.journal_entries"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM accounting.opening_balance_workbooks"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                (f["period"],),
            ).fetchone()[0]
            == "closed"
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
                (f["period"],),
            ).fetchone()[0]
            == 1
        )


@pytest.mark.parametrize("stage", ["review", "prepare", "post"])
def test_current_schema_close_yields_to_source_writer_and_preserves_money(
    fresh_current_database, stage
):
    url = fresh_current_database["source"]
    with psycopg.connect(url) as setup:
        f = wallet(new_book(setup))
        if stage != "review":
            close._move_to_review(setup, f["period"], f["actor"])
        if stage == "post":
            prepare(f)
    with psycopg.connect(url) as writer, psycopg.connect(url) as reviewer:
        writer.execute("SET statement_timeout='2s'")
        reviewer.execute("SET statement_timeout='2s'")
        reviewer.execute("SET lock_timeout='750ms'")
        event = _event(f | {"conn": writer})
        with (
            pytest.raises(
                psycopg.Error,
                match="Source activity is in progress; retry period close",
            ) as failure,
            reviewer.transaction(),
        ):
            if stage == "review":
                close._move_to_review(reviewer, f["period"], f["actor"])
            elif stage == "prepare":
                prepare(f | {"conn": reviewer})
            else:
                post(f | {"conn": reviewer})
        assert failure.value.sqlstate == "23514"
        assert reviewer.execute("SHOW lock_timeout").fetchone()[0] == "750ms"
        # The rejected close must release every partial source lock. The writer
        # can finish its money observation while the caller transaction is open.
        writer.execute(
            "INSERT INTO treasury.movement_lines(id,event_id,account_id,ledger_context_id,component,signed_amount,effective_at,evidence_id) VALUES(%s,%s,%s,%s,'principal',100,%s,%s)",
            (
                uuid4(),
                event,
                f["account"],
                f["context"],
                _instant(f["start"]),
                f["evidence"],
            ),
        )
        writer.commit()
        assert (
            reviewer.execute(
                "SELECT sum(signed_amount) FROM treasury.movement_lines WHERE event_id=%s",
                (event,),
            ).fetchone()[0]
            == 100
        )
        assert reviewer.execute(
            "SELECT EXISTS(SELECT 1 FROM accounting.period_source_blockers(%s) WHERE source_id=%s)",
            (f["period"], event),
        ).fetchone()[0]
        assert (
            reviewer.execute(
                "SELECT count(*) FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
                (f["period"],),
            ).fetchone()[0]
            == 0
        )


def test_current_schema_commit_rejects_new_source_without_rewriting_first_book(
    fresh_current_database,
):
    with psycopg.connect(fresh_current_database["source"]) as connection:
        f = wallet(new_book(connection))
        connection.commit()
        with (
            pytest.raises(psycopg.Error, match="unreconciled|manifest.*changed"),
            connection.transaction(),
        ):
            close._move_to_review(connection, f["period"], f["actor"])
            prepare(f)
            post(f)
            _event(f)
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        assert (
            connection.execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                (f["period"],),
            ).fetchone()[0]
            == "open"
        )
        for table in (
            "period_review_manifests",
            "period_close_preparations",
            "period_close_postings",
        ):
            assert (
                connection.execute(
                    f"SELECT count(*) FROM accounting.{table} WHERE fiscal_period_id=%s",
                    (f["period"],),
                ).fetchone()[0]
                == 0
            )
        assert (
            connection.execute(
                "SELECT count(*) FROM accounting.journal_entries"
            ).fetchone()[0]
            == 0
        )


def test_current_schema_source_details_require_live_private_wallet_access(
    fresh_current_database, monkeypatch
):
    url = fresh_current_database["source"]
    monkeypatch.setattr(
        period_close_repository, "open_connection", lambda: psycopg.connect(url)
    )
    repository = period_close_repository.PostgresPeriodCloseRepository()
    with psycopg.connect(url) as connection:
        f = wallet(new_book(connection))
        event = _event(f)
        connection.commit()
        actor = SimpleNamespace(user_id=f["actor"], registered_device_id=f["device"])

        def restricted():
            coverage = repository.source_coverage(f["period"], actor=actor)
            assert coverage["blocker_count"] == 1
            assert coverage["blockers"] == [
                {
                    "source_type": "restricted_source",
                    "source_id": None,
                    "effective_date": None,
                    "amount": None,
                    "reason": "treasury_account_access_required",
                }
            ]

        restricted()
        connection.execute(
            "INSERT INTO core.role_permissions(role_id,permission_code) SELECT id,'treasury.view' FROM core.roles WHERE code='management' ON CONFLICT DO NOTHING"
        )
        connection.execute(
            "INSERT INTO treasury.account_access(account_id,user_id,permissions,granted_by) VALUES(%s,%s,ARRAY['treasury.view'],%s)",
            (f["account"], f["actor"], f["actor"]),
        )
        connection.commit()
        restricted()
        connection.execute(
            "UPDATE treasury.account_access SET private_history=true WHERE account_id=%s AND user_id=%s",
            (f["account"], f["actor"]),
        )
        connection.commit()
        details = repository.source_coverage(f["period"], actor=actor)["blockers"]
        assert details[0]["source_id"] == str(event)
        assert details[0]["amount"] == "100.00"
        assert "account_id" not in details[0]
        connection.execute(
            "UPDATE treasury.account_access SET enabled=false WHERE account_id=%s AND user_id=%s",
            (f["account"], f["actor"]),
        )
        connection.commit()
        restricted()
        assert repository.get_item(f["period"]).source_blocker_count == 1
        assert f["period"] not in {
            item.fiscal_period_id
            for item in repository.list_items(status="ready_for_review")
        }


def test_current_schema_late_money_remains_recorded_and_flags_closed_history(
    fresh_current_database, monkeypatch
):
    url = fresh_current_database["source"]
    monkeypatch.setattr(
        period_close_repository, "open_connection", lambda: psycopg.connect(url)
    )
    repository = period_close_repository.PostgresPeriodCloseRepository()
    with psycopg.connect(url) as connection:
        f = wallet(new_book(connection))
        close._move_to_review(connection, f["period"], f["actor"])
        prepare(f)
        post(f)
        connection.commit()
        event = _event(f)
        connection.commit()
        assert connection.execute(
            "SELECT amount FROM treasury.events WHERE id=%s", (event,)
        ).fetchone()[0] == Decimal(100)
        closed = {
            item.fiscal_period_id: item
            for item in repository.list_items(status="closed")
        }
        assert closed[f["period"]].close_status == "closed_source_review_required"
        assert f["period"] in {
            item.fiscal_period_id for item in repository.list_items(status="blocked")
        }
        assert (
            connection.execute(
                "SELECT (accounting.period_review_manifest_state(%s)->>'current')::boolean",
                (f["period"],),
            ).fetchone()[0]
            is False
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
                (f["period"],),
            ).fetchone()[0]
            == 1
        )
