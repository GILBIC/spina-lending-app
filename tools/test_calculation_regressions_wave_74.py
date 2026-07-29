#!/usr/bin/env python3
"""Regression coverage for Regular, 7x7, renewals, and ADV/PASS day states."""
from __future__ import annotations

import ast
import math
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
SERVICE_PATH = ROOT / "spina_app" / "services" / "loan_cycles.py"
REPORT_ENGINE_PATH = ROOT / "spina_app" / "report_engine.py"

from spina_app.calculation_rules import (  # noqa: E402
    allocate_x7_payments,
    ceil_thousand_units,
    normalized_total_to_pay,
    shift_due_date_for_renewal,
    x7_daily_interest,
)
from spina_app.services.loan_cycles import (  # noqa: E402
    build_cycle_timing,
    cycle_sort_key,
    finalize_cycle_record,
)


def extract_function(source: str, name: str, namespace: dict):
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, (name, len(matches))
    module = ast.Module(body=[matches[0]], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(APP_PATH), "exec"), namespace)
    return namespace[name]


def close(actual: float, expected: float, tolerance: float = 0.001) -> None:
    assert math.isclose(float(actual), float(expected), abs_tol=tolerance), (actual, expected)


def test_pure_rules() -> None:
    close(normalized_total_to_pay("Regular", 5000, 1000, 5000), 6000)
    close(normalized_total_to_pay("Regular", 5000, 1000, 6500), 6500)
    close(normalized_total_to_pay("7x7", 5000, 999, 9999), 5000)

    shifted = shift_due_date_for_renewal("2026-01-01", "2026-05-01", "2026-02-01")
    assert shifted == date(2026, 6, 1), shifted
    assert shift_due_date_for_renewal("2026-01-01", "2026-05-01", "2026-01-01") == date(2026, 5, 1)

    assert ceil_thousand_units(0) == 0
    assert ceil_thousand_units(1) == 1
    assert ceil_thousand_units(1000) == 1
    assert ceil_thousand_units(1000.01) == 2
    close(x7_daily_interest(5000), 35)
    close(x7_daily_interest(4999.99), 35)
    close(x7_daily_interest(4000), 28)
    close(x7_daily_interest(4000.01), 35)

    two_days = allocate_x7_payments(
        5000,
        "2026-01-01",
        [("2026-01-01", 100), ("2026-01-02", 100)],
        "2026-01-02",
    )
    close(two_days["interest_paid"], 70)
    close(two_days["principal_paid"], 130)
    close(two_days["remaining_principal"], 4870)
    close(two_days["completion_pct"], 2.6)

    interest_only = allocate_x7_payments(
        5000,
        "2026-01-01",
        [("2026-01-01", 20)],
        "2026-01-01",
    )
    close(interest_only["remaining_principal"], 5000)
    close(interest_only["interest_arrears"], 15)
    close(interest_only["payoff_with_interest"], 5015)

    same_day = allocate_x7_payments(
        5000,
        "2026-01-01",
        [("2026-01-01", 100), ("2026-01-01", 150)],
        "2026-01-01",
    )
    close(same_day["total_collected"], 150)
    close(same_day["interest_paid"], 35)
    close(same_day["principal_paid"], 115)
    close(same_day["remaining_principal"], 4885)


