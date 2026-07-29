#!/usr/bin/env python3
"""Guarded extraction of all remaining dashboard code from the desktop entry file."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

CORE_START = "# --- BEGIN: Dashboard tab - finishing loans based on latest released date ---"
CORE_END = "# --- END: Dashboard tab - finishing loans based on latest released date ---"
MODERN_START = "# --- BEGIN: v17 modern Dashboard UI with easy charts ---"
MODERN_END = "# --- END: v20 Dashboard relevant charts + visible labels ---"
INSTALL_START = "# --- BEGIN: Dashboard feature installer Wave 76 ---"
INSTALL_END = "# --- END: Dashboard feature installer Wave 76 ---"

INSTALL_BLOCK = f'''{INSTALL_START}
from spina_app.features.dashboard import (
    install_dashboard_feature as _wave76_install_dashboard_feature,
)

_wave76_install_dashboard_feature(
    globals().get("App"),
    log_exc=globals().get("_log_exc"),
    log_suppressed_once=globals().get("_log_suppressed_once"),
)
{INSTALL_END}'''

MODERN_REMOVAL_BLOCK = '''# --- BEGIN: Dashboard legacy patch blocks removed Wave 76 ---
# Dashboard presentation, charts, filters, role handling, and runtime hooks now
# live behind spina_app.features.dashboard.install_dashboard_feature().
# --- END: Dashboard legacy patch blocks removed Wave 76 ---'''

LATE_BRIDGE_PATTERN = re.compile(
    r"\n# Dashboard presentation callback bridge configured in Wave 28\.\n"
    r"_spina_v17_configure_feature\(\n"
    r"\s*draw_v18_charts=_spina_v18_draw_dashboard_charts,\n"
    r"\s*draw_v20_charts=_spina_v20_draw_dashboard_charts,\n"
    r"\)\n",
    re.MULTILINE,
)


def replace_marked_block(
    source: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    if source.count(start_marker) != 1 or source.count(end_marker) != 1:
        raise RuntimeError(
            f"Expected one guarded block for {start_marker!r}; "
            f"found starts={source.count(start_marker)} ends={source.count(end_marker)}"
        )
    start = source.index(start_marker)
    end = source.index(end_marker, start) + len(end_marker)
    return source[:start] + replacement + source[end:]


def validate_result(source: str) -> None:
    required = (
        INSTALL_START,
        "from spina_app.features.dashboard import (",
        "_wave76_install_dashboard_feature(",
        MODERN_REMOVAL_BLOCK.splitlines()[0],
    )
    forbidden = (
        CORE_START,
        MODERN_START,
        "def _spina_dashboard_fetch_rows(self):",
        "_spina_v17_configure_feature(",
        "App.refresh_dashboard = _spina_v20_refresh_dashboard",
        "Dashboard presentation callback bridge configured in Wave 28.",
    )
    for token in required:
        if token not in source:
            raise RuntimeError(f"Wave 76 result missing required token: {token}")
    for token in forbidden:
        if token in source:
            raise RuntimeError(f"Wave 76 result retained legacy token: {token}")
    if source.count(INSTALL_START) != 1 or source.count(INSTALL_END) != 1:
        raise RuntimeError("Wave 76 installer block must appear exactly once")


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    if INSTALL_START in source:
        validate_result(source)
        print("Wave 76 full dashboard modularization already applied: changed=False")
        return

    source = replace_marked_block(source, CORE_START, CORE_END, INSTALL_BLOCK)
    source = replace_marked_block(
        source,
        MODERN_START,
        MODERN_END,
        MODERN_REMOVAL_BLOCK,
    )
    source, bridge_count = LATE_BRIDGE_PATTERN.subn("\n", source, count=1)
    if bridge_count != 1:
        raise RuntimeError(
            "Expected one late dashboard chart callback bridge; "
            f"replaced={bridge_count}"
        )

    validate_result(source)
    APP.write_text(source, encoding="utf-8")
    print("Wave 76 full dashboard modularization applied: changed=True")


if __name__ == "__main__":
    main()
