"""Apply SPINA modularization Wave 22 for Collectors summary presentation helpers."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/collectors.py")
TEST = Path("tools/test_collectors_summary_wave_22.py")
PERMANENT_WORKFLOW = Path(".github/workflows/collectors-summary-wave-22.yml")
TEMP_WORKFLOW = Path(".github/workflows/apply-collectors-summary-wave-22.yml")
SELF = Path("tools/apply_collectors_summary_wave_22.py")

TARGETS = {
    "_spina_v25_collector_card": "b9ca1623ad69f7052c4bd547032785a22367c206764167182cfea3e039d56137",
    "_spina_v25_style_collector_trees": "95dfa8ba6f95999c1dd4ccd1d3f9a5ff0bc9f03862dfd7d2ead365a676ecd250",
    "_spina_v25_update_collector_cards": "1698c4918ee9795c2721a073ebf0ae98c8feab860c6081d1974594c79ccddbb7",
}
EXPECTED_SOURCE_SHA = "34a90eda8af221dde254a2681cb44f966b157784ebfc585f50704abbb49708a4"
IMPORT_BLOCK = [
    "from spina_app.tabs.collectors import (",
    "    _spina_v25_collector_card,",
    "    _spina_v25_style_collector_trees,",
    "    _spina_v25_update_collector_cards,",
    ")",
]


def function_source(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    source_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"Unexpected current-main source SHA: {source_sha}")

    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))
    nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS
    }
    missing = sorted(set(TARGETS) - set(nodes))
    if missing:
        raise SystemExit(f"Missing target functions: {missing}")

    sources: dict[str, str] = {}
    ranges: list[tuple[int, int, str]] = []
    for name in TARGETS:
        node = nodes[name]
        source = function_source(lines, node)
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if digest != TARGETS[name]:
            raise SystemExit(f"Source hash mismatch for {name}: {digest}")
        sources[name] = source
        ranges.append((node.lineno, node.end_lineno, name))

    ranges.sort()
    output: list[str] = []
    cursor = 0
    inserted = False
    for start, end, _name in ranges:
        output.extend(lines[cursor : start - 1])
        if not inserted:
            output.extend(IMPORT_BLOCK)
            inserted = True
        cursor = end
    output.extend(lines[cursor:])
    SOURCE.write_text("\n".join(output) + "\n", encoding="utf-8")

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    module_text = '''"""Collectors summary presentation helpers extracted from the SPINA desktop entry module.

Collector records, route assignment, database access, printing, notes, and calculations remain
owned by the desktop application. This module owns only summary-card construction, Treeview
styling, and display-card refresh behavior.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from spina_app.theme_palettes import _spina_v25_collector_colors
from spina_app.utilities.numbers import _spina_v25_parse_count_from_var

'''
    module_text += "\n\n\n".join(sources[name] for name in TARGETS) + "\n"
    MODULE.write_text(module_text, encoding="utf-8")

    TEST.write_text(TEST_CONTENT, encoding="utf-8")
    PERMANENT_WORKFLOW.write_text(PERMANENT_WORKFLOW_CONTENT, encoding="utf-8")

    TEMP_WORKFLOW.unlink(missing_ok=True)
    SELF.unlink(missing_ok=True)


TEST_CONTENT = r'''"""Regression checks for Collectors summary presentation Wave 22."""

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
'''

PERMANENT_WORKFLOW_CONTENT = r'''name: Collectors summary Wave 22

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    if: github.head_ref == 'agent/collectors-summary-wave-22'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 30
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Verify local Python
        shell: cmd
        run: |
          where python
          python --version

      - name: Compile application, module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app\tabs\collectors.py
          python -m py_compile tools\test_collectors_summary_wave_22.py

      - name: Run Collectors summary regression
        shell: cmd
        run: python -m tools.test_collectors_summary_wave_22

      - name: Run redundancy audit
        shell: cmd
        run: python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json redundancy-report.json

      - name: Run SPINA quality audit
        shell: cmd
        run: python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json quality-report.json

      - name: Upload audit reports
        uses: actions/upload-artifact@v4
        with:
          name: collectors-summary-wave-22-audits
          path: |
            redundancy-report.json
            quality-report.json
'''


if __name__ == "__main__":
    main()
