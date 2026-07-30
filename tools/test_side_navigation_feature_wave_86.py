#!/usr/bin/env python3
"""Regression coverage for final side-navigation runtime ownership Wave 86."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app.features import side_navigation as feature

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
HEADER = ROOT / "spina_app" / "account_header_presentation.py"
FEATURE = ROOT / "spina_app" / "features" / "side_navigation.py"


def check_architecture() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")
    feature_text = FEATURE.read_text(encoding="utf-8")

    assert "install_side_navigation_feature" in header_text
    assert 'namespace.get("App")' in header_text
    assert 'namespace.get("_log_suppressed_once")' in header_text
    assert desktop_text.count("_wave46_configure_account_header_dependencies(globals())") == 1

    for removed in (
        "# --- BEGIN: v13 side-tabs-only UI fix ---",
        "# --- END: v13 side-tabs-only UI fix ---",
        "# --- BEGIN: Modern sidebar nav refresh after role changes ---",
        "# --- END: Modern sidebar nav refresh after role changes ---",
        "_spina_v13_app_init",
        "_spina_v13_apply_role_access",
        "_spina_apply_role_access_modern_sidebar",
    ):
        assert removed not in desktop_text, removed

    tree = ast.parse(feature_text)
    installer = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "install_side_navigation_feature"
    )
    source = ast.get_source_segment(feature_text, installer) or ""
    for token in (
        'fallback_attr="__init__"',
        'fallback_attr="_setup_style"',
        'fallback_attr="_apply_ui_theme"',
        'fallback_attr="apply_role_access"',
        "app_class.__init__ = init_with_side_navigation",
        "app_class.apply_role_access = apply_role_with_side_navigation",
        "app_class._spina_side_navigation_wave86_installed = True",
    ):
        assert token in source, token

    forbidden = (
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "CREATE TABLE",
        ".commit(",
        ".rollback(",
        "write_text(",
        "write_bytes(",
        ".unlink(",
    )
    lowered = feature_text.lower()
    for token in forbidden:
        assert token.lower() not in lowered, token


def check_runtime() -> None:
    events: list[str] = []
    logs: list[tuple[str, str]] = []

    original_hide = feature._spina_v13_hide_main_notebook_tabs
    original_rebuild = feature._spina_v13_rebuild_side_nav
    original_items = feature._spina_v13_side_nav_items
    original_refresh = feature._spina_v13_refresh_side_nav_selection

    feature._spina_v13_hide_main_notebook_tabs = lambda self: events.append("hide")
    feature._spina_v13_rebuild_side_nav = lambda self: events.append("rebuild")
    feature._spina_v13_side_nav_items = lambda self: [("tab", "Page", "•")]
    feature._spina_v13_refresh_side_nav_selection = lambda self: events.append("select")

    class Harness:
        def __init__(self):
            events.append("current-init")

        def _setup_style(self):
            events.append("current-setup")

        def _apply_ui_theme(self):
            events.append("current-theme")

        def apply_role_access(self):
            events.append("current-role")

    def base_init(self):
        events.append("init")

    def base_setup(self):
        events.append("setup")
        return "setup-result"

    def base_theme(self):
        events.append("theme")
        return "theme-result"

    def legacy_role(self):
        events.append("legacy-role")
        return "legacy-role-result"

    def base_role(self):
        events.append("role")
        return "role-result"

    namespace = {
        "App": Harness,
        "_spina_v13_orig_init": base_init,
        "_spina_v13_orig_setup_style": base_setup,
        "_spina_v13_orig_apply_theme": base_theme,
        "_spina_v13_orig_apply_role": legacy_role,
        "_spina_orig_apply_role_modern_sidebar": base_role,
        "_log_suppressed_once": lambda key, message, exc=None: logs.append(
            (key, message)
        ),
    }

    try:
        assert feature.install_side_navigation_feature(
            Harness,
            namespace=namespace,
            log_suppressed_once=namespace["_log_suppressed_once"],
        )
        assert Harness._spina_side_navigation_wave86_installed is True

        instance = Harness()
        assert events == ["init", "hide", "rebuild"]
        events.clear()

        assert instance._setup_style() == "setup-result"
        assert events == ["setup", "hide"]
        events.clear()

        assert instance._apply_ui_theme() == "theme-result"
        assert events == ["theme", "hide", "rebuild"]
        events.clear()

        assert instance.apply_role_access() == "role-result"
        assert events == ["role", "hide", "rebuild"]
        assert "legacy-role" not in events
        events.clear()

        init_wrapper = Harness.__init__
        role_wrapper = Harness.apply_role_access
        assert feature.install_side_navigation_feature(Harness, namespace=namespace)
        assert Harness.__init__ is init_wrapper
        assert Harness.apply_role_access is role_wrapper

        class StartupCancelled(Exception):
            pass

        class CancelHarness:
            pass

        def cancelled_init(self):
            events.append("cancel")
            raise StartupCancelled()

        assert feature.install_side_navigation_feature(
            CancelHarness,
            namespace={
                "App": CancelHarness,
                "_spina_v13_orig_init": cancelled_init,
            },
        )
        try:
            CancelHarness()
        except StartupCancelled:
            pass
        else:
            raise AssertionError("startup cancellation was swallowed")
        assert events == ["cancel"]
        assert not logs
    finally:
        feature._spina_v13_hide_main_notebook_tabs = original_hide
        feature._spina_v13_rebuild_side_nav = original_rebuild
        feature._spina_v13_side_nav_items = original_items
        feature._spina_v13_refresh_side_nav_selection = original_refresh


def main() -> None:
    check_architecture()
    check_runtime()
    print("Wave 86 side-navigation feature regression passed.")


if __name__ == "__main__":
    main()
