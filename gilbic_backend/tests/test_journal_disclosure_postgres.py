"""Retained mixed-journal decomposition is private, exact and versioned."""

import importlib.util
import json
import os
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_period_close_postgres import _body, _manual_journal
from test_reporting_policy_postgres import book_db as _book_db
from test_reporting_policy_postgres import liabilities as _liabilities
from test_reporting_policy_postgres import policy
from test_reporting_policy_postgres import reporting_db as _reporting_db

book_db = _book_db
liabilities = _liabilities
reporting_db = _reporting_db

MIGRATION = (
    Path(__file__).resolve().parents[1] / "sql/0161_add_journal_disclosure_reviews.sql"
)


@pytest.fixture
def disclosure_db(reporting_db):
    f = reporting_db
    if MIGRATION.exists():
        f["conn"].execute(_body(MIGRATION.read_text(encoding="utf-8")))
    f["policy"] = policy(f)
    return add_mixed_journal(f)


def add_mixed_journal(f):
    f["conn"].execute(
        "INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance) VALUES('1598','test_mixed_asset','Synthetic mixed acquisition','asset','debit')"
    )
    f["journal"], _ = _manual_journal(
        f["conn"],
        actor_id=f["actor"],
        posting_date=f["day"],
        description="Synthetic mixed acquisition",
        lines=[
            {"account_code": "1598", "debit": "1000.00", "credit": "0.00"},
            {"account_code": "1010", "debit": "0.00", "credit": "400.00"},
            {"account_code": "2300", "debit": "0.00", "credit": "600.00"},
        ],
    )
    f["lines"] = [
        str(row[0])
        for row in f["conn"]
        .execute(
            "SELECT id FROM accounting.journal_lines WHERE journal_entry_id=%s ORDER BY line_number",
            (f["journal"],),
        )
        .fetchall()
    ]
    f["conn"].execute(
        "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
        (
            uuid4(),
            f["book"],
            f["policy"],
            Jsonb(
                {
                    "journal_line_id": f["lines"][1],
                    "expected_amount": "-400.00",
                    "expected_version": 0,
                    "allocations": [{"category": "investing", "amount": "-400.00"}],
                    "evidence_reference": "test:cash",
                    "evidence_digest": "a" * 64,
                    "reviewed": True,
                }
            ),
            f["actor"],
        ),
    )
    return f


def financing_policy(f, *, request=None, version=0, codes=None):
    try:
        return (
            f["conn"]
            .execute(
                "SELECT accounting.retain_disclosure_policy(%s,%s,%s,%s,%s,%s)",
                (
                    request or uuid4(),
                    f["book"],
                    f["policy"],
                    version,
                    Jsonb(
                        {
                            "financing_account_codes": ["2300"]
                            if codes is None
                            else codes,
                            "evidence_reference": "test:funding-policy",
                            "evidence_digest": "b" * 64,
                            "reviewed": True,
                        }
                    ),
                    f["actor"],
                ),
            )
            .fetchone()[0]
        )
    except psycopg.errors.UndefinedFunction:
        pytest.fail("Retained financing disclosure policy is not implemented")


def review_payload(f):
    try:
        digest = (
            f["conn"]
            .execute(
                "SELECT accounting.journal_disclosure_digest(%s,%s)",
                (f["journal"], f["policy"]),
            )
            .fetchone()[0]
        )
    except psycopg.errors.UndefinedFunction:
        pytest.fail("Stable mixed-journal review digest is not implemented")

    def part(credit, amount, category):
        return {
            "debit_line_id": f["lines"][0],
            "credit_line_id": credit,
            "amount": amount,
            "classification": category,
            "evidence_reference": "test:asset-funding",
            "evidence_digest": "c" * 64,
        }

    return {
        "journal_entry_id": str(f["journal"]),
        "expected_version": 0,
        "source_digest": digest,
        "components": [
            part(f["lines"][1], "400.00", "cash_investing"),
            part(f["lines"][2], "600.00", "noncash_investing_financing"),
        ],
        "reason": "Asset funded partly in cash and partly by borrowing.",
        "evidence_reference": "test:mixed",
        "evidence_digest": "d" * 64,
        "reviewed": True,
    }


def retain(f, policy_id, payload, request=None):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.retain_journal_disclosure_review(%s,%s,%s,%s,%s)",
            (request or uuid4(), f["book"], policy_id, Jsonb(payload), f["actor"]),
        )
        .fetchone()[0]
    )


def test_mixed_review_retains_exact_snapshot_and_retry(disclosure_db):
    f = disclosure_db
    dp = financing_policy(f)
    payload = review_payload(f)
    request = uuid4()
    assert retain(f, dp, payload, request) == request
    assert retain(f, dp, payload, request) == request
    row = (
        f["conn"]
        .execute(
            "SELECT payload,source_digest,version FROM accounting.journal_disclosure_reviews WHERE id=%s",
            (request,),
        )
        .fetchone()
    )
    assert row == (payload, payload["source_digest"], 1)
    with pytest.raises(psycopg.Error, match="conflict"), f["conn"].transaction():
        retain(f, dp, payload | {"reason": "Changed"}, request)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["components"].pop(),
        lambda p: p["components"].append(deepcopy(p["components"][1])),
        lambda p: p["components"][1].update(amount="600.01"),
        lambda p: p["components"][1].update(amount="599.99"),
        lambda p: p["components"][1].update(amount="600.001"),
        lambda p: p["components"][1].update(amount=600),
        lambda p: p["components"][1].update(debit_line_id=str(uuid4())),
        lambda p: p["components"][1].update(classification="cash_financing"),
        lambda p: p["components"][0].update(classification="noncash_investing"),
        lambda p: p["components"][0].update(classification="cash_financing"),
        lambda p: p.update(source_digest="0" * 64),
        lambda p: p.update(expected_version=1),
        lambda p: p.update(reviewed=False),
    ],
)
def test_database_rejects_inexact_or_stale_review(disclosure_db, mutation):
    f = disclosure_db
    dp = financing_policy(f)
    payload = review_payload(f)
    mutation(payload)
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        retain(f, dp, payload)


