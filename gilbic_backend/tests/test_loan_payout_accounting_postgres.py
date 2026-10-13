"""A real protected loan payout counts cash once before borrower completion."""

import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.treasury_models import COMMAND_ADAPTER
from native_current_schema_test_support import (
    NATIVE_SCHEMA_BASELINE,
    current_native_head,
    install_native_fixture_migration,
    native_schema_definitions,
)
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from test_first_loan_postgres import private_fixture_configuration  # noqa: F401
from test_treasury_loan_payout_postgres import (
    confirm,
    debit,
)
from test_treasury_loan_payout_postgres import (
    payout_case as operational_fixture,
)
from test_treasury_loan_payout_postgres import (
    prepare as prepare_operational,
)
from test_treasury_receipt_accounting_postgres import mapping
from treasury_test_support import actor, evidence, grant_live, version

MIGRATION = (
    Path(__file__).resolve().parents[1] / "sql" / "0157_add_loan_payout_accounting.sql"
)


@pytest.fixture
def payout_database(monkeypatch, request):
    url = os.getenv("GILBIC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit disposable PostgreSQL URL required")
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
            isolated = make_conninfo(**(params | {"dbname": name}))
            monkeypatch.setenv("GILBIC_TEST_DATABASE_URL", isolated)
            with psycopg.connect(isolated, row_factory=dict_row) as conn:
                request.node.stash[NATIVE_SCHEMA_BASELINE] = (
                    native_schema_definitions(conn)
                    if current_native_head(conn)
                    else None
                )
                manager = actor(conn)
                conn.execute(
                    "SELECT accounting.configure_book_identity('synthetic','Synthetic payout book','test:payout-book',%s,%s)",
                    ("a" * 64, manager.user_id),
                )
                if MIGRATION.exists():
                    if (
                        conn.execute(
                            "SELECT to_regprocedure('accounting.treasury_transfer_mapping_snapshot(uuid,uuid)') AS helper"
                        ).fetchone()["helper"]
                        is None
                    ):
                        install_native_fixture_migration(
                            conn,
                            MIGRATION.with_name(
                                "0153_add_treasury_transfer_accounting.sql"
                            ),
                        )
                    install_native_fixture_migration(conn, MIGRATION)
            yield isolated
        finally:
            assert re.fullmatch(r"spina_treasury_validation_[a-f0-9]{24}", name)
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def payout_accounting(payout_database, monkeypatch, tmp_path):
    operational = operational_fixture.__wrapped__(monkeypatch, tmp_path)
    f = next(operational)
    try:
        conn = f["connection"]
        owner = f["owner"]
        grant_live(conn, owner.user_id, "treasury.view", "treasury.account.manage")
        conn.execute(
            "INSERT INTO treasury.account_access(account_id,user_id,permissions,private_history,granted_by) VALUES(%s,%s,ARRAY['treasury.view','treasury.account.manage'],true,%s) ON CONFLICT(account_id,user_id) DO UPDATE SET private_history=true,permissions=excluded.permissions",
            (f["account_id"], owner.user_id, owner.user_id),
        )
        day = conn.execute(
            "SELECT (now() AT TIME ZONE 'Asia/Manila')::date AS day"
        ).fetchone()["day"]
        period = conn.execute(
            "SELECT accounting.create_fiscal_period('Synthetic payout period',%s,%s,%s) AS id",
            (day - timedelta(days=1), day + timedelta(days=2), owner.user_id),
        ).fetchone()["id"]
        f |= {"conn": conn, "actor": owner, "wallet": f["account_id"], "period": period}
        f["mapping"] = mapping(f)
        conn.commit()
        yield f
    finally:
        operational.close()


def coordinates(f, payout_id, stage):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.loan_payout_coordinates(%s,%s) AS source",
            (payout_id, stage),
        )
        .fetchone()["source"]
    )


def post_stage(f, payout_id, stage):
    source = coordinates(f, payout_id, stage)
    preparation = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_loan_payout_accounting(%s,%s,%s,%s,%s) AS id",
            (payout_id, stage, source["source_digest"], uuid4(), f["owner"].user_id),
        )
        .fetchone()["id"]
    )
    row = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_payout_accounting_preparations WHERE id=%s",
            (preparation,),
        )
        .fetchone()
    )
    params = (
        row["id"],
        row["source_digest"],
        row["confirmation_token"],
        f["owner"].user_id,
    )
    query = "SELECT accounting.post_loan_payout_accounting(%s,%s,%s,%s) AS id"
    journal = f["conn"].execute(query, params).fetchone()["id"]
    assert f["conn"].execute(query, params).fetchone()["id"] == journal
    f["conn"].commit()
    return journal


def balances(f):
    return {
        row["code"]: row["amount"]
        for row in f["conn"]
        .execute(
            "SELECT a.code,sum(l.debit-l.credit) AS amount FROM accounting.journal_lines l JOIN accounting.journal_entries j ON j.id=l.journal_entry_id JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' GROUP BY a.code"
        )
        .fetchall()
    }


def complete_borrower(f, prepared):
    command = COMMAND_ADAPTER.validate_python(
        {
            "action": "loan_payout_first_loan_complete",
            "request_id": uuid4(),
            "account_id": f["account_id"],
            "expected_version": version(f),
            "payout_id": prepared["target_id"],
            "payout_version": 3,
            "evidence_id": evidence(f),
            "reviewed_amount": "1000.00",
            "borrower_confirmed": True,
            "receipt_method": "gcash",
            "acknowledged_at": datetime.now(timezone.utc),
            "borrower_attestation": "Synthetic witnessed borrower receipt of the full protected net proceeds.",
        }
    )
    return f["service"].execute(f["owner"], command)


def test_prepared_payout_is_not_a_cash_journal(payout_accounting):
    f = payout_accounting
    _, prepared = prepare_operational(f, destination="borrower")
    assert prepared["result"]["payout"]["status"] == "prepared"
    with pytest.raises(psycopg.Error, match="actual.*debit|verified.*debit") as error:
        coordinates(f, prepared["target_id"], "debit")
    assert error.value.sqlstate == "55000"
    f["conn"].rollback()
    assert balances(f) == {}


def test_verified_payout_debit_records_transit_and_fee_once(payout_accounting):
    f = payout_accounting
    _, prepared = prepare_operational(f, destination="borrower")
    debit(f, prepared, fee="2.00")
    post_stage(f, prepared["target_id"], "debit")
    assert balances(f) == {
        "1030": Decimal(-1002),
        "1050": Decimal(1000),
        "5240": Decimal(2),
    }


def test_borrower_completion_clears_transit_without_second_cash_credit(
    payout_accounting,
):
    f = payout_accounting
    _, prepared = prepare_operational(f, destination="collector")
    debit(f, prepared)
    post_stage(f, prepared["target_id"], "debit")
    confirm(f, prepared["target_id"])
    assert balances(f) == {"1030": Decimal(-1000), "1050": Decimal(1000)}
    f["conn"].commit()
    completed = complete_borrower(f, prepared)
    assert completed["result"]["payout"]["status"] == "completed"
    post_stage(f, prepared["target_id"], "completion")
    assert balances(f) == {
        "1030": Decimal(-1000),
        "1050": Decimal(0),
        "1100": Decimal(1000),
    }
