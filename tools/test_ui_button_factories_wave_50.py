from __future__ import annotations

import ast
import hashlib
import importlib
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
UI_CONTROLS = ROOT / "spina_app" / "ui_controls.py"
THEME_PALETTES = ROOT / "spina_app" / "theme_palettes.py"
COLLECTOR_MODULE = ROOT / "spina_app" / "collector_tab_presentation.py"
LOGIN_MODULE = ROOT / "spina_app" / "login_dialog_presentation.py"

TARGETS = (
    "_spina_v25_collector_button",
    "_spina_v27_route_button",
    "_spina_v32_login_button",
)
EXPECTED_LINES = {
    "_spina_v25_collector_button": 29,
    "_spina_v27_route_button": 30,
    "_spina_v32_login_button": 28,
}
EXPECTED_HASHES = {
    "_spina_v25_collector_button": "ea864f236d0ec9e89ae442101cf42d052a298d227ef3a1381e46634e4fdaff8e",
    "_spina_v27_route_button": "942ec48ae940ba90097d84b71141096757f30a00c402189857dcf52b80d4c247",
    "_spina_v32_login_button": "2c03274b2c00ef5314610f3a30134d1dedeaabed2e87fbb950acd8821846bace",
}
EXPECTED_SIGNATURES = {
    "_spina_v25_collector_button": "parent, text, command=None, kind='normal', width=None",
    "_spina_v27_route_button": "parent, text, command=None, kind='normal', width=None",
    "_spina_v32_login_button": "parent, text, command=None, kind='normal', width=None",
}
EXPECTED_CALLS = {
    "_spina_v25_collector_button": ["_spina_v25_collector_colors", "tk.Button"],
    "_spina_v27_route_button": ["_spina_v27_route_colors", "tk.Button"],
    "_spina_v32_login_button": ["_spina_v32_login_colors", "tk.Button"],
}
PALETTE_HASHES = {
    "_spina_v25_collector_colors": "8cfd57240e8f25ae6dcd8c9b00817e48af7fcfd74319312fe639ebe1f18adba0",
    "_spina_v32_login_colors": "810a66f0d451c8410bc643dea96ad80cf69068e092482b4c772440304ed38a45",
}
PROTECTED_CALLERS = {
    (DESKTOP, "_spina_v25_build_collectors_tab", "plain"): "f5b787f580fd4202ebbc324e70da4a8c2adee5190e959c3af01b0e2402b32e92",
    (COLLECTOR_MODULE, "_spina_v27_build_collectors_tab", "newline"): "5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb",
    (LOGIN_MODULE, "_spina_v32_prompt_login", "newline"): "0dc7c87e702bf93da77bbf6a9fc490a005114716e4ef487f10a203bfe75e48a3",
}
SQL_WRITE_RE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE)\b",
    re.I,
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


def plain_normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in textwrap.dedent(source).strip().splitlines())


def source_hash(source: str, mode: str = "newline") -> str:
    value = normalized(source) if mode == "newline" else plain_normalized(source)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def top_function(text: str, tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def source_for(text: str, node: ast.AST) -> str:
    source = ast.get_source_segment(text, node)
    assert source is not None
    return source


def calls_for(node: ast.FunctionDef) -> list[str]:
    return sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })


def verify_function(path: Path, name: str, expected: str, mode: str = "newline") -> ast.FunctionDef:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = top_function(text, tree, name)
    actual = source_hash(source_for(text, node), mode)
    assert actual == expected, (path.name, name, actual, expected)
    return node


def main() -> None:
    module = importlib.import_module("spina_app.ui_controls")
    ui_text = UI_CONTROLS.read_text(encoding="utf-8")
    ui_tree = ast.parse(ui_text)

    for name in TARGETS:
        assert callable(getattr(module, name))
        node = top_function(ui_text, ui_tree, name)
        source = source_for(ui_text, node)
        assert len(normalized(source).splitlines()) == EXPECTED_LINES[name]
        assert source_hash(source) == EXPECTED_HASHES[name]
        assert ast.unparse(node.args) == EXPECTED_SIGNATURES[name]
        assert calls_for(node) == EXPECTED_CALLS[name]
        for part in ast.walk(node):
            if isinstance(part, ast.Attribute):
                assert not dotted(part).startswith("self.db")
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                assert not SQL_WRITE_RE.search(part.value)

    palette_imports = [
        node for node in ui_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.theme_palettes"
    ]
    assert len(palette_imports) == 1
    aliases = {(item.name, item.asname) for item in palette_imports[0].names}
    assert ("_spina_v25_collector_colors", None) in aliases
    assert ("_spina_v25_collector_colors", "_spina_v27_route_colors") in aliases
    assert ("_spina_v32_login_colors", None) in aliases

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    for name in TARGETS:
        assert not [node for node in desktop_tree.body if isinstance(node, ast.FunctionDef) and node.name == name], name

    complete_imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.ui_controls"
        and set(TARGETS).issubset({alias.asname or alias.name for alias in node.names})
    ]
    assert len(complete_imports) == 1, len(complete_imports)
    legacy_builder = top_function(desktop_text, desktop_tree, "_spina_v25_build_collectors_tab")
    assert complete_imports[0].lineno < legacy_builder.lineno

    for (path, name, mode), expected in PROTECTED_CALLERS.items():
        node = verify_function(path, name, expected, mode)
        calls = calls_for(node)
        expected_target = {
            "_spina_v25_build_collectors_tab": "_spina_v25_collector_button",
            "_spina_v27_build_collectors_tab": "_spina_v27_route_button",
            "_spina_v32_prompt_login": "_spina_v32_login_button",
        }[name]
        assert expected_target in calls, (name, expected_target)

    for name, expected in PALETTE_HASHES.items():
        verify_function(THEME_PALETTES, name, expected)

    print("Wave 50 UI button-factory regression passed: 3 factories, 87 lines.")


if __name__ == "__main__":
    main()
