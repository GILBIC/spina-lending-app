"""Bounded Treasury/Collector close guard: explicit synthetic PostgreSQL only."""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import psycopg
import pytest
import test_period_close_postgres as close
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0141_add_accounting_source_close_guard.sql"
)


def _connect():
    url = os.getenv("GILBIC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit disposable GILBIC_TEST_DATABASE_URL required")
    params = conninfo_to_dict(url)
    if (
        os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1"
        or params.get("host") not in {"127.0.0.1", "localhost", "::1"}
        or params.get("hostaddr", params.get("host"))
        not in {"127.0.0.1", "localhost", "::1"}
        or not re.fullmatch(
            r"spina_treasury_validation_[a-f0-9]{24}", params.get("dbname", "")
        )
        or any(
            key in params for key in ("service", "servicefile", "passfile", "options")
        )
    ):
        raise RuntimeError(
            "Close source tests require an explicitly disposable loopback spina database"
        )
    return psycopg.connect(url)


@pytest.fixture
def source_close():
    with _connect() as conn:
        try:
            if os.getenv("SPINA_SOURCE_CLOSE_BASELINE") != "1":
                conn.execute(close._body(MIGRATION.read_text(encoding="utf-8")))
            suffix = uuid4().hex
            actor = close._management_actor(conn, suffix)
            start = conn.execute(
                "SELECT greatest(coalesce(max(end_date)+1,DATE '2045-01-01'),DATE '2045-01-01') FROM accounting.fiscal_periods"
            ).fetchone()[0]
            end = start + timedelta(days=9)
            period = conn.execute(
                "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
                ("Source close " + suffix, start, end, actor),
            ).fetchone()[0]
            device, context, account, evidence = (uuid4() for _ in range(4))
            conn.execute(
                "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) VALUES(%s,%s,%s,'web','active')",
                (device, actor, device.hex),
            )
            conn.execute(
                "INSERT INTO treasury.contexts(id,kind,created_by) VALUES(%s,'synthetic',%s)",
                (context, actor),
            )
            conn.execute(
                """INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id)
                VALUES(%s,%s,'gcash','Synthetic close wallet','synthetic',%s)""",
                (account, context, actor),
            )
            conn.execute(
                """INSERT INTO treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256)
                VALUES(%s,%s,%s,%s,'recipient','application/pdf',20,%s)""",
                (evidence, account, actor, device, "1" * 64),
            )
            yield {
                "conn": conn,
                "actor": actor,
                "period": period,
                "start": start,
                "end": end,
                "device": device,
                "context": context,
                "account": account,
                "evidence": evidence,
            }
        finally:
            conn.rollback()


def _instant(day):
    return datetime.combine(day, time(0), tzinfo=timezone(timedelta(hours=8)))


def _event(f, when=None):
    event = uuid4()
    f["conn"].execute(
        """INSERT INTO treasury.events(id,account_id,ledger_context_id,provider,reference,direction,amount,
        effective_at,recorded_by_user_id,verified_by_user_id,device_id,evidence_id,recipient_attestation,classification,reason)
        VALUES(%s,%s,%s,'synthetic',%s,'credit',100,%s,%s,%s,%s,%s,'Synthetic recipient evidence','unclassified','Synthetic test')""",
        (
            event,
            f["account"],
            f["context"],
            event.hex,
            when or _instant(f["start"]),
            f["actor"],
            f["actor"],
            f["device"],
            f["evidence"],
        ),
    )
    return event


def _blockers(f):
    return (
        f["conn"]
        .execute(
            "SELECT source_type,source_id,effective_date,amount,reason FROM accounting.period_source_blockers(%s)",
            (f["period"],),
        )
        .fetchall()
    )


def _prepare(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_period_close(%s,%s)", (f["period"], f["actor"])
        )
        .fetchone()[0]
    )


