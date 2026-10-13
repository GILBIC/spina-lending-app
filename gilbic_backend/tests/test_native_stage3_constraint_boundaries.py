"""The aged-proof boundary must run all guards and preserve their failures."""

from types import SimpleNamespace

import pytest
from native_stage3_constraint_boundaries import flush_completed_action


class Connection:
    def __init__(self, *, fail=None, **settings):
        self.statements = []
        self.fail = fail
        self.settings = {
            "statement_timeout_ms": 60000,
            "lock_timeout_ms": 5000,
            "jit": "off",
            "all_initially_deferred": True,
        } | settings

    def execute(self, statement):
        self.statements.append(statement)
        if statement == "SET CONSTRAINTS ALL IMMEDIATE" and self.fail:
            raise self.fail
        return SimpleNamespace(fetchone=lambda: self.settings)


def test_completed_action_flushes_all_then_restores_initial_deferred_mode():
    conn, timings = Connection(), []
    flush_completed_action(conn, "completed_cash", timings)
    assert conn.statements[-2:] == [
        "SET CONSTRAINTS ALL IMMEDIATE",
        "SET CONSTRAINTS ALL DEFERRED",
    ]
    assert timings[0]["phase"] == "completed_cash"
    assert timings[0]["elapsed_seconds"] >= 0


def test_failed_guard_propagates_without_restoration_or_success_timing():
    original = RuntimeError("exactness guard rejected current source")
    conn, timings = Connection(fail=original), []
    with pytest.raises(RuntimeError) as raised:
        flush_completed_action(conn, "completed_cash", timings)
    assert raised.value is original
    assert conn.statements[-1] == "SET CONSTRAINTS ALL IMMEDIATE"
    assert "SET CONSTRAINTS ALL DEFERRED" not in conn.statements
    assert timings == []


@pytest.mark.parametrize(
    "settings",
    [
        {"statement_timeout_ms": 0},
        {"statement_timeout_ms": 120000},
        {"lock_timeout_ms": 15000},
        {"jit": "on"},
        {"all_initially_deferred": False},
    ],
)
def test_changed_limits_or_initial_modes_stop_before_constraint_changes(settings):
    conn = Connection(**settings)
    with pytest.raises(AssertionError):
        flush_completed_action(conn, "completed_cash", [])
    assert not any(statement.startswith("SET ") for statement in conn.statements)
