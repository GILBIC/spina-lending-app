from __future__ import annotations

import pytest

from gilbic_backend import database


class FakeConnection:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.exited += 1
        if exc_type is None:
            self.commits += 1
        else:
            self.rollbacks += 1
        return False

    def close(self) -> None:
        self.closed = True


def test_open_connection_commits_successful_operation(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(database, "connect_database", lambda settings=None: connection)

    with database.open_connection() as opened:
        assert opened is connection

    assert connection.entered == 1
    assert connection.exited == 1
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed is True


def test_open_connection_rolls_back_failed_operation(monkeypatch) -> None:
    connection = FakeConnection()
    monkeypatch.setattr(database, "connect_database", lambda settings=None: connection)

    with pytest.raises(RuntimeError, match="stop"):
        with database.open_connection():
            raise RuntimeError("stop")

    assert connection.entered == 1
    assert connection.exited == 1
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed is True
