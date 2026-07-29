#!/usr/bin/env python3
"""Run Wave 75 service coverage after the dashboard repository extraction."""
from __future__ import annotations

from pathlib import Path

from tools import test_loan_cycle_service_wave_75 as wave75

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPOSITORY = ROOT / "spina_app" / "repositories" / "dashboard.py"
SERVICE = ROOT / "spina_app" / "services" / "loan_cycles.py"


def test_delegated_wiring() -> None:
    app_source = APP.read_text(encoding="utf-8")
    repository_source = REPOSITORY.read_text(encoding="utf-8")
    service_source = SERVICE.read_text(encoding="utf-8")

    assert "def _spina_dashboard_fetch_rows" not in app_source
    assert "_wave76_install_dashboard_feature(" in app_source

    required_repository = (
        "build_cycle_timing(",
        "finalize_cycle_record(record, effective_today)",
        "finalized_rows.sort(key=cycle_sort_key)",
    )
    for token in required_repository:
        assert token in repository_source, token

    required_service = (
        "def build_cycle_timing(",
        "def finalize_cycle_record(",
        "def cycle_sort_key(",
    )
    for token in required_service:
        assert token in service_source, token


def main() -> None:
    wave75.test_cycle_timing()
    wave75.test_regular_finalization()
    wave75.test_x7_fixed_principal_finalization()
    wave75.test_sorting()
    test_delegated_wiring()
    print("Wave 75 compatibility under Wave 76 passed.")


if __name__ == "__main__":
    main()
