from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

import spina_app.theme_application as theme_application

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/theme_application.py")
EXPECTED_FUNCTION_AST_SHA256 = "89c90643ea9ca729c4c7764e9784219ca96358f681c41310d8cc757035996c72"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_structure() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    source_tree = ast.parse(source_text)
    app = next(
        node for node in source_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "set_theme"
        for node in app.body
    ), "legacy App.set_theme must be removed after the complete extraction"

    assert "from spina_app.theme_application import (" in source_text
    assert "_configure_wave72_theme(globals())" in source_text
    assert "App.set_theme = _wave72_set_theme" in source_text
    assert source_text.index("App.set_theme = _wave72_set_theme") < source_text.index("if __name__ == '__main__':")

    module_tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    extracted = _function(module_tree, "set_theme")
    assert _sha256(ast.dump(extracted, include_attributes=False)) == EXPECTED_FUNCTION_AST_SHA256
    assert str(inspect.signature(theme_application.set_theme)) == "(self, theme: 'str', persist: 'bool' = True)"


def _configured_dependencies(saved, logs, load_result=None, load_error=None):
    def load_settings():
        if load_error is not None:
            raise load_error
        return dict(load_result or {"existing": 1})

    def save_settings(settings):
        saved.append(dict(settings))

    def log_once(key, message, exc):
        logs.append((key, message, type(exc).__name__))

    missing = theme_application.configure_theme_application_dependencies({
        "_DEFAULT_SETTINGS": {"fallback": 1},
        "load_settings": load_settings,
        "save_settings": save_settings,
        "_log_suppressed_once": log_once,
    })
    assert missing == []


class _Button:
    def __init__(self, events):
        self.events = events

    def configure(self, **kwargs):
        self.events.append(("button", kwargs))


class _App:
    def __init__(self):
        self.events = []
        self.root = object()
        self.theme_btn = _Button(self.events)
        self.ui_theme = "light"
        self.fail_setup = False

    def _setup_style(self):
        self.events.append(("setup", self.ui_theme))
        if self.fail_setup:
            raise RuntimeError("setup failed")

    def _apply_ui_theme(self, style):
        self.events.append(("fallback", style, self.ui_theme))

    def _theme_toggle_text(self):
        return "toggle:" + self.ui_theme

    def _refresh_header_theme(self):
        self.events.append(("header", self.ui_theme))

    def _apply_tk_theme_recursive(self, root):
        self.events.append(("tk", root, self.ui_theme))

    def _refresh_modern_shell_theme(self):
        self.events.append(("shell", self.ui_theme))


def test_dark_persisted() -> None:
    saved, logs = [], []
    _configured_dependencies(saved, logs, load_result={"existing": 1})
    app = _App()

    theme_application.set_theme(app, " Dark Mode ", persist=True)

    assert app.ui_theme == "dark"
    assert saved == [{"existing": 1, "ui_theme": "dark"}]
    assert logs == []
    assert ("setup", "dark") in app.events
    assert ("button", {"text": "toggle:dark"}) in app.events
    assert ("header", "dark") in app.events
    assert ("shell", "dark") in app.events


def test_light_without_persistence() -> None:
    saved, logs = [], []
    _configured_dependencies(saved, logs)
    app = _App()

    theme_application.set_theme(app, "anything", persist=False)

    assert app.ui_theme == "light"
    assert saved == []
    assert logs == []


def test_settings_fallback_and_style_fallback() -> None:
    saved, logs = [], []
    _configured_dependencies(saved, logs, load_error=RuntimeError("load failed"))
    app = _App()
    app.fail_setup = True

    original_style = theme_application.ttk.Style
    try:
        theme_application.ttk.Style = lambda root: ("style", root)
        theme_application.set_theme(app, "dark", persist=True)
    finally:
        theme_application.ttk.Style = original_style

    assert saved == [{"fallback": 1, "ui_theme": "dark"}]
    assert any(event[0] == "fallback" for event in app.events)
    assert app.ui_theme == "dark"


def main() -> None:
    test_structure()
    test_dark_persisted()
    test_light_without_persistence()
    test_settings_fallback_and_style_fallback()
    print("Wave 72 whole-function theme extraction regressions passed")


if __name__ == "__main__":
    main()
