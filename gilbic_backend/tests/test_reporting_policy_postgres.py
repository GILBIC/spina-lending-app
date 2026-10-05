"""Retained reporting judgments do not alter the posted ledger."""

from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.financial_reporting import cash_flow_statement
from gilbic_backend.reporting_evidence_repository import read_reporting_policy
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_accounting_book_postgres import book_db as _book_db
from test_liability_control_postgres import liabilities as _liabilities
from test_liability_control_postgres import line
from test_period_close_postgres import _body

book_db = _book_db
liabilities = _liabilities
MIGRATION = Path(__file__).resolve().parents[1] / "sql/0147_add_reporting_evidence.sql"


@pytest.fixture
def reporting_db(liabilities):
    f = liabilities
    if MIGRATION.exists():
        f["conn"].execute(_body(MIGRATION.read_text(encoding="utf-8")))
    f["period"] = (
        f["conn"]
        .execute(
            "SELECT id FROM accounting.fiscal_periods WHERE start_date=%s", (f["day"],)
        )
        .fetchone()[0]
    )
    return f


def policy(f, *, request=None, expected_version=0, **changes):
    payload = {
        "cash_account_codes": ["1010", "1020", "1030"],
        "framework_label": "Internal accrual lending reports",
        "notes": [
            {
                "title": "Basis",
                "text": "Synthetic management reports only.",
                "evidence_reference": "test:policy-note",
                "evidence_digest": "b" * 64,
            }
        ],
        "evidence_reference": "test:reporting-policy",
        "evidence_digest": "a" * 64,
        "reviewed": True,
    }
    payload.update(changes)
    try:
        return (
            f["conn"]
            .execute(
                "SELECT accounting.retain_reporting_policy(%s,%s,%s,%s,%s,%s)",
                (
                    request or uuid4(),
                    f["book"],
                    f["period"],
                    expected_version,
                    Jsonb(payload),
                    f["actor"],
                ),
            )
            .fetchone()[0]
        )
    except psycopg.errors.UndefinedFunction:
        pytest.fail("Retained reporting policy function is not implemented")


def test_reporting_policy_is_immutable_exact_and_book_bound(reporting_db):
    f = reporting_db
    request = uuid4()
    identity = policy(f, request=request)
    assert policy(f, request=request) == identity
    with (
        pytest.raises(psycopg.Error, match="conflict|changed"),
        f["conn"].transaction(),
    ):
        policy(f, request=request, framework_label="Changed interpretation")
    with pytest.raises(psycopg.Error, match="immutable"), f["conn"].transaction():
        f["conn"].execute(
            "DELETE FROM accounting.reporting_policy_versions WHERE id=%s", (identity,)
        )
    with pytest.raises(psycopg.Error, match="book"), f["conn"].transaction():
        policy(f | {"book": uuid4()}, expected_version=1)


@pytest.mark.parametrize("codes", [["1100"], ["1010", "1010"], [], ["9999"]])
def test_cash_definition_requires_known_unique_cash_controls(reporting_db, codes):
    with pytest.raises(psycopg.Error, match="cash"), reporting_db["conn"].transaction():
        policy(reporting_db, cash_account_codes=codes)


@pytest.mark.parametrize(
    "change",
    [
        {"cash_account_codes": [1010]},
        {
            "notes": [
                {
                    "title": "Basis",
                    "text": "\n\t",
                    "evidence_reference": "test:blank",
                    "evidence_digest": "b" * 64,
                }
            ]
        },
    ],
)
def test_reporting_evidence_does_not_coerce_codes_or_accept_blank_notes(
    reporting_db, change
):
    with pytest.raises(psycopg.Error), reporting_db["conn"].transaction():
        policy(reporting_db, **change)


def test_policy_versions_require_fresh_review_and_current_authority(reporting_db):
    f = reporting_db
    request = uuid4()
    first = policy(f, request=request)
    second = policy(
        f, expected_version=1, framework_label="Revised internal presentation"
    )
    assert second != first
    assert policy(f, request=request) == first
    with pytest.raises(psycopg.Error, match="version"), f["conn"].transaction():
        policy(f, expected_version=1)
    f["conn"].execute(
        "UPDATE core.users SET status='inactive' WHERE id=%s", (f["actor"],)
    )
    with (
        pytest.raises(psycopg.Error, match="Management|permission"),
        f["conn"].transaction(),
    ):
        policy(f, request=request)


@pytest.mark.parametrize(
    "change",
    [
        "code='1099'",
        "system_key='changed_cash'",
        "account_type='expense'",
        "normal_balance='credit'",
        "is_posting=false",
    ],
)
def test_changed_cash_identity_cannot_become_a_complete_zero_report(
    reporting_db, change
):
    f = reporting_db
    policy(f)
    line(f)
    f["conn"].execute("UPDATE accounting.accounts SET " + change + " WHERE code='1010'")
    with f["conn"].cursor(row_factory=dict_row) as cursor:
        changed = read_reporting_policy(cursor, f["period"])
    result = cash_flow_statement(
        policy=changed, opening_cash=0, closing_cash=0, lines=[]
    )
    assert result["status"] == "cash_definition_changed"
    assert result["closing_cash"] is None


def test_retired_cash_control_remains_in_historical_reports(reporting_db):
    f = reporting_db
    policy(f)
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_active=false WHERE code='1010'"
    )
    with f["conn"].cursor(row_factory=dict_row) as cursor:
        retained = read_reporting_policy(cursor, f["period"])
    assert retained["cash_definition_valid"] is True


def test_cash_classification_is_exact_and_creates_no_journal(reporting_db):
    f = reporting_db
    selected = policy(f)
    liability_line = line(f)
    journal, cash_line = (
        f["conn"]
        .execute(
            "SELECT j.id,cash.id FROM accounting.journal_lines original JOIN accounting.journal_entries j ON j.id=original.journal_entry_id JOIN accounting.journal_lines cash ON cash.journal_entry_id=j.id AND cash.line_number=2 WHERE original.id=%s",
            (liability_line,),
        )
        .fetchone()
    )
    before = (
        f["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
    )
    payload = {
        "journal_line_id": str(cash_line),
        "expected_amount": "100.00",
        "expected_version": 0,
        "allocations": [{"category": "financing", "amount": "100.00"}],
        "evidence_reference": "test:financing-contract",
        "evidence_digest": "c" * 64,
        "reviewed": True,
    }
    request = uuid4()
    params = (request, f["book"], selected, Jsonb(payload), f["actor"])
    query = "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)"
    result = f["conn"].execute(query, params).fetchone()[0]
    assert f["conn"].execute(query, params).fetchone()[0] == result
    assert (
        f["conn"]
        .execute("SELECT count(*) FROM accounting.journal_entries")
        .fetchone()[0]
        == before
    )
    with pytest.raises(psycopg.Error, match="exact|amount"), f["conn"].transaction():
        f["conn"].execute(
            query,
            (
                uuid4(),
                f["book"],
                selected,
                Jsonb(payload | {"expected_amount": "99.00"}),
                f["actor"],
            ),
        )
    with pytest.raises(psycopg.Error, match="immutable"), f["conn"].transaction():
        f["conn"].execute("TRUNCATE accounting.cash_flow_classifications")
    assert journal is not None
    f["conn"].execute("UPDATE accounting.accounts SET code='1099' WHERE code='1010'")
    assert f["conn"].execute(query, params).fetchone()[0] == result
    with (
        pytest.raises(psycopg.Error, match="Cash definition changed"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            query,
            (
                uuid4(),
                f["book"],
                selected,
                Jsonb(payload | {"expected_version": 1}),
                f["actor"],
            ),
        )
