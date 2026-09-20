"""Opt-in proof against a newly generated disposable database, never live data."""

import csv
import hashlib
import io
import json
import os
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.accounting_export import (
    AccountingExportError,
    build_accounting_export,
)
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from test_accounting_export import unpack

from gilbic_backend import accounting_export_repository as repository_module

DSN = os.environ.get("GILBIC_ACCOUNTING_EXPORT_TEST_DSN", "")
pytestmark = pytest.mark.skipif(
    not DSN, reason="Dedicated disposable accounting export runner is not configured"
)
START = date(2097, 9, 1)
END = date(2097, 9, 30)


def _draft(connection, actor, posting_date, amount="0.01"):
    return connection.execute(
        "SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s)",
        (
            posting_date,
            "Synthetic export José <script> unsafe",
            actor,
            Jsonb(
                [
                    {
                        "account_code": "97001",
                        "description": "=synthetic",
                        "debit": amount,
                        "credit": "0.00",
                    },
                    {
                        "account_code": "97002",
                        "description": "retained control",
                        "debit": "0.00",
                        "credit": amount,
                    },
                ]
            ),
        ),
    ).fetchone()[0]


def _post(connection, actor, posting_date, amount="0.01"):
    entry = _draft(connection, actor, posting_date, amount)
    connection.execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)", (entry, actor)
    )
    return entry


def _counts(dsn):
    with psycopg.connect(dsn) as connection:
        return connection.execute(
            "SELECT (SELECT count(*) FROM accounting.journal_entries), (SELECT count(*) FROM accounting.journal_lines), (SELECT count(*) FROM accounting.journal_events), (SELECT count(*) FROM accounting.cancelled_journal_draft_audit)"
        ).fetchone()


