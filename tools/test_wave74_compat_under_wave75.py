#!/usr/bin/env python3
"""Run the Wave 74 suite against the Wave 75 delegated dashboard wiring."""
from __future__ import annotations

from pathlib import Path

from tools import test_calculation_regressions_wave_74 as wave74
from spina_app.services.loan_cycles import (
    build_cycle_timing,
    cycle_sort_key,
    finalize_cycle_record,
)

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "spina_app" / "services" / "loan_cycles.py"


_original_dashboard_namespace = wave74.dashboard_namespace


def dashboard_namespace() -> dict:
    namespace = _original_dashboard_namespace()
    namespace.update(
        {
            "_wave75_build_cycle_timing": build_cycle_timing,
            "_wave75_finalize_cycle_record": finalize_cycle_record,
            "_wave75_cycle_sort_key": cycle_sort_key,
        }
    )
    return namespace


def test_static_wiring(app_source: str) -> None:
    required_app = (
        "# Wave 74: shared calculation rules.",
        "_wave74_normalized_total_to_pay(",
        "_wave75_build_cycle_timing(",
        "_wave75_finalize_cycle_record(rec, today)",
        "rows.sort(key=_wave75_cycle_sort_key)",
    )
    for token in required_app:
        assert token in app_source, token

    service_source = SERVICE.read_text(encoding="utf-8")
    required_service = (
        "shift_due_date_for_renewal(",
        "allocation = allocate_x7_payments(",
        'rec["total_collected"]',
        'rec["interest_paid"]',
        'rec["interest_arrears"]',
    )
    for token in required_service:
        assert token in service_source, token

    assert "if cycle_days > 0 and (due_date is None or due_date < latest_release)" not in app_source


wave74.dashboard_namespace = dashboard_namespace
wave74.test_static_wiring = test_static_wiring


if __name__ == "__main__":
    wave74.main()
    print("Wave 74 compatibility under Wave 75 passed.")
