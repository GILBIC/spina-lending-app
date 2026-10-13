"""Two synthetic databases prove application binding, not infrastructure ACLs."""

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.config import Settings
from gilbic_backend.database import connect_database, open_connection
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.pq import TransactionStatus
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_period_close_postgres import _management_actor, _manual_journal, _period

from gilbic_backend import financial_statements_repository as statements

isolated_statement_database = _isolated_statement_database


def _seed(url, label, amount):
    migration = (
        Path(__file__).resolve().parents[1]
        / "sql"
        / "0144_add_accounting_book_identity.sql"
    )
    with psycopg.connect(url) as connection:
        connection.execute(migration.read_text(encoding="utf-8"))
        actor = _management_actor(connection, uuid4().hex)
        book = connection.execute(
            "SELECT accounting.configure_book_identity('owner_operations',%s,'test:database-isolation',%s,%s)",
            (label, "c" * 64, actor),
        ).fetchone()[0]
        period, start, _ = _period(connection, actor_id=actor, suffix=uuid4().hex)
        journal, _ = _manual_journal(
            connection,
            actor_id=actor,
            posting_date=start,
            description=label,
            lines=[
                {"account_code": "1010", "debit": amount, "credit": "0"},
                {"account_code": "4000", "debit": "0", "credit": amount},
            ],
        )
    return book, period, journal


def test_two_database_books_keep_journals_separate_and_reject_wrong_pin(
    isolated_statement_database, monkeypatch
):
    first_url = isolated_statement_database
    parameters = conninfo_to_dict(first_url)
    second_name = "spina_book_peer_" + uuid4().hex
    second_url = make_conninfo(**(parameters | {"dbname": second_name}))
    admin_url = make_conninfo(**(parameters | {"dbname": "postgres"}))
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(second_name), sql.Identifier(parameters["dbname"])
            )
        )
        try:
            first_book, first_period, first_journal = _seed(
                first_url, "Synthetic isolation A", "111.00"
            )
            second_book, second_period, second_journal = _seed(
                second_url, "Synthetic isolation B", "222.00"
            )
            assert first_book != second_book
            first_settings = Settings(
                database_url=first_url,
                expected_accounting_book_id=first_book,
                _env_file=None,
            )
            second_settings = Settings(
                database_url=second_url,
                expected_accounting_book_id=second_book,
                _env_file=None,
            )

            for settings, expected, excluded in (
                (first_settings, first_journal, second_journal),
                (second_settings, second_journal, first_journal),
            ):
                with connect_database(settings) as connection:
                    assert connection.info.transaction_status == TransactionStatus.IDLE
                    assert connection.execute(
                        "SELECT id FROM accounting.journal_entries WHERE id=%s",
                        (expected,),
                    ).fetchone() == (expected,)
                    assert (
                        connection.execute(
                            "SELECT id FROM accounting.journal_entries WHERE id=%s",
                            (excluded,),
                        ).fetchone()
                        is None
                    )

            with pytest.raises(ValueError, match="does not match"):
                connect_database(
                    Settings(
                        database_url=second_url,
                        expected_accounting_book_id=first_book,
                        _env_file=None,
                    )
                )

            monkeypatch.setattr(
                statements, "open_connection", lambda: open_connection(first_settings)
            )
            first_pack = (
                statements.PostgresFinancialStatementsRepository().load_statement_pack(
                    period_id=first_period
                )
            )
            monkeypatch.setattr(
                statements, "open_connection", lambda: open_connection(second_settings)
            )
            second_pack = (
                statements.PostgresFinancialStatementsRepository().load_statement_pack(
                    period_id=second_period
                )
            )
            assert first_pack.book_identity.book_id == first_book
            assert second_pack.book_identity.book_id == second_book
            assert first_pack.net_income == Decimal("111.00")
            assert second_pack.net_income == Decimal("222.00")
        finally:
            admin.execute(
                sql.SQL("DROP DATABASE {}").format(sql.Identifier(second_name))
            )
