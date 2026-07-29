#!/usr/bin/env python3
"""Run Wave 74 calculation coverage through the Wave 76 repository adapter."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from spina_app.repositories.dashboard import fetch_dashboard_rows
from tools import test_calculation_regressions_wave_74 as wave74

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPOSITORY = ROOT / "spina_app" / "repositories" / "dashboard.py"
SERVICE = ROOT / "spina_app" / "services" / "loan_cycles.py"


def test_repository_dashboard_integration() -> None:
    conn = wave74.build_dashboard_db()
    app = SimpleNamespace(db=SimpleNamespace(conn=conn))
    rows = fetch_dashboard_rows(app)
    by_uid = {row["client_uid"]: row for row in rows}

    regular = by_uid["REG-1"]
    wave74.close(regular["total_to_pay"], 6000)
    wave74.close(regular["paid"], 2000)
    wave74.close(regular["remaining"], 4000)
    wave74.close(regular["completion_pct"], 100.0 / 3.0)
    assert str(regular["latest_released"]) == "2026-02-01"
    assert str(regular["payment_start"]) == "2026-02-02"
    assert str(regular["due_date"]) == "2026-06-01"

    seven = by_uid["X7-1"]
    wave74.close(seven["total_collected"], 200)
    wave74.close(seven["interest_paid"], 70)
    wave74.close(seven["paid"], 130)
    wave74.close(seven["remaining"], 4870)
    wave74.close(seven["completion_pct"], 2.6)
    wave74.close(seven["daily_interest"], 35)
    wave74.close(seven["interest_basis_principal"], 5000)
    conn.close()


def test_static_delegation() -> None:
    app_source = APP.read_text(encoding="utf-8")
    repository_source = REPOSITORY.read_text(encoding="utf-8")
    service_source = SERVICE.read_text(encoding="utf-8")

    assert "_wave76_install_dashboard_feature(" in app_source
    assert "def _spina_dashboard_fetch_rows" not in app_source
    for token in (
        "normalized_total_to_pay(",
        "build_cycle_timing(",
        "finalize_cycle_record(record, effective_today)",
    ):
        assert token in repository_source, token
    for token in (
        "shift_due_date_for_renewal(",
        "allocation = allocate_x7_payments(",
        'rec["daily_interest"]',
        'rec["interest_basis_principal"]',
    ):
        assert token in service_source, token


def main() -> None:
    app_source = APP.read_text(encoding="utf-8")
    wave74.test_pure_rules()
    test_repository_dashboard_integration()
    wave74.test_adv_and_pass_inputs(app_source)
    test_static_delegation()
    print("Wave 74 compatibility under Wave 76 passed.")


if __name__ == "__main__":
    main()
