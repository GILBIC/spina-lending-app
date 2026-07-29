#!/usr/bin/env python3
"""Run Wave 28 presentation coverage with the Wave 76 feature installer."""
from __future__ import annotations

from pathlib import Path

from tools import test_dashboard_presentation_wave_28 as wave28

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
FEATURE = ROOT / "spina_app" / "features" / "dashboard.py"


def assert_dashboard_startup_wiring() -> None:
    app_source = APP.read_text(encoding="utf-8")
    feature_source = FEATURE.read_text(encoding="utf-8")

    assert app_source.count("_wave76_install_dashboard_feature(") == 1
    assert "from spina_app.features.dashboard import (" in app_source
    assert "from spina_app.tabs.dashboard import (" in feature_source
    for token in (
        "_spina_apply_dashboard_role",
        "_spina_configure_dashboard_tree_theme",
        "_spina_v17_build_dashboard_tab",
        "_spina_v19_visible_dashboard_rows",
        "_spina_v20_populate_dashboard_tree",
        "_spina_v20_refresh_dashboard",
    ):
        assert token in feature_source, token
    assert "def _spina_dashboard_fetch_rows" not in app_source


wave28.assert_dashboard_startup_wiring = assert_dashboard_startup_wiring


if __name__ == "__main__":
    wave28.main()
    print("Wave 28 compatibility under Wave 76 passed.")
