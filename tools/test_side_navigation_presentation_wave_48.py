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
TARGETS = ('_spina_v13_hide_main_notebook_tabs', '_spina_v13_side_nav_items', '_spina_v13_rebuild_side_nav', '_spina_v13_refresh_side_nav_selection', '_spina_v13_setup_style', '_spina_v13_apply_ui_theme')
EXPECTED_LINES = {'_spina_v13_hide_main_notebook_tabs': 28, '_spina_v13_side_nav_items': 32, '_spina_v13_rebuild_side_nav': 99, '_spina_v13_refresh_side_nav_selection': 30, '_spina_v13_setup_style': 7, '_spina_v13_apply_ui_theme': 8}
EXPECTED_HASHES = {'_spina_v13_hide_main_notebook_tabs': '62fe7625905ea293f37e7bd3128aaef64b589a797628955d1b3f2c83eb9982dd', '_spina_v13_side_nav_items': 'af8615304dd0219ad93bd0ad8269f553fbb5120c05550d3d1253f5b1017f6a67', '_spina_v13_rebuild_side_nav': 'f41ca714d7123c3a82188c788a1973b4e6b85ea5bc51a38321d2757c9ffb0504', '_spina_v13_refresh_side_nav_selection': '9eb3edef07caef16a5b0139ce1b584e8ef2494d032e6a958d8b79bdcdb576ea1', '_spina_v13_setup_style': '7dbacc332c577d69bb553d2ee4e2ccaaa75ec74e1bcbbe45caf85e1c1aed6d69', '_spina_v13_apply_ui_theme': 'a00a234ffd6a60002dcb7d94c183e54deb5b3e890fd5e3a2e3ff81f57896b566'}
EXPECTED_SIGNATURES = {'_spina_v13_hide_main_notebook_tabs': 'self', '_spina_v13_side_nav_items': 'self', '_spina_v13_rebuild_side_nav': 'self', '_spina_v13_refresh_side_nav_selection': 'self', '_spina_v13_setup_style': 'self, *args, **kwargs', '_spina_v13_apply_ui_theme': 'self, *args, **kwargs'}
EXPECTED_CALLS = {'_spina_v13_hide_main_notebook_tabs': ['_log_suppressed_once', '_ttk.Style', 'getattr', 'nb.configure', 'st.configure', 'st.layout'], '_spina_v13_side_nav_items': ['getattr', 'icons.get', 'items.append', 'list', 'nb.tab', 'nb.tabs', 'str', 'strip'], '_spina_v13_rebuild_side_nav': ['_log_suppressed_once', '_spina_v13_hide_main_notebook_tabs', '_spina_v13_side_nav_items', 'bottom.pack', 'btn.pack', 'child.destroy', 'frame.configure', 'frame.pack_propagate', 'frame.winfo_children', 'getattr', 'lbl.pack', 'lower', 'p.get', 'self._refresh_side_nav_selection', 'self._select_side_tab', 'self._side_nav_labels.append', 'self._theme_palette', 'sep.pack', 'sep2.pack', 'startswith', 'str', 'strip', 'subtitle.pack', 'title.pack', 'tk.Button', 'tk.Frame', 'tk.Label'], '_spina_v13_refresh_side_nav_selection': ['btn.configure', 'buttons.items', 'getattr', 'list', 'lower', 'p.get', 'self._theme_palette', 'self.nb.select', 'startswith', 'str'], '_spina_v13_setup_style': ['_spina_v13_hide_main_notebook_tabs', '_spina_v13_orig_setup_style'], '_spina_v13_apply_ui_theme': ['_spina_v13_hide_main_notebook_tabs', '_spina_v13_orig_apply_theme', '_spina_v13_rebuild_side_nav']}
PROTECTED_NEIGHBORS = {'_spina_v13_app_init': '62e844676d744f80d3ededa1e0d53c086e1d56780520e2b255c83287ff814e46', '_spina_v13_apply_role_access': 'eae9878597fda6f89b72699b5a74e187975654d2a65d5b4a2c4fc69f6b97fc8a'}
FORBIDDEN_TEXT = ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', '.commit(', '.rollback(', 'write_text(', 'write_bytes(', '.unlink(', 'save_users_db', 'verify_login', 'hash_password', 'force_change_password', 'must_change_password')


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def source_for(text: str, node: ast.AST) -> str:
    source = ast.get_source_segment(text, node)
    assert source is not None
    return source


def function_nodes(tree: ast.AST, name: str):
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]


def check_function(text: str, node: ast.FunctionDef, name: str) -> None:
    source = source_for(text, node)
    assert len(normalized(source).splitlines()) == EXPECTED_LINES[name]
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_HASHES[name]
    assert ast.unparse(node.args) == EXPECTED_SIGNATURES[name]
    calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
    assert calls == EXPECTED_CALLS[name], (name, calls)
    lower = source.lower()
    for forbidden in FORBIDDEN_TEXT:
        assert forbidden.lower() not in lower, (name, forbidden)


def find_capture(tree: ast.AST, name: str, attr: str):
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            matches.append(node)
    assert len(matches) == 1, (name, len(matches))
    rendered = ast.unparse(matches[0].value)
    assert 'App' in rendered and attr in rendered, (name, rendered)
    return matches[0]


def find_binding(tree: ast.AST, attr: str, value_name: str):
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name) and target.value.id == "App"
            and target.attr == attr
            and isinstance(node.value, ast.Name) and node.value.id == value_name
        ):
            matches.append(node)
    assert len(matches) == 1, (attr, value_name, len(matches))
    return matches[0]


def main() -> None:
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

    imports = [
        node for node in ast.walk(desktop_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.side_navigation_presentation"
    ]
    assert len(imports) == 1
    aliases = {(item.name, item.asname) for item in imports[0].names}
    assert ("configure_side_navigation_dependencies", "_wave48_configure_side_navigation_dependencies") in aliases
    for name in TARGETS:
        assert (name, "_wave48" + name) in aliases

    symbol_rebinds = []
    configure_lines = []
    for node in ast.walk(desktop_tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in TARGETS and isinstance(node.value, ast.Name):
                symbol_rebinds.append((target.id, node.value.id))
        if (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_wave48_configure_side_navigation_dependencies"
        ):
            configure_lines.append(node.lineno)
    assert sorted(symbol_rebinds) == sorted((name, "_wave48" + name) for name in TARGETS)
    assert len(configure_lines) == 2, configure_lines
    configure_lines.sort()

    setup_capture = find_capture(desktop_tree, "_spina_v13_orig_setup_style", "_setup_style")
    setup_binding = find_binding(desktop_tree, "_setup_style", "_spina_v13_setup_style")
    theme_capture = find_capture(desktop_tree, "_spina_v13_orig_apply_theme", "_apply_ui_theme")
    theme_binding = find_binding(desktop_tree, "_apply_ui_theme", "_spina_v13_apply_ui_theme")
    assert setup_capture.lineno < configure_lines[0] < setup_binding.lineno
    assert theme_capture.lineno < configure_lines[1] < theme_binding.lineno

    for name, expected_hash in PROTECTED_NEIGHBORS.items():
        matches = function_nodes(desktop_tree, name)
        assert len(matches) == 1, (name, len(matches))
        source = source_for(desktop_text, matches[0])
        assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == expected_hash

    init_bindings = [
        node for node in ast.walk(desktop_tree)
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Attribute)
        and isinstance(node.targets[0].value, ast.Name)
        and node.targets[0].value.id == "App"
        and node.targets[0].attr == "__init__"
        and isinstance(node.value, ast.Name)
        and node.value.id == "_spina_v13_app_init"
    ]
    role_bindings = [
        node for node in ast.walk(desktop_tree)
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Attribute)
        and isinstance(node.targets[0].value, ast.Name)
        and node.targets[0].value.id == "App"
        and node.targets[0].attr == "apply_role_access"
        and isinstance(node.value, ast.Name)
        and node.value.id == "_spina_v13_apply_role_access"
    ]
    assert len(init_bindings) == 1
    assert len(role_bindings) == 1

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
    items = module._spina_v13_side_nav_items(fake)
    assert items == [("dashboard", "Dashboard", "◈"), ("clients", "Clients", "◉")]

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

    print("Wave 48 side-navigation presentation regression passed.")


if __name__ == "__main__":
    main()
