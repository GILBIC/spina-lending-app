#!/usr/bin/env python3
"""Guarded complete Data Bank extraction for SPINA Wave 82."""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPO_PATH = ROOT / "spina_app" / "repositories" / "data_bank.py"
AUDIT_PATH = ROOT / "spina_app" / "data_bank_audit.py"
EXPORT_PATH = ROOT / "spina_app" / "data_bank_exports.py"
AUTO_PATH = ROOT / "spina_app" / "data_bank_auto_close.py"

DB_METHODS = (
    "_log_transaction_history",
    "get_databank_daily_total",
    "get_databank_day_close",
    "is_databank_day_closed",
    "_append_databank_day_close_history",
    "list_databank_day_close_history",
    "list_databank_day_collectors",
    "get_databank_day_collector_totals",
    "replace_databank_day_collectors",
    "set_databank_day_close",
    "reopen_databank_day",
    "set_databank_day_workflow",
    "list_databank_day_close_records",
    "add_or_update_transaction",
    "delete_transaction",
    "delete_transactions_for_day",
    "get_transaction",
    "get_transaction_by_uid",
    "add_or_update_transaction_by_uid",
    "import_missing_clients_from_transactions",
)
PURE_DB_METHODS = (
    "_databank_day_close_bucket",
    "_dayclose_norm_workflow",
    "_dayclose_variance_status",
)
AUDIT_METHODS = (
    "_audit_money_text",
    "_audit_parse_date_filters",
    "_audit_set_today",
    "_audit_set_last7",
    "_audit_set_all",
    "_audit_tree_factory",
    "_audit_set_detail_text",
    "_audit_show_selected",
)
TOP_FUNCTIONS = (
    "_spina_perf_month_transactions",
    "export_range_template",
    "_spina_auto_close_after_days_value",
    "_spina_auto_close_candidate_dates",
    "_spina_schedule_auto_daily_close",
)

INSTALLER = '''# --- BEGIN: Data Bank feature installer Wave 82 ---
from spina_app.features.data_bank import install_data_bank_feature as _wave82_install_data_bank_feature

_wave82_install_data_bank_feature(
    globals().get("App"),
    loan_db_cls=globals().get("LoanDB"),
    namespace=globals(),
    log_exc=globals().get("_log_exc"),
    log_suppressed_once=globals().get("_log_suppressed_once"),
)
# --- END: Data Bank feature installer Wave 82 ---
'''

NAV_ONLY = '''# Navigation helpers retained after complete Data Bank modularization Wave 82.
from spina_app.navigation import (
    configure_navigation_dependencies as _wave29_configure_navigation,
    _update_data_toolbar as _wave29_nav_update_data_toolbar,
    _side_nav_items as _wave29_nav_side_nav_items,
    _rebuild_side_nav as _wave29_nav_rebuild_side_nav,
    _refresh_side_nav_selection as _wave29_nav_refresh_side_nav_selection,
    _header_palette as _wave29_nav_header_palette,
    _make_header_button as _wave29_nav_make_header_button,
    _refresh_mode_toggle as _wave29_nav_refresh_mode_toggle,
    _vscroll as _wave29_nav_vscroll,
    _month_label as _wave29_nav_month_label,
    _on_mousewheel_sync as _wave29_nav_on_mousewheel_sync,
    _update_toolbar_states as _wave29_nav_update_toolbar_states,
)
_wave29_configure_navigation(
    log_suppressed_once=_log_suppressed_once,
    fmt_currency_callback=fmt_currency,
)
App._update_data_toolbar = _wave29_nav_update_data_toolbar
App._side_nav_items = _wave29_nav_side_nav_items
App._rebuild_side_nav = _wave29_nav_rebuild_side_nav
App._refresh_side_nav_selection = _wave29_nav_refresh_side_nav_selection
App._header_palette = _wave29_nav_header_palette
App._make_header_button = _wave29_nav_make_header_button
App._refresh_mode_toggle = _wave29_nav_refresh_mode_toggle
App._vscroll = _wave29_nav_vscroll
App._month_label = _wave29_nav_month_label
App._on_mousewheel_sync = _wave29_nav_on_mousewheel_sync
App._update_toolbar_states = _wave29_nav_update_toolbar_states

'''


def _module_preamble(title: str, configure_name: str) -> str:
    return f'''"""{title}"""
from __future__ import annotations

import calendar
import json
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

_DEPENDENCIES: dict[str, Any] = {{}}
_PROTECTED = {{"__name__", "__file__", "__package__", "__builtins__", "_DEPENDENCIES", "_PROTECTED", "{configure_name}"}}


def {configure_name}(namespace: Mapping[str, Any]) -> None:
    _DEPENDENCIES.clear()
    _DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED:
            globals()[name] = value

'''


def _source(node: ast.AST, text: str) -> str:
    segment = ast.get_source_segment(text, node)
    if not segment:
        raise AssertionError(f"Unable to extract source for {getattr(node, 'name', type(node).__name__)}")
    return textwrap.dedent(segment).rstrip() + "\n\n"


