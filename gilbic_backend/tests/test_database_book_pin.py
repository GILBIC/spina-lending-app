from uuid import uuid4

import pytest
from gilbic_backend.config import Settings

from gilbic_backend import database


class ProbeConnection:
    def __init__(self, row):
        self.row = row
        self.closed = False
        self.rolled_back = False

    def execute(self, query):
        assert "accounting.book_identity" in query
        return self

    def fetchone(self):
        return self.row

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.mark.parametrize("actual", [None, (uuid4(),)])
def test_configured_deployment_pin_rejects_unconfigured_or_other_book(
    monkeypatch, actual
):
    conn = ProbeConnection(actual)
    monkeypatch.setattr(database.psycopg, "connect", lambda *args, **kwargs: conn)
    settings = Settings(_env_file=None, expected_accounting_book_id=uuid4())
    with pytest.raises(ValueError, match="Accounting book identity does not match"):
        database.connect_database(settings)
    assert conn.closed


def test_matching_book_pin_leaves_clean_transaction_for_report_isolation(monkeypatch):
    book = uuid4()
    conn = ProbeConnection((book,))
    monkeypatch.setattr(database.psycopg, "connect", lambda *args, **kwargs: conn)
    settings = Settings(_env_file=None, expected_accounting_book_id=book)
    assert database.connect_database(settings) is conn
    assert conn.rolled_back and not conn.closed


def test_wrong_pin_returns_unavailable_readiness_instead_of_throwing(monkeypatch):
    conn = ProbeConnection((uuid4(),))
    monkeypatch.setattr(database.psycopg, "connect", lambda *args, **kwargs: conn)
    assert (
        database.database_ready(
            Settings(_env_file=None, expected_accounting_book_id=uuid4())
        )
        is False
    )
    assert conn.closed
