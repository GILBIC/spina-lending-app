"""Liability evidence consumes exact posted lines, never a second cash effect."""

import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_accounting_book_postgres import book_db as _book_db_fixture
from test_accounting_book_postgres import configure
from test_period_close_postgres import _body, _manual_journal

MIGRATION = (
    Path(__file__).resolve().parents[1] / "sql/0144_add_liability_control_schedule.sql"
)
book_db = _book_db_fixture
pytestmark = pytest.mark.skipif(
    not os.getenv("GILBIC_TEST_DATABASE_URL"),
    reason="Explicit disposable PostgreSQL URL required",
)


@pytest.fixture
def liabilities(book_db):
    conn, actor = book_db
    if MIGRATION.exists():
        conn.execute(_body(MIGRATION.read_text(encoding="utf-8")))
    book = configure(conn, actor, "owner_operations")
    start = conn.execute(
        "SELECT greatest(current_date, coalesce(max(end_date)+1,current_date)) FROM accounting.fiscal_periods"
    ).fetchone()[0]
    conn.execute(
        "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
        (uuid4().hex, start, start + timedelta(days=12), actor),
    )
    return {"conn": conn, "actor": actor, "book": book, "day": start}


def line(f, amount="100.00", *, code="2000", debit=False, day=0):
    value = {
        "account_code": code,
        "debit": amount if debit else "0",
        "credit": "0" if debit else amount,
    }
    contra = {
        "account_code": "1010",
        "debit": "0" if debit else amount,
        "credit": amount if debit else "0",
    }
    journal, _ = _manual_journal(
        f["conn"],
        actor_id=f["actor"],
        posting_date=f["day"] + timedelta(days=day),
        description="Synthetic liability evidence",
        lines=[value, contra],
    )
    return (
        f["conn"]
        .execute(
            "SELECT id FROM accounting.journal_lines WHERE journal_entry_id=%s AND line_number=1",
            (journal,),
        )
        .fetchone()[0]
    )


def coordinates(f, line_id):
    row = (
        f["conn"]
        .execute(
            """SELECT a.code,l.debit+l.credit,j.posting_date,j.source_type,j.source_reference
        FROM accounting.journal_lines l JOIN accounting.journal_entries j ON j.id=l.journal_entry_id
        JOIN accounting.accounts a ON a.id=l.account_id WHERE l.id=%s""",
            (line_id,),
        )
        .fetchone()
    )
    return {
        "journal_line_id": str(line_id),
        "expected_account_code": row[0],
        "expected_amount": format(row[1], ".2f"),
        "expected_posting_date": str(row[2]),
        "expected_source_type": row[3],
        "expected_source_reference": row[4],
        "evidence_reference": "test:retained-contract",
        "evidence_digest": "a" * 64,
        "reviewed": True,
    }


def register(f, line_id, *, request=None, **changes):
    payload = dict(
        coordinates(f, line_id),
        kind="trade_payable",
        counterparty="Synthetic supplier",
        due_date=str(f["day"] + timedelta(days=5)),
    )
    payload.update(changes)
    try:
        return (
            f["conn"]
            .execute(
                "SELECT accounting.register_liability_obligation(%s,%s,%s,%s)",
                (request or uuid4(), f["book"], Jsonb(payload), f["actor"]),
            )
            .fetchone()[0]
        )
    except psycopg.errors.UndefinedFunction:
        pytest.fail("The protected liability registration function is not implemented")


def movement(
    f, obligation, line_id, *, request=None, kind="settlement", reverses=None, **changes
):
    payload = dict(
        coordinates(f, line_id),
        obligation_id=str(obligation),
        kind=kind,
        reverses_claim_id=str(reverses) if reverses else None,
    )
    payload.update(changes)
    return (
        f["conn"]
        .execute(
            "SELECT accounting.record_liability_movement(%s,%s,%s,%s)",
            (request or uuid4(), f["book"], Jsonb(payload), f["actor"]),
        )
        .fetchone()[0]
    )


def balance(f, obligation, day=12):
    return (
        f["conn"]
        .execute(
            "SELECT outstanding_amount FROM accounting.liability_control_schedule(%s) WHERE obligation_id=%s",
            (f["day"] + timedelta(days=day), obligation),
        )
        .fetchone()[0]
    )


