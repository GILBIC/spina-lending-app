from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "theme_presentation.py"
TARGETS = ('_theme_toggle_text', '_theme_palette', '_apply_ui_theme', '_apply_tk_theme_recursive', '_refresh_modern_shell_theme', '_refresh_header_theme')
EXPECTED = {'_theme_toggle_text': '0b731a0168cf4cfc1dae0bc61be590016f430439967c231945b5ba54984446c5', '_theme_palette': '3fbc5f639f57dbeb38317f972b066ef4b341c34fdf0eec69e04a23e2339f9895', '_apply_ui_theme': '6a664ebfbdcc0b72748da1f5f0d0153144b5fcb5f16ddafbf425bb61b72a2fc1', '_apply_tk_theme_recursive': '87708debed3c355bd014e0f88dd15610951a28e8c84947f3104155864d4dcc60', '_refresh_modern_shell_theme': 'bc2b6f85d12771bd87a4acc294c10a94a5c6d913152b5454ca16228cf13cc4f7', '_refresh_header_theme': '3d7f79b5b95654e10bdaff5e628851b717d34f1687bef39906dd3aac25368a2a'}
EXPECTED_TOTAL_LINES = 313
FORBIDDEN_TEXT = ('SAVE_SETTINGS', 'LOAD_SETTINGS', '_WRITE_JSON_ATOMIC', 'INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', '.COMMIT(', '.ROLLBACK(', 'WRITE_TEXT(', 'WRITE_BYTES(', '.UNLINK(')
MUTATING_CALLS = ('_write_json_atomic', 'commit', 'copy', 'copy2', 'load_settings', 'makedirs', 'mkdir', 'move', 'remove', 'rename', 'rmdir', 'rollback', 'save_settings', 'touch', 'unlink', 'write', 'write_bytes', 'write_text')


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def digest(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text, filename=str(MODULE))
    funcs = {
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert set(TARGETS) <= set(funcs), sorted(set(TARGETS) - set(funcs))
    actual_lines = 0
    for name in TARGETS:
        node = funcs[name]
        segment = ast.get_source_segment(module_text, node)
        assert segment
        assert digest(segment) == EXPECTED[name], name
        actual_lines += (node.end_lineno or node.lineno) - node.lineno + 1
        upper = segment.upper()
        for token in FORBIDDEN_TEXT:
            assert token not in upper, (name, token)
        for item in ast.walk(node):
            if not isinstance(item, ast.Call):
                continue
            fn = item.func
            call_name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
            assert call_name.lower() not in MUTATING_CALLS, (name, call_name)
            assert call_name != "open", name
    assert actual_lines == EXPECTED_TOTAL_LINES, (actual_lines, EXPECTED_TOTAL_LINES)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text, filename=str(DESKTOP))
    app_class = next(node for node in desktop_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {
        node.name
        for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not (set(TARGETS) & remaining), sorted(set(TARGETS) & remaining)
    assigned = set()
    for node in desktop_tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "App":
            if target.attr in TARGETS:
                assigned.add(target.attr)
                assert node.lineno > (app_class.end_lineno or app_class.lineno)
    assert assigned == set(TARGETS), sorted(set(TARGETS) - assigned)
    assert "def set_theme(" in desktop_text
    assert "def toggle_theme(" in desktop_text
    print(f"Wave 35 theme presentation regression passed: {len(TARGETS)} methods / {actual_lines} lines.")


if __name__ == "__main__":
    main()
