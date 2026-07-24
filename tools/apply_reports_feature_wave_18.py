from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DEST = Path("spina_app/tabs/reports.py")
MANIFEST = Path("tools/fixtures/reports_feature_wave_18_manifest.json")
TEST = Path("tools/test_reports_feature_wave_18.py")

SELECTED = [
    "_spina_v22_style_reports_tree",
    "_spina_v22_button",
    "_spina_v22_report_card",
    "_spina_v22_build_reports_tab",
    "_spina_v22_reports_selection_status",
    "_spina_v22_update_report_cards",
]

EXPECTED_HASHES = {
    "_spina_v22_style_reports_tree": "7806005950aed1a63d0441c255481debf90a2e2b163882c28d63ed7ae37212e8",
    "_spina_v22_button": "1b32428737c758fddbe7478872c58f79b0e3178b311f345831e1e04a10ac377f",
    "_spina_v22_report_card": "a096f81b7379b2927bb039eee9b61140a201c17fd2506e1be8fba0adc9fc3903",
    "_spina_v22_build_reports_tab": "e36f0feed87ada871f0123b6a0140154782fd2fe78a1bfe086d7a50611ad5e13",
    "_spina_v22_reports_selection_status": "60718c64e7c9fb25f6fb1e29ee565e69bdade7fc7e1e50150c265ca13da8527f",
    "_spina_v22_update_report_cards": "f45eb96e79ffd28794a5b30eec462a6e0d72183ad4455430e6e61bd352a2eff1",
}

