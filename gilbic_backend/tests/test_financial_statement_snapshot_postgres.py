"""A report must not combine balances from different committed GL snapshots."""

import os
import re
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from test_period_close_postgres import _management_actor, _manual_journal, _period

from gilbic_backend import financial_statements_repository as statements


@pytest.fixture
def isolated_statement_database():
    url = os.environ.get("GILBIC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit disposable PostgreSQL URL required")
    params = conninfo_to_dict(url)
    assert os.environ.get("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    assert params.get("host") in {"127.0.0.1", "localhost", "::1"}
    assert params.get("hostaddr", params["host"]) in {"127.0.0.1", "localhost", "::1"}
    assert not {"service", "servicefile", "options", "passfile"}.intersection(params)
    assert re.fullmatch(r"spina_treasury_validation_[a-f0-9]{24}", params["dbname"])
    name = "spina_statement_snapshot_" + uuid4().hex
    admin_url = make_conninfo(**(params | {"dbname": "postgres"}))
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(name), sql.Identifier(params["dbname"])
            )
        )
        try:
            yield make_conninfo(**(params | {"dbname": name}))
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_statement_pack_uses_one_snapshot_during_concurrent_post(
    monkeypatch, isolated_statement_database
):
    url = isolated_statement_database
    with psycopg.connect(url) as setup:
        actor = _management_actor(setup, uuid4().hex)
        period, start, _ = _period(setup, actor_id=actor, suffix=uuid4().hex)
        _manual_journal(
            setup,
            actor_id=actor,
            posting_date=start,
            description="Initial synthetic income",
            lines=[
                {"account_code": "1010", "debit": "100.00", "credit": "0"},
                {"account_code": "4000", "debit": "0", "credit": "100.00"},
            ],
        )
    monkeypatch.setattr(statements, "open_connection", lambda: psycopg.connect(url))

    class InterleavedReport(statements.PostgresFinancialStatementsRepository):
        def _load_movements(self, cursor, **kwargs):
            rows = super()._load_movements(cursor, **kwargs)
            if kwargs["period_id"] is not None:
                with psycopg.connect(url) as writer:
                    _manual_journal(
                        writer,
                        actor_id=actor,
                        posting_date=start,
                        description="Concurrent synthetic income",
                        lines=[
                            {"account_code": "1010", "debit": "25.00", "credit": "0"},
                            {"account_code": "4000", "debit": "0", "credit": "25.00"},
                        ],
                    )
            return rows

    report = InterleavedReport().load_statement_pack(period_id=period)
    assert report.net_income == Decimal("100.00")
    assert report.unclosed_earnings_to_date == report.net_income
    assert report.total_assets == Decimal("100.00")
    # The next request must see the newly committed journal.
    fresh = statements.PostgresFinancialStatementsRepository().load_statement_pack(
        period_id=period
    )
    assert fresh.net_income == fresh.total_assets == Decimal("125.00")
