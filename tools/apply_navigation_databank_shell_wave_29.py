"""Guarded extractor for Navigation + Data Bank shell Wave 29."""

from __future__ import annotations

import ast
import hashlib
import subprocess
import textwrap
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
NAV_MODULE = ROOT / "spina_app" / "navigation.py"
DATA_MODULE = ROOT / "spina_app" / "tabs" / "data_bank_shell.py"
PERMANENT_WORKFLOW = ROOT / ".github" / "workflows" / "navigation-databank-shell-wave-29.yml"

EXPECTED_SOURCE_BLOB = "fd3c6dd0509c3b4fedc14fc22068825b4280f31b"
EXPECTED_HASHES = {
    "navigation": {
        "_update_data_toolbar": "1af8b42b2ee75d4f77895c3967aeeae7da2f52ca252802d4d998a30037af27d8",
        "_side_nav_items": "2292ae8c5f0abfb3377e87f3806b3b4fdb60044c9d87d12870058c46f3070992",
        "_rebuild_side_nav": "21038d8e472cb203ef8d97bb7ca046ba1f0aa5747c50b4bb8e93fbc8e8f321ac",
        "_refresh_side_nav_selection": "267a6a9c6b03e86e0bb5a7e8f12d6ba30d45f671aeca5b5768e043e304265b7f",
        "_header_palette": "95fe45cc646eb065f154c094f0ff0c3a0ca3d0daedd9912f431df04e91b6ea6a",
        "_make_header_button": "3e459cc3abb6a0a9e75d6579c16ceed914bf132a5ccbce1068189848bc363ec3",
        "_refresh_mode_toggle": "59fcb7a113e603b46a57c4a4104df994117ec007ef5f7980e6337ce62e2ee91c",
        "_vscroll": "48efe34b1cd4c5c71242b0ff1a804abb1804ee43d2c483851226d2ae4f3394f1",
        "_month_label": "28a2bef3865fa0cd2f818b97b33b2f885b967b5f7ea0d9cb83f744a8bced412a",
        "_on_mousewheel_sync": "7258e548972db5e497e1177b9bedc778822ebe924afde5f4935afcc278e16dc6",
        "_update_toolbar_states": "bd423a3ffc8b56588c4816137f4a9f5180da3767ee947f8b164de4283bf542bd",
    },
    "data_bank_shell": {
        "_looks_like_data_grid": "c46f3d5b5f3363d46352d1dc690a075820f59a62d21969d134054557a747b6ff",
        "_locate_data_tree": "355c3a1b8445ce76e1fd939447b00766d881feed1a2903035a5882a31266d0a5",
        "_ensure_databank_edit_bindings": "afc7b403055a870249ef2aeca67d8d2e32b29960a97787fdb01307ef5aeafe9b",
        "_show_audit_tab": "b9c0a43f780b524fba160c1fb6b83feab1c5b82a3d772a1e54598b967767a18f",
        "_hide_audit_tab": "ae19be5e52cef380acf5b7148668a5f8561076b926cdea35be5841fd42d5d5eb",
        "_resize_databank_columns": "d350345101372a9246ffeb133be9c8b201adb72b123d95167656ddd3f0c0f927",
    },
}
ALL_TARGETS = {name for group in EXPECTED_HASHES.values() for name in group}
EXPECTED_LINES = 546

NAV_HEADER = '''"""Navigation presentation helpers extracted from the SPINA desktop entry module."""

from __future__ import annotations

import calendar
import os
import tkinter as tk
from tkinter import ttk


def _noop_log(*args, **kwargs):
    return None


_log_suppressed_once = _noop_log


def fmt_currency(value):
    return str(value)


def configure_navigation_dependencies(*, log_suppressed_once, fmt_currency_callback):
    """Bind application-owned logging and currency display helpers."""
    global _log_suppressed_once, fmt_currency
    _log_suppressed_once = log_suppressed_once or _noop_log
    fmt_currency = fmt_currency_callback or str
'''

DATA_HEADER = '''"""Data Bank shell and layout helpers extracted from the SPINA desktop entry module."""

from __future__ import annotations


def _noop_log(*args, **kwargs):
    return None


_log_suppressed_once = _noop_log
_log_ignored = _noop_log


def configure_data_bank_shell_dependencies(*, log_suppressed_once, log_ignored):
    """Bind application-owned logging helpers used by Data Bank presentation code."""
    global _log_suppressed_once, _log_ignored
    _log_suppressed_once = log_suppressed_once or _noop_log
    _log_ignored = log_ignored or _noop_log
'''