def dashboard_namespace() -> dict:
    def parse_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(str(value or "")[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    def as_float(value):
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    def status_for(completion, remaining, days_left):
        if remaining <= 0.004:
            return "Complete", 5
        if completion >= 75:
            return "75%+", 20
        return "In Progress", 80

    return {
        "sqlite3": sqlite3,
        "date": date,
        "datetime": datetime,
        "timedelta": timedelta,
        "_spina_dash__parse_date": parse_date,
        "_spina_dash__float": as_float,
        "_spina_dash__status_for": status_for,
        "_log_exc": lambda *args, **kwargs: None,
        "_wave74_allocate_x7_payments": allocate_x7_payments,
        "_wave74_normalized_total_to_pay": normalized_total_to_pay,
        "_wave74_shift_due_date_for_renewal": shift_due_date_for_renewal,
        "_wave75_build_cycle_timing": build_cycle_timing,
        "_wave75_finalize_cycle_record": finalize_cycle_record,
        "_wave75_cycle_sort_key": cycle_sort_key,
    }


def build_dashboard_db() -> sqlite3.Connection:
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
    conn.execute(
        """INSERT INTO clients
        (client_uid, person_uid, name, loan_type, area, principal, interest_amount,
         total_to_pay, date_released, due_date, payment_start_date,
         pay_start_offset_days, is_archived)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)""",
        ("REG-1", "P-1", "Regular Test", "Regular", "A", 5000, 1000, 5000,
         "2026-01-01", "2026-05-01", "", 1),
    )
    conn.execute(
        """INSERT INTO clients
        (client_uid, person_uid, name, loan_type, area, principal, interest_amount,
         total_to_pay, date_released, due_date, payment_start_date,
         pay_start_offset_days, is_archived)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)""",
        ("X7-1", "P-2", "Seven Test", "7x7", "B", 5000, 0, 0,
         "2026-01-01", "2026-05-01", "", 1),
    )
    conn.execute(
        "INSERT INTO renewals (client_uid, loan_type, renew_date) VALUES (?,?,?)",
        ("REG-1", "Regular", "2026-02-01"),
    )
    conn.execute(
        "INSERT INTO transactions (client_uid,name,loan_type,date,payment) VALUES (?,?,?,?,?)",
        ("REG-1", "Regular Test", "Regular", "2026-01-20", 1000),
    )
    conn.execute(
        "INSERT INTO transactions (client_uid,name,loan_type,date,payment) VALUES (?,?,?,?,?)",
        ("REG-1", "Regular Test", "Regular", "2026-02-02", 2000),
    )
    conn.execute(
        "INSERT INTO transactions (client_uid,name,loan_type,date,payment) VALUES (?,?,?,?,?)",
        ("X7-1", "Seven Test", "7x7", "2026-01-02", 100),
    )
    conn.execute(
        "INSERT INTO transactions (client_uid,name,loan_type,date,payment) VALUES (?,?,?,?,?)",
        ("X7-1", "Seven Test", "7x7", "2026-01-03", 100),
    )
    conn.commit()
    return conn


def test_dashboard_integration(app_source: str) -> None:
    ns = dashboard_namespace()
    norm_lt = extract_function(app_source, "_spina_dash__norm_lt", ns)
    ns["_spina_dash__norm_lt"] = norm_lt
    fetch_rows = extract_function(app_source, "_spina_dashboard_fetch_rows", ns)

    conn = build_dashboard_db()
    app = SimpleNamespace(db=SimpleNamespace(conn=conn))
    rows = fetch_rows(app)
    by_uid = {row["client_uid"]: row for row in rows}

    regular = by_uid["REG-1"]
    close(regular["total_to_pay"], 6000)
    close(regular["paid"], 2000)
    close(regular["remaining"], 4000)
    close(regular["completion_pct"], 100.0 / 3.0)
    assert regular["latest_released"] == date(2026, 2, 1)
    assert regular["payment_start"] == date(2026, 2, 2)
    assert regular["due_date"] == date(2026, 6, 1), regular["due_date"]

    seven = by_uid["X7-1"]
    close(seven["total_collected"], 200)
    close(seven["interest_paid"], 70)
    close(seven["paid"], 130)
    close(seven["remaining"], 4870)
    close(seven["completion_pct"], 2.6)
    assert seven["payoff_with_interest"] >= seven["remaining"]
    conn.close()


def daterange_inclusive(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def test_adv_and_pass_inputs(app_source: str) -> None:
    ns = {
        "_date_soapatch": date,
        "_dt_soapatch": datetime,
        "_daterange_inclusive": daterange_inclusive,
        "_log_suppressed_once": lambda *args, **kwargs: None,
    }
    parser = extract_function(app_source, "parse_advance_ranges", ns)
    ns["parse_advance_ranges"] = parser
    ns["_parse_adv_range_any"] = lambda _text: None

    adv_strip = re.compile(r"\[\s*ADV\s*:[^\]]*\]", re.I)
    ns["_extract_reason_and_color_from_desc"] = lambda desc: (
        adv_strip.sub("", str(desc or "")).strip(),
        "",
    )
    report_source = app_source
    if "def _collect_day_flags_for_month(" not in report_source and REPORT_ENGINE_PATH.exists():
        report_source = REPORT_ENGINE_PATH.read_text(encoding="utf-8")
    collect = extract_function(report_source, "_collect_day_flags_for_month", ns)

    assert parser("[ADV:2026-07-02,2026-07-03,2026-07-05]") == [
        ("2026-07-02", "2026-07-03"),
        ("2026-07-05", "2026-07-05"),
    ]

    txns = [
        {
            "date": "2026-07-01",
            "payment": 300,
            "description": "[ADV:2026-07-01..2026-07-03]",
        },
        {"date": "2026-07-06", "payment": 100, "description": ""},
        {"date": "2026-07-06", "payment": 150, "description": ""},
    ]
    flags = collect(txns, date(2026, 7, 1), date(2026, 7, 31))
    assert flags[date(2026, 7, 1)]["paid"] == 300
    assert not flags[date(2026, 7, 1)].get("adv", False)
    assert flags[date(2026, 7, 2)]["adv"] is True
    assert flags[date(2026, 7, 3)]["adv"] is True
    assert flags[date(2026, 7, 2)]["adv_paid_on"] == {"2026-07-01"}
    assert date(2026, 7, 4) not in flags
    assert flags[date(2026, 7, 6)]["paid"] == 150


def test_static_wiring(app_source: str) -> None:
    required_app = [
        "# Wave 74: shared calculation rules.",
        "_wave74_normalized_total_to_pay(",
        "_wave75_build_cycle_timing(",
        "_wave75_finalize_cycle_record(",
        "rows.sort(key=_wave75_cycle_sort_key)",
    ]
    for token in required_app:
        assert token in app_source, token

    service_source = SERVICE_PATH.read_text(encoding="utf-8")
    required_service = [
        "shift_due_date_for_renewal(",
        "allocate_x7_payments(",
        'rec["total_collected"]',
        'rec["interest_paid"]',
        'rec["interest_arrears"]',
    ]
    for token in required_service:
        assert token in service_source, token

    if "# --- BEGIN: Reports feature installer Wave 80 ---" in app_source:
        report_source = REPORT_ENGINE_PATH.read_text(encoding="utf-8")
        assert "def _collect_day_flags_for_month(" in report_source
        assert "def generate_client_pdf(" in report_source
        assert "_wave74_x7_daily_interest" in report_source

    assert "if cycle_days > 0 and (due_date is None or due_date < latest_release)" not in app_source


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    test_pure_rules()
    test_static_wiring(app_source)
    test_dashboard_integration(app_source)
    test_adv_and_pass_inputs(app_source)
    print("Wave 74 calculation regression tests passed")


if __name__ == "__main__":
    main()
