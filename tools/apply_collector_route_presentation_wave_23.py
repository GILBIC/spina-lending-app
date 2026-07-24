"""Apply SPINA modularization Wave 23 for Collector Route presentation helpers."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/collector_route.py")
TEST = Path("tools/test_collector_route_presentation_wave_23.py")
PERMANENT_WORKFLOW = Path(".github/workflows/collector-route-presentation-wave-23.yml")
TEMP_WORKFLOW = Path(".github/workflows/apply-collector-route-presentation-wave-23.yml")
SELF = Path("tools/apply_collector_route_presentation_wave_23.py")

TARGETS = {
    "_spina_v27_update_route_cards": "f94913183205a9e0d867eb955635e03a56f710cc4d24d17b473f42f522037c09",
    "_spina_v27_hidden_collector_widgets": "2c0e5dc9118fcf9f4dc5c4e3c90c8295e648f1b78e9d24895286048bb1933d7a",
}
PROTECTED = {
    "_spina_v27_route_button": "8844297897e05fbfe9667fbee211551769923d062993f9c2798b7e9b8d577dfb",
    "_spina_v27_build_collectors_tab": "3494cf016d693790236be39cdaa3248c72b6828fc06b5a7df764c452a385d68e",
    "_spina_v27_get_route_master_areas": "f8d7d34de72b66a467f1108d5476c022caa6e5c5e08d40b167b7a599959f2ce5",
    "_spina_v27_collector_editor_dialog": "030e09ac5b71b6acfd3564ddc7f70eb96616a11692ba80c385fbc942886dbd98",
}
EXPECTED_SOURCE_SHA = "8d56ff494c763bfec00df968173b548220af8f6a68ecb63b63fa1f2f83981e98"
IMPORT_BLOCK = [
    "from spina_app.tabs.collector_route import (",
    "    configure_collector_route_dependencies,",
    "    _spina_v27_update_route_cards,",
    "    _spina_v27_hidden_collector_widgets,",
    ")",
    "configure_collector_route_dependencies(globals())",
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
    all_nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(TARGETS) - set(all_nodes))
    if missing:
        raise SystemExit(f"Missing target functions: {missing}")

    for name, expected_hash in PROTECTED.items():
        node = all_nodes.get(name)
        if node is None:
            raise SystemExit(f"Missing protected function: {name}")
        digest = hashlib.sha256(function_source(lines, node).encode("utf-8")).hexdigest()
        if digest != expected_hash:
            raise SystemExit(f"Protected source changed for {name}: {digest}")

    sources: dict[str, str] = {}
    ranges: list[tuple[int, int, str]] = []
    for name, expected_hash in TARGETS.items():
        node = all_nodes[name]
        source = function_source(lines, node)
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if digest != expected_hash:
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
    module_text = '''"""Collector Route presentation helpers extracted from the SPINA desktop entry module.

Collector records, route assignments, PostgreSQL access, printing, notes, closing, and all
payment or balance calculations remain owned by the desktop application. This module owns only
route summary-card refresh and hidden compatibility widget construction.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Mapping

from spina_app.utilities.numbers import _spina_v27_count_from_text

_REQUIRED_DEPENDENCIES = ("_spina_v27_route_colors",)


def configure_collector_route_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind the desktop-owned Collector Route palette helper."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)

'''
    module_text += "\n\n\n".join(sources[name] for name in TARGETS) + "\n"
    MODULE.write_text(module_text, encoding="utf-8")

    TEST.write_text(TEST_CONTENT, encoding="utf-8")
    PERMANENT_WORKFLOW.write_text(PERMANENT_WORKFLOW_CONTENT, encoding="utf-8")

    TEMP_WORKFLOW.unlink(missing_ok=True)
    SELF.unlink(missing_ok=True)


TEST_CONTENT = r'''"""Regression checks for Collector Route presentation Wave 23."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/collector_route.py")
TARGETS = {
    "_spina_v27_update_route_cards": "f94913183205a9e0d867eb955635e03a56f710cc4d24d17b473f42f522037c09",
    "_spina_v27_hidden_collector_widgets": "2c0e5dc9118fcf9f4dc5c4e3c90c8295e648f1b78e9d24895286048bb1933d7a",
}
PROTECTED = {
    "_spina_v27_route_button": "8844297897e05fbfe9667fbee211551769923d062993f9c2798b7e9b8d577dfb",
    "_spina_v27_build_collectors_tab": "3494cf016d693790236be39cdaa3248c72b6828fc06b5a7df764c452a385d68e",
    "_spina_v27_get_route_master_areas": "f8d7d34de72b66a467f1108d5476c022caa6e5c5e08d40b167b7a599959f2ce5",
    "_spina_v27_collector_editor_dialog": "030e09ac5b71b6acfd3564ddc7f70eb96616a11692ba80c385fbc942886dbd98",
}


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def main() -> None:
    app_text = SOURCE.read_text(encoding="utf-8")
    app_lines = app_text.splitlines()
    app_tree = ast.parse(app_text, filename=str(SOURCE))
    app_nodes = {
        node.name: node
        for node in app_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    remaining = set(TARGETS) & set(app_nodes)
    assert not remaining, f"Definitions still remain in desktop source: {sorted(remaining)}"

    imported = set()
    for node in app_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.collector_route":
            imported.update(alias.name for alias in node.names)
    assert set(TARGETS).issubset(imported), f"Collector Route imports differ: {sorted(imported)}"
    assert "configure_collector_route_dependencies" in imported
    assert "configure_collector_route_dependencies(globals())" in app_text

    for name, expected_hash in PROTECTED.items():
        node = app_nodes.get(name)
        assert node is not None, f"Protected function missing: {name}"
        digest = hashlib.sha256(source_for(app_lines, node).encode("utf-8")).hexdigest()
        assert digest == expected_hash, f"Protected source changed for {name}: {digest}"

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

    module = importlib.import_module("spina_app.tabs.collector_route")
    for name in TARGETS:
        assert callable(getattr(module, name, None)), f"{name} is not callable after import"

    configure = getattr(module, "configure_collector_route_dependencies", None)
    assert callable(configure)
    sentinel = lambda _self=None: {"green": "#0", "orange": "#1", "panel": "#2", "fg": "#3"}
    assert configure({"_spina_v27_route_colors": sentinel}) == ()
    assert module._spina_v27_route_colors is sentinel
    assert hasattr(module, "_spina_v27_count_from_text")
    print("Collector Route presentation Wave 23 regression passed.")


if __name__ == "__main__":
    main()
'''

PERMANENT_WORKFLOW_CONTENT = r'''name: Collector Route presentation Wave 23

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    if: github.head_ref == 'agent/collector-route-presentation-wave-23'
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
          python -m py_compile spina_app\tabs\collector_route.py
          python -m py_compile tools\test_collector_route_presentation_wave_23.py

      - name: Run Collector Route presentation regression
        shell: cmd
        run: python -m tools.test_collector_route_presentation_wave_23

      - name: Run redundancy audit
        shell: cmd
        run: python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json redundancy-report.json

      - name: Run SPINA quality audit
        shell: cmd
        run: python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json quality-report.json

      - name: Upload audit reports
        uses: actions/upload-artifact@v4
        with:
          name: collector-route-presentation-wave-23-audits
          path: |
            redundancy-report.json
            quality-report.json
'''


if __name__ == "__main__":
    main()
