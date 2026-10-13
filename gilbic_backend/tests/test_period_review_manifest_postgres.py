"""A reviewed economic source identity must survive through formal close."""

import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_ecl_read_only_measurement_postgres as measurement
import test_regular_journal_posting_postgres as regular
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from test_proven_source_composition_postgres import _install as install_composition
from test_treasury_receipt_accounting_postgres import install, mapping, post, prepare
from test_treasury_receipt_accounting_postgres import receipt_db as _receipt_db

receipt_db = _receipt_db
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0154_add_retained_period_review_manifests.sql"
)


@pytest.fixture
def reviewed_source(receipt_db):
    f = receipt_db
    install_composition(f["conn"])
    if os.getenv("SPINA_REVIEW_MANIFEST_BASELINE") != "1" and MIGRATION.exists():
        install(f["conn"], MIGRATION)
    post(f, prepare(f, mapping(f)))
    return f


def _review(f, status="review"):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.set_fiscal_period_status(%s,%s,%s)",
            (f["period"], status, f["actor"].user_id),
        )
        .fetchone()["set_fiscal_period_status"]
    )


def _state(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.period_review_manifest_state(%s) AS result",
            (f["period"],),
        )
        .fetchone()["result"]
    )


def _snapshot(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.period_review_source_snapshot(%s) AS result",
            (f["period"],),
        )
        .fetchone()["result"]
    )


def _manual(f, *, income=False):
    journal = (
        f["conn"]
        .execute(
            "SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s) AS id",
            (
                f["day"],
                "Synthetic independent posted source for review identity",
                f["actor"].user_id,
                Jsonb(
                    [
                        {"account_code": "1010", "debit": "25.00", "credit": "0.00"},
                        {
                            "account_code": "4000" if income else "3000",
                            "debit": "0.00",
                            "credit": "25.00",
                        },
                    ]
                ),
            ),
        )
        .fetchone()["id"]
    )
    f["conn"].execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)",
        (journal, f["actor"].user_id),
    )


def _next_day(f):
    return (
        f["conn"]
        .execute(
            "SELECT end_date+1 AS day FROM accounting.fiscal_periods WHERE id=%s",
            (f["period"],),
        )
        .fetchone()["day"]
    )


def _future_application(f):
    conn = f["conn"]
    day = _next_day(f)
    with conn.cursor(row_factory=tuple_row) as cursor:
        _client, loan = measurement._loan(
            cursor, suffix=uuid4().hex, actor_id=f["actor"].user_id, release_date=day
        )
        # Use the receipt borrower for the funded source, preserving loan linkage.
        cursor.execute(
            "UPDATE lending.loans SET client_id=%s WHERE id=%s", (f["client"], loan)
        )
        cursor.execute(
            "SELECT set_config('spina.treasury_receipt_id',%s,true)",
            (str(f["receipt"]),),
        )
        source = regular._create_collection(
            cursor,
            suffix=uuid4().hex,
            loan_id=loan,
            client_id=f["client"],
            actor_id=f["actor"].user_id,
            device_id=f["actor"].registered_device_id,
            sequence=1771,
            collection_date=day,
            amount="50.00",
        )
        cursor.execute("SELECT set_config('spina.treasury_receipt_id','',true)")
    conn.execute(
        "INSERT INTO treasury.applications(id,receipt_id,account_id,ledger_context_id,amount,status,source_result,created_by) VALUES(%s,%s,%s,%s,50,'active',%s,%s)",
        (
            uuid4(),
            f["receipt"],
            f["wallet"],
            f["context"],
            Jsonb(
                {
                    "status": "recorded",
                    "transaction_ids": [str(source)],
                    "amount": "50.00",
                }
            ),
            f["actor"].user_id,
        ),
    )
    conn.execute(
        "UPDATE treasury.receipts SET applied_amount=applied_amount+50,version=version+1 WHERE id=%s",
        (f["receipt"],),
    )


def _future_refund(f):
    event = uuid4()
    effective = datetime.combine(
        _next_day(f), time(0, 30), tzinfo=timezone(timedelta(hours=8))
    )
    f["conn"].execute(
        "INSERT INTO treasury.events(id,account_id,ledger_context_id,provider,reference,direction,amount,effective_at,recorded_by_user_id,verified_by_user_id,device_id,evidence_id,recipient_attestation,classification,reason) VALUES(%s,%s,%s,'gcash',%s,'debit',10,%s,%s,%s,%s,%s,'Synthetic recipient verification','receipt_refund','Synthetic later actual refund')",
        (
            event,
            f["wallet"],
            f["context"],
            event.hex,
            effective,
            f["actor"].user_id,
            f["actor"].user_id,
            f["actor"].registered_device_id,
            f["evidence"],
        ),
    )
    f["conn"].execute(
        "INSERT INTO treasury.movement_lines(id,event_id,account_id,ledger_context_id,component,signed_amount,effective_at,evidence_id) VALUES(%s,%s,%s,%s,'principal',-10,%s,%s)",
        (uuid4(), event, f["wallet"], f["context"], effective, f["evidence"]),
    )
    f["conn"].execute(
        "INSERT INTO treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount) VALUES(%s,%s,%s,'receipt_refund',%s,1,10)",
        (uuid4(), event, f["context"], f["receipt"]),
    )
    f["conn"].execute(
        "UPDATE treasury.receipts SET refunded_amount=refunded_amount+10,version=version+1 WHERE id=%s",
        (f["receipt"],),
    )


