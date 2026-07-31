#!/usr/bin/env python3
"""Regression coverage for redundant sidebar cleanup Wave 87."""
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
SHELL = ROOT / "spina_app" / "features" / "application_shell.py"

REMOVED_TEXT = (
    "# --- BEGIN: Modern sidebar nav refresh after role changes ---",
    "# --- END: Modern sidebar nav refresh after role changes ---",
    "_spina_orig_apply_role_modern_sidebar",
    "_spina_apply_role_access_modern_sidebar",
    "# --- BEGIN: v13 side-tabs-only UI fix ---",
    "# --- END: v13 side-tabs-only UI fix ---",
    "_wave48_configure_side_navigation_dependencies",
    "_spina_v13_orig_setup_style",
    "_spina_v13_orig_apply_theme",
    "_spina_v13_orig_init",
    "_spina_v13_orig_apply_role",
    "_spina_v13_app_init",
    "_spina_v13_apply_role_access",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def check_architecture() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(DESKTOP))

    for token in REMOVED_TEXT:
        assert token not in text, token
    assert text.count("# --- Legacy modern sidebar role wrapper removed Wave 87 ---") == 1
    assert text.count("# --- Legacy v13 sidebar wrapper removed Wave 87 ---") == 1
    assert text.count("_wave46_configure_account_header_dependencies(globals())") == 1
    assert "install_application_shell" in header
    assert "install_side_navigation_feature" not in header
    assert "install_side_navigation_feature" in shell
    assert "side_navigation_installer(" in shell

    forbidden_bindings = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = dotted(node.targets[0])
        value = dotted(node.value)
        if target in {
            "App.__init__",
            "App.apply_role_access",
            "App._setup_style",
            "App._apply_ui_theme",
        } and (
            value.startswith("_spina_v13")
            or value.startswith("_spina_apply_role_access_modern_sidebar")
        ):
            forbidden_bindings.append((target, value))
    assert not forbidden_bindings, forbidden_bindings


def check_fallback_runtime() -> None:
    events: list[str] = []
    original_hide = feature._spina_v13_hide_main_notebook_tabs
    original_rebuild = feature._spina_v13_rebuild_side_nav
    original_items = feature._spina_v13_side_nav_items
    original_refresh = feature._spina_v13_refresh_side_nav_selection

    feature._spina_v13_hide_main_notebook_tabs = lambda self: events.append("hide")
    feature._spina_v13_rebuild_side_nav = lambda self: events.append("rebuild")
    feature._spina_v13_side_nav_items = lambda self: []
    feature._spina_v13_refresh_side_nav_selection = lambda self: events.append("select")

    class Harness:
        def __init__(self):
            events.append("current-init")

        def _setup_style(self):
            events.append("current-setup")
            return "setup"

        def _apply_ui_theme(self):
            events.append("current-theme")
            return "theme"

        def apply_role_access(self):
            events.append("current-role")
            return "role"

    base_init = Harness.__init__
    base_setup = Harness._setup_style
    base_theme = Harness._apply_ui_theme
    base_role = Harness.apply_role_access

    try:
        assert feature.install_side_navigation_feature(
            Harness,
            namespace={"App": Harness},
        )
        assert Harness._spina_side_navigation_wave86_original_init is base_init
        assert Harness._spina_side_navigation_wave86_original_setup_style is base_setup
        assert Harness._spina_side_navigation_wave86_original_apply_theme is base_theme
        assert Harness._spina_side_navigation_wave86_original_apply_role is base_role

        instance = Harness()
        assert events == ["current-init", "hide", "rebuild"]
        events.clear()

        assert instance._setup_style() == "setup"
        assert events == ["current-setup", "hide"]
        events.clear()

        assert instance._apply_ui_theme() == "theme"
        assert events == ["current-theme", "hide", "rebuild"]
        events.clear()

        assert instance.apply_role_access() == "role"
        assert events == ["current-role", "hide", "rebuild"]
        events.clear()

        init_wrapper = Harness.__init__
        role_wrapper = Harness.apply_role_access
        assert feature.install_side_navigation_feature(Harness, namespace={"App": Harness})
        assert Harness.__init__ is init_wrapper
        assert Harness.apply_role_access is role_wrapper

        class StartupCancelled(Exception):
            pass

        class CancelHarness:
            def __init__(self):
                events.append("cancel")
                raise StartupCancelled()

        assert feature.install_side_navigation_feature(
            CancelHarness,
            namespace={"App": CancelHarness},
        )
        try:
            CancelHarness()
        except StartupCancelled:
            pass
        else:
            raise AssertionError("startup cancellation was swallowed")
        assert events == ["cancel"]
    finally:
        feature._spina_v13_hide_main_notebook_tabs = original_hide
        feature._spina_v13_rebuild_side_nav = original_rebuild
        feature._spina_v13_side_nav_items = original_items
        feature._spina_v13_refresh_side_nav_selection = original_refresh


def main() -> None:
    check_architecture()
    check_fallback_runtime()
    print("Wave 87 redundant sidebar cleanup regression passed.")


if __name__ == "__main__":
    main()
