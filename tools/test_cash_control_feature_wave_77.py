#!/usr/bin/env python3
"""Installer and compatibility checks for Cash Control Wave 77."""
from __future__ import annotations

from pathlib import Path

from spina_app.features.cash_control import install_cash_control_feature

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "cash_control.py"
TAB_PATH = ROOT / "spina_app" / "tabs" / "cash_control.py"

LEGACY_START = (
    "# --- BEGIN: Cash Control tab - percent buffer + net renewal cash forecast + "
    "separated current/forecast safe amounts ---"
)
MODERN_START = (
    "# --- BEGIN: v21 Modern Cash Control UI with graphs, labels, and explanation ---"
)
INSTALL_START = "# --- BEGIN: Cash Control feature installer Wave 77 ---"


def test_installer_idempotence() -> None:
    class DummyApp:
        def __init__(self, *_args, **_kwargs):
            self.base_initialized = True

        def apply_role_access(self, *args, **kwargs):
            return args, kwargs

        def _on_mode_change(self, *args, **kwargs):
            return args, kwargs

    assert install_cash_control_feature(DummyApp)
    assert DummyApp._spina_cash_control_wave77_installed is True
    assert callable(DummyApp._build_cash_control_tab)
    assert callable(DummyApp.refresh_cash_control)
    assert callable(DummyApp._cash_control_get_collection_totals)
    assert callable(DummyApp._cash_control_get_average_collection)
    assert callable(DummyApp._cash_control_reserve_rows)

    first_init = DummyApp.__init__
    first_role = DummyApp.apply_role_access
    first_mode = DummyApp._on_mode_change
    instance = DummyApp()
    assert instance.base_initialized is True

    assert install_cash_control_feature(DummyApp)
    assert DummyApp.__init__ is first_init
    assert DummyApp.apply_role_access is first_role
    assert DummyApp._on_mode_change is first_mode


def test_static_compatibility() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    feature_source = FEATURE_PATH.read_text(encoding="utf-8")
    tab_source = TAB_PATH.read_text(encoding="utf-8")

    assert "def install_cash_control_feature(" in feature_source
    assert "app_class._build_cash_control_tab = _spina_v21_cash_build_tab" in feature_source
    assert "def refresh_cash_control(" in feature_source
    assert "configure_cash_control_dependencies(" in feature_source
    assert "_spina_v21_cash_build_tab" in tab_source
    assert "_spina_v21_cash_draw_charts" in tab_source

    staged = app_source.count(LEGACY_START) == 1 and app_source.count(MODERN_START) == 1
    extracted = (
        app_source.count(INSTALL_START) == 1
        and LEGACY_START not in app_source
        and MODERN_START not in app_source
    )
    assert staged or extracted


def main() -> None:
    test_installer_idempotence()
    test_static_compatibility()
    print("Wave 77 Cash Control feature installer tests passed.")


if __name__ == "__main__":
    main()