def reversal(f, line_id, day=3):
    journal = (
        f["conn"]
        .execute(
            "SELECT journal_entry_id FROM accounting.journal_lines WHERE id=%s",
            (line_id,),
        )
        .fetchone()[0]
    )
    reversed_id = (
        f["conn"]
        .execute(
            "SELECT accounting.create_manual_reversal_draft(%s,%s,%s,'Synthetic exact reversal')",
            (journal, f["actor"], f["day"] + timedelta(days=day)),
        )
        .fetchone()[0]
    )
    f["conn"].execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)", (reversed_id, f["actor"])
    )
    return (
        f["conn"]
        .execute(
            "SELECT id FROM accounting.journal_lines WHERE journal_entry_id=%s AND line_number=1",
            (reversed_id,),
        )
        .fetchone()[0]
    )


def test_partial_settlement_registers_existing_cash_only_once(liabilities):
    f = liabilities
    credit, debit = line(f), line(f, "40.00", debit=True, day=1)
    journals_before = (
        f["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
    )
    obligation = register(f, credit)
    movement(f, obligation, debit)
    assert balance(f, obligation) == Decimal("60.00")
    assert balance(f, obligation, day=0) == Decimal("100.00")
    assert (
        f["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
        == journals_before
    )
    row = (
        f["conn"]
        .execute(
            "SELECT ledger_balance,schedule_balance,difference,unregistered_line_count FROM accounting.liability_control_reconciliation(%s) WHERE account_code='2000'",
            (f["day"] + timedelta(days=12),),
        )
        .fetchone()
    )
    assert row == (Decimal("60.00"), Decimal("60.00"), Decimal("0.00"), 0)


def test_exact_retry_and_changed_evidence_conflict(liabilities):
    f = liabilities
    credit, request = line(f), uuid4()
    obligation = register(f, credit, request=request)
    assert register(f, credit, request=request) == obligation
    with (
        pytest.raises(psycopg.Error, match="conflict|changed"),
        f["conn"].transaction(),
    ):
        register(f, credit, request=request, evidence_digest="b" * 64)
    with pytest.raises(psycopg.Error, match="claimed"), f["conn"].transaction():
        register(f, credit)


def test_over_settlement_rejected_and_line_cannot_be_reused(liabilities):
    f = liabilities
    obligation = register(f, line(f))
    debit = line(f, "60.00", debit=True, day=1)
    movement(f, obligation, debit)
    with pytest.raises(psycopg.Error, match="claimed"), f["conn"].transaction():
        movement(f, obligation, debit)
    with pytest.raises(psycopg.Error, match="exceed|negative"), f["conn"].transaction():
        movement(f, obligation, line(f, "50.00", debit=True, day=2))
    assert balance(f, obligation) == Decimal("40.00")


def test_only_actual_matching_journal_reversal_restores_liability(liabilities):
    f = liabilities
    obligation = register(f, line(f))
    debit = line(f, "40.00", debit=True, day=1)
    claim = movement(f, obligation, debit)
    with pytest.raises(psycopg.Error, match="reversal"), f["conn"].transaction():
        movement(
            f, obligation, line(f, "40.00", day=2), kind="reversal", reverses=claim
        )
    movement(f, obligation, reversal(f, debit), kind="reversal", reverses=claim)
    assert balance(f, obligation) == Decimal("100.00")


def test_backdated_settlement_cannot_hide_historical_negative_balance(liabilities):
    f = liabilities
    obligation = register(f, line(f))
    debit = line(f, "80.00", debit=True, day=1)
    claim = movement(f, obligation, debit)
    movement(f, obligation, reversal(f, debit, day=4), kind="reversal", reverses=claim)
    with pytest.raises(psycopg.Error, match="exceed|negative"), f["conn"].transaction():
        movement(f, obligation, line(f, "50.00", debit=True, day=3))


@pytest.mark.parametrize(
    "changes",
    [
        {"reviewed": False},
        {"expected_amount": "99.00"},
        {"expected_account_code": "2100"},
        {"expected_source_type": "opening_balance"},
        {"evidence_digest": "bad"},
        {"kind": "borrowing_owner"},
        {"counterparty": "\t"},
        {"unknown": "field"},
    ],
)
def test_mismatched_or_unreviewed_registration_is_rejected(liabilities, changes):
    f = liabilities
    credit = line(f)
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        register(f, credit, **changes)


def test_owner_borrowing_is_liability_not_capital(liabilities):
    f = liabilities
    obligation = register(f, line(f, code="2310"), kind="borrowing_owner")
    assert balance(f, obligation) == Decimal("100.00")
    assert f["conn"].execute(
        "SELECT account_type,normal_balance FROM accounting.accounts WHERE code='2310'"
    ).fetchone() == ("liability", "credit")


def test_original_obligation_reversal_has_no_remaining_liability(liabilities):
    f = liabilities
    credit = line(f)
    obligation = register(f, credit)
    movement(f, obligation, reversal(f, credit), kind="reversal", reverses=obligation)
    assert balance(f, obligation) == Decimal("0.00")


def test_partial_settlement_must_reverse_before_original_recognition(liabilities):
    f = liabilities
    credit = line(f)
    obligation = register(f, credit)
    movement(f, obligation, line(f, "40.00", debit=True, day=1))
    with pytest.raises(psycopg.Error, match="exceed|negative"), f["conn"].transaction():
        movement(
            f, obligation, reversal(f, credit), kind="reversal", reverses=obligation
        )


def test_same_posted_line_cannot_settle_two_obligations(liabilities):
    f = liabilities
    first, second = register(f, line(f)), register(f, line(f))
    debit = line(f, "40.00", debit=True, day=1)
    movement(f, first, debit)
    with pytest.raises(psycopg.Error, match="claimed"), f["conn"].transaction():
        movement(f, second, debit)
    assert balance(f, first) == Decimal("60.00")
    assert balance(f, second) == Decimal("100.00")


def test_movement_retry_retains_claim_and_rejects_changed_evidence(liabilities):
    f = liabilities
    obligation = register(f, line(f))
    debit, request = line(f, "40.00", debit=True, day=1), uuid4()
    claim = movement(f, obligation, debit, request=request)
    assert movement(f, obligation, debit, request=request) == claim
    with (
        pytest.raises(psycopg.Error, match="conflict|changed"),
        f["conn"].transaction(),
    ):
        movement(
            f, obligation, debit, request=request, evidence_reference="test:changed"
        )
    assert balance(f, obligation) == Decimal("60.00")


def test_tax_control_cannot_be_adopted_by_generic_liability_schedule(liabilities):
    f = liabilities
    with (
        pytest.raises(psycopg.Error, match="coordinates|control"),
        f["conn"].transaction(),
    ):
        register(f, line(f, code="2100"))


def test_copied_managed_source_reference_cannot_be_registered_as_manual(liabilities):
    f = liabilities
    journal = (
        f["conn"]
        .execute(
            "SELECT accounting.create_manual_journal_draft(%s,'Synthetic copied source',%s,%s)",
            (
                f["day"],
                f["actor"],
                Jsonb(
                    [
                        {"account_code": "2000", "credit": "100.00", "debit": "0"},
                        {"account_code": "1010", "credit": "0", "debit": "100.00"},
                    ]
                ),
            ),
        )
        .fetchone()[0]
    )
    f["conn"].execute(
        "UPDATE accounting.journal_entries SET source_reference=%s WHERE id=%s",
        (str(uuid4()), journal),
    )
    f["conn"].execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)", (journal, f["actor"])
    )
    credit = (
        f["conn"]
        .execute(
            "SELECT id FROM accounting.journal_lines WHERE journal_entry_id=%s AND line_number=1",
            (journal,),
        )
        .fetchone()[0]
    )
    with pytest.raises(psycopg.Error, match="copy.*managed"), f["conn"].transaction():
        register(f, credit)