def test_review_is_immutable_and_revision_preserves_history(disclosure_db):
    f = disclosure_db
    dp = financing_policy(f)
    payload = review_payload(f)
    first = retain(f, dp, payload)
    second = retain(
        f,
        dp,
        payload
        | {"expected_version": 1, "reason": "Reconfirmed retained source evidence."},
    )
    assert first != second
    for statement in [
        "DELETE FROM accounting.journal_disclosure_reviews",
        "UPDATE accounting.journal_disclosure_reviews SET version=90",
        "TRUNCATE accounting.journal_disclosure_reviews",
    ]:
        with pytest.raises(psycopg.Error, match="immutable"), f["conn"].transaction():
            f["conn"].execute(statement)


@pytest.mark.parametrize("codes", [["1010"], ["2300", "2300"], ["9999"], [2300]])
def test_financing_policy_requires_explicit_compatible_accounts(disclosure_db, codes):
    with pytest.raises(psycopg.Error), disclosure_db["conn"].transaction():
        financing_policy(disclosure_db, codes=codes)


def test_labels_do_not_stale_digest_but_semantics_do(disclosure_db):
    f = disclosure_db
    financing_policy(f)
    original = review_payload(f)["source_digest"]
    f["conn"].execute(
        "UPDATE accounting.accounts SET name='New display label',is_active=false WHERE code='1598'"
    )
    assert review_payload(f)["source_digest"] == original
    f["conn"].execute(
        "UPDATE accounting.accounts SET system_key='changed_meaning' WHERE code='1598'"
    )
    assert review_payload(f)["source_digest"] != original


def test_changed_policy_and_revoked_actor_block_retention(disclosure_db):
    f = disclosure_db
    dp = financing_policy(f)
    payload = review_payload(f)
    request = retain(f, dp, payload)
    financing_policy(f, version=1, codes=[])
    with pytest.raises(psycopg.Error, match="policy"), f["conn"].transaction():
        retain(f, dp, payload | {"expected_version": 1})
    f["conn"].execute(
        "UPDATE core.users SET status='inactive' WHERE id=%s", (f["actor"],)
    )
    with (
        pytest.raises(psycopg.Error, match="Management|permission"),
        f["conn"].transaction(),
    ):
        retain(f, dp, payload, request)


def read_report(f):
    assert importlib.util.find_spec("gilbic_backend.journal_disclosure_repository"), (
        "Disclosure report repository is not implemented"
    )
    from gilbic_backend.journal_disclosure_repository import read_journal_disclosures
    from psycopg.rows import dict_row

    with f["conn"].cursor(row_factory=dict_row) as cursor:
        return read_journal_disclosures(cursor, f["period"], f["actor"])


def test_database_report_includes_mixed_journal_and_exact_financing_rollforward(
    disclosure_db,
):
    f = disclosure_db
    dp = financing_policy(f)
    before = read_report(f)
    assert before["coverage"]["blocked_count"] == 1
    retain(f, dp, review_payload(f))
    result = read_report(f)
    assert result["status"] == "complete_for_posted_ledger"
    assert result["noncash_components"][0]["amount"] == "600.00"
    assert result["financing_liabilities"][0]["closing_balance"] == "600.00"
    assert result["financing_liabilities"][0]["difference"] == "0.00"
    candidate = result["journals"][0]
    assert candidate["review_version"] == 1
    assert candidate["source_digest"] == review_payload(f)["source_digest"]
    assert all(
        "client_id" not in item and "loan_id" not in item for item in candidate["lines"]
    )
    assert "snapshot" not in candidate
    if directory := os.getenv("ACCOUNTING_DISCLOSURE_CONTRACT_DIRECTORY"):
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "journal-disclosures.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )


def test_new_journal_policy_and_cash_revision_produce_current_blockers(disclosure_db):
    f = disclosure_db
    dp = financing_policy(f)
    retain(f, dp, review_payload(f))
    f["conn"].execute(
        "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
        (
            uuid4(),
            f["book"],
            f["policy"],
            Jsonb(
                {
                    "journal_line_id": f["lines"][1],
                    "expected_amount": "-400.00",
                    "expected_version": 1,
                    "allocations": [{"category": "financing", "amount": "-400.00"}],
                    "evidence_reference": "test:revised-cash",
                    "evidence_digest": "a" * 64,
                    "reviewed": True,
                }
            ),
            f["actor"],
        ),
    )
    assert read_report(f)["blockers"][0]["reason"] == "source_changed"
    financing_policy(f, version=1, codes=[])
    assert read_report(f)["blockers"][0]["reason"] == "policy_changed"
    _manual_journal(
        f["conn"],
        actor_id=f["actor"],
        posting_date=f["day"],
        description="Additional real candidate",
        lines=[
            {"account_code": "1598", "debit": "1.00", "credit": "0.00"},
            {"account_code": "2300", "debit": "0.00", "credit": "1.00"},
        ],
    )
    result = read_report(f)
    assert result["coverage"]["journal_count"] == 2
    assert result["coverage"]["blocked_count"] == 2


def test_read_rechecks_live_authority(disclosure_db):
    f = disclosure_db
    financing_policy(f)
    f["conn"].execute(
        "UPDATE core.users SET status='inactive' WHERE id=%s", (f["actor"],)
    )
    with (
        pytest.raises(psycopg.Error, match="Management|permission"),
        f["conn"].transaction(),
    ):
        read_report(f)