def _post(f):
    digest = (
        f["conn"]
        .execute(
            "SELECT close_digest FROM accounting.period_close_preparations WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()[0]
    )
    return close._post_close(
        f["conn"],
        period_id=f["period"],
        actor_id=f["actor"],
        token="c" * 64,
        close_digest=digest,
        net_income="0.00",
        end_date=f["end"],
    )


def test_review_rejects_unposted_actual_money(source_close):
    """Baseline RED: review used to succeed despite a raw verified cash event."""
    f = source_close
    _event(f)
    with (
        pytest.raises(psycopg.Error, match="unreconciled source"),
        f["conn"].transaction(),
    ):
        close._move_to_review(f["conn"], f["period"], f["actor"])


def test_queue_and_summary_explain_unreconciled_sources(source_close):
    f = source_close
    _event(f)
    status, blocker = (
        f["conn"]
        .execute(
            "SELECT close_status,close_blocker FROM accounting.period_close_queue WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()
    )
    assert status == "blocked_unreconciled_sources"
    assert "Treasury or Collector" in blocker
    assert str(f["account"]) not in blocker
    assert (
        f["conn"]
        .execute("SELECT blocked_count FROM accounting.period_close_summary")
        .fetchone()[0]
        >= 1
    )


def test_migration_replay_preserves_blocker_and_private_function_grants(source_close):
    f = source_close
    event = _event(f)
    f["conn"].execute(close._body(MIGRATION.read_text(encoding="utf-8")))
    assert any(row[1] == event for row in _blockers(f))
    assert (
        f["conn"]
        .execute(
            """SELECT count(*) FROM pg_proc p
        CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
        WHERE p.oid IN (
            'accounting.period_source_blockers(uuid)'::regprocedure,
            'accounting.assert_period_source_complete(uuid)'::regprocedure,
            'accounting.prepare_period_close(uuid,uuid)'::regprocedure,
            'accounting.prepare_period_close_ledger_snapshot(uuid,uuid)'::regprocedure
        ) AND a.grantee=0 AND a.privilege_type='EXECUTE'"""
        )
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    "missing_trigger",
    [
        None,
        "accounting_period_source_transition_guard",
        "accounting_period_source_transition_commit_guard",
        "accounting_period_source_preparation_guard",
        "accounting_period_source_preparation_commit_guard",
    ],
)
def test_release_probe_requires_enabled_source_guards(
    source_close, monkeypatch, missing_trigger
):
    from psycopg import sql

    from gilbic_backend import release_preflight

    conn = source_close["conn"]
    if missing_trigger:
        table = (
            "fiscal_periods"
            if "transition" in missing_trigger
            else "period_close_preparations"
        )
        conn.execute(
            sql.SQL("ALTER TABLE accounting.{} DISABLE TRIGGER {}").format(
                sql.Identifier(table), sql.Identifier(missing_trigger)
            )
        )
    monkeypatch.setattr(release_preflight, "_connect", lambda _: nullcontext(conn))
    result = release_preflight.probe_database(None)
    assert result.get("accounting_source_guards") is (missing_trigger is None)


@pytest.mark.parametrize("stage", ["review", "prepare", "post"])
def test_raw_treasury_without_any_draft_blocks_and_rolls_back(source_close, stage):
    f = source_close
    if stage != "review":
        close._move_to_review(f["conn"], f["period"], f["actor"])
    if stage == "post":
        _prepare(f)
    event = _event(f)
    rows = _blockers(f)
    assert (
        "treasury_event",
        event,
        f["start"],
        100,
        "treasury_gl_mapping_required",
    ) in rows
    assert (
        f["conn"]
        .execute(
            "SELECT account_id FROM accounting.period_source_blockers(%s) WHERE source_id=%s",
            (f["period"], event),
        )
        .fetchone()[0]
        == f["account"]
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.journal_entries WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()[0]
        == 0
    )
    with (
        pytest.raises(psycopg.Error, match="unreconciled source"),
        f["conn"].transaction(),
    ):
        if stage == "review":
            close._move_to_review(f["conn"], f["period"], f["actor"])
        elif stage == "prepare":
            _prepare(f)
        else:
            _post(f)
    assert f["conn"].execute(
        "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
    ).fetchone()[0] == ("open" if stage == "review" else "review")
    assert f["conn"].execute(
        "SELECT count(*) FROM accounting.period_close_preparations WHERE fiscal_period_id=%s",
        (f["period"],),
    ).fetchone()[0] == int(stage == "post")
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()[0]
        == 0
    )


def test_manila_cutoff_and_net_zero_correction_are_not_silently_excluded(source_close):
    f = source_close
    before = _event(f, _instant(f["start"]) - timedelta(microseconds=1))
    event = _event(f, _instant(f["start"]))
    after = _event(f, _instant(f["end"] + timedelta(days=1)))
    correction = uuid4()
    f["conn"].execute(
        """INSERT INTO treasury.movement_lines(id,event_id,account_id,ledger_context_id,component,signed_amount,effective_at,evidence_id)
        VALUES(%s,%s,%s,%s,'correction',-100,%s,%s)""",
        (
            correction,
            event,
            f["account"],
            f["context"],
            _instant(f["start"]),
            f["evidence"],
        ),
    )
    ids = {row[1] for row in _blockers(f)}
    assert event in ids and correction in ids
    assert before not in ids and after not in ids


def _collector_opening(f, day, *, active=True):
    conn = f["conn"]
    opening, anchor, credit = uuid4(), uuid4(), uuid4()
    conn.execute(
        """INSERT INTO treasury.opening_positions(id,account_id,ledger_context_id,cutoff,amount,evidence_id,reason,status,created_by)
        VALUES(%s,%s,%s,%s,100,%s,'Synthetic supported count','active',%s)""",
        (opening, f["account"], f["context"], _instant(day), f["evidence"], f["actor"]),
    )
    conn.execute(
        """INSERT INTO treasury.collector_openings(id,account_id,ledger_context_id,collector_user_id,payload)
        VALUES(%s,%s,%s,%s,%s)""",
        (
            anchor,
            f["account"],
            f["context"],
            f["actor"],
            Jsonb(
                {
                    "opening_id": str(opening),
                    "opening_version": 1,
                    "amount": "20.00",
                    "cutoff": _instant(day).isoformat(),
                    "status": "active" if active else "draft",
                    "evidence_id": str(f["evidence"]),
                    "reason": "Synthetic credit",
                }
            ),
        ),
    )
    conn.execute(
        """INSERT INTO treasury.collector_credits(id,account_id,ledger_context_id,collector_user_id,payload)
        VALUES(%s,%s,%s,%s,%s)""",
        (
            credit,
            f["account"],
            f["context"],
            f["actor"],
            Jsonb(
                {
                    "case_id": None,
                    "opening_anchor_id": str(anchor),
                    "origin_account_id": str(f["account"]),
                    "recognized_amount": "20.00",
                    "reclassified_amount": "0.00",
                    "returned_amount": "0.00",
                    "applied_amount": "0.00",
                    "reserved_amount": "0.00",
                    "outstanding_amount": "20.00",
                    "available_amount": "20.00",
                    "frozen": False,
                    "status": "outstanding",
                    "entries": [],
                }
            ),
        ),
    )
    return anchor, credit


def test_collector_raw_entry_and_opening_need_mapping_without_liability_zero_rule(
    source_close,
):
    f = source_close
    _anchor, credit = _collector_opening(f, f["start"] - timedelta(days=1))
    assert (
        _blockers(f) == []
    )  # A prior-period outstanding liability is not itself a blocker.
    entry = uuid4()
    f["conn"].execute(
        """INSERT INTO treasury.collector_entries(id,account_id,ledger_context_id,collector_user_id,payload,created_at)
        VALUES(%s,%s,%s,%s,%s,%s)""",
        (
            entry,
            f["account"],
            f["context"],
            f["actor"],
            Jsonb(
                {
                    "credit_id": str(credit),
                    "kind": "recognition",
                    "amount": "20.00",
                    "action_id": None,
                }
            ),
            _instant(f["start"]),
        ),
    )
    assert any(row[0] == "collector_entry" and row[1] == entry for row in _blockers(f))
    with (
        pytest.raises(psycopg.Error, match="unreconciled source"),
        f["conn"].transaction(),
    ):
        close._move_to_review(f["conn"], f["period"], f["actor"])


def test_empty_close_succeeds_and_late_actual_money_is_retained_and_visible(
    source_close,
):
    f = source_close
    assert _blockers(f) == []
    close._move_to_review(f["conn"], f["period"], f["actor"])
    _prepare(f)
    _post(f)
    f["conn"].commit()  # Later source recording has its own transaction.
    event = _event(f)
    f["conn"].commit()
    assert any(row[1] == event for row in _blockers(f))
    assert (
        f["conn"]
        .execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        )
        .fetchone()[0]
        == "closed"
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()[0]
        == 1
    )
    assert f["conn"].execute(
        "SELECT source_close_status,comprehensive_source_coverage FROM accounting.period_source_close_state WHERE fiscal_period_id=%s",
        (f["period"],),
    ).fetchone() == ("closed_source_review_required", False)
    status, blocker = (
        f["conn"]
        .execute(
            "SELECT close_status,close_blocker FROM accounting.period_close_queue WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()
    )
    assert status == "blocked_closed_source_review_required"
    assert "remains closed" in blocker


def test_active_collector_opening_blocks_at_its_original_cutoff(source_close):
    f = source_close
    anchor, _ = _collector_opening(f, f["start"])
    assert any(
        row[0] == "collector_opening" and row[1] == anchor for row in _blockers(f)
    )


@pytest.mark.parametrize(
    "gross,physical,credit,blocks",
    [
        ("0.00", "0.00", "0.00", False),
        ("100.00", "0.00", "0.00", True),
        ("0.00", "5.00", "0.00", True),
    ],
)
def test_zero_effect_pass_settlement_is_nonfinancial_but_net_zero_financial_settlement_blocks(
    source_close, gross, physical, credit, blocks
):
    f = source_close
    settlement = uuid4()
    remittance, count_id = uuid4(), uuid4()
    recipient = close._management_actor(f["conn"], uuid4().hex)
    f["conn"].execute(
        """INSERT INTO lending.collection_remittances(id,remittance_number,collector_user_id,recipient_user_id,
            collection_date,transaction_count,payment_count,unable_to_pay_count,covered_payment_count,client_count,total_amount)
            VALUES(%s,%s,%s,%s,%s,1,0,1,0,1,%s)""",
        (remittance, remittance.hex, f["actor"], recipient, f["start"], gross),
    )
    f["conn"].execute(
        "INSERT INTO treasury.collector_counts(id,account_id,ledger_context_id,collector_user_id,payload) VALUES(%s,%s,%s,%s,%s)",
        (
            count_id,
            f["account"],
            f["context"],
            f["actor"],
            Jsonb(
                {
                    "remittance_id": str(remittance),
                    "recipient_user_id": str(recipient),
                    "source_digest": "a" * 64,
                    "gross_obligation": gross,
                    "refund_due_total": gross,
                    "physical_cash_required": "0.00",
                    "counted_amount": physical,
                    "difference": physical,
                    "counted_at": _instant(f["start"]).isoformat(),
                    "recorded_at": _instant(f["start"]).isoformat(),
                    "disposition": "counted_ready",
                    "source_snapshot": {},
                    "evidence_id": str(f["evidence"]),
                    "recipient_attestation": "Synthetic counted cash evidence",
                }
            ),
        ),
    )
    f["conn"].execute(
        "INSERT INTO treasury.collector_settlements(id,account_id,ledger_context_id,collector_user_id,payload) VALUES(%s,%s,%s,%s,%s)",
        (
            settlement,
            f["account"],
            f["context"],
            f["actor"],
            Jsonb(
                {
                    "remittance_id": str(remittance),
                    "count_id": str(count_id),
                    "recipient_user_id": str(recipient),
                    "event_id": None,
                    "gross_obligation": gross,
                    "physical_amount": physical,
                    "authorized_credit_amount": credit,
                    "accepted_at": _instant(f["start"]).isoformat(),
                }
            ),
        ),
    )
    assert any(row[1] == settlement for row in _blockers(f)) is blocks
    if not blocks:
        close._move_to_review(f["conn"], f["period"], f["actor"])


def test_preparation_retry_revalidates_later_evidence(source_close):
    f = source_close
    close._move_to_review(f["conn"], f["period"], f["actor"])
    preparation = _prepare(f)
    _event(f)
    with (
        pytest.raises(psycopg.Error, match="unreconciled source"),
        f["conn"].transaction(),
    ):
        _prepare(f)
    assert (
        f["conn"]
        .execute(
            "SELECT id FROM accounting.period_close_preparations WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()[0]
        == preparation
    )


def test_source_guard_rejects_stale_transaction_snapshot(source_close):
    f = source_close
    f["conn"].commit()
    with pytest.raises(psycopg.Error, match="READ COMMITTED"), f["conn"].transaction():
        f["conn"].execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        close._move_to_review(f["conn"], f["period"], f["actor"])
    assert (
        f["conn"]
        .execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        )
        .fetchone()[0]
        == "open"
    )


def test_commit_revalidates_sources_added_by_closing_transaction(source_close):
    f = source_close
    with (
        pytest.raises(psycopg.Error, match="unreconciled source"),
        f["conn"].transaction(),
    ):
        close._move_to_review(f["conn"], f["period"], f["actor"])
        _event(f)
        f["conn"].execute(
            "SET CONSTRAINTS accounting.accounting_period_source_transition_commit_guard IMMEDIATE"
        )
    assert (
        f["conn"]
        .execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        )
        .fetchone()[0]
        == "open"
    )