def test_private_liability_evidence_has_no_client_grants(liabilities):
    f = liabilities
    for role in ("anon", "authenticated", "service_role"):
        if (
            not f["conn"]
            .execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
            .fetchone()
        ):
            continue
        assert (
            not f["conn"]
            .execute(
                "SELECT has_table_privilege(%s,'accounting.liability_line_claims','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')",
                (role,),
            )
            .fetchone()[0]
        )
        assert (
            not f["conn"]
            .execute(
                "SELECT has_function_privilege(%s,'accounting.register_liability_obligation(uuid,uuid,jsonb,uuid)','EXECUTE')",
                (role,),
            )
            .fetchone()[0]
        )


def test_liability_chart_collision_is_rejected_without_rewriting_account(liabilities):
    f = liabilities
    # Model a pre-migration conflicting meaning. The installed guard separately
    # prevents creating this collision after migration.
    f["conn"].execute(
        "DROP TRIGGER IF EXISTS liability_control_definition ON accounting.accounts"
    )
    f["conn"].execute(
        "UPDATE accounting.accounts SET name='Existing private definition',system_key='existing_private_definition' WHERE code='2310'"
    )
    with pytest.raises(psycopg.Error, match="collision"), f["conn"].transaction():
        f["conn"].execute(_body(MIGRATION.read_text(encoding="utf-8")))
    assert (
        f["conn"]
        .execute("SELECT name FROM accounting.accounts WHERE code='2310'")
        .fetchone()[0]
        == "Existing private definition"
    )