DEPENDENCIES = [
    "_load_ledger_prefs",
    "_save_ledger_prefs",
    "_log_exc",
    "pick_date",
    "pick_date_range",
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def top_level_functions(text: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(text)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def source_for_node(lines: list[str], node: ast.FunctionDef) -> str:
    return "".join(lines[node.lineno - 1 : node.end_lineno]).rstrip("\r\n")


def build_module(function_sources: list[str]) -> str:
    dependency_names = ",\n    ".join(repr(name) for name in DEPENDENCIES)
    exports = ",\n    ".join(repr(name) for name in ["configure_reports_dependencies", *SELECTED])
    header = f'''"""Modern Reports tab presentation extracted from the SPINA desktop entry module.

Business calculations, PDF generation, report totals, database access, and report-log
operations remain owned by the desktop application. This module owns only the modern
Reports tab construction and display refresh helpers.
"""

from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Mapping

from spina_app.theme_palettes import _spina_v22_reports_colors

_REQUIRED_DEPENDENCIES = (
    {dependency_names},
)


def configure_reports_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind application-owned callbacks used by the Reports presentation module."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)


'''
    footer = f'''\n\n__all__ = [
    {exports},
]\n'''
    return header + "\n\n".join(function_sources) + footer


def build_import_block() -> str:
    imported = "\n".join(f"    {name}," for name in SELECTED)
    return f'''from spina_app.tabs.reports import (
    configure_reports_dependencies as _spina_v22_configure_reports_dependencies,
{imported}
)
_spina_v22_configure_reports_dependencies(globals())'''


def build_test() -> str:
    hashes_json = json.dumps(EXPECTED_HASHES, indent=4, sort_keys=True)
    selected_json = json.dumps(SELECTED, indent=4)
    return f'''from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

MAIN = Path("{MAIN.as_posix()}")
MODULE = Path("{DEST.as_posix()}")
SELECTED = {selected_json}
EXPECTED_HASHES = {hashes_json}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sources(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    out = {{}}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = "".join(lines[node.lineno - 1 : node.end_lineno]).rstrip("\\r\\n")
    return out


def _assert_structure() -> None:
    main_text = MAIN.read_text(encoding="utf-8")
    main_tree = ast.parse(main_text)
    main_defs = {{
        node.name
        for node in main_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}
    for name in SELECTED:
        assert name not in main_defs, f"{{name}} still defined in desktop source"
        assert name in main_text, f"{{name}} import or caller missing from desktop source"

    assert "_spina_v22_configure_reports_dependencies(globals())" in main_text
    assert "App._build_reports_tab = _spina_v22_build_reports_tab" in main_text
    assert "_spina_v22_prev_refresh_reports" in main_text
    assert "App.refresh_reports = _spina_v22_refresh_reports" in main_text

    module_sources = _sources(MODULE)
    for name, expected_hash in EXPECTED_HASHES.items():
        assert name in module_sources, f"{{name}} missing from Reports module"
        actual = _sha(module_sources[name])
        assert actual == expected_hash, f"{{name}} source hash changed: {{actual}}"


def _assert_dependency_bridge() -> None:
    mod = importlib.import_module("spina_app.tabs.reports")
    sentinels = {{
        "_load_ledger_prefs": lambda: {{"reports_page_size": "A4"}},
        "_save_ledger_prefs": lambda prefs: prefs,
        "_log_exc": lambda *args, **kwargs: None,
        "pick_date": lambda *args, **kwargs: None,
        "pick_date_range": lambda *args, **kwargs: None,
    }}
    missing = mod.configure_reports_dependencies(sentinels)
    assert missing == ()
    for name, value in sentinels.items():
        assert getattr(mod, name) is value


def _assert_card_refresh_behavior() -> None:
    mod = importlib.import_module("spina_app.tabs.reports")

    class Var:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value

    class Label:
        def __init__(self):
            self.text = None
        def configure(self, **kwargs):
            self.text = kwargs.get("text")

    class Tree:
        def get_children(self):
            return ("a", "b", "c")

    labels = {{key: (Label(), Label()) for key in ("clients", "view", "range", "page")}}
    app = type("AppStub", (), {{}})()
    app._reports_stat_labels = labels
    app.reports_tree = Tree()
    app._mode_filter = lambda: "7x7"
    app.start_date_var = Var("2026-07-01")
    app.end_date_var = Var("2026-07-24")
    app.report_page_size_var = Var("Folio 8.5 x 13")

    result = mod._spina_v22_update_report_cards(app)
    assert result is None
    assert labels["clients"][0].text == "3"
    assert labels["view"][0].text == "7x7"
    assert labels["range"][0].text == "2026-07-01 → 2026-07-24"
    assert labels["page"][0].text == "Folio 8.5 x 13"


def main() -> None:
    _assert_structure()
    _assert_dependency_bridge()
    _assert_card_refresh_behavior()
    print("Reports feature Wave 18 regression passed")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    text = MAIN.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    functions = top_level_functions(text)

    missing = [name for name in SELECTED if name not in functions]
    if missing:
        if DEST.exists() and all(name not in functions for name in SELECTED):
            print("Reports feature already extracted")
            return
        raise RuntimeError(f"Missing selected Reports functions: {missing}")

    nodes = [functions[name] for name in SELECTED]
    nodes.sort(key=lambda node: node.lineno)
    if [node.name for node in nodes] != SELECTED:
        raise RuntimeError("Reports functions are not in the expected source order")

    sources: list[str] = []
    records = []
    for node in nodes:
        source = source_for_node(lines, node)
        actual_hash = sha256_text(source)
        expected_hash = EXPECTED_HASHES[node.name]
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Exact source guard failed for {node.name}: expected {expected_hash}, got {actual_hash}"
            )
        sources.append(source)
        records.append(
            {
                "name": node.name,
                "start_line": node.lineno,
                "end_line": node.end_lineno,
                "source_lines": node.end_lineno - node.lineno + 1,
                "sha256": actual_hash,
            }
        )

    for previous, current in zip(nodes, nodes[1:]):
        between = "".join(lines[previous.end_lineno : current.lineno - 1])
        if between.strip():
            raise RuntimeError(
                f"Unexpected non-whitespace source between {previous.name} and {current.name}"
            )

    start = nodes[0].lineno - 1
    end = nodes[-1].end_lineno
    import_block = build_import_block() + "\n\n"
    new_text = "".join(lines[:start]) + import_block + "".join(lines[end:])

    DEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(build_module(sources), encoding="utf-8", newline="\n")
    MAIN.write_text(new_text, encoding="utf-8", newline="\n")
    MANIFEST.write_text(
        json.dumps(
            {
                "wave": 18,
                "feature": "modern_reports_presentation",
                "destination": DEST.as_posix(),
                "function_count": len(SELECTED),
                "moved_source_lines": sum(item["source_lines"] for item in records),
                "dependencies_kept_in_desktop": DEPENDENCIES,
                "functions": records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    TEST.write_text(build_test(), encoding="utf-8", newline="\n")

    ast.parse(MAIN.read_text(encoding="utf-8"))
    ast.parse(DEST.read_text(encoding="utf-8"))
    ast.parse(TEST.read_text(encoding="utf-8"))
    print(f"Extracted {len(SELECTED)} Reports functions and {sum(item['source_lines'] for item in records)} lines")


if __name__ == "__main__":
    main()
