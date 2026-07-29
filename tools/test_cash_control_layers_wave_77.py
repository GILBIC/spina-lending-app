#!/usr/bin/env python3
"""Behavior and structural tests for Cash Control repository/service Wave 77."""
from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from spina_app.calculation_rules import allocate_x7_payments
from spina_app.repositories.cash_control import (
    fetch_average_collection,
    fetch_collection_totals,
    fetch_x7_cycle_payments,
)
from spina_app.services.cash_control import (
    build_reserve_rows,
    calculate_safe_cash,
    estimated_payoff_with_interest,
    parse_percent,
)

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPOSITORY_PATH = ROOT / "spina_app" / "repositories" / "cash_control.py"
SERVICE_PATH = ROOT / "spina_app" / "services" / "cash_control.py"


def close(actual: float, expected: float, tolerance: float = 0.001) -> None:
    assert math.isclose(float(actual), float(expected), abs_tol=tolerance), (
        actual,
        expected,
    )


def build_app() -> SimpleNamespace:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            client_uid TEXT,
            name TEXT,
            loan_type TEXT,
            date TEXT,
            payment REAL
        );
        """
    )
    rows = [
        ("REG-1", "Regular Client", "Regular", "2026-07-01", 100.0),
        ("X7-1", "Emergency Client", "Emer", "2026-07-01", 35.0),
        ("X7-2", "Legacy Seven", "7x7emer", "2026-07-01", 15.0),
        ("REG-1", "Regular Client", "Regular", "2026-07-02", 0.0),
        ("REG-1", "Regular Client", "Regular", "2026-07-03", 250.0),
        ("X7-3", "Seven Client", "7x7", "2026-07-02", 100.0),
        ("X7-3", "Seven Client", "7x7", "2026-07-03", 100.0),
    ]
    conn.executemany(
        "INSERT INTO transactions (client_uid,name,loan_type,date,payment) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return SimpleNamespace(db=SimpleNamespace(conn=conn))


def test_repository_behavior() -> None:
    app = build_app()
    totals = fetch_collection_totals(app, "2026-07-01")
    close(totals["regular"], 100.0)
    close(totals["7x7"], 50.0)
    close(totals["other"], 0.0)
    close(totals["combined"], 150.0)

    average = fetch_average_collection(app, "2026-07-05", window_days=4)
    # July 1, July 2, and July 3 have non-zero combined collections.
    assert average["active_days"] == 3
    close(average["total"], 600.0)
    close(average["average"], 200.0)

    emer_payments = fetch_x7_cycle_payments(
        app,
        {"client_uid": "X7-1", "name": "Emergency Client"},
        date(2026, 7, 1),
        date(2026, 7, 1),
    )
    legacy_payments = fetch_x7_cycle_payments(
        app,
        {"client_uid": "X7-2", "name": "Legacy Seven"},
        date(2026, 7, 1),
        date(2026, 7, 1),
    )
    assert emer_payments == [(date(2026, 7, 1), 35.0)]
    assert legacy_payments == [(date(2026, 7, 1), 15.0)]
    app.db.conn.close()


def test_payoff_behavior() -> None:
    regular = estimated_payoff_with_interest(
        SimpleNamespace(),
        {"loan_type": "Regular", "remaining": 725.5},
        date(2026, 7, 3),
    )
    close(regular, 725.5)

    payments = [(date(2026, 7, 2), 100.0), (date(2026, 7, 3), 100.0)]
    record = {
        "loan_type": "7x7",
        "principal": 5000.0,
        "payment_start": datetime(2026, 7, 1, 8, 30),
        "client_uid": "X7-3",
        "name": "Seven Client",
    }
    expected = allocate_x7_payments(
        5000.0,
        date(2026, 7, 1),
        payments,
        date(2026, 7, 3),
    )["payoff_with_interest"]
    actual = estimated_payoff_with_interest(
        SimpleNamespace(),
        record,
        date(2026, 7, 3),
        payment_fetcher=lambda *_args, **_kwargs: payments,
    )
    close(actual, expected)


def test_reserve_rows_and_safe_cash() -> None:
    dashboard_rows = [
        {
            "name": "Complete Client",
            "loan_type": "Regular",
            "principal": 1000.0,
            "remaining": 200.0,
            "completion_pct": 100.0,
            "days_left": 0,
            "status": "Complete",
        },
        {
            "name": "Legacy Emergency",
            "loan_type": "Emergency",
            "principal": 600.0,
            "remaining": 300.0,
            "completion_pct": 80.0,
            "days_left": 10,
            "status": "In Progress",
        },
        {
            "name": "Early Client",
            "loan_type": "Regular",
            "principal": 400.0,
            "remaining": 200.0,
            "completion_pct": 20.0,
            "days_left": 90,
            "status": "In Progress",
        },
    ]
    app = SimpleNamespace(_dashboard_rows=dashboard_rows)
    reserves = build_reserve_rows(
        app,
        14,
        selected_date="2026-07-01",
        payoff_estimator=lambda _app, row, _date: row.get("remaining", 0.0),
    )
    assert [row["name"] for row in reserves] == [
        "Complete Client",
        "Legacy Emergency",
        "Early Client",
    ]
    assert len(reserves) == 3
    assert "interest included" in reserves[1]["reserve_reason"]
    close(sum(row["reserve_amount"] for row in reserves), 2000.0)

    summary = calculate_safe_cash(
        cash_on_hand=1000.0,
        today_collection=500.0,
        average_daily_collection=100.0,
        forecast_days=2,
        buffer_percent=10.0,
        reserve_rows=reserves,
    )
    close(summary["reserve_total"], 2000.0)
    close(summary["expected_renewal_payoff"], 700.0)
    close(summary["net_renewal_need"], 1300.0)
    close(summary["current_available"], 1500.0)
    close(summary["current_buffer"], 150.0)
    close(summary["safe_now"], 50.0)
    close(summary["forecast_available"], 1700.0)
    close(summary["forecast_buffer"], 170.0)
    close(summary["forecast_safe"], 230.0)


def test_percent_parser() -> None:
    close(parse_percent("10%"), 10.0)
    close(parse_percent("0.10"), 10.0)
    close(parse_percent("200"), 100.0)
    close(parse_percent("-5"), 0.0)
    close(parse_percent("bad", default=12.0), 12.0)


def test_static_safety() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    repository_source = REPOSITORY_PATH.read_text(encoding="utf-8")
    service_source = SERVICE_PATH.read_text(encoding="utf-8")

    # This stage adds tested layers but deliberately leaves production wiring intact.
    assert app_source.count(
        "# --- BEGIN: Cash Control tab - percent buffer + net renewal cash forecast + separated current/forecast safe amounts ---"
    ) == 1
    assert "def fetch_collection_totals(" in repository_source
    assert "def fetch_average_collection(" in repository_source
    assert "def fetch_x7_cycle_payments(" in repository_source
    assert "'7x7emer','emer','emergency'" in repository_source
    assert "def estimated_payoff_with_interest(" in service_source
    assert "def build_reserve_rows(" in service_source
    assert "def calculate_safe_cash(" in service_source
    assert "if isinstance(value, datetime):" in service_source

    lowered_repository = repository_source.lower()
    lowered_service = service_source.lower()
    for forbidden in ("insert into", "update transactions", "delete from", "alter table"):
        assert forbidden not in lowered_repository, forbidden
    assert "import tkinter" not in lowered_repository
    assert "from tkinter" not in lowered_repository
    assert "import tkinter" not in lowered_service
    assert "from tkinter" not in lowered_service


def main() -> None:
    test_repository_behavior()
    test_payoff_behavior()
    test_reserve_rows_and_safe_cash()
    test_percent_parser()
    test_static_safety()
    print("Wave 77 Cash Control repository/service tests passed.")


if __name__ == "__main__":
    main()