def test_review_retains_exact_source_and_ledger_identity(reviewed_source):
    f = reviewed_source
    assert _review(f) == "review"
    row = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.period_review_manifests WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()
    )
    assert row is not None and row["reviewed_by_user_id"] == f["actor"].user_id
    assert row["source_snapshot"] == _snapshot(f)
    state = _state(f)
    assert state["current"] is True
    assert state["version"] == 1
    assert state["source_digest"] == row["source_digest"]
    assert state["source_count"] > 0 and state["journal_count"] > 0
    assert state["comprehensive_source_coverage"] is False
    assert "source_snapshot" not in state


def test_return_to_open_then_review_creates_new_immutable_version(reviewed_source):
    f = reviewed_source
    _review(f)
    first = _state(f)
    _review(f, "open")
    _review(f)
    second = _state(f)
    assert second["version"] == 2 and second["manifest_id"] != first["manifest_id"]
    assert second["source_digest"] == first["source_digest"]
    with pytest.raises(psycopg.Error, match="immutable"), f["conn"].transaction():
        f["conn"].execute(
            "DELETE FROM accounting.period_review_manifests WHERE id=%s",
            (first["manifest_id"],),
        )


def test_same_balance_chart_identity_change_rejects_close_preparation(reviewed_source):
    f = reviewed_source
    _manual(f)
    _review(f)
    f["conn"].execute(
        "UPDATE accounting.accounts SET name='Changed reviewed cash chart' WHERE code='1010'"
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.period_source_blockers(%s) "
            "WHERE source_type <> 'period_review_manifest'",
            (f["period"],),
        )
        .fetchone()["n"]
        == 0
    )
    if os.environ.get("SPINA_REVIEW_MANIFEST_BASELINE") != "1":
        blockers = (
            f["conn"]
            .execute(
                "SELECT reason FROM accounting.period_source_blockers(%s) "
                "WHERE source_type = 'period_review_manifest'",
                (f["period"],),
            )
            .fetchall()
        )
        assert [row["reason"] for row in blockers] == ["retained_review_source_changed"]
    with (
        pytest.raises(psycopg.Error, match="manifest|review.*changed"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "SELECT accounting.prepare_period_close(%s,%s)",
            (f["period"], f["actor"].user_id),
        )


@pytest.mark.parametrize("later", ["application", "refund"])
def test_later_receipt_leg_does_not_change_earlier_cutoff_identity(
    reviewed_source, later
):
    f = reviewed_source
    _review(f)
    before = _snapshot(f)
    {"application": _future_application, "refund": _future_refund}[later](f)
    assert _snapshot(f) == before
    assert _state(f)["current"] is True


def test_direct_review_cannot_bypass_manifest_capture(reviewed_source):
    f = reviewed_source
    with (
        pytest.raises(psycopg.Error, match="manifest|retained review"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "SELECT set_config('spina.accounting_period_transition','on',true)"
        )
        f["conn"].execute(
            "UPDATE accounting.fiscal_periods SET status='review' WHERE id=%s",
            (f["period"],),
        )


def test_protected_closing_entry_preserves_bound_review_identity(reviewed_source):
    f = reviewed_source
    _manual(f, income=True)
    _review(f)
    before = _state(f)
    preparation_id = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_period_close(%s,%s) AS id",
            (f["period"], f["actor"].user_id),
        )
        .fetchone()["id"]
    )
    preparation = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.period_close_preparations WHERE id=%s",
            (preparation_id,),
        )
        .fetchone()
    )
    binding = (
        f["conn"]
        .execute(
            "SELECT manifest_id FROM accounting.period_close_manifest_bindings WHERE preparation_id=%s",
            (preparation_id,),
        )
        .fetchone()
    )
    assert str(binding["manifest_id"]) == before["manifest_id"]
    f["conn"].execute(
        "SELECT accounting.post_period_close(%s,%s,%s,%s,%s,'3100',%s,'period_close_retained_earnings_v1')",
        (
            f["period"],
            f["actor"].user_id,
            "a" * 64,
            preparation["close_digest"],
            preparation["net_income"],
            preparation["period_end_date"],
        ),
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    after = _state(f)
    assert (
        after["current"] is True and after["source_digest"] == before["source_digest"]
    )