def _find_class(tree: ast.Module, name: str) -> ast.ClassDef:
    found = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name]
    if len(found) != 1:
        raise AssertionError((name, len(found)))
    return found[0]


def _methods(cls: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _top_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _blank_nodes(text: str, nodes: list[ast.AST]) -> str:
    lines = text.splitlines(keepends=True)
    occupied: set[int] = set()
    for node in nodes:
        start = int(getattr(node, "lineno", 0)) - 1
        end = int(getattr(node, "end_lineno", 0))
        assert start >= 0 and end > start
        for index in range(start, end):
            if index in occupied:
                raise AssertionError(("overlapping removal", index + 1))
            occupied.add(index)
            lines[index] = "\n" if lines[index].endswith("\n") else ""
    return "".join(lines)


def _remove_inclusive(text: str, start_marker: str, end_marker: str, *, required: bool = True) -> str:
    start = text.find(start_marker)
    if start < 0:
        if required:
            raise AssertionError(("missing start", start_marker))
        return text
    end = text.find(end_marker, start)
    if end < 0:
        raise AssertionError(("missing end", end_marker))
    end += len(end_marker)
    while end < len(text) and text[end] in "\r\n":
        end += 1
    return text[:start] + text[end:]


def _remove_until(text: str, start_marker: str, next_marker: str, *, required: bool = True) -> str:
    start = text.find(start_marker)
    if start < 0:
        if required:
            raise AssertionError(("missing start", start_marker))
        return text
    end = text.find(next_marker, start)
    if end < 0:
        raise AssertionError(("missing next", next_marker))
    return text[:start] + text[end:]


def _replace_between(text: str, start_marker: str, next_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    end = text.find(next_marker, start)
    if start < 0 or end < 0:
        raise AssertionError((start_marker, next_marker))
    return text[:start] + replacement + text[end:]


def _write_modules(original: str, db_nodes, audit_nodes, top_nodes) -> None:
    REPO_PATH.parent.mkdir(parents=True, exist_ok=True)
    repo = _module_preamble("Data Bank repository extracted in SPINA Wave 82.", "configure_data_bank_repository_dependencies")
    for name in DB_METHODS:
        repo += _source(db_nodes[name], original)
    repo += _source(top_nodes["_spina_perf_month_transactions"], original)
    REPO_PATH.write_text(repo.rstrip() + "\n", encoding="utf-8")

    audit = _module_preamble("Data Bank audit controller helpers extracted in SPINA Wave 82.", "configure_data_bank_audit_dependencies")
    for name in AUDIT_METHODS:
        audit += _source(audit_nodes[name], original)
    AUDIT_PATH.write_text(audit.rstrip() + "\n", encoding="utf-8")

    exports = _module_preamble("Data Bank export actions extracted in SPINA Wave 82.", "configure_data_bank_export_dependencies")
    exports += _source(top_nodes["export_range_template"], original)
    EXPORT_PATH.write_text(exports.rstrip() + "\n", encoding="utf-8")

    auto = _module_preamble("Configurable Data Bank auto-close extracted in SPINA Wave 82.", "configure_data_bank_auto_close_dependencies")
    for name in ("_spina_auto_close_after_days_value", "_spina_auto_close_candidate_dates", "_spina_schedule_auto_daily_close"):
        auto += _source(top_nodes[name], original)
    AUTO_PATH.write_text(auto.rstrip() + "\n", encoding="utf-8")


def apply() -> bool:
    original = APP_PATH.read_text(encoding="utf-8")
    if "# --- BEGIN: Data Bank feature installer Wave 82 ---" in original:
        assert original.count("# --- BEGIN: Data Bank feature installer Wave 82 ---") == 1
        assert original.count("# --- END: Data Bank feature installer Wave 82 ---") == 1
        for path in (REPO_PATH, AUDIT_PATH, EXPORT_PATH, AUTO_PATH):
            assert path.exists(), path
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        return False

    tree = ast.parse(original, filename=str(APP_PATH))
    loan_db = _find_class(tree, "LoanDB")
    app = _find_class(tree, "App")
    loan_methods = _methods(loan_db)
    app_methods = _methods(app)
    top = _top_functions(tree)

    for name in DB_METHODS + PURE_DB_METHODS:
        assert name in loan_methods, name
    for name in AUDIT_METHODS:
        assert name in app_methods, name
    for name in TOP_FUNCTIONS:
        assert name in top, name

    _write_modules(original, loan_methods, app_methods, top)

    removals = [loan_methods[name] for name in DB_METHODS + PURE_DB_METHODS]
    removals += [app_methods[name] for name in AUDIT_METHODS]
    removals += [top[name] for name in TOP_FUNCTIONS]
    text = _blank_nodes(original, removals)

    text = _replace_between(
        text,
        "# Wave 72: complete Data Bank feature/controller extraction.",
        "class App:",
        "",
    )
    text = _remove_until(
        text,
        "# Wave 72: bind complete Data Bank App methods before later runtime patches.",
        "# --- Wave 54 Audit presentation wiring ---",
    )
    text = _remove_inclusive(text, "# --- Wave 54 Audit presentation wiring ---", "# --- End Wave 54 Audit presentation wiring ---")

    # Preserve navigation while removing Wave 29 Data Bank shell ownership.
    text = _replace_between(
        text,
        "# Navigation + Data Bank shell helpers extracted in Wave 29.",
        "# ---------- Collector Route UI helpers (selection + bulk + inline edit) ----------",
        NAV_ONLY,
    )

    text = _remove_until(text, "# Wave 56: System Data tab construction presentation.", "# Wave 57: Data Bank Close History dialog presentation.")
    text = _remove_until(text, "# Wave 57: Data Bank Close History dialog presentation.", "# Wave 58: System Data date and summary helpers.")
    text = _remove_until(text, "# Wave 58: System Data date and summary helpers.", "# Wave 59: Data Bank month navigation and grid presentation.")
    text = _remove_until(text, "# Wave 59: Data Bank month navigation and grid presentation.", "# Wave 60: Data Bank inline editor and missed-reason presentation.")
    text = _remove_until(text, "# Wave 60: Data Bank inline editor and missed-reason presentation.", "# Wave 61: Data Bank cell write actions.")
    text = _remove_until(text, "# Wave 61: Data Bank cell write actions.", "# Wave 62: Data Bank Delete Day destructive workflow.")
    text = _remove_until(text, "# Wave 62: Data Bank Delete Day destructive workflow.", "# --- BEGIN: Reports feature installer Wave 80 ---")
    text = _remove_until(text, "# Wave 66: Data Bank close-records presentation.", "from spina_app.backup_history_presentation import (")

    text = _remove_inclusive(text, "# --- BEGIN: Configurable Auto Daily Close ---", "# --- END: Configurable Auto Daily Close ---")
    text = _remove_inclusive(text, "# --- BEGIN: Save Collector Route copy after Daily Close ---", "# --- END: Save Collector Route copy after Daily Close ---")
    text = _remove_inclusive(text, "# --- BEGIN: v15 modern Data Bank UI ---", "# --- END: v15 modern Data Bank UI ---")
    text = _remove_inclusive(text, "# --- BEGIN: v16 bigger Data Bank payment grid tuning ---", "# --- END: v16 bigger Data Bank payment grid tuning ---")

    # Remove independent range-export binding now owned by the installer.
    text = _remove_until(
        text,
        "# Bind the independent date-range Excel export; Clients bindings are installed in Wave 81.",
        "# === Phase 2: hierarchical Area manager override ===",
    )

    # Remove the old final performance binding but retain shared indexes/norm helpers.
    text = _remove_until(
        text,
        "# Bind optimized loaders after the normal app methods are installed.",
        "# --- END: LARGE DATA PERFORMANCE PATCH (clients + databank) ---",
    )

    # Remove late import-log binding; the module remains and is configured by Wave 82.
    text = _remove_until(
        text,
        "# Wave 53: active Import Log viewer presentation extraction.",
        "# Refresh application-owned dependencies after all runtime patches load.",
    )

    old_tail = "# Refresh application-owned dependencies after all runtime patches load.\n_wave72_databank_feature.configure_databank_feature_dependencies(globals())"
    if old_tail not in text:
        raise AssertionError("missing final Wave 72 dependency refresh")
    text = text.replace(old_tail, INSTALLER.rstrip(), 1)

    # Normalize excessive blank runs while retaining readable architecture spacing.
    while "\n\n\n\n\n" in text:
        text = text.replace("\n\n\n\n\n", "\n\n\n")

    forbidden = (
        "_wave72_databank_feature",
        "_wave54_build_audit_tab",
        "_wave57_open_databank_close_history_dialog",
        "_wave59_refresh_data_grid",
        "_wave60_begin_cell_edit",
        "_wave61_save_cell_edit",
        "_wave62_open_delete_day_dialog",
        "_wave66_open_databank_close_records_dialog",
        "_spina_orig_app_init_autoclose",
        "_spina_v15_orig_refresh_data_grid",
        "def _spina_perf_month_transactions(",
        "def export_range_template(",
    )
    for token in forbidden:
        assert token not in text, token
    assert text.count("# --- BEGIN: Data Bank feature installer Wave 82 ---") == 1
    assert text.count("install_data_bank_feature as _wave82_install_data_bank_feature") == 1

    ast.parse(text, filename=str(APP_PATH))
    APP_PATH.write_text(text.rstrip() + "\n", encoding="utf-8")
    return True


def main() -> None:
    changed_first = apply()
    changed_second = apply()
    assert changed_first is True
    assert changed_second is False
    print("Wave 82 Data Bank extraction applied twice and is idempotent")


if __name__ == "__main__":
    main()
