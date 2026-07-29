#!/usr/bin/env python3
"""Guarded, idempotent Cash Control extraction for Wave 77."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

LEGACY_START = (
    "# --- BEGIN: Cash Control tab - percent buffer + net renewal cash forecast + "
    "separated current/forecast safe amounts ---"
)
LEGACY_END = (
    "# --- END: Cash Control tab - percent buffer + net renewal cash forecast + "
    "separated current/forecast safe amounts ---"
)
MODERN_START = (
    "# --- BEGIN: v21 Modern Cash Control UI with graphs, labels, and explanation ---"
)
MODERN_END = (
    "# --- END: v21 Modern Cash Control UI with graphs, labels, and explanation ---"
)
INSTALL_START = "# --- BEGIN: Cash Control feature installer Wave 77 ---"
INSTALL_END = "# --- END: Cash Control feature installer Wave 77 ---"

INSTALL_BLOCK = f'''{INSTALL_START}
from spina_app.features.cash_control import (
    install_cash_control_feature as _wave77_install_cash_control_feature,
)

_wave77_install_cash_control_feature(
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
        raise AssertionError("Partial Wave 77 installer markers found")

    updated = _replace_marked_block(source, LEGACY_START, LEGACY_END, INSTALL_BLOCK)
    updated = _replace_marked_block(updated, MODERN_START, MODERN_END, "")

    required = (
        INSTALL_START,
        "install_cash_control_feature as _wave77_install_cash_control_feature",
        "_wave77_install_cash_control_feature(",
        INSTALL_END,
    )
    for token in required:
        if updated.count(token) != 1:
            raise AssertionError(f"Wave 77 installer token mismatch: {token!r}")

    forbidden = (
        LEGACY_START,
        LEGACY_END,
        MODERN_START,
        MODERN_END,
        "def _spina_cashctl_get_collection_totals(",
        "def _spina_cashctl_get_average_collection(",
        "def _spina_cashctl_estimated_payoff_with_interest(",
        "def _spina_cashctl_reserve_rows(",
        "def _spina_cashctl_build_tab(",
        "def _spina_cashctl_refresh(",
        "def _spina_cashctl_apply_role(",
        "def _spina_v21_cash_refresh(",
    )
    for token in forbidden:
        if token in updated:
            raise AssertionError(f"Legacy Cash Control token remains: {token!r}")
    return updated


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    updated = apply(source)
    # Prove idempotence before writing.
    if apply(updated) != updated:
        raise AssertionError("Wave 77 extraction is not idempotent")
    APP_PATH.write_text(updated, encoding="utf-8")
    print("Wave 77 Cash Control extraction applied successfully.")


if __name__ == "__main__":
    main()
