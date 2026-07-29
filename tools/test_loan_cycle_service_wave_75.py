#!/usr/bin/env python3
"""Regression tests for the Wave 75 loan-cycle service extraction."""
from __future__ import annotations

import ast
import math
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

from spina_app.services.loan_cycles import (  # noqa: E402
    build_cycle_timing,
    cycle_sort_key,
    finalize_cycle_record,
    normalize_payment_start_offset,
)


def close(actual: float, expected: float, tolerance: float = 0.001) -> None:
    assert math.isclose(float(actual), float(expected), abs_tol=tolerance), (actual, expected)


def test_cycle_timing() -> None:
    assert normalize_payment_start_offset(-5) == 0
    assert normalize_payment_start_offset(0) == 0
    assert normalize_payment_start_offset(1) == 1
    assert normalize_payment_start_offset(9) == 1
    assert normalize_payment_start_offset("bad") == 1

    timing = build_cycle_timing(
        "2026-01-01",
        "2026-05-01",
        "2026-02-01",
        1,
        "2026-04-01",
    )
    assert timing["date_released"] == date(2026, 1, 1)
    assert timing["latest_released"] == date(2026, 2, 1)
    assert timing["payment_start"] == date(2026, 2, 2)
    assert timing["due_date"] == date(2026, 6, 1)
    assert timing["days_left"] == 61
    assert 48.0 < timing["time_passed_pct"] < 50.0

    no_release = build_cycle_timing(None, None, None, 0, "2026-07-29")
    assert no_release["latest_released"] == date(2026, 7, 29)
    assert no_release["payment_start"] == date(2026, 7, 29)
    assert no_release["due_date"] is None


def test_regular_finalization() -> None:
    source = {
        "name": "Regular Test",
        "loan_type": "Regular",
        "principal": 5000,
        "total_to_pay": 6000,
        "paid": 2000,
        "days_left": 30,
        "_x7_payments": [],
    }
    result = finalize_cycle_record(source, "2026-01-10")
    close(result["paid"], 2000)
    close(result["remaining"], 4000)
    close(result["completion_pct"], 100.0 / 3.0)
    assert result["status"] == "In Progress"
    assert result["priority"] == 80
    assert "_x7_payments" not in result
    assert "_x7_payments" in source  # input is not mutated


def test_x7_fixed_principal_finalization() -> None:
    source = {
        "name": "Seven Test",
        "loan_type": "7x7",
        "principal": 5000,
        "total_to_pay": 5000,
        "payment_start": "2026-01-02",
        "days_left": 100,
        "paid": 0,
        "_x7_payments": [
            ("2026-01-02", 100),
            ("2026-01-03", 100),
        ],
    }
    result = finalize_cycle_record(source, "2026-01-03")
    close(result["total_collected"], 200)
    close(result["interest_paid"], 70)
    close(result["paid"], 130)
    close(result["remaining"], 4870)
    close(result["completion_pct"], 2.6)
    close(result["daily_interest"], 35)
    close(result["interest_basis_principal"], 5000)
    assert result["payoff_with_interest"] >= result["remaining"]
    assert "_x7_payments" not in result

    # The fixed daily-interest basis must not fall with the remaining balance.
    low_balance = {
        "name": "Boundary Test",
        "loan_type": "7x7",
        "principal": 2000,
        "total_to_pay": 2000,
        "payment_start": "2026-01-01",
        "days_left": 100,
        "_x7_payments": [("2026-01-01", 1500)],
    }
    boundary = finalize_cycle_record(low_balance, "2026-01-02")
    assert boundary["remaining"] < 1000
    close(boundary["daily_interest"], 14)
    close(boundary["interest_basis_principal"], 2000)


def test_sorting() -> None:
    rows = [
        {"name": "B", "priority": 80, "principal": 5000, "completion_pct": 20},
        {"name": "A", "priority": 20, "principal": 1000, "completion_pct": 90},
        {"name": "C", "priority": 80, "principal": 7000, "completion_pct": 10},
    ]
    rows.sort(key=cycle_sort_key)
    assert [row["name"] for row in rows] == ["A", "C", "B"]


def dashboard_function_source(app_source: str) -> str:
    tree = ast.parse(app_source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_spina_dashboard_fetch_rows":
            segment = ast.get_source_segment(app_source, node)
            assert segment
            return segment
    raise AssertionError("_spina_dashboard_fetch_rows not found")


def test_static_wiring() -> None:
    app_source = APP.read_text(encoding="utf-8")
    function_source = dashboard_function_source(app_source)
    required = (
        "_wave75_build_cycle_timing(",
        "_wave75_finalize_cycle_record(rec, today)",
        "rows.sort(key=_wave75_cycle_sort_key)",
    )
    for token in required:
        assert token in function_source, token

    forbidden = (
        "due_date = _wave74_shift_due_date_for_renewal(",
        "allocation = _wave74_allocate_x7_payments(",
        "status, priority = _spina_dash__status_for(",
        "rows.sort(key=lambda x:",
    )
    for token in forbidden:
        assert token not in function_source, token


def main() -> None:
    test_cycle_timing()
    test_regular_finalization()
    test_x7_fixed_principal_finalization()
    test_sorting()
    test_static_wiring()
    print("Wave 75 loan-cycle service tests passed.")


if __name__ == "__main__":
    main()
