"""Synthetic transactional cash preparation; guarded local DB fixture only."""

import os
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.employee_authorization import EmployeeAccessDenied
from gilbic_backend.employee_operations import EmployeeConflict
from test_cash_disbursement_contract import command
from test_employee_operations_postgres import database  # noqa: F401

URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL, reason="Guarded disposable PostgreSQL is not configured"
)


@pytest.fixture
def cash(database):  # noqa: F811
    case = database
    case.connection.execute(
        "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code='employee'",
        (case.users["one"].user_id,),
    )
    case.connection.execute(
        "insert into accounting.fiscal_periods(label,start_date,end_date,status) values(%s,'2036-01-01','2036-01-31','open')",
        ("Synthetic cash " + uuid4().hex,),
    )
    return case


def payload(**values):
    return command(
        id=str(uuid4()), request_id=str(uuid4()), as_of="2036-01-05", **values
    )


@pytest.mark.parametrize("actor", ["one", "owner"])
@pytest.mark.parametrize("cash_code", ["1010", "1030"])
def test_preparation_is_one_exact_draft_with_atomic_history_and_replay(
    cash, actor, cash_code
):
    p = payload(cash_account_code=cash_code)
    result = cash.run(actor, p)
    assert cash.run(actor, p) == dict(result, replayed=True)
    record = cash.record("accounting_preparations", p["id"])
    entry = record["payload"]["journal_entry_id"]
    row = cash.connection.execute(
        "select status,entry_number,created_by_user_id from accounting.journal_entries where id=%s",
        (entry,),
    ).fetchone()
    assert row["status"] == "draft" and row["entry_number"] is None
    assert row["created_by_user_id"] == cash.users[actor].user_id
    rows = cash.connection.execute(
        "select a.code,l.debit,l.credit from accounting.journal_lines l join accounting.accounts a on a.id=l.account_id where journal_entry_id=%s order by line_number",
        (entry,),
    ).fetchall()
    assert [(r["code"], r["debit"], r["credit"]) for r in rows] == [
        ("5210", Decimal("1250.50"), Decimal(0)),
        (cash_code, Decimal(0), Decimal("1250.50")),
    ]
    assert (
        cash.connection.execute(
            "select count(*) n from core.employee_history where request_id=%s",
            (p["request_id"],),
        ).fetchone()["n"]
        == 1
    )
    assert (
        cash.connection.execute(
            "select count(*) n from core.employee_action_receipts where request_id=%s",
            (p["request_id"],),
        ).fetchone()["n"]
        == 1
    )
    assert (
        cash.connection.execute(
            "select count(*) n from core.audit_logs where action='cash_disbursement.prepare' and target_id=%s",
            (p["id"],),
        ).fetchone()["n"]
        == 1
    )
    workspace = cash.workspace(actor)
    assert workspace["capabilities"]["can_prepare_cash_disbursement"] is True
    visible = next(
        r for r in workspace["accounting_preparations"] if r["id"] == p["id"]
    )
    assert visible["allowed_actions"] == []
    with pytest.raises(EmployeeConflict):
        cash.run(actor, dict(p, request_id=str(uuid4()), expected_version=1))
    with pytest.raises(EmployeeConflict):
        cash.run(actor, dict(p, amount="1251.00"))


@pytest.mark.parametrize("change", ["permission", "role", "device", "account"])
def test_authority_is_rechecked_even_for_replay(cash, change):
    p = payload()
    cash.run("one", p)
    user = cash.users["one"]
    if change == "permission":
        cash.connection.execute(
            "delete from core.role_permissions rp using core.roles r where r.id=rp.role_id and r.code='employee' and rp.permission_code='cash_disbursement.prepare'"
        )
    elif change == "role":
        cash.connection.execute(
            "delete from core.user_roles ur using core.roles r where r.id=ur.role_id and r.code='employee' and ur.user_id=%s",
            (user.user_id,),
        )
    elif change == "device":
        cash.connection.execute(
            "update core.devices set status='revoked' where id=%s",
            (user.registered_device_id,),
        )
    else:
        cash.connection.execute(
            "update core.users set status='inactive' where id=%s", (user.user_id,)
        )
    with pytest.raises(EmployeeAccessDenied):
        cash.run("one", p)


def test_collector_and_generic_accounting_path_cannot_bypass_cash_constraints(cash):
    with pytest.raises(EmployeeAccessDenied):
        cash.run("two", payload())
    p = payload()
    cash.run("owner", p)
    with pytest.raises(EmployeeConflict):
        cash.call(
            "owner",
            "accounting_prepare",
            id=p["id"],
            expected_version=1,
            preparation_kind="reconciliation",
            description="Replacement",
            as_of="2036-01-05",
            evidence="Synthetic",
            statement_balance="1.00",
            ledger_balance="1.00",
        )
    assert not cash.workspace("two")["capabilities"]["can_prepare_cash_disbursement"]
    assert not cash.workspace("two")["accounting_preparations"]
    assert (
        cash.connection.execute(
            "select 1 from core.user_roles ur join core.role_permissions rp on rp.role_id=ur.role_id where ur.user_id=%s and rp.permission_code='accounting.journal.manage'",
            (cash.users["one"].user_id,),
        ).fetchone()
        is None
    )


def test_failed_journal_validation_leaves_no_preparation_history_or_receipt(cash):
    p = payload()
    cash.connection.execute(
        "update accounting.accounts set is_active=false where code='5210'"
    )
    before = cash.connection.execute(
        "select count(*) n from accounting.journal_entries"
    ).fetchone()["n"]
    with pytest.raises(psycopg.Error):
        cash.run("one", p)
    assert (
        cash.connection.execute(
            "select count(*) n from accounting.journal_entries"
        ).fetchone()["n"]
        == before
    )
    for table, column in [
        ("employee_accounting_preparations", "id"),
        ("employee_history", "request_id"),
        ("employee_action_receipts", "request_id"),
    ]:
        identity = p["id"] if column == "id" else p["request_id"]
        assert (
            cash.connection.execute(
                f"select count(*) n from core.{table} where {column}=%s", (identity,)
            ).fetchone()["n"]
            == 0
        )


def test_audit_failure_rolls_back_created_journal_history_and_receipt(cash):
    p = payload()
    before = cash.connection.execute(
        "select count(*) n from accounting.journal_entries"
    ).fetchone()["n"]
    cash.connection.execute(
        """create function pg_temp.reject_cash_audit() returns trigger language plpgsql as $$ begin if NEW.action='cash_disbursement.prepare' then raise exception 'Synthetic audit failure'; end if; return NEW; end $$"""
    )
    cash.connection.execute(
        "create trigger synthetic_cash_audit_failure before insert on core.audit_logs for each row execute function pg_temp.reject_cash_audit()"
    )
    with pytest.raises(psycopg.Error, match="Synthetic audit failure"):
        cash.run("one", p)
    assert (
        cash.connection.execute(
            "select count(*) n from accounting.journal_entries"
        ).fetchone()["n"]
        == before
    )
    for table, column in [
        ("employee_accounting_preparations", "id"),
        ("employee_history", "request_id"),
        ("employee_action_receipts", "request_id"),
    ]:
        assert (
            cash.connection.execute(
                f"select count(*) n from core.{table} where {column}=%s",
                (p["id"] if column == "id" else p["request_id"],),
            ).fetchone()["n"]
            == 0
        )
