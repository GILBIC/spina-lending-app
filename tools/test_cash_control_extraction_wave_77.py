#!/usr/bin/env python3
"""Validate the generated Wave 77 Cash Control production wiring."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "cash_control.py"
REPOSITORY_PATH = ROOT / "spina_app" / "repositories" / "cash_control.py"
SERVICE_PATH = ROOT / "spina_app" / "services" / "cash_control.py"
TAB_PATH = ROOT / "spina_app" / "tabs" / "cash_control.py"

INSTALL_START = "# --- BEGIN: Cash Control feature installer Wave 77 ---"
INSTALL_END = "# --- END: Cash Control feature installer Wave 77 ---"
LEGACY_START = (
    "# --- BEGIN: Cash Control tab - percent buffer + net renewal cash forecast + "
    "separated current/forecast safe amounts ---"
)
MODERN_START = (
    "# --- BEGIN: v21 Modern Cash Control UI with graphs, labels, and explanation ---"
)


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    feature_source = FEATURE_PATH.read_text(encoding="utf-8")
    repository_source = REPOSITORY_PATH.read_text(encoding="utf-8")
    service_source = SERVICE_PATH.read_text(encoding="utf-8")
    tab_source = TAB_PATH.read_text(encoding="utf-8")

    assert app_source.count(INSTALL_START) == 1
    assert app_source.count(INSTALL_END) == 1
    assert app_source.count("_wave77_install_cash_control_feature(") == 1
    assert LEGACY_START not in app_source
    assert MODERN_START not in app_source

    forbidden_main = (
        "def _spina_cashctl_get_collection_totals(",
        "def _spina_cashctl_get_average_collection(",
        "def _spina_cashctl_estimated_payoff_with_interest(",
        "def _spina_cashctl_reserve_rows(",
        "def _spina_cashctl_build_tab(",
        "def _spina_cashctl_refresh(",
        "def _spina_cashctl_apply_role(",
        "def _spina_v21_cash_refresh(",
        "App._build_cash_control_tab = _spina_v21_cash_build_tab",
        "App.refresh_cash_control = _spina_v21_cash_refresh",
    )
    for token in forbidden_main:
        assert token not in app_source, token

    required_feature = (
        "def install_cash_control_feature(",
        "def refresh_cash_control(",
        "app_class._build_cash_control_tab = _spina_v21_cash_build_tab",
        "app_class._spina_cash_control_wave77_installed = True",
    )
    for token in required_feature:
        assert token in feature_source, token

    required_repository = (
        "def fetch_collection_totals(",
        "def fetch_average_collection(",
        "def fetch_x7_cycle_payments(",
    )
    for token in required_repository:
        assert token in repository_source, token

    required_service = (
        "def estimated_payoff_with_interest(",
        "def build_reserve_rows(",
        "def calculate_safe_cash(",
    )
    for token in required_service:
        assert token in service_source, token

    assert "def _spina_v21_cash_build_tab(" in tab_source
    assert "def _spina_v21_cash_draw_charts(" in tab_source
    print("Wave 77 generated Cash Control extraction tests passed.")


if __name__ == "__main__":
    main()
