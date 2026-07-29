#!/usr/bin/env python3
"""Validate committed or generated Client Info Logs Wave 78 wiring."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "client_info_logs.py"
REPOSITORY_PATH = ROOT / "spina_app" / "repositories" / "client_info_logs.py"
SERVICE_PATH = ROOT / "spina_app" / "services" / "client_info_logs.py"
TAB_PATH = ROOT / "spina_app" / "tabs" / "client_info_logs.py"

INSTALL_START = "# --- BEGIN: Client Info Logs feature installer Wave 78 ---"
INSTALL_END = "# --- END: Client Info Logs feature installer Wave 78 ---"
LEGACY_START = "# --- BEGIN: Easy Client Info Logs tab ---"
MODERN_START = "# --- BEGIN: v24 Modern Client Info Logs UI ---"


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    feature_source = FEATURE_PATH.read_text(encoding="utf-8")
    repository_source = REPOSITORY_PATH.read_text(encoding="utf-8")
    service_source = SERVICE_PATH.read_text(encoding="utf-8")
    tab_source = TAB_PATH.read_text(encoding="utf-8")

    assert app_source.count(INSTALL_START) == 1
    assert app_source.count(INSTALL_END) == 1
    assert app_source.count("_wave78_install_client_info_logs_feature(") == 1
    assert LEGACY_START not in app_source
    assert MODERN_START not in app_source

    for token in (
        "def _spina_cilog_field_label(",
        "def _spina_cilog_fetch_rows(",
        "_spina_orig_app_init_cilog = App.__init__",
        "_spina_orig_refresh_clients_cilog = getattr(App, 'refresh_clients', None)",
        "App._build_client_info_logs_tab = _spina_v24_build_client_info_logs_tab",
    ):
        assert token not in app_source, token

    for token in (
        "def install_client_info_logs_feature(",
        "def fetch_client_info_log_rows(",
        "app_class._build_client_info_logs_tab =",
        "app_class._spina_client_info_logs_wave78_installed = True",
    ):
        assert token in feature_source, token

    for token in (
        "def ensure_client_history_schema(",
        "def fetch_client_history_records(",
    ):
        assert token in repository_source, token

    for token in (
        "def client_info_field_label(",
        "def transform_client_history_records(",
    ):
        assert token in service_source, token

    for token in (
        "def _spina_v24_build_client_info_logs_tab(",
        "def _spina_v24_render_client_info_logs(",
        "def _spina_v24_refresh_client_info_logs(",
    ):
        assert token in tab_source, token

    print("Wave 78 Client Info Logs extraction tests passed.")


if __name__ == "__main__":
    main()
