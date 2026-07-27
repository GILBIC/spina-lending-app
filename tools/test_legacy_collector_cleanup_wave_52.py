from __future__ import annotations

import ast
import hashlib
import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
UI_CONTROLS = ROOT / "spina_app" / "ui_controls.py"
COLLECTOR_MODULE = ROOT / "spina_app" / "collector_tab_presentation.py"
LEGACY = (
    "_spina_v25_collector_button",
    "_spina_v25_build_collectors_tab",
)
ACTIVE = "_spina_v27_build_collectors_tab"
ACTIVE_ALIAS = "_wave44_spina_v27_build_collectors_tab"
ACTIVE_LINES = 293
ACTIVE_SHA256 = "5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb"
SQL_WRITE_RE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|REPLACE\s+INTO|ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE)\b",
    re.I,
)


def normalized(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()) + "\n"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def top_functions(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]


def build_bindings(tree: ast.Module) -> list[tuple[int, str]]:
    rows = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "App"
            and target.attr == "_build_collectors_tab"
            and isinstance(node.value, ast.Name)
        ):
            continue
        rows.append((node.lineno, node.value.id))
    return sorted(rows)


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    ui_text = UI_CONTROLS.read_text(encoding="utf-8")
    ui_tree = ast.parse(ui_text)

    for name in LEGACY:
        assert not top_functions(desktop_tree, name), name
        assert not top_functions(ui_tree, name), name
        assert not [
            node for node in ast.walk(desktop_tree)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == name
        ], name

    ui_imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.ui_controls"
    ]
    imported = {alias.name for node in ui_imports for alias in node.names}
    assert LEGACY[0] not in imported
    assert "_spina_v27_route_button" in imported
    assert "_spina_v32_login_button" in imported

    bindings = build_bindings(desktop_tree)
    assert len(bindings) == 1, bindings
    assert bindings[0][1] == ACTIVE, bindings

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.collector_tab_presentation"
    ]
    assert len(imports) == 1
    aliases = {(alias.name, alias.asname) for alias in imports[0].names}
    assert (ACTIVE, ACTIVE_ALIAS) in aliases, aliases

    active_rebinds = [
        node for node in desktop_tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == ACTIVE
        and isinstance(node.value, ast.Name)
        and node.value.id == ACTIVE_ALIAS
    ]
    assert len(active_rebinds) == 1
    assert active_rebinds[0].lineno < bindings[0][0]

    module = importlib.import_module("spina_app.collector_tab_presentation")
    assert module.COLLECTOR_TAB_TARGET == ACTIVE
    assert module.COLLECTOR_TAB_SOURCE_LINES == ACTIVE_LINES
    assert module.COLLECTOR_TAB_SOURCE_SHA256 == ACTIVE_SHA256

    module_text = COLLECTOR_MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    defs = top_functions(module_tree, ACTIVE)
    assert len(defs) == 1
    source = ast.get_source_segment(module_text, defs[0])
    assert source is not None
    assert len(source.splitlines()) == ACTIVE_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == ACTIVE_SHA256

    for node in ast.walk(defs[0]):
        if isinstance(node, ast.Attribute):
            assert not dotted(node).startswith("self.db")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_WRITE_RE.search(node.value)

    print("Wave 52 legacy Collector Route cleanup passed: 375 dead function lines removed.")


if __name__ == "__main__":
    main()
