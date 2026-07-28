from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from spina_app.client_new_status import (
    _is_client_new,
    configure_client_new_status_dependencies,
)


SELECT_SQL = "SELECT new_until, created_at, date_released FROM clients WHERE name=? AND loan_type=?"


class FakeCursor:
    def __init__(self, row: Any, calls: list[tuple[str, tuple[Any, ...]]]) -> None:
        self.row = row
        self.calls = calls

    def execute(self, sql: str, params: tuple[Any, ...]):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row: Any) -> None:
        self.row = row
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.row, self.calls)


@dataclass
class Host:
    row: Any
    loan_type: str = "Regular"
    use_nested_db: bool = False

    def __post_init__(self) -> None:
        conn = FakeConnection(self.row)
        self.connection = conn
        if self.use_nested_db:
            self.conn = None
            self.db = type("DB", (), {"conn": conn})()
        else:
            self.conn = conn
            self.db = None

    def _mode_filter(self) -> str:
        return self.loan_type


def call(row: Any, ledger_date: str, days=None, *, nested: bool = False):
    host = Host(row=row, use_nested_db=nested)
    result = _is_client_new(host, " Alice ", ledger_date, days)
    assert host.connection.calls == [(SELECT_SQL, ("Alice", "Regular"))]
    return result


def main() -> None:
    configure_client_new_status_dependencies({"_load_ledger_prefs": lambda: {"new_highlight_days": 7}})

    assert call(
        {"new_until": "2026-08-10", "created_at": "2026-01-01", "date_released": "2026-01-01"},
        "2026-08-10",
    ) is True
    assert call(
        {"new_until": "2026-08-09", "created_at": "2026-01-01", "date_released": "2026-01-01"},
        "2026-08-10",
    ) is False
    assert call(
        {"new_until": "", "created_at": "2026-08-01", "date_released": "2026-08-01"},
        "2026-08-02",
        30,
    ) is False
    assert call(
        {"new_until": "not-a-date", "created_at": "2026-08-01", "date_released": "2026-08-01"},
        "2026-08-02",
        30,
    ) is False

    assert call(
        {"new_until": None, "created_at": "2026-08-01", "date_released": "2026-07-01"},
        "2026-08-08",
        7,
    ) is True
    assert call(
        {"new_until": None, "created_at": "2026-08-01", "date_released": "2026-07-01"},
        "2026-08-09",
        7,
    ) is False
    assert call(
        {"new_until": None, "created_at": None, "date_released": "2026-08-01"},
        "2026-08-08",
        "7",
        nested=True,
    ) is True
    assert call((None, None, "2026-08-01"), "2026-08-08", None) is True
    assert call((None, "2026-08-01", "2026-07-01"), "2026-08-08", "") is True
    assert call((None, "2026-08-01", "2026-07-01"), "2026-08-08", 0) is False
    assert call((None, None, None), "2026-08-08", 7) is False

    blank = Host(row=(None, "2026-08-01", "2026-08-01"))
    assert _is_client_new(blank, "   ", "2026-08-01", 7) is False
    assert blank.connection.calls == []

    missing = type("MissingConnection", (), {"_mode_filter": lambda self: "Regular"})()
    assert _is_client_new(missing, "Alice", "2026-08-01", 7) is False

    no_row = Host(row=None)
    assert _is_client_new(no_row, "Alice", "2026-08-01", 7) is False
    assert no_row.connection.calls == [(SELECT_SQL, ("Alice", "Regular"))]

    configure_client_new_status_dependencies({"_load_ledger_prefs": lambda: {"new_highlight_days": 3}})
    assert call((None, "2026-08-01", None), "2026-08-04", None) is True
    assert call((None, "2026-08-01", None), "2026-08-05", None) is False

    print("Wave 70 client-new behavior regression passed")


if __name__ == "__main__":
    main()
