from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

LEGACY_HASHES = {
    "_spina_v25_collector_button": "f122f949ef4a355ec83dfa5942874f408ef3ea5fb186ad4740827df8c56eb613",
    "_spina_v25_build_collectors_tab": "f5b787f580fd4202ebbc324e70da4a8c2adee5190e959c3af01b0e2402b32e92",
}
LEGACY_LINES = {
    "_spina_v25_collector_button": 29,
    "_spina_v25_build_collectors_tab": 346,
}
ACTIVE = "_spina_v27_build_collectors_tab"
ACTIVE_IMPORT_ALIAS = "_wave44_spina_v27_build_collectors_tab"


def normalized_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def top_functions(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]


def source_for(text: str, node: ast.AST) -> str:
    source = ast.get_source_segment(text, node)
    assert source is not None
    return source


def build_bindings(tree: ast.Module) -> list[tuple[ast.Assign, str]]:
    rows: list[tuple[ast.Assign, str]] = []
    for node in ast.walk(tree):
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
        rows.append((node, node.value.id))
    rows.sort(key=lambda row: row[0].lineno)
    return rows


def owner_map(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.FunctionDef):
            return current.name
        current = parents.get(current)
    return None


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    tree = ast.parse(text)

    legacy_nodes: dict[str, ast.FunctionDef] = {}
    for name, expected_hash in LEGACY_HASHES.items():
        matches = top_functions(tree, name)
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = source_for(text, node)
        assert normalized_hash(source) == expected_hash, (name, normalized_hash(source))
        actual_lines = (node.end_lineno or node.lineno) - node.lineno + 1
        assert actual_lines == LEGACY_LINES[name], (name, actual_lines)
        legacy_nodes[name] = node

    parents = owner_map(tree)
    button_loads = []
    builder_loads = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            continue
        if node.id == "_spina_v25_collector_button":
            button_loads.append((node.lineno, enclosing_function(node, parents)))
        elif node.id == "_spina_v25_build_collectors_tab":
            builder_loads.append((node.lineno, enclosing_function(node, parents)))
    assert button_loads and all(owner == "_spina_v25_build_collectors_tab" for _, owner in button_loads), button_loads
    assert len(builder_loads) == 1 and builder_loads[0][1] is None, builder_loads

    bindings = build_bindings(tree)
    binding_values = [value for _, value in bindings]
    assert binding_values == ["_spina_v25_build_collectors_tab", ACTIVE], binding_values
    legacy_binding = bindings[0][0]

    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.collector_tab_presentation"
    ]
    assert len(imports) == 1
    aliases = {(alias.name, alias.asname) for alias in imports[0].names}
    assert (ACTIVE, ACTIVE_IMPORT_ALIAS) in aliases, aliases

    active_rebinds = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == ACTIVE
        and isinstance(node.value, ast.Name)
        and node.value.id == ACTIVE_IMPORT_ALIAS
    ]
    assert len(active_rebinds) == 1
    assert active_rebinds[0].lineno < bindings[-1][0].lineno

    edits: list[tuple[int, int]] = []
    for node in legacy_nodes.values():
        assert node.end_lineno is not None
        edits.append((node.lineno - 1, node.end_lineno))
    assert legacy_binding.end_lineno is not None
    edits.append((legacy_binding.lineno - 1, legacy_binding.end_lineno))

    for start, end in sorted(edits, reverse=True):
        del lines[start:end]

    updated = newline.join(lines) + (newline if text.endswith(("\n", "\r\n")) else "")
    updated_tree = ast.parse(updated)
    for name in LEGACY_HASHES:
        assert not top_functions(updated_tree, name), name
        assert not [
            node for node in ast.walk(updated_tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name
        ], name

    updated_bindings = build_bindings(updated_tree)
    assert [value for _, value in updated_bindings] == [ACTIVE], updated_bindings
    updated_imports = [
        node for node in updated_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.collector_tab_presentation"
    ]
    assert len(updated_imports) == 1
    updated_aliases = {(alias.name, alias.asname) for alias in updated_imports[0].names}
    assert (ACTIVE, ACTIVE_IMPORT_ALIAS) in updated_aliases

    DESKTOP.write_text(updated, encoding="utf-8", newline="")
    print("Removed 375 lines of superseded v25 Collector Route presentation code.")


if __name__ == "__main__":
    main()
