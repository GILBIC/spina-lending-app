from __future__ import annotations

import ast
import hashlib
import importlib
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "side_navigation_presentation.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "side_navigation.py"
HEADER_PATH = ROOT / "spina_app" / "account_header_presentation.py"
TARGETS = (
    "_spina_v13_hide_main_notebook_tabs",
    "_spina_v13_side_nav_items",
    "_spina_v13_rebuild_side_nav",
    "_spina_v13_refresh_side_nav_selection",
    "_spina_v13_setup_style",
    "_spina_v13_apply_ui_theme",
)
EXPECTED_LINES = {
    "_spina_v13_hide_main_notebook_tabs": 28,
    "_spina_v13_side_nav_items": 32,
    "_spina_v13_rebuild_side_nav": 99,
    "_spina_v13_refresh_side_nav_selection": 30,
    "_spina_v13_setup_style": 7,
    "_spina_v13_apply_ui_theme": 8,
}
EXPECTED_HASHES = {
    "_spina_v13_hide_main_notebook_tabs": "62fe7625905ea293f37e7bd3128aaef64b589a797628955d1b3f2c83eb9982dd",
    "_spina_v13_side_nav_items": "af8615304dd0219ad93bd0ad8269f553fbb5120c05550d3d1253f5b1017f6a67",
    "_spina_v13_rebuild_side_nav": "f41ca714d7123c3a82188c788a1973b4e6b85ea5bc51a38321d2757c9ffb0504",
    "_spina_v13_refresh_side_nav_selection": "9eb3edef07caef16a5b0139ce1b584e8ef2494d032e6a958d8b79bdcdb576ea1",
    "_spina_v13_setup_style": "7dbacc332c577d69bb553d2ee4e2ccaaa75ec74e1bcbbe45caf85e1c1aed6d69",
    "_spina_v13_apply_ui_theme": "a00a234ffd6a60002dcb7d94c183e54deb5b3e890fd5e3a2e3ff81f57896b566",
}
EXPECTED_SIGNATURES = {
    "_spina_v13_hide_main_notebook_tabs": "self",
    "_spina_v13_side_nav_items": "self",
    "_spina_v13_rebuild_side_nav": "self",
    "_spina_v13_refresh_side_nav_selection": "self",
    "_spina_v13_setup_style": "self, *args, **kwargs",
    "_spina_v13_apply_ui_theme": "self, *args, **kwargs",
}
EXPECTED_CALLS = {
    "_spina_v13_hide_main_notebook_tabs": ["_log_suppressed_once", "_ttk.Style", "getattr", "nb.configure", "st.configure", "st.layout"],
    "_spina_v13_side_nav_items": ["getattr", "icons.get", "items.append", "list", "nb.tab", "nb.tabs", "str", "strip"],
    "_spina_v13_rebuild_side_nav": ["_log_suppressed_once", "_spina_v13_hide_main_notebook_tabs", "_spina_v13_side_nav_items", "bottom.pack", "btn.pack", "child.destroy", "frame.configure", "frame.pack_propagate", "frame.winfo_children", "getattr", "lbl.pack", "lower", "p.get", "self._refresh_side_nav_selection", "self._select_side_tab", "self._side_nav_labels.append", "self._theme_palette", "sep.pack", "sep2.pack", "startswith", "str", "strip", "subtitle.pack", "title.pack", "tk.Button", "tk.Frame", "tk.Label"],
    "_spina_v13_refresh_side_nav_selection": ["btn.configure", "buttons.items", "getattr", "list", "lower", "p.get", "self._theme_palette", "self.nb.select", "startswith", "str"],
    "_spina_v13_setup_style": ["_spina_v13_hide_main_notebook_tabs", "_spina_v13_orig_setup_style"],
    "_spina_v13_apply_ui_theme": ["_spina_v13_hide_main_notebook_tabs", "_spina_v13_orig_apply_theme", "_spina_v13_rebuild_side_nav"],
}
FORBIDDEN_TEXT = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", ".commit(", ".rollback(", "write_text(", "write_bytes(",
    ".unlink(", "save_users_db", "verify_login", "hash_password",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def function_nodes(tree: ast.AST, name: str):
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]


def check_function(text: str, node: ast.FunctionDef, name: str) -> None:
    source = ast.get_source_segment(text, node)
    assert source is not None
    assert len(normalized(source).splitlines()) == EXPECTED_LINES[name]
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_HASHES[name]
    assert ast.unparse(node.args) == EXPECTED_SIGNATURES[name]
    calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
    assert calls == EXPECTED_CALLS[name], (name, calls)
    lower = source.lower()
    for forbidden in FORBIDDEN_TEXT:
        assert forbidden.lower() not in lower, (name, forbidden)


def check_architecture() -> None:
    module = importlib.import_module("spina_app.side_navigation_presentation")
    assert module.SIDE_NAVIGATION_TARGETS == list(TARGETS)
    assert module.SIDE_NAVIGATION_SOURCE_LINES == EXPECTED_LINES
    assert module.SIDE_NAVIGATION_SOURCE_SHA256 == EXPECTED_HASHES
    assert module.SIDE_NAVIGATION_SIGNATURES == EXPECTED_SIGNATURES
    assert module.SIDE_NAVIGATION_CALLS == EXPECTED_CALLS
    assert module.SIDE_NAVIGATION_TOTAL_SOURCE_LINES == 204

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    for name in TARGETS:
        matches = function_nodes(module_tree, name)
        assert len(matches) == 1, (name, len(matches))
        check_function(module_text, matches[0], name)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    for name in TARGETS:
        assert not function_nodes(desktop_tree, name), name
    assert "spina_app.side_navigation_presentation" not in desktop_text
    assert "# --- BEGIN: v13 side-tabs-only UI fix ---" not in desktop_text
    assert "_spina_orig_apply_role_modern_sidebar" not in desktop_text

    feature_text = FEATURE_PATH.read_text(encoding="utf-8")
    feature_tree = ast.parse(feature_text)
    imports = [
        node for node in feature_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.side_navigation_presentation"
    ]
    assert len(imports) == 1
    imported = {alias.name for alias in imports[0].names}
    assert set(TARGETS).issubset(imported)
    installer = function_nodes(feature_tree, "install_side_navigation_feature")
    assert len(installer) == 1
    installer_source = ast.get_source_segment(feature_text, installer[0]) or ""
    for token in (
        "app_class._side_nav_items = _spina_v13_side_nav_items",
        "app_class._rebuild_side_nav = _spina_v13_rebuild_side_nav",
        "app_class._refresh_side_nav_selection = _spina_v13_refresh_side_nav_selection",
        "app_class._hide_main_notebook_tabs = _spina_v13_hide_main_notebook_tabs",
    ):
        assert token in installer_source, token

    header_text = HEADER_PATH.read_text(encoding="utf-8")
    assert "install_side_navigation_feature" in header_text
    assert "install_side_navigation_feature(" in header_text


def check_behavior() -> None:
    module = importlib.import_module("spina_app.side_navigation_presentation")

    class FakeNotebook:
        def tabs(self):
            return ["dashboard", "hidden", "clients"]

        def tab(self, tab, field):
            data = {
                "dashboard": {"state": "normal", "text": "Dashboard"},
                "hidden": {"state": "hidden", "text": "Audit"},
                "clients": {"state": "normal", "text": "Clients"},
            }
            return data[tab][field]

    fake = type("Fake", (), {"nb": FakeNotebook()})()
    assert module._spina_v13_side_nav_items(fake) == [
        ("dashboard", "Dashboard", "◈"),
        ("clients", "Clients", "◉"),
    ]

    events = []
    original_hide = module._spina_v13_hide_main_notebook_tabs
    original_rebuild = module._spina_v13_rebuild_side_nav
    original_setup = getattr(module, "_spina_v13_orig_setup_style", None)
    original_theme = getattr(module, "_spina_v13_orig_apply_theme", None)
    try:
        module._spina_v13_hide_main_notebook_tabs = lambda self: events.append("hide")
        module._spina_v13_rebuild_side_nav = lambda self: events.append("rebuild")
        module._spina_v13_orig_setup_style = lambda self, *a, **k: events.append("setup") or "setup-result"
        module._spina_v13_orig_apply_theme = lambda self, *a, **k: events.append("theme") or "theme-result"
        dummy = object()
        assert module._spina_v13_setup_style(dummy) == "setup-result"
        assert events == ["setup", "hide"]
        events.clear()
        assert module._spina_v13_apply_ui_theme(dummy) == "theme-result"
        assert events == ["theme", "hide", "rebuild"]
    finally:
        module._spina_v13_hide_main_notebook_tabs = original_hide
        module._spina_v13_rebuild_side_nav = original_rebuild
        if original_setup is None:
            module.__dict__.pop("_spina_v13_orig_setup_style", None)
        else:
            module._spina_v13_orig_setup_style = original_setup
        if original_theme is None:
            module.__dict__.pop("_spina_v13_orig_apply_theme", None)
        else:
            module._spina_v13_orig_apply_theme = original_theme


def main() -> None:
    check_architecture()
    check_behavior()
    print("Wave 48 side-navigation presentation regression passed.")


if __name__ == "__main__":
    main()