def test_liability_chart_replay_preserves_display_name_and_retirement(liabilities):
    conn = liabilities["conn"]
    conn.execute(
        "UPDATE accounting.accounts SET name='Retired owner financing',is_active=false WHERE code='2310'"
    )
    conn.execute(_body(MIGRATION.read_text(encoding="utf-8")))
    assert conn.execute(
        "SELECT name,is_active,system_key FROM accounting.accounts WHERE code='2310'"
    ).fetchone() == ("Retired owner financing", False, "owner_borrowings")


def test_offsetting_unregistered_lines_are_still_visible(liabilities):
    f = liabilities
    line(f)
    line(f, debit=True, day=1)
    row = (
        f["conn"]
        .execute(
            "SELECT difference,unregistered_line_count FROM accounting.liability_control_reconciliation(%s) WHERE account_code='2000'",
            (f["day"] + timedelta(days=12),),
        )
        .fetchone()
    )
    assert row == (Decimal("0.00"), 2)


def test_live_authority_and_book_are_rechecked(liabilities):
    f = liabilities
    credit = line(f)
    original_book = f["book"]
    f["book"] = uuid4()
    with pytest.raises(psycopg.Error, match="book"), f["conn"].transaction():
        register(f, credit)
    f["book"] = original_book
    f["conn"].execute(
        "UPDATE core.users SET status='inactive' WHERE id=%s", (f["actor"],)
    )
    with (
        pytest.raises(psycopg.Error, match="Management|authority|permission"),
        f["conn"].transaction(),
    ):
        register(f, credit)


def test_registration_audit_failure_rolls_back_line_claim(liabilities):
    f = liabilities
    credit = line(f)
    f[
        "conn"
    ].execute("""CREATE FUNCTION pg_temp.fail_liability_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF NEW.action='accounting.liability.registered' THEN RAISE EXCEPTION 'Synthetic audit failure'; END IF; RETURN NEW; END $$;
        CREATE TRIGGER liability_test_audit BEFORE INSERT ON core.audit_logs FOR EACH ROW EXECUTE FUNCTION pg_temp.fail_liability_audit()""")
    with (
        pytest.raises(psycopg.Error, match="Synthetic audit failure"),
        f["conn"].transaction(),
    ):
        register(f, credit)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.liability_line_claims WHERE journal_line_id=%s",
            (credit,),
        )
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE accounting.liability_obligations SET counterparty='replacement'",
        "DELETE FROM accounting.liability_line_claims",
        "TRUNCATE accounting.liability_line_claims",
    ],
)
def test_retained_schedule_and_evidence_are_immutable(liabilities, statement):
    f = liabilities
    register(f, line(f))
    with pytest.raises(psycopg.Error, match="immutable"), f["conn"].transaction():
        f["conn"].execute(statement)
