from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
PROTECTED_CALLERS = {
    (DESKTOP, "_spina_v25_build_collectors_tab", "plain"): "f5b787feb012af35a41a6976af63684e01e958694d5b75e91df8d0b7a2af1c8",
    (COLLECTOR_MODULE, "_spina_v27_build_collectors_tab", "newline"): "5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb",
    (LOGIN_MODULE, "_spina_v32_prompt_login", "newline"): "0dc7c87e702bf93da77bbf6a9fc490a005114716e4ef487f10a203bfe75e48a3",
}
PALETTE_HASHES = {
    "_spina_v25_collector_colors": "8cfd57240e8f25ae6dcd8c9b00817e48af7fcfd74319312fe639ebe1f18adba0",
    "_spina_v32_login_colors": "810a66f0d451c8410bc643dea96ad80cf69068e092482b4c772440304ed38a45",
}
FORBIDDEN = (
    "connect_db(", "self.db", ".execute(", ".executemany(", ".commit(",
    ".rollback(", "run_write(", "open(", "json.load", "json.dump",
    "write_text(", "write_bytes(", "os.makedirs", "os.remove",
    "subprocess.", "threading.", "_verify_login", "_load_users_db",
    "password", "permission", "INSERT INTO", "UPDATE ", "DELETE FROM ",
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


def verify_target(text: str, tree: ast.Module, name: str) -> tuple[ast.FunctionDef, str]:
    node = top_function(text, tree, name)
    source = source_for(text, node)
    assert len(normalized(source).splitlines()) == EXPECTED_LINES[name]
    assert source_hash(source) == EXPECTED_HASHES[name]
    assert ast.unparse(node.args) == EXPECTED_SIGNATURES[name]
    assert calls_for(node) == EXPECTED_CALLS[name]
    lower = source.lower()
    for token in FORBIDDEN:
        assert token.lower() not in lower, (name, token)
    return node, source


def verify_function_hash(path: Path, name: str, expected: str, mode: str) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    node = top_function(text, tree, name)
    actual = source_hash(source_for(text, node), mode)
    assert actual == expected, (path.name, name, actual, expected)


def rewrite_palette_import(text: str) -> str:
    tree = ast.parse(text)
    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.theme_palettes"
    ]
    assert len(imports) == 1, len(imports)
    node = imports[0]
    assert node.end_lineno is not None
    aliases = [(alias.name, alias.asname) for alias in node.names]
    required = [
        ("_spina_v25_collector_colors", None),
        ("_spina_v25_collector_colors", "_spina_v27_route_colors"),
        ("_spina_v32_login_colors", None),
    ]
    for item in required:
        if item not in aliases:
            aliases.append(item)

    rendered = ["from spina_app.theme_palettes import ("]
    for name, asname in aliases:
        rendered.append(f"    {name}" + (f" as {asname}" if asname else "") + ",")
    rendered.append(")")

    lines = text.splitlines()
    lines[node.lineno - 1:node.end_lineno] = rendered
    suffix = "\n" if text.endswith("\n") else ""
    updated = "\n".join(lines) + suffix
    ast.parse(updated)
    return updated


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    target_nodes: dict[str, ast.FunctionDef] = {}
    sources: dict[str, str] = {}
    for name in TARGETS:
        node, source = verify_target(desktop_text, desktop_tree, name)
        target_nodes[name] = node
        sources[name] = source

    for (path, name, mode), expected in PROTECTED_CALLERS.items():
        verify_function_hash(path, name, expected, mode)
    for name, expected in PALETTE_HASHES.items():
        verify_function_hash(THEME_PALETTES, name, expected, "newline")

    ui_text = UI_CONTROLS.read_text(encoding="utf-8")
    ui_tree = ast.parse(ui_text)
    for name in TARGETS:
        assert not [node for node in ui_tree.body if isinstance(node, ast.FunctionDef) and node.name == name], name

    ui_updated = rewrite_palette_import(ui_text)
    ui_updated = ui_updated.rstrip() + "\n\n\n" + "\n\n".join(
        normalized(sources[name]).rstrip() for name in TARGETS
    ) + "\n"
    ui_updated_tree = ast.parse(ui_updated)
    for name in TARGETS:
        moved = top_function(ui_updated, ui_updated_tree, name)
        assert source_hash(source_for(ui_updated, moved)) == EXPECTED_HASHES[name]

    lines = desktop_text.splitlines()
    first = target_nodes[TARGETS[0]]
    assert first.end_lineno is not None
    import_block = [
        "from spina_app.ui_controls import (",
        "    _spina_v25_collector_button,",
        "    _spina_v27_route_button,",
        "    _spina_v32_login_button,",
        ")",
    ]
    edits: list[tuple[int, int, list[str]]] = [(first.lineno - 1, first.end_lineno, import_block)]
    for name in TARGETS[1:]:
        node = target_nodes[name]
        assert node.end_lineno is not None
        edits.append((node.lineno - 1, node.end_lineno, []))
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = replacement
    desktop_updated = "\n".join(lines) + ("\n" if desktop_text.endswith("\n") else "")
    desktop_updated_tree = ast.parse(desktop_updated)

    for name in TARGETS:
        assert not [node for node in desktop_updated_tree.body if isinstance(node, ast.FunctionDef) and node.name == name], name
    complete_imports = [
        node for node in desktop_updated_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.ui_controls"
        and set(TARGETS).issubset({alias.asname or alias.name for alias in node.names})
    ]
    assert len(complete_imports) == 1, len(complete_imports)
    legacy_builder = top_function(desktop_updated, desktop_updated_tree, "_spina_v25_build_collectors_tab")
    assert complete_imports[0].lineno < legacy_builder.lineno

    for (path, name, mode), expected in PROTECTED_CALLERS.items():
        if path == DESKTOP:
            node = top_function(desktop_updated, desktop_updated_tree, name)
            assert source_hash(source_for(desktop_updated, node), mode) == expected
        else:
            verify_function_hash(path, name, expected, mode)

    UI_CONTROLS.write_text(ui_updated, encoding="utf-8")
    DESKTOP.write_text(desktop_updated, encoding="utf-8")
    print("Prepared guarded Wave 50 UI button consolidation: 3 factories, 87 lines.")


if __name__ == "__main__":
    main()
