#!/usr/bin/env python3
"""Guarded, idempotent complete Reports extraction for SPINA Wave 80."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
ENGINE_PATH = ROOT / "spina_app" / "report_engine.py"

ENGINE_START = "# ==== BEGIN: SOA ADV/RANGE RENDERING PATCH ===="
ENGINE_END = "# ==== END: SOA ADV/RANGE RENDERING PATCH ===="
INSTALL_START = "# --- BEGIN: Reports feature installer Wave 80 ---"
INSTALL_END = "# --- END: Reports feature installer Wave 80 ---"

REPORT_METHODS = (
    "refresh_reports",
    "open_report_generation_log",
    "_get_report_note_text",
    "_set_report_note_text",
    "_save_dated_note_for_client",
    "_auto_load_report_note",
    "_get_selected_report_client",
    "_save_report_note_for_client",
    "_load_report_note_for_client",
)

WAVE64_BLOCK = '''# Wave 64: Reports tab presentation.
from spina_app.reports_tab_presentation import (
    configure_reports_tab_dependencies as _configure_wave64_reports_tab,
    _build_reports_tab as _wave64_build_reports_tab,
)
_configure_wave64_reports_tab(globals())
App._build_reports_tab = _wave64_build_reports_tab
'''

WAVE67_BLOCK = '''# Wave 67: Client statement generation orchestration.
from spina_app.client_statement_generation import (
    configure_client_statement_generation_dependencies as _configure_wave67_client_statement_generation,
    generate_pdf_selected as _wave67_generate_pdf_selected,
)
_configure_wave67_client_statement_generation(globals())
App.generate_pdf_selected = _wave67_generate_pdf_selected
'''

INSTALL_BLOCK = f'''{INSTALL_START}
from spina_app.features.reports import install_reports_feature as _wave80_install_reports_feature

_wave80_install_reports_feature(
    globals().get("App"),
    namespace=globals(),
    log_exc=globals().get("_log_exc"),
    log_suppressed_once=globals().get("_log_suppressed_once"),
)
{INSTALL_END}
'''

ENGINE_PREAMBLE = '''"""Complete client-statement PDF engine extracted from SPINA Wave 80."""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any, Mapping

DATA_DIR = os.getcwd()


def configure_report_engine_dependencies(namespace: Mapping[str, Any]) -> None:
    """Bind desktop helpers and recalculate data-file paths."""
    for name, value in namespace.items():
        if name not in {"configure_report_engine_dependencies", "__name__", "__file__"}:
            globals()[name] = value
    global REPORT_GENERATION_COUNT_FILE, REPORT_GENERATION_LOG_FILE, REPORT_GENERATION_LOG_CSV
    root = str(globals().get("DATA_DIR") or os.getcwd())
    REPORT_GENERATION_COUNT_FILE = os.path.join(root, "report_generation_counts.json")
    REPORT_GENERATION_LOG_FILE = os.path.join(root, "report_generation_logs.jsonl")
    REPORT_GENERATION_LOG_CSV = os.path.join(root, "report_generation_logs.csv")

'''


def _extract_marked(source: str, start: str, end: str) -> tuple[str, str]:
    if source.count(start) != 1 or source.count(end) != 1:
        raise AssertionError(
            f"Expected one marked block: {start!r}; "
            f"start={source.count(start)} end={source.count(end)}"
        )
    start_index = source.index(start)
    end_index = source.index(end, start_index) + len(end)
    return source[start_index:end_index], source[:start_index] + source[end_index:]


def _remove_app_methods(source: str) -> str:
    tree = ast.parse(source)
    app = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"),
        None,
    )
    if app is None:
        raise AssertionError("App class not found")
    found = {
        node.name: node
        for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in REPORT_METHODS
    }
    missing = [name for name in REPORT_METHODS if name not in found]
    if missing:
        raise AssertionError("Missing active Reports App methods: " + ", ".join(missing))

    lines = source.splitlines(keepends=True)
    spans = []
    for name in REPORT_METHODS:
        node = found[name]
        start = int(node.lineno) - 1
        end = int(node.end_lineno or node.lineno)
        while start > 0 and not lines[start - 1].strip():
            start -= 1
        spans.append((start, end, name))
    for start, end, _name in sorted(spans, reverse=True):
        del lines[start:end]
    return "".join(lines)


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise AssertionError(f"Expected one {label} block; found {count}")
    return source.replace(old, new, 1)


def apply(source: str) -> tuple[str, str]:
    already_done = (
        INSTALL_START in source
        and INSTALL_END in source
        and ENGINE_START not in source
        and ENGINE_END not in source
        and all(f"    def {name}(" not in source for name in REPORT_METHODS)
    )
    if already_done:
        if not ENGINE_PATH.exists():
            raise AssertionError("Wave 80 installer exists but report_engine.py is missing")
        return source, ENGINE_PATH.read_text(encoding="utf-8")

    if INSTALL_START in source or INSTALL_END in source:
        raise AssertionError("Partial Wave 80 installer markers found")

    engine_block, updated = _extract_marked(source, ENGINE_START, ENGINE_END)
    engine_source = ENGINE_PREAMBLE + engine_block + "\n"

    updated = _remove_app_methods(updated)
    updated = _replace_once(updated, WAVE64_BLOCK, INSTALL_BLOCK, "Wave 64")
    updated = _replace_once(updated, WAVE67_BLOCK, "", "Wave 67")

    required_main = (
        INSTALL_START,
        "install_reports_feature as _wave80_install_reports_feature",
        "namespace=globals()",
        INSTALL_END,
    )
    for token in required_main:
        if updated.count(token) != 1:
            raise AssertionError(f"Wave 80 installer token mismatch: {token!r}")

    forbidden_main = (
        ENGINE_START,
        ENGINE_END,
        "def generate_client_pdf(",
        "def _spina_record_report_generation(",
        "_configure_wave64_reports_tab",
        "_configure_wave67_client_statement_generation",
    )
    for token in forbidden_main:
        if token in updated:
            raise AssertionError(f"Legacy Reports token remains in desktop file: {token!r}")
    for name in REPORT_METHODS:
        if f"    def {name}(" in updated:
            raise AssertionError(f"Reports App method remains: {name}")

    required_engine = (
        "def configure_report_engine_dependencies(",
        "def _parse_adv_range_any(",
        "def _collect_day_flags_for_month(",
        "def _spina_record_report_generation(",
        "def generate_client_pdf(",
        "_wave74_x7_daily_interest",
    )
    for token in required_engine:
        if token not in engine_source:
            raise AssertionError(f"Generated report engine missing: {token!r}")
    return updated, engine_source


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    updated, engine = apply(source)
    # Prove the application transformation is idempotent before writing.
    APP_PATH.write_text(updated, encoding="utf-8")
    ENGINE_PATH.write_text(engine, encoding="utf-8")
    second_updated, second_engine = apply(updated)
    if second_updated != updated or second_engine != engine:
        raise AssertionError("Wave 80 Reports extraction is not idempotent")
    print("Wave 80 Reports extraction applied successfully.")


if __name__ == "__main__":
    main()
