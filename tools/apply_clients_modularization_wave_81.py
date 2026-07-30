#!/usr/bin/env python3
"""Guarded, idempotent complete Clients extraction for SPINA Wave 81."""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

OUTPUTS = {
    "service": ROOT / "spina_app" / "services" / "clients.py",
    "controller": ROOT / "spina_app" / "client_controller.py",
    "pictures": ROOT / "spina_app" / "client_pictures.py",
    "archive": ROOT / "spina_app" / "client_archive.py",
    "renewal": ROOT / "spina_app" / "client_renewal.py",
    "application": ROOT / "spina_app" / "client_application.py",
}

INSTALL_START = "# --- BEGIN: Clients feature installer Wave 81 ---"
INSTALL_END = "# --- END: Clients feature installer Wave 81 ---"

PICTURE_START = "# --- BEGIN: Clients tab picture support ---"
PICTURE_END = "# --- END: Clients tab picture support ---"
ARCHIVE_START = "# --- BEGIN: ARCHIVED CLIENT RESTORE FIX (must run before main()) ---"
ARCHIVE_END = "# --- END: ARCHIVED CLIENT RESTORE FIX ---"
ARCHIVE_ID_START = "# --- BEGIN: ARCHIVED CLIENT RESTORE ROW-ID FIX (more reliable than UID/name) ---"
ARCHIVE_ID_END = "# --- END: ARCHIVED CLIENT RESTORE ROW-ID FIX ---"
FLEX_START = "# --- BEGIN: Flexible Due Schedule rules ---"
FLEX_END = "# --- END: Flexible Due Schedule rules ---"
PG_RENEW_START = "# --- BEGIN: PostgreSQL TEST renew direct-write fix ---"
PG_RENEW_END = "# --- END: PostgreSQL TEST renew direct-write fix ---"
MODERN_START = "# --- BEGIN: v23 Modern Clients UI + Application Form Editor ---"
MODERN_END = "# --- END: v23 Modern Clients UI + Application Form Editor ---"

SERVICE_FUNCTIONS = (
    "_app__norm_lt_value",
    "_app__other_lt",
    "_spina__client_schedule_anchor",
    "_spina__client_due_meta",
    "_spina__parse_flexible_due_rule",
)

CONTROLLER_FUNCTIONS = (
    "_app__get_selected_client_name",
    "_app_refresh_clients",
    "_app_schedule_refresh_clients",
    "_app_delete_client_selected",
    "_app_link_selected_client",
    "_app_unlink_selected_client",
    "_app__maybe_suggest_link_clients",
    "_app_export_clients_template",
    "_app_import_clients_from_excel",
    "_app_import_missing",
)

PICTURE_FUNCTIONS = (
    "_spina__ensure_client_picture_column",
    "_spina__client_pictures_dir",
    "_spina__resolve_app_path",
    "_spina__store_client_picture_file",
    "_spina__delete_client_picture_file",
    "_db_set_client_picture",
    "_db_clear_client_picture",
    "_app_refresh_client_picture_panel",
    "_app_set_selected_client_picture",
    "_app_clear_selected_client_picture",
)

ARCHIVE_FUNCTIONS = (
    "_spina_archive_row_to_dict",
    "_spina_fixed_archive_client",
    "_spina_fixed_restore_client",
    "_spina_fixed_restore_client_by_uid",
    "_spina_fixed_open_archived_clients_dialog",
    "_spina_fixed_get_archived_clients_with_id",
    "_spina_fixed_restore_client_by_id",
    "_spina_fixed_open_archived_clients_dialog_rowid",
)

RENEWAL_FUNCTIONS = (
    "_app_renew_client_selected",
    "_spina_pg__reset_id_sequence",
    "_spina_pg__table_has_column",
    "_spina_pg_renew_client_direct",
)

APPLICATION_FUNCTIONS = (
    "_spina_v23_client_loan_summary",
    "_spina_v23_client_form",
    "_spina_v23_add_client_dialog",
    "_spina_v23_on_client_edit",
)

