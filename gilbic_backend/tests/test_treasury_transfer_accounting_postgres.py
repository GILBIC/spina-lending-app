"""Actual owned-wallet legs retain separate dates, fees and positive transit."""

import hashlib
import os
import re
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from gilbic_backend.treasury_authorization import require_account
from gilbic_backend.treasury_disbursements import transfer
from gilbic_backend.treasury_models import TransferRecord
from gilbic_backend.treasury_repository import TreasuryService
from test_treasury_receipt_accounting_postgres import (
    RECEIPT_FILE,
    install,
    mapping,
    seed,
)
from treasury_test_support import connect, grant_live

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0150_add_treasury_transfer_accounting.sql"
)


def seed_transfer(conn, tmp_path):
    f = seed(conn)
    store = PrivateEvidenceStore(tmp_path)
    store.put(f["evidence"], RECEIPT_FILE, "application/pdf")
    destination, evidence, transfer_id = uuid4(), uuid4(), uuid4()
    conn.execute(
        "INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) VALUES(%s,%s,'bank','Synthetic destination bank','owner_business',%s)",
        (destination, f["context"], f["actor"].user_id),
    )
    conn.execute(
        "INSERT INTO treasury.account_access(account_id,user_id,permissions,private_history,granted_by) VALUES(%s,%s,ARRAY['treasury.view','treasury.account.manage','treasury.transfer.record'],true,%s)",
        (destination, f["actor"].user_id, f["actor"].user_id),
    )
    conn.execute(
        "UPDATE treasury.account_access SET permissions=array_append(permissions,'treasury.transfer.record') WHERE account_id=%s AND user_id=%s",
        (f["wallet"], f["actor"].user_id),
    )
    grant_live(conn, f["actor"].user_id, "treasury.transfer.record")
    conn.execute(
        "INSERT INTO treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256) VALUES(%s,%s,%s,%s,'recipient','application/pdf',%s,%s)",
        (
            evidence,
            destination,
            f["actor"].user_id,
            f["actor"].registered_device_id,
            len(RECEIPT_FILE),
            hashlib.sha256(RECEIPT_FILE).hexdigest(),
        ),
    )
    store.put(evidence, RECEIPT_FILE, "application/pdf")
    return f | {
        "destination": destination,
        "destination_evidence": evidence,
        "transfer": transfer_id,
        "source_mapping": mapping(f),
        "destination_mapping": mapping(f | {"wallet": destination}),
        "service": TreasuryService(store=store),
        "store": store,
    }


def record_leg(f, leg, *, fee="0.00", day=None):
    conn = f["conn"]
    source = leg == "source"
    account_id = f["wallet"] if source else f["destination"]
    other_id = f["destination"] if source else f["wallet"]
    accounts = {}
    for current in sorted([account_id, other_id], key=str):
        accounts[current] = require_account(
            conn, f["actor"], current, "treasury.transfer.record", private=True
        )
    command = TransferRecord(
        action="transfer_record",
        request_id=uuid4(),
        account_id=account_id,
        expected_version=accounts[account_id]["version"],
        transfer_id=f["transfer"],
        leg=leg,
        other_account_id=other_id,
        other_account_version=accounts[other_id]["version"],
        amount="100.00",
        fee=fee,
        provider=accounts[account_id]["kind"],
        reference=uuid4().hex,
        effective_at=datetime.combine(
            day or (f["day"] if source else f["day"] + timedelta(days=1)),
            time(12),
            tzinfo=timezone(timedelta(hours=8)),
        ),
        evidence_id=f["evidence"] if source else f["destination_evidence"],
        recipient_attestation="Synthetic independent actual leg evidence",
        reason="Synthetic owned-wallet transfer",
    )
    return transfer(f["service"], conn, f["actor"], accounts[account_id], command)[2]


@pytest.fixture
def transfer_db(tmp_path):
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    with connect() as conn:
        try:
            f = seed_transfer(conn, tmp_path)
            if MIGRATION.exists():
                install(conn, MIGRATION)
            yield f
        finally:
            conn.rollback()


