#!/usr/bin/env python3
"""Guarded, idempotent Client Info Logs extraction for Wave 78."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

LEGACY_START = "# --- BEGIN: Easy Client Info Logs tab ---"
LEGACY_END = "# --- END: Easy Client Info Logs tab ---"
MODERN_START = "# --- BEGIN: v24 Modern Client Info Logs UI ---"
MODERN_END = "# --- END: v24 Modern Client Info Logs UI ---"
INSTALL_START = "# --- BEGIN: Client Info Logs feature installer Wave 78 ---"
INSTALL_END = "# --- END: Client Info Logs feature installer Wave 78 ---"

INSTALL_BLOCK = f'''{INSTALL_START}
from spina_app.features.client_info_logs import (
    install_client_info_logs_feature as _wave78_install_client_info_logs_feature,
)

_wave78_install_client_info_logs_feature(
    globals().get("App"),
    log_exc=globals().get("_log_exc"),
    log_suppressed_once=globals().get("_log_suppressed_once"),
)
{INSTALL_END}'''


def _replace_marked_block(source: str, start: str, end: str, replacement: str) -> str:
    if source.count(start) != 1 or source.count(end) != 1:
        raise AssertionError(
            f"Expected one marked block for {start!r}; found "
            f"start={source.count(start)} end={source.count(end)}"
        )
    start_index = source.index(start)
    end_index = source.index(end, start_index) + len(end)
    return source[:start_index] + replacement + source[end_index:]


def apply(source: str) -> str:
    already_extracted = (
        source.count(INSTALL_START) == 1
        and source.count(INSTALL_END) == 1
        and LEGACY_START not in source
        and LEGACY_END not in source
        and MODERN_START not in source
        and MODERN_END not in source
    )
    if already_extracted:
        return source

    if INSTALL_START in source or INSTALL_END in source:
        raise AssertionError("Partial Wave 78 installer markers found")

    updated = _replace_marked_block(source, LEGACY_START, LEGACY_END, INSTALL_BLOCK)
    updated = _replace_marked_block(updated, MODERN_START, MODERN_END, "")

    required = (
        INSTALL_START,
        "install_client_info_logs_feature as _wave78_install_client_info_logs_feature",
        "_wave78_install_client_info_logs_feature(",
        INSTALL_END,
    )
    for token in required:
        if updated.count(token) != 1:
            raise AssertionError(f"Wave 78 installer token mismatch: {token!r}")

    forbidden = (
        LEGACY_START,
        LEGACY_END,
        MODERN_START,
        MODERN_END,
        "def _spina_cilog_field_label(",
        "def _spina_cilog_fetch_rows(",
        "_spina_orig_app_init_cilog = App.__init__",
        "_spina_orig_refresh_clients_cilog = getattr(App, 'refresh_clients', None)",
        "App._build_client_info_logs_tab = _spina_v24_build_client_info_logs_tab",
        "App.render_client_info_logs = _spina_v24_render_client_info_logs",
        "App.refresh_client_info_logs = _spina_v24_refresh_client_info_logs",
    )
    for token in forbidden:
        if token in updated:
            raise AssertionError(f"Legacy Client Info Logs token remains: {token!r}")
    return updated


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    updated = apply(source)
    if apply(updated) != updated:
        raise AssertionError("Wave 78 extraction is not idempotent")
    APP_PATH.write_text(updated, encoding="utf-8")
    print("Wave 78 Client Info Logs extraction applied successfully.")


if __name__ == "__main__":
    main()