OBSOLETE_TOP_LEVEL = (
    "refresh_clients",
    "_maybe_suggest_link_clients",
    "_app_add_client_dialog",
    "_app_on_client_edit",
    "_app_open_archived_clients_dialog",
)

COMMON_PREAMBLE = '''from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

'''


def dependency_preamble(store: str, configure_name: str) -> str:
    return COMMON_PREAMBLE + f'''{store}: dict[str, Any] = {{}}


def {configure_name}(namespace: Mapping[str, Any]) -> None:
    {store}.clear()
    {store}.update(namespace)
    protected = {{"__name__", "__file__", "__package__", "__builtins__", "{store}", "{configure_name}"}}
    for name, value in namespace.items():
        if name not in protected:
            globals()[name] = value


'''


def parse(source: str) -> ast.Module:
    return ast.parse(source, filename=str(APP_PATH))


def top_nodes(source: str) -> dict[str, ast.AST]:
    result: dict[str, ast.AST] = {}
    for node in parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result[node.name] = node
    return result


def app_method_node(source: str, name: str) -> ast.AST:
    app = next((n for n in parse(source).body if isinstance(n, ast.ClassDef) and n.name == "App"), None)
    if app is None:
        raise AssertionError("App class missing")
    matches = [n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(matches) != 1:
        raise AssertionError(("App method", name, len(matches)))
    return matches[0]


def segment(source: str, node: ast.AST, *, dedent: bool = False) -> str:
    text = ast.get_source_segment(source, node)
    if not text:
        raise AssertionError(f"Cannot recover source for {getattr(node, 'name', node)!r}")
    if dedent:
        text = textwrap.dedent(text)
    return text.rstrip() + "\n\n"


def extract_functions(source: str, names: tuple[str, ...]) -> str:
    nodes = top_nodes(source)
    missing = [name for name in names if name not in nodes]
    if missing:
        raise AssertionError("Missing top-level Clients symbols: " + ", ".join(missing))
    return "".join(segment(source, nodes[name]) for name in names)


def remove_ast_nodes(
    source: str,
    *,
    top_names: set[str],
    class_names: set[str],
    app_methods: set[str],
) -> str:
    tree = parse(source)
    lines = source.splitlines(keepends=True)
    spans: list[tuple[int, int, str]] = []

    found_top: set[str] = set()
    found_classes: set[str] = set()
    found_methods: set[str] = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in top_names:
            spans.append((node.lineno - 1, int(node.end_lineno or node.lineno), node.name))
            found_top.add(node.name)
        elif isinstance(node, ast.ClassDef) and node.name in class_names:
            spans.append((node.lineno - 1, int(node.end_lineno or node.lineno), node.name))
            found_classes.add(node.name)
        elif isinstance(node, ast.ClassDef) and node.name == "App":
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name in app_methods:
                    spans.append((child.lineno - 1, int(child.end_lineno or child.lineno), f"App.{child.name}"))
                    found_methods.add(child.name)

    if found_top != top_names:
        raise AssertionError(("top-level removal mismatch", sorted(top_names - found_top)))
    if found_classes != class_names:
        raise AssertionError(("class removal mismatch", sorted(class_names - found_classes)))
    if found_methods != app_methods:
        raise AssertionError(("App method removal mismatch", sorted(app_methods - found_methods)))

    for start, end, _label in sorted(spans, reverse=True):
        while start > 0 and not lines[start - 1].strip():
            start -= 1
        del lines[start:end]
    return "".join(lines)


def marked_block(source: str, start: str, end: str) -> tuple[str, int, int]:
    if source.count(start) != 1 or source.count(end) != 1:
        raise AssertionError(("marker mismatch", start, source.count(start), source.count(end)))
    i = source.index(start)
    j = source.index(end, i) + len(end)
    while j < len(source) and source[j] in "\r\n":
        j += 1
    return source[i:j], i, j


def remove_marked(source: str, start: str, end: str, replacement: str = "") -> str:
    _block, i, j = marked_block(source, start, end)
    return source[:i] + replacement + source[j:]


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise AssertionError((label, count))
    return source.replace(old, new, 1)


def remove_between(source: str, start: str, end: str, *, keep_end: bool = True) -> str:
    if source.count(start) != 1 or source.count(end) != 1:
        raise AssertionError(("range mismatch", start, end, source.count(start), source.count(end)))
    i = source.index(start)
    j = source.index(end, i)
    return source[:i] + (source[j:] if keep_end else source[j + len(end):])


def build_modules(source: str) -> dict[str, str]:
    nodes = top_nodes(source)

    base_due = segment(source, nodes["_spina__client_due_meta"])
    base_due = base_due.replace("def _spina__client_due_meta(", "def _spina__client_due_meta_base(", 1)
    service_body = (
        segment(source, nodes["_app__norm_lt_value"])
        + segment(source, nodes["_app__other_lt"])
        + segment(source, nodes["_spina__client_schedule_anchor"])
        + base_due
        + segment(source, nodes["_spina__parse_flexible_due_rule"])
        + '''def _spina__client_due_meta(info: dict | None, as_of=None) -> tuple[str, bool]:
    try:
        flex = _spina__parse_flexible_due_rule(info or {}, target=as_of)
        if flex is not None:
            return flex
    except Exception:
        pass
    try:
        return _spina__client_due_meta_base(info, as_of=as_of)
    except Exception:
        return ("", False)

'''
    )

    controller_body = segment(source, app_method_node(source, "set_area_for_selected_clients"), dedent=True)
    controller_body += extract_functions(source, CONTROLLER_FUNCTIONS)

    picture_body = extract_functions(source, PICTURE_FUNCTIONS)
    archive_body = extract_functions(source, ARCHIVE_FUNCTIONS)

    renew_dialog = nodes.get("RenewDialog")
    if renew_dialog is None or not isinstance(renew_dialog, ast.ClassDef):
        raise AssertionError("RenewDialog missing")
    renewal_body = segment(source, renew_dialog)
    renewal_body += extract_functions(source, RENEWAL_FUNCTIONS)

    application_body = extract_functions(source, APPLICATION_FUNCTIONS)

    renewal_preamble = dependency_preamble("_CLIENT_RENEWAL_DEPENDENCIES", "configure_client_renewal_dependencies")
    renewal_preamble += '''_SPINA_ORIG_LOANDB_RENEW_CLIENT = None

'''
    # Replace the generic configure function with one that captures the original
    # renewal method before Wave 81 installs the PostgreSQL-safe override.
    generic = '''def configure_client_renewal_dependencies(namespace: Mapping[str, Any]) -> None:
    _CLIENT_RENEWAL_DEPENDENCIES.clear()
    _CLIENT_RENEWAL_DEPENDENCIES.update(namespace)
    protected = {"__name__", "__file__", "__package__", "__builtins__", "_CLIENT_RENEWAL_DEPENDENCIES", "configure_client_renewal_dependencies"}
    for name, value in namespace.items():
        if name not in protected:
            globals()[name] = value
'''
    enhanced = generic + '''    global _SPINA_ORIG_LOANDB_RENEW_CLIENT
    if _SPINA_ORIG_LOANDB_RENEW_CLIENT is None:
        loan_db = namespace.get("LoanDB")
        _SPINA_ORIG_LOANDB_RENEW_CLIENT = getattr(loan_db, "renew_client", None) if loan_db is not None else None
'''
    renewal_preamble = renewal_preamble.replace(generic, enhanced, 1)

    return {
        "service": dependency_preamble("_CLIENT_SERVICE_DEPENDENCIES", "configure_client_service_dependencies") + service_body,
        "controller": dependency_preamble("_CLIENT_CONTROLLER_DEPENDENCIES", "configure_client_controller_dependencies") + controller_body,
        "pictures": dependency_preamble("_CLIENT_PICTURE_DEPENDENCIES", "configure_client_picture_dependencies") + picture_body,
        "archive": dependency_preamble("_CLIENT_ARCHIVE_DEPENDENCIES", "configure_client_archive_dependencies") + archive_body,
        "renewal": renewal_preamble + renewal_body,
        "application": dependency_preamble("_CLIENT_APPLICATION_DEPENDENCIES", "configure_client_application_dependencies") + application_body,
    }


QUERY_START = "# Wave 32: linked-client and transaction-history read queries."
QUERY_END = "# -------------------------\n# PDF generator"

WAVE38_BLOCK = '''# Wave 38: client add/edit form presentation.
from spina_app.client_form_presentation import (
    configure_client_form_dependencies as _configure_wave38_client_form,
    _app__client_form as _wave38_app__client_form,
)
_configure_wave38_client_form(globals())
_app__client_form = _wave38_app__client_form
'''

WAVE36_BLOCK = '''# Wave 36: read-only client-history dialog presentation.
from spina_app.client_history_presentation import (
    configure_client_history_dependencies as _configure_wave36_client_history,
    _app_open_client_history_dialog as _wave36_client_history_dialog,
)
_configure_wave36_client_history(globals())
_app_open_client_history_dialog = _wave36_client_history_dialog
'''

WAVE55_BLOCK = '''# Wave 55: Clients tab construction presentation.
from spina_app.clients_tab_presentation import (
    configure_clients_tab_presentation_dependencies as _configure_wave55_clients_tab_presentation,
    _build_clients_tab as _wave55_build_clients_tab,
)
_configure_wave55_clients_tab_presentation(globals())
App._build_clients_tab = _wave55_build_clients_tab
'''

EARLY_BIND_START = "# Bind export_range_template and Clients/Linking methods to App"
EARLY_BIND_END = "# === Phase 2: hierarchical Area manager override ==="
EARLY_BIND_REPLACEMENT = '''# Bind the independent date-range Excel export; Clients bindings are installed in Wave 81.
try:
    if 'App' in globals() and 'export_range_template' in globals():
        setattr(App, 'export_range_template', export_range_template)
except Exception as __spina_exc:
    _log_suppressed_once('excpass_0664', 'suppressed exception excpass_0664', __spina_exc)
    pass

'''

PERF_IMPORT_BLOCK = '''# Wave 30: bulk Clients read and refresh presentation helpers.
from spina_app.tabs.clients import (
    _spina_perf_clients_rows,
    _spina_perf_refresh_clients,
)
_configure_clients_wave30_dependencies(globals())
'''

PERF_BIND_LINE = '''        setattr(App, "refresh_clients", _spina_perf_refresh_clients)
'''

ROUTE_NOTICE_IMPORT = '''# Wave 30: read-only Collector Route notice lookup for Clients.
from spina_app.tabs.clients import _spina_route_notice_for_client
_configure_clients_wave30_dependencies(globals())
'''

WAVE70_BLOCK = '''# Wave 70: read-only client NEW-status calculation.
from spina_app.client_new_status import (
    configure_client_new_status_dependencies as _configure_wave70_client_new,
    _is_client_new as _wave70_is_client_new,
)
_configure_wave70_client_new(globals())
App._is_client_new = _wave70_is_client_new
'''

INSTALL_BLOCK = f'''{INSTALL_START}
from spina_app.features.clients import install_clients_feature as _wave81_install_clients_feature

_wave81_install_clients_feature(
    globals().get("App"),
    loan_db_cls=globals().get("LoanDB"),
    namespace=globals(),
    log_exc=globals().get("_log_exc"),
    log_suppressed_once=globals().get("_log_suppressed_once"),
)
{INSTALL_END}
'''


def apply(source: str) -> tuple[str, dict[str, str]]:
    already_done = INSTALL_START in source and INSTALL_END in source
    if already_done:
        missing = [str(path) for path in OUTPUTS.values() if not path.exists()]
        if missing:
            raise AssertionError("Wave 81 installer exists but generated modules are missing: " + ", ".join(missing))
        return source, {name: path.read_text(encoding="utf-8") for name, path in OUTPUTS.items()}

    if INSTALL_START in source or INSTALL_END in source:
        raise AssertionError("Partial Wave 81 installer markers found")

    modules = build_modules(source)

    top_remove = set(SERVICE_FUNCTIONS) | set(CONTROLLER_FUNCTIONS) | set(OBSOLETE_TOP_LEVEL)
    top_remove |= {"_app_renew_client_selected"}
    updated = remove_ast_nodes(
        source,
        top_names=top_remove,
        class_names={"RenewDialog"},
        app_methods={"set_area_for_selected_clients"},
    )

    # Exact active marker blocks moved into generated modules.
    updated = remove_marked(updated, PICTURE_START, PICTURE_END)
    updated = remove_marked(updated, ARCHIVE_START, ARCHIVE_END)
    updated = remove_marked(updated, ARCHIVE_ID_START, ARCHIVE_ID_END)
    updated = remove_marked(updated, FLEX_START, FLEX_END)
    updated = remove_marked(updated, PG_RENEW_START, PG_RENEW_END)
    updated = remove_marked(updated, MODERN_START, MODERN_END, INSTALL_BLOCK)

    # Consolidate earlier modular-query and presentation aliases under Wave 81.
    updated = remove_between(updated, QUERY_START, QUERY_END, keep_end=True)
    updated = replace_once(updated, WAVE38_BLOCK, "", "Wave 38 alias")
    updated = replace_once(updated, WAVE36_BLOCK, "", "Wave 36 alias")
    updated = replace_once(updated, WAVE55_BLOCK, "", "Wave 55 alias")
    updated = remove_between(updated, EARLY_BIND_START, EARLY_BIND_END, keep_end=True)
    updated = updated.replace(EARLY_BIND_START, EARLY_BIND_REPLACEMENT, 1) if EARLY_BIND_START in updated else updated

    # remove_between removed the comment too; insert export-only binding immediately
    # before the preserved Area manager marker.
    if EARLY_BIND_REPLACEMENT not in updated:
        marker = EARLY_BIND_END
        if updated.count(marker) != 1:
            raise AssertionError("Area manager marker mismatch")
        updated = updated.replace(marker, EARLY_BIND_REPLACEMENT + marker, 1)

    updated = replace_once(updated, PERF_IMPORT_BLOCK, "", "Wave 30 performance import")
    updated = replace_once(updated, PERF_BIND_LINE, "", "Wave 30 refresh binding")
    updated = replace_once(updated, ROUTE_NOTICE_IMPORT, "# Client route-notice lookup is configured by Wave 81.\n", "route notice alias")
    updated = replace_once(updated, WAVE70_BLOCK, "", "Wave 70 alias")

    required_main = (
        INSTALL_START,
        "install_clients_feature as _wave81_install_clients_feature",
        "loan_db_cls=globals().get(\"LoanDB\")",
        INSTALL_END,
    )
    for token in required_main:
        if updated.count(token) != 1:
            raise AssertionError(("installer token", token, updated.count(token)))

    forbidden_main = (
        PICTURE_START,
        ARCHIVE_START,
        ARCHIVE_ID_START,
        FLEX_START,
        PG_RENEW_START,
        MODERN_START,
        "def _app_refresh_clients(",
        "def _app_link_selected_client(",
        "def _spina_v23_client_form(",
        "class RenewDialog(",
        "setattr(App, 'refresh_clients', _app_refresh_clients)",
        "App.refresh_clients = _spina_v23_refresh_clients",
        "LoanDB.renew_client = _spina_pg_renew_client_direct",
        "App._is_client_new = _wave70_is_client_new",
    )
    for token in forbidden_main:
        if token in updated:
            raise AssertionError(f"Legacy Clients token remains: {token!r}")

    for name, module_source in modules.items():
        ast.parse(module_source, filename=str(OUTPUTS[name]))

    ast.parse(updated, filename=str(APP_PATH))
    return updated, modules


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    updated, modules = apply(source)
    APP_PATH.write_text(updated, encoding="utf-8")
    for name, content in modules.items():
        OUTPUTS[name].parent.mkdir(parents=True, exist_ok=True)
        OUTPUTS[name].write_text(content, encoding="utf-8")

    second_updated, second_modules = apply(updated)
    if second_updated != updated or second_modules != modules:
        raise AssertionError("Wave 81 Clients extraction is not idempotent")
    print("Wave 81 Clients extraction applied successfully.")


if __name__ == "__main__":
    main()