def coordinates(f, leg):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.treasury_transfer_coordinates(%s,%s,%s,%s) AS source",
            (f["transfer"], leg, f["source_mapping"], f["destination_mapping"]),
        )
        .fetchone()["source"]
    )


def prepare(f, leg):
    source = coordinates(f, leg)
    result = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_treasury_transfer(%s,%s,%s,%s,%s,%s,%s) AS id",
            (
                f["transfer"],
                leg,
                f["source_mapping"],
                f["destination_mapping"],
                source["source_digest"],
                uuid4(),
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )
    return (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_transfer_preparations WHERE id=%s",
            (result,),
        )
        .fetchone()
    )


def post(f, prep):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.post_treasury_transfer(%s,%s,%s,%s) AS id",
            (
                prep["id"],
                prep["source_digest"],
                prep["confirmation_token"],
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )


def test_transfer_accounting_does_not_seed_money_or_post_from_metadata(transfer_db):
    conn = transfer_db["conn"]
    assert (
        conn.execute(
            "SELECT to_regclass('accounting.treasury_transfer_postings') AS relation"
        ).fetchone()["relation"]
        is not None
    ), "Transfer accounting migration is missing"
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.treasury_transfer_postings"
        ).fetchone()["n"]
        == 0
    )


def test_real_source_debit_preserves_fee_and_positive_transit(transfer_db):
    f = transfer_db
    result = record_leg(f, "source", fee="2.00")
    assert result["transfer"]["status"] == "in_transit"
    source = coordinates(f, "source")
    assert all(
        re.fullmatch(r"\d+\.\d{2}", line[key])
        for line in source["lines"]
        for key in ("debit", "credit")
    ), "Public journal coordinates must preserve exact two-decimal money strings"
    by_code = {line["account_code"]: line for line in source["lines"]}
    assert Decimal(by_code["1040"]["debit"]) == Decimal("100.00")
    assert Decimal(by_code["5240"]["debit"]) == Decimal("2.00")
    assert Decimal(by_code["1030"]["credit"]) == Decimal("102.00")
    assert source["posting_date"] == f["day"].isoformat()
    prep = prepare(f, "source")
    journal = post(f, prep)
    assert post(f, prep) == journal
    status = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_transfer_posting_status WHERE journal_entry_id=%s",
            (journal,),
        )
        .fetchone()
    )
    assert status["exact_posted"] is True and status["correction_pending"] is False


def test_second_actual_leg_preserves_its_date_and_clears_only_its_transfer(transfer_db):
    f = transfer_db
    record_leg(f, "source", fee="2.00")
    source_prep = prepare(f, "source")
    first = post(f, source_prep)
    record_leg(f, "destination")
    assert post(f, source_prep) == first
    source = coordinates(f, "destination")
    assert source["posting_date"] == (f["day"] + timedelta(days=1)).isoformat()
    assert {line["account_code"] for line in source["lines"]} == {"1030", "1040"}
    second = post(f, prepare(f, "destination"))
    assert second != first
    statuses = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.treasury_transfer_posting_status WHERE transfer_id=%s",
            (f["transfer"],),
        )
        .fetchall()
    )
    assert len(statuses) == 2 and all(
        row["exact_posted"] and not row["correction_pending"] for row in statuses
    )
    assert (
        f["conn"]
        .execute(
            "SELECT sum(l.debit-l.credit) AS amount FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE a.code='1040'"
        )
        .fetchone()["amount"]
        == 0
    )


def test_destination_only_retains_actual_credit_without_inventing_source_debit(
    transfer_db,
):
    f = transfer_db
    result = record_leg(f, "destination")
    assert result["transfer"]["status"] == "destination_received_source_unconfirmed"
    with pytest.raises(psycopg.Error, match="source|Source"), f["conn"].transaction():
        coordinates(f, "destination")
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.treasury_transfer_postings")
        .fetchone()["n"]
        == 0
    )
