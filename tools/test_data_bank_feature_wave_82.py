#!/usr/bin/env python3
"""Focused behavior and installer regressions for Data Bank Wave 82."""
from __future__ import annotations

import sqlite3
from datetime import date


def service_checks() -> None:
    from spina_app.services.data_bank import (
        COMBINED_CLOSE_BUCKET,
        auto_close_cutoff,
        combined_close_bucket,
        normalize_close_workflow,
        parse_auto_close_days,
        record_is_closed,
        variance_status,
    )

    assert combined_close_bucket("Regular") == COMBINED_CLOSE_BUCKET == "__ALL__"
    assert combined_close_bucket("7x7") == "__ALL__"
    assert normalize_close_workflow("", variance=0, is_closed=True) == "Resolved"
    assert normalize_close_workflow(None, variance=-1, is_closed=True) == "Pending"
    assert normalize_close_workflow(None, variance=0, is_closed=False) == "Open"
    assert normalize_close_workflow("resolved", variance=99, is_closed=True) == "Resolved"
    assert variance_status(0.004) == "Balanced"
    assert variance_status(2) == "Overage"
    assert variance_status(-2) == "Short"
    assert parse_auto_close_days({"auto_close_after_days": "3"}) == 3
    assert parse_auto_close_days({"auto_close_after_days": -1}) == 0
    assert parse_auto_close_days({"auto_close_after_days": 999}) == 365
    assert auto_close_cutoff(3, today=date(2026, 7, 30)).isoformat() == "2026-07-27"
    assert auto_close_cutoff(0, today=date(2026, 7, 30)) is None
    assert record_is_closed({"is_closed": 1}) is True
    assert record_is_closed({"is_closed": 0}) is False


def repository_checks() -> None:
    from spina_app.repositories import data_bank

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            client_uid TEXT,
            date TEXT,
            payment REAL,
            description TEXT,
            loan_type TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO transactions(name, client_uid, date, payment, description, loan_type) VALUES (?,?,?,?,?,?)",
        [
            ("Regular Client", "r1", "2026-07-20", 100, "", "Regular"),
            ("7x7 Client", "x1", "2026-07-20", 35, "", "7x7"),
            ("Legacy Emergency", "x2", "2026-07-20", 14, "", "Emer"),
            ("Other Day", "r2", "2026-07-21", 50, "", "Regular"),
        ],
    )
    conn.commit()

    class FakeDB:
        def __init__(self, connection):
            self.conn = connection

    data_bank.configure_data_bank_repository_dependencies({})
    db = FakeDB(conn)
    combined = data_bank.get_databank_daily_total(db, "2026-07-20", loan_type="__ALL__")
    regular = data_bank.get_databank_daily_total(db, "2026-07-20", loan_type="Regular")
    x7 = data_bank.get_databank_daily_total(db, "2026-07-20", loan_type="7x7")
    assert round(float(combined), 2) == 149.00
    assert round(float(regular), 2) == 100.00
    # Preserve the current query behavior; legacy Emergency compatibility is
    # protected by the existing calculation/report suites.
    assert round(float(x7), 2) == 35.00


def auto_close_candidate_checks() -> None:
    from spina_app import data_bank_auto_close

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE transactions (date TEXT, payment REAL)")
    conn.executemany(
        "INSERT INTO transactions(date, payment) VALUES (?,?)",
        [("2026-07-20", 100), ("2026-07-21", 0), ("2026-07-22", 50)],
    )

    class FakeDB:
        def __init__(self):
            self.conn = conn

        def get_databank_day_close(self, day):
            return {"is_closed": 1} if day == "2026-07-20" else None

    data_bank_auto_close.configure_data_bank_auto_close_dependencies({})
    assert data_bank_auto_close._spina_auto_close_candidate_dates(FakeDB(), "2026-07-22") == ["2026-07-22"]


def installer_checks() -> None:
    from spina_app.features.data_bank import (
        DATA_BANK_APP_METHODS,
        DATA_BANK_DB_METHODS,
        install_data_bank_feature,
    )

    class FakeApp:
        def __init__(self):
            self.started = True

        def _update_data_toolbar(self, *args, **kwargs):
            return "toolbar-base"

        def _apply_ui_theme(self, *args, **kwargs):
            return "theme-base"

    class FakeLoanDB:
        pass

    def no_op(*args, **kwargs):
        return None

    namespace = {
        "App": FakeApp,
        "LoanDB": FakeLoanDB,
        "_log_exc": no_op,
        "_log_suppressed_once": no_op,
        "_log_ignored": no_op,
        "fmt_currency": lambda value: f"PHP {float(value or 0):,.2f}",
        "_spina_perf_ensure_indexes": lambda db: True,
        "_spina_perf_norm_lt": lambda value: "7x7" if "7" in str(value) else "Regular",
        "_spina_perf_clients_rows": lambda *args, **kwargs: [],
    }

    base_init = FakeApp.__init__
    base_toolbar = FakeApp._update_data_toolbar
    base_theme = FakeApp._apply_ui_theme
    assert install_data_bank_feature(FakeApp, loan_db_cls=FakeLoanDB, namespace=namespace)
    first_init = FakeApp.__init__
    first_app = {name: getattr(FakeApp, name) for name in DATA_BANK_APP_METHODS}
    first_db = {name: getattr(FakeLoanDB, name) for name in DATA_BANK_DB_METHODS}

    assert install_data_bank_feature(FakeApp, loan_db_cls=FakeLoanDB, namespace=namespace)
    second_app = {name: getattr(FakeApp, name) for name in DATA_BANK_APP_METHODS}
    second_db = {name: getattr(FakeLoanDB, name) for name in DATA_BANK_DB_METHODS}

    assert first_init is FakeApp.__init__
    assert first_init is not base_init
    assert first_app == second_app
    assert first_db == second_db
    assert FakeApp._spina_data_bank_wave82_base_update_toolbar is base_toolbar
    assert FakeApp._spina_data_bank_wave82_base_apply_theme is base_theme
    assert FakeApp.refresh_data_grid.__module__ == "spina_app.databank_feature"
    assert FakeApp.export_range_template.__module__ == "spina_app.data_bank_exports"
    assert FakeApp._audit_show_selected.__module__ == "spina_app.data_bank_audit"
    assert FakeLoanDB.get_databank_daily_total.__module__ == "spina_app.repositories.data_bank"
    assert FakeLoanDB._databank_day_close_bucket(None) == "__ALL__"
    assert callable(namespace["_spina_auto_close_after_days_value"])
    assert callable(namespace["_spina_auto_close_candidate_dates"])


def main() -> None:
    service_checks()
    repository_checks()
    auto_close_candidate_checks()
    installer_checks()
    print("Wave 82 complete Data Bank feature regressions passed")


if __name__ == "__main__":
    main()
