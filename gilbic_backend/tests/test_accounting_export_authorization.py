from contextlib import contextmanager
from datetime import date
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend import accounting_export_repository as module


def test_private_wallet_denial_precedes_export_money_and_evidence_reads(monkeypatch):
    actor, period = uuid4(), uuid4()
    queries = []

    class Cursor:
        def execute(self, query, parameters=None):
            query = str(query)
            queries.append(query)
            if "require_disclosure_actor(%s" in query:
                if parameters == (actor, None):
                    return
                assert parameters == (actor, period)
                raise psycopg.errors.InsufficientPrivilege(
                    "Synthetic private wallet denial"
                )

        def fetchone(self):
            return {"guard": "accounting.require_disclosure_actor"}

        def fetchall(self):
            return [{"id": period}]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Connection:
        def cursor(self, **kwargs):
            return Cursor()

    @contextmanager
    def opened():
        yield Connection()

    monkeypatch.setattr(module, "open_connection", opened)
    monkeypatch.setattr(module, "set_json_loads", lambda *args: None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        module.PostgresAccountingExportRepository().load_snapshot(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            actor_user_id=actor,
            include_reporting=True,
        )
    assert queries[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    assert not any(
        "journal_lines" in query or "transaction_timestamp" in query
        for query in queries
    )