PERMANENT_WORKFLOW_TEXT = '''name: Navigation and Data Bank shell Wave 29

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    if: github.head_ref == 'agent/navigation-databank-shell-wave-29'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 35

    steps:
      - name: Check out exact PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0

      - name: Verify local Python
        shell: cmd
        run: |
          where python
          python --version

      - name: Compile application, Wave 29 modules, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app/navigation.py
          python -m py_compile spina_app/tabs/data_bank_shell.py
          python -m py_compile tools/test_navigation_databank_shell_wave_29.py
          python -m compileall -q spina_app

      - name: Run Navigation and Data Bank shell regression
        shell: cmd
        run: python -m tools.test_navigation_databank_shell_wave_29

      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check

      - name: Run redundancy audit
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-29-redundancy.json

      - name: Run SPINA quality audit
        shell: cmd
        run: python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-29-quality.json

      - name: Upload Wave 29 reports
        uses: actions/upload-artifact@v4
        with:
          name: navigation-databank-shell-wave-29-reports
          path: |
            artifacts/wave-29-redundancy.json
            artifacts/wave-29-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], cwd=ROOT, text=True
    ).strip()


def source_segment(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def recursive_function_hashes(text: str) -> dict[str, str]:
    tree = ast.parse(text)
    lines = text.splitlines()
    result: dict[str, str] = {}

    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{node.name}"
                segment = source_segment(lines, node)
                result[name] = hashlib.sha256(segment.encode("utf-8")).hexdigest()
                visit(node.body, f"{name}.")

    visit(tree.body)
    return result


def original_app_assignments(text: str) -> list[tuple[str, str]]:
    tree = ast.parse(text)
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
                and target.attr in ALL_TARGETS
            ):
                rows.append((target.attr, ast.dump(node.value, include_attributes=False)))
    return rows


def replacement_lines(value: str) -> list[str]:
    if value and not value.endswith("\n"):
        value += "\n"
    return value.splitlines(keepends=True)


def apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    lines = text.splitlines(keepends=True)
    for start, end, replacement in sorted(edits, key=lambda item: item[0], reverse=True):
        lines[start:end] = replacement_lines(replacement)
    return "".join(lines)


def alias(group: str, name: str) -> str:
    stem = name.lstrip("_")
    prefix = "nav" if group == "navigation" else "dbshell"
    return f"_wave29_{prefix}_{stem}"


def wiring_block() -> str:
    nav_imports = [
        "    configure_navigation_dependencies as _wave29_configure_navigation,",
        *[
            f"    {name} as {alias('navigation', name)},"
            for name in EXPECTED_HASHES["navigation"]
        ],
    ]
    data_imports = [
        "    configure_data_bank_shell_dependencies as _wave29_configure_data_bank_shell,",
        *[
            f"    {name} as {alias('data_bank_shell', name)},"
            for name in EXPECTED_HASHES["data_bank_shell"]
        ],
    ]
    assignments = [
        f"App.{name} = {alias(group, name)}"
        for group in ("navigation", "data_bank_shell")
        for name in EXPECTED_HASHES[group]
    ]
    return "\n".join(
        [
            "",
            "# Navigation + Data Bank shell helpers extracted in Wave 29.",
            "from spina_app.navigation import (",
            *nav_imports,
            ")",
            "from spina_app.tabs.data_bank_shell import (",
            *data_imports,
            ")",
            "",
            "_wave29_configure_navigation(",
            "    log_suppressed_once=_log_suppressed_once,",
            "    fmt_currency_callback=fmt_currency,",
            ")",
            "_wave29_configure_data_bank_shell(",
            "    log_suppressed_once=_log_suppressed_once,",
            "    log_ignored=_log_ignored,",
            ")",
            "",
            *assignments,
            "",
        ]
    )


def build_module(header: str, sources: list[str]) -> str:
    functions = [textwrap.dedent(source) for source in sources]
    return header.rstrip() + "\n\n\n" + "\n\n\n".join(functions) + "\n"


def main() -> None:
    assert git_blob(SOURCE) == EXPECTED_SOURCE_BLOB, (
        git_blob(SOURCE),
        EXPECTED_SOURCE_BLOB,
    )
    assert not NAV_MODULE.exists(), NAV_MODULE
    assert not DATA_MODULE.exists(), DATA_MODULE
    assert not PERMANENT_WORKFLOW.exists(), PERMANENT_WORKFLOW

    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))
    apps = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"]
    assert len(apps) == 1
    app = apps[0]
    methods: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = defaultdict(list)
    for node in app.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods[node.name].append(node)

    extracted: dict[str, list[str]] = {"navigation": [], "data_bank_shell": []}
    edits: list[tuple[int, int, str]] = []
    total_lines = 0
    for group, hashes in EXPECTED_HASHES.items():
        for name, expected_hash in hashes.items():
            nodes = methods.get(name, [])
            assert len(nodes) == 1, (name, len(nodes))
            node = nodes[0]
            source = source_segment(lines, node)
            actual_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
            assert actual_hash == expected_hash, (name, actual_hash, expected_hash)
            total_lines += (node.end_lineno or node.lineno) - node.lineno + 1
            extracted[group].append(source)
            edits.append((node.lineno - 1, node.end_lineno, ""))
    assert total_lines == EXPECTED_LINES, total_lines

    original_hashes = recursive_function_hashes(text)
    original_assignments = original_app_assignments(text)
    assert original_assignments == [
        (
            "_update_data_toolbar",
            "Name(id='_spina_dayclose_update_data_toolbar', ctx=Load())",
        )
    ], original_assignments

    edits.append((app.end_lineno, app.end_lineno, wiring_block()))
    new_source = apply_edits(text, edits)
    ast.parse(new_source, filename=str(SOURCE))

    new_hashes = recursive_function_hashes(new_source)
    removed = {f"App.{name}" for name in ALL_TARGETS}
    assert set(original_hashes) - set(new_hashes) == removed
    assert not (set(new_hashes) - set(original_hashes))
    for name, expected_hash in original_hashes.items():
        if name in removed:
            continue
        assert new_hashes[name] == expected_hash, name

    new_original_assignments = [
        row
        for row in original_app_assignments(new_source)
        if "_wave29_" not in row[1]
    ]
    assert new_original_assignments == original_assignments

    nav_text = build_module(NAV_HEADER, extracted["navigation"])
    data_text = build_module(DATA_HEADER, extracted["data_bank_shell"])
    ast.parse(nav_text, filename=str(NAV_MODULE))
    ast.parse(data_text, filename=str(DATA_MODULE))

    write_lf(SOURCE, new_source)
    write_lf(NAV_MODULE, nav_text)
    write_lf(DATA_MODULE, data_text)
    write_lf(PERMANENT_WORKFLOW, PERMANENT_WORKFLOW_TEXT)

    print(
        "Wave 29 guarded extraction applied:",
        len(ALL_TARGETS),
        "methods,",
        total_lines,
        "lines",
    )


if __name__ == "__main__":
    main()