def _wait_for_lock(observer, pid):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        waiting = observer.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s AND NOT granted)", (pid,)
        ).fetchone()[0]
        if waiting:
            return
        sleep(0.01)
    pytest.fail("Concurrent source/close did not reach the expected relation lock")


def test_source_writer_in_progress_rejects_close_then_retry_sees_committed_source(
    source_close,
):
    f = source_close
    f["conn"].commit()
    with (
        _connect() as writer,
        _connect() as reviewer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        writer.execute("SET statement_timeout='8s'")
        reviewer.execute("SET statement_timeout='8s'")
        event = _event(dict(f, conn=writer))

        def review():
            try:
                close._move_to_review(reviewer, f["period"], f["actor"])
                reviewer.commit()
                return "unexpected success"
            except psycopg.Error as error:
                reviewer.rollback()
                return str(error)

        pending = pool.submit(review)
        try:
            assert (
                "Source activity is in progress; retry period close."
                in pending.result(timeout=3)
            )
        finally:
            writer.commit()
        assert "unreconciled source" in review()
        assert any(row[1] == event for row in _blockers(f))
        assert (
            f["conn"]
            .execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                (f["period"],),
            )
            .fetchone()[0]
            == "open"
        )


def test_close_first_serializes_late_writer_without_discarding_cash(source_close):
    f = source_close
    f["conn"].commit()
    close._move_to_review(f["conn"], f["period"], f["actor"])
    _prepare(f)
    _post(f)
    with _connect() as writer, ThreadPoolExecutor(max_workers=1) as pool:
        writer.execute("SET statement_timeout='8s'")
        pid = writer.info.backend_pid

        def write_event():
            event = _event(dict(f, conn=writer))
            writer.commit()
            return event

        pending = pool.submit(write_event)
        try:
            _wait_for_lock(f["conn"], pid)
        finally:
            f["conn"].commit()
        event = pending.result(timeout=10)
        assert any(row[1] == event for row in _blockers(f))
        assert (
            f["conn"]
            .execute(
                "SELECT source_close_status FROM accounting.period_source_close_state WHERE fiscal_period_id=%s",
                (f["period"],),
            )
            .fetchone()[0]
            == "closed_source_review_required"
        )