def test_complete_read_only_snapshot_and_concurrent_consistency(monkeypatch):
    params = conninfo_to_dict(DSN)
    assert params["dbname"].startswith("spina_export_test_")
    assert params.get("hostaddr", params.get("host")) in {"127.0.0.1", "::1"}
    suffix = uuid4().hex
    with psycopg.connect(DSN) as connection:
        actor = connection.execute(
            "INSERT INTO core.users(username,full_name,status) VALUES(%s,'Synthetic export manager','active') RETURNING id",
            (f"export-{suffix}",),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO core.user_roles(user_id,role_id) SELECT %s,id FROM core.roles WHERE code='management'",
            (actor,),
        )
        connection.execute(
            "INSERT INTO accounting.fiscal_periods(label,start_date,end_date) VALUES('Synthetic export proof','2097-08-01','2097-10-31')"
        )
        connection.execute(
            "INSERT INTO accounting.accounts(code,system_key,name,account_type,normal_balance) VALUES('97001','export-proof-debit','Synthetic retired asset','asset','debit'),('97002','export-proof-credit','Synthetic control equity','equity','credit')"
        )
        _post(connection, actor, date(2097, 8, 31), "2.00")
        first = None
        for _ in range(260):
            entry = _post(connection, actor, START)
            first = first or entry
        reversal = connection.execute(
            "SELECT accounting.create_manual_reversal_draft(%s,%s,%s,%s)",
            (first, actor, END, "Synthetic reversal evidence"),
        ).fetchone()[0]
        connection.execute(
            "SELECT accounting.post_journal_entry(%s,%s)", (reversal, actor)
        )
        draft = _draft(connection, actor, START, "9000.00")
        cancelled = _draft(connection, actor, START, "90071992547409.91")
        connection.execute(
            "SELECT accounting.cancel_manual_journal_draft(%s,%s)", (cancelled, actor)
        )
        _post(connection, actor, date(2097, 10, 1), "7000.00")
        connection.execute(
            "UPDATE accounting.accounts SET is_active=false WHERE code='97001'"
        )

    @contextmanager
    def opened():
        with psycopg.connect(DSN) as connection:
            yield connection

    monkeypatch.setattr(repository_module, "open_connection", opened)
    before = _counts(DSN)
    repository = repository_module.PostgresAccountingExportRepository()
    snapshot = repository.load_snapshot(start_date=START, end_date=END)
    content = build_accounting_export(
        snapshot, start_date=START, end_date=END, generated_by_user_id=actor
    )
    assert _counts(DSN) == before
    files = unpack(content)
    manifest = json.loads(files["manifest.json"])
    journals = list(csv.DictReader(io.StringIO(files["general-journal.csv"].decode())))
    events = list(csv.DictReader(io.StringIO(files["accounting-audit.csv"].decode())))
    assert len(journals) == 522
    assert len({row["entry_id"] for row in journals}) == 261
    assert len(events) > 520
    assert not any(row["entry_id"] == str(draft) for row in journals)
    assert any(row["entry_id"] == str(draft) for row in events)
    assert any(row["reversal_of_entry_id"] == str(first) for row in journals)
    cancelled_rows = json.loads(files["cancelled-drafts.json"])
    assert len(cancelled_rows) == 1 and cancelled_rows[0]["prior_events"]
    assert cancelled_rows[0]["lines"][0]["debit"] == "90071992547409.91"
    assert manifest["totals"] == {
        "opening_debit": "2.00",
        "opening_credit": "2.00",
        "movement_debit": "2.61",
        "movement_credit": "2.61",
        "closing_debit": "4.59",
        "closing_credit": "4.59",
    }
    assert (
        next(row for row in snapshot["accounts"] if row["account_code"] == "97001")[
            "is_active"
        ]
        is False
    )
    for limit_name, limit_value in (("MAX_ROWS", 1), ("MAX_BYTES", 64)):
        with monkeypatch.context() as context:
            context.setattr(repository_module, limit_name, limit_value)
            with pytest.raises(AccountingExportError) as error:
                repository.load_snapshot(start_date=START, end_date=END)
            assert error.value.code == "oversized"

    # A second writer commits after this export's account aggregation. The same
    # repeatable-read snapshot must still return the old journal/audit rows.
    injected = False
    verified_read_only = False

    class Cursor:
        def __init__(self, inner):
            self.inner = inner

        def __enter__(self):
            self.inner.__enter__()
            return self

        def __exit__(self, *args):
            return self.inner.__exit__(*args)

        def execute(self, query, parameters=None):
            nonlocal injected, verified_read_only
            if not injected and "SELECT journal.id AS entry_id" in str(query):
                self.inner.execute("SHOW transaction_isolation")
                assert (
                    self.inner.fetchone()["transaction_isolation"] == "repeatable read"
                )
                self.inner.execute("SHOW transaction_read_only")
                assert self.inner.fetchone()["transaction_read_only"] == "on"
                verified_read_only = True
                with psycopg.connect(DSN) as writer:
                    writer.execute(
                        "UPDATE accounting.accounts SET is_active=true WHERE code='97001'"
                    )
                    _post(writer, actor, START, "0.03")
                injected = True
            return self.inner.execute(query, parameters)

        def fetchone(self):
            return self.inner.fetchone()

        def __iter__(self):
            return iter(self.inner)

    class Connection:
        def __init__(self, inner):
            self.inner = inner

        def cursor(self, **kwargs):
            return Cursor(self.inner.cursor(**kwargs))

        @property
        def adapters(self):
            return self.inner.adapters

    @contextmanager
    def concurrent_opened():
        with psycopg.connect(DSN) as connection:
            yield Connection(connection)

    monkeypatch.setattr(repository_module, "open_connection", concurrent_opened)
    concurrent = repository.load_snapshot(start_date=START, end_date=END)
    assert injected and verified_read_only
    assert concurrent["journals"] == snapshot["journals"]
    assert concurrent["accounts"] == snapshot["accounts"]
    assert concurrent["audit"] == snapshot["audit"]
    monkeypatch.setattr(repository_module, "open_connection", opened)
    fresh = repository.load_snapshot(start_date=START, end_date=END)
    assert len(fresh["journals"]) == 524

    sample_path = os.environ.get("GILBIC_ACCOUNTING_EXPORT_SAMPLE_OUTPUT")
    if sample_path:
        Path(sample_path).write_bytes(content)
    proof_path = os.environ.get("GILBIC_ACCOUNTING_EXPORT_PROOF_OUTPUT")
    if proof_path:
        Path(proof_path).write_text(
            json.dumps(
                {
                    "status": "passed",
                    "synthetic": True,
                    "production_acceptance": False,
                    "journal_entries": 261,
                    "journal_lines": 522,
                    "journal_events": len(events),
                    "cancelled_drafts": 1,
                    "no_export_mutation": True,
                    "repeatable_read_only_verified": True,
                    "concurrent_commit_excluded": True,
                    "draft_excluded": True,
                    "reversal_retained": True,
                    "retired_account_retained": True,
                    "sample_sha256": hashlib.sha256(content).hexdigest(),
                    "totals": manifest["totals"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
