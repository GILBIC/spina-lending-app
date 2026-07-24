"""Regression checks for Collectors summary presentation Wave 22."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/collectors.py")
TARGETS = {
    "_spina_v25_collector_card": "b9ca1623ad69f7052c4bd547032785a22367c206764167182cfea3e039d56137",
    "_spina_v25_style_collector_trees": "95dfa8ba6f95999c1dd4ccd1d3f9a5ff0bc9f03862dfd7d2ead365a676ecd250",
    "_spina_v25_update_collector_cards": "1698c4918ee9795c2721a073ebf0ae98c8feab860c6081d1974594c79ccddbb7",
}


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def main() -> None:
    app_text = SOURCE.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text, filename=str(SOURCE))
    remaining = {
        node.name
        for node in app_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS
    }
    assert not remaining, f"Definitions still remain in desktop source: {sorted(remaining)}"

    imported = set()
    for node in app_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.collectors":
            imported.update(alias.name for alias in node.names)
    assert imported == set(TARGETS), f"Collectors imports differ: {sorted(imported)}"

    module_text = MODULE.read_text(encoding="utf-8")
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text, filename=str(MODULE))
    module_nodes = {
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS
    }
    assert set(module_nodes) == set(TARGETS), f"Module definitions differ: {sorted(module_nodes)}"

    for name, expected_hash in TARGETS.items():
        source = source_for(module_lines, module_nodes[name])
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        assert digest == expected_hash, f"Source changed for {name}: {digest}"

    module = importlib.import_module("spina_app.tabs.collectors")
    for name in TARGETS:
        value = getattr(module, name, None)
        assert callable(value), f"{name} is not callable after import"

    assert hasattr(module, "_spina_v25_collector_colors")
    assert hasattr(module, "_spina_v25_parse_count_from_var")
    print("Collectors summary Wave 22 regression passed.")


if __name__ == "__main__":
    main()
