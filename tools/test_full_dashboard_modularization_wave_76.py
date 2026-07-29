#!/usr/bin/env python3
"""Integration and static checks for full Dashboard modularization Wave 76."""
from __future__ import annotations

import math
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from spina_app.features.dashboard import install_dashboard_feature
from spina_app.repositories.dashboard import fetch_dashboard_rows

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPOSITORY_PATH = ROOT / "spina_app" / "repositories" / "dashboard.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "dashboard.py"


def close(actual: float, expected: float, tolerance: float = 0.001) -> None:
    assert math.isclose(float(actual), float(expected), abs_tol=tolerance), (
        actual,
        expected,
    )


def build_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            client_uid TEXT,
            person_uid TEXT,
            name TEXT,
            loan_type TEXT,
            area TEXT,
            principal REAL,
            interest_amount REAL,
            total_to_pay REAL,
            date_released TEXT,
            due_date TEXT,
            payment_start_date TEXT,
            pay_start_offset_days INTEGER,
            is_archived INTEGER DEFAULT 0
        );
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            client_uid TEXT,
            name TEXT,
            loan_type TEXT,
            date TEXT,
            payment REAL
        );
        CREATE TABLE renewals (
            id INTEGER PRIMARY KEY,
            client_uid TEXT,
            loan_type TEXT,
            renew_date TEXT
        );
        """
    )
    clients = [
        (
            "REG-1",
            "P-1",
            "Regular Test",
            "Regular",
            "A",
            5000,
            1000,
            5000,
            "2026-01-01",
            "2026-05-01",
            "",
            1,
            0,
        ),
        (
            "X7-1",
            "P-2",
            "Seven Test",
            "7x7",
            "B",
            5000,
            0,
            0,
            "2026-02-01",
            "2026-06-01",
            "",
            1,
            0,
        ),
        (
            "OLD-1",
            "P-3",
            "Archived Test",
            "Regular",
            "C",
            3000,
            600,
            3600,
            "2026-01-01",
            "2026-05-01",
            "",
            1,
            1,
        ),
    ]
    conn.executemany(
        """INSERT INTO clients
        (client_uid, person_uid, name, loan_type, area, principal,
         interest_amount, total_to_pay, date_released, due_date,
         payment_start_date, pay_start_offset_days, is_archived)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        clients,
    )
    conn.execute(
        "INSERT INTO renewals (client_uid, loan_type, renew_date) VALUES (?,?,?)",
        ("REG-1", "Regular", "2026-02-01"),
    )
    transactions = [
        ("REG-1", "Regular Test", "Regular", "2026-01-20", 1000),
        ("REG-1", "Regular Test", "Regular", "2026-02-02", 2000),
        ("X7-1", "Seven Test", "7x7", "2026-02-02", 100),
        ("X7-1", "Seven Test", "7x7", "2026-02-03", 100),
    ]
    conn.executemany(
        "INSERT INTO transactions (client_uid,name,loan_type,date,payment) VALUES (?,?,?,?,?)",
        transactions,
    )
    conn.commit()
    return conn


def test_repository_integration() -> None:
    conn = build_database()
    logs: list[tuple[str, object]] = []
    app = SimpleNamespace(db=SimpleNamespace(conn=conn))
    rows = fetch_dashboard_rows(
        app,
        log_exc=lambda context, exc=None: logs.append((context, exc)),
        today=date(2026, 2, 3),
    )
    by_uid = {row["client_uid"]: row for row in rows}
    assert set(by_uid) == {"REG-1", "X7-1"}
    assert not logs, logs

    regular = by_uid["REG-1"]
    close(regular["total_to_pay"], 6000)
    close(regular["paid"], 2000)
    close(regular["remaining"], 4000)
    close(regular["completion_pct"], 100.0 / 3.0)
    assert regular["latest_released"] == date(2026, 2, 1)
    assert regular["payment_start"] == date(2026, 2, 2)
    assert regular["due_date"] == date(2026, 6, 1)

    seven = by_uid["X7-1"]
    close(seven["daily_interest"], 35)
    close(seven["interest_basis_principal"], 5000)
    close(seven["total_collected"], 200)
    close(seven["interest_paid"], 70)
    close(seven["paid"], 130)
    close(seven["remaining"], 4870)
    close(seven["completion_pct"], 2.6)
    conn.close()


def test_feature_installer() -> None:
    class DummyApp:
        def __init__(self, *_args, **_kwargs):
            self.base_initialized = True

        def _apply_ui_theme(self, style=None):
            return style

        def apply_role_access(self, *args, **kwargs):
            return (args, kwargs)

        def _on_mode_change(self, *args, **kwargs):
            return (args, kwargs)

    assert install_dashboard_feature(DummyApp)
    assert DummyApp._spina_dashboard_wave76_installed is True
    assert DummyApp._build_dashboard_tab.__name__ == "_spina_v17_build_dashboard_tab"
    assert DummyApp.refresh_dashboard.__name__ == "_spina_v20_refresh_dashboard"
    assert DummyApp._populate_dashboard_tree.__name__ == "_spina_v20_populate_dashboard_tree"
    assert DummyApp._dashboard_visible_rows.__name__ == "_spina_v19_visible_dashboard_rows"
    first_init = DummyApp.__init__
    assert install_dashboard_feature(DummyApp)
    assert DummyApp.__init__ is first_init


def test_static_extraction() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    repository_source = REPOSITORY_PATH.read_text(encoding="utf-8")
    feature_source = FEATURE_PATH.read_text(encoding="utf-8")

    assert app_source.count("# --- BEGIN: Dashboard feature installer Wave 76 ---") == 1
    assert app_source.count("_wave76_install_dashboard_feature(") == 1
    forbidden_main = (
        "def _spina_dashboard_fetch_rows(self):",
        "# --- BEGIN: v17 modern Dashboard UI with easy charts ---",
        "# --- BEGIN: v18 Dashboard contrast + clearer easy charts ---",
        "# --- BEGIN: v19 Dashboard default to all active clients ---",
        "# --- BEGIN: v20 Dashboard relevant charts + visible labels ---",
        "_spina_v17_configure_feature(",
        "App.refresh_dashboard = _spina_v20_refresh_dashboard",
    )
    for token in forbidden_main:
        assert token not in app_source, token

    required_repository = (
        "def fetch_dashboard_rows(",
        "normalized_total_to_pay(",
        "build_cycle_timing(",
        "finalize_cycle_record(record, effective_today)",
        "finalized_rows.sort(key=cycle_sort_key)",
    )
    for token in required_repository:
        assert token in repository_source, token

    required_feature = (
        "def install_dashboard_feature(",
        "configure_dashboard_chart_dependencies(",
        "configure_legacy_dashboard_feature(",
        "app_class._build_dashboard_tab = _spina_v17_build_dashboard_tab",
        "app_class.refresh_dashboard = _spina_v20_refresh_dashboard",
    )
    for token in required_feature:
        assert token in feature_source, token


def main() -> None:
    test_repository_integration()
    test_feature_installer()
    test_static_extraction()
    print("Wave 76 full Dashboard modularization tests passed.")


if __name__ == "__main__":
    main()
