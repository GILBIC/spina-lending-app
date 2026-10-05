"""Exact leg admission, retained history and transfer-specific transit controls."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from test_treasury_receipt_accounting_postgres import mapping
from test_treasury_transfer_accounting_postgres import (
    coordinates,
    post,
    prepare,
    record_leg,
)
from test_treasury_transfer_accounting_postgres import transfer_db as _transfer_db

transfer_db = _transfer_db


def test_transfer_metadata_does_not_authorize_cash_or_transit(transfer_db):
    f = transfer_db
    f["conn"].execute(
        "INSERT INTO treasury.transfers(id,ledger_context_id,source_account_id,destination_account_id,amount) VALUES(%s,%s,%s,%s,100)",
        (f["transfer"], f["context"], f["wallet"], f["destination"]),
    )
    for leg in ("source", "destination"):
        with (
            pytest.raises(psycopg.Error, match="Actual verified transfer leg"),
            f["conn"].transaction(),
        ):
            coordinates(f, leg)


def test_confirmation_and_request_retries_must_match_exact_preparation(transfer_db):
    f = transfer_db
    record_leg(f, "source")
    prep = prepare(f, "source")
    args = (
        f["transfer"],
        "source",
        f["source_mapping"],
        f["destination_mapping"],
        prep["source_digest"],
        prep["request_id"],
        f["actor"].user_id,
    )
    assert (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_treasury_transfer(%s,%s,%s,%s,%s,%s,%s) AS id",
            args,
        )
        .fetchone()["id"]
        == prep["id"]
    )
    with pytest.raises(psycopg.Error, match="retry"), f["conn"].transaction():
        f["conn"].execute(
            "SELECT accounting.prepare_treasury_transfer(%s,%s,%s,%s,%s,%s,%s)",
            args[:4] + ("0" * 64,) + args[5:],
        )
    for change in ("confirmation_token", "source_digest"):
        with (
            pytest.raises(psycopg.Error, match="confirmation"),
            f["conn"].transaction(),
        ):
            post(f, prep | {change: "0" * 64})


def status(f, leg="source"):
    return (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_transfer_posting_status WHERE transfer_id=%s AND leg=%s",
            (f["transfer"], leg),
        )
        .fetchone()
    )


def append_correction(f):
    f["conn"].execute(
        "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) SELECT %s,source_event_id,2,'correct','Synthetic later actual correction',%s FROM treasury.transfers WHERE id=%s",
        (uuid4(), f["actor"].user_id, f["transfer"]),
    )


@pytest.mark.parametrize(
    "change",
    [
        "source_mapping",
        "destination_mapping",
        "source_permission",
        "destination_permission",
        "management_permission",
        "chart",
        "correction",
        "header_amount",
    ],
)
def test_stale_review_cannot_post_any_money(transfer_db, change):
    f = transfer_db
    record_leg(f, "source", fee="2.00")
    prep = prepare(f, "source")
    conn = f["conn"]
    if change.endswith("mapping"):
        wallet = f["wallet"] if change.startswith("source") else f["destination"]
        mapping(f | {"wallet": wallet}, version=1, reference="test:replacement-mapping")
    elif change in {"source_permission", "destination_permission"}:
        wallet = f["wallet"] if change.startswith("source") else f["destination"]
        conn.execute(
            "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
            (wallet,),
        )
    elif change == "management_permission":
        conn.execute(
            "DELETE FROM core.role_permissions WHERE permission_code='accounting.journal.manage'"
        )
    elif change == "chart":
        conn.execute(
            "UPDATE accounting.accounts SET normal_balance='credit' WHERE code='5240'"
        )
    elif change == "correction":
        append_correction(f)
    else:
        conn.execute(
            "UPDATE treasury.transfers SET amount=99 WHERE id=%s", (f["transfer"],)
        )
    with pytest.raises(psycopg.Error), conn.transaction():
        post(f, prep)
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.treasury_transfer_postings"
        ).fetchone()["n"]
        == 0
    )


def test_late_correction_keeps_cash_once_and_requires_review(transfer_db):
    f = transfer_db
    record_leg(f, "source")
    prep = prepare(f, "source")
    entry = post(f, prep)
    append_correction(f)
    assert post(f, prep) == entry
    current = status(f)
    assert current["exact_posted"] is True and current["correction_pending"] is True
    record_leg(f, "destination")
    with pytest.raises(psycopg.Error, match="source|Source"), f["conn"].transaction():
        coordinates(f, "destination")


@pytest.mark.parametrize("code", ["1030", "5240"])
def test_semantic_chart_change_flags_retained_transfer_review(transfer_db, code):
    f = transfer_db
    record_leg(f, "source", fee="2.00")
    post(f, prepare(f, "source"))
    f["conn"].execute(
        "UPDATE accounting.accounts SET normal_balance='credit' WHERE code=%s", (code,)
    )
    current = status(f)
    assert current["exact_posted"] is True and current["correction_pending"] is True


def test_account_retirement_and_label_change_preserve_history(transfer_db):
    f = transfer_db
    record_leg(f, "source", fee="2.00")
    post(f, prepare(f, "source"))
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_active=false,name='Retired synthetic control' WHERE code IN('1030','1040','5240')"
    )
    current = status(f)
    assert current["exact_posted"] is True and current["correction_pending"] is False


def test_transit_is_reconciled_by_transfer_and_actual_cutoff(transfer_db):
    f = transfer_db
    record_leg(f, "source", fee="2.00")
    post(f, prepare(f, "source"))
    record_leg(f, "destination")
    post(f, prepare(f, "destination"))
    for cutoff, expected in (
        (f["day"], Decimal("100.00")),
        (f["day"] + timedelta(days=1), Decimal("0.00")),
    ):
        row = (
            f["conn"]
            .execute(
                "SELECT * FROM accounting.treasury_transfer_transit_reconciliation(%s) WHERE transfer_id=%s",
                (cutoff, f["transfer"]),
            )
            .fetchone()
        )
        assert row["expected_transit"] == row["ledger_transit"] == expected
        assert row["difference"] == 0 and row["requires_review"] is False


def test_destination_date_cannot_precede_actual_source_date(transfer_db):
    f = transfer_db
    record_leg(f, "source", day=f["day"] + timedelta(days=1))
    post(f, prepare(f, "source"))
    record_leg(f, "destination", day=f["day"])
    with (
        pytest.raises(psycopg.Error, match="chronology|source"),
        f["conn"].transaction(),
    ):
        coordinates(f, "destination")


@pytest.mark.parametrize(
    "table",
    ["treasury_transfer_preparations", "treasury_transfer_postings", "journal_lines"],
)
def test_transfer_evidence_and_cash_proof_cannot_be_truncated(transfer_db, table):
    f = transfer_db
    record_leg(f, "source")
    post(f, prepare(f, "source"))
    with (
        pytest.raises(psycopg.Error, match="immutable|protected|Protected|transfer"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            sql.SQL("TRUNCATE accounting.{} CASCADE").format(sql.Identifier(table))
        )


def test_unprivileged_role_has_no_raw_transfer_accounting_surface(transfer_db):
    f = transfer_db
    conn = f["conn"]
    role = "transfer_probe_" + uuid4().hex
    conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
    for function in (
        "accounting.treasury_transfer_coordinates(uuid,text,uuid,uuid)",
        "accounting.post_treasury_transfer(uuid,text,text,uuid)",
        "accounting.treasury_transfer_origin(uuid,text)",
    ):
        assert (
            conn.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",
                (role, function),
            ).fetchone()["allowed"]
            is False
        )
    for table in (
        "accounting.treasury_transfer_preparations",
        "accounting.treasury_transfer_postings",
        "accounting.treasury_transfer_posting_status",
    ):
        assert (
            conn.execute(
                "SELECT has_table_privilege(%s,%s,'SELECT') AS allowed", (role, table)
            ).fetchone()["allowed"]
            is False
        )
