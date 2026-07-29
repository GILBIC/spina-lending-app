#!/usr/bin/env python3
"""Generate and apply the complete Collector Route modularization for Wave 79.

The active report engine is intentionally copied from the final top-level definitions in
production source. This avoids manually rewriting thousands of lines of validated PDF and
financial logic while still moving ownership out of the desktop entry module.
"""
from __future__ import annotations

import ast
from pathlib import Path
import textwrap
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
CONTROLLER_PATH = ROOT / "spina_app" / "collector_route_controller.py"
REPORT_PATH = ROOT / "spina_app" / "collector_route_report.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "collector_route.py"

INSTALL_START = "# --- BEGIN: Collector Route feature installer Wave 79 ---"
INSTALL_END = "# --- END: Collector Route feature installer Wave 79 ---"

MARKED_BLOCKS = (
    (
        "# --- BEGIN: v25 Modern Collector Route UI ---",
        "# --- END: v25 Modern Collector Route UI ---",
    ),
    (
        "# --- BEGIN: v26 Collector Route remove visible right-side panel ---",
        "# --- END: v26 Collector Route remove visible right-side panel ---",
    ),
    (
        "# --- BEGIN: v27 Modern Collector Route Overview + Better Route Editor ---",
        "# --- END: v27 Modern Collector Route Overview + Better Route Editor ---",
    ),
    (
        "# --- BEGIN: v28 Collector Route duplicate note cleanup marker ---",
        "# --- END: v28 Collector Route duplicate note cleanup marker ---",
    ),
    (
        "# --- BEGIN: v29 Safe PDF/File Open Fix ---",
        "# --- END: v29 Safe PDF/File Open Fix ---",
    ),
    (
        "# --- BEGIN: v30 Collector Route notes show + de-duplicate fix ---",
        "# --- END: v30 Collector Route notes show + de-duplicate fix ---",
    ),
)

CONTROLLER_EXPLICIT = {
    "_schedule_collectors_refresh",
    "_clear_collectors_search_filters",
    "_populate_collector_details",
    "_save_collector_notes",
    "_save_selected_collector_notes",
    "_spina_v27_get_route_master_areas",
}
CONTROLLER_PREFIXES = ("_collectors_", "_on_collectors_")
CONTROLLER_SKIP_EXPORT = {"_on_collectors_select", "_build_collectors_tab"}

CLASS_METHODS = {
    "_show_conflicts",
    "_show_unassigned_areas",
    "_show_no_area_clients",
    "_delete_selected_collector",
    "_edit_selected_collector",
    "_add_collector",
    "_build_collectors_tab",
}
CLASS_SKIP_EXPORT = {"_build_collectors_tab"}

REPORT_EXPLICIT = {
    "print_collector_route_daily_ledger",
    "print_full_daily_ledger",
    "_normalize_client_name_for_lookup",
}
REPORT_PREFIXES = ("_spina_route_", "_spina_crc_")

COLLECTOR_MODULE_IMPORTS = {
    "spina_app.tabs.collectors",
    "spina_app.tabs.collector_route",
    "spina_app.collector_tab_presentation",
    "spina_app.collector_dialog_presentation",
    "spina_app.collector_refresh_presentation",
}

INSTALL_BLOCK = f'''{INSTALL_START}
from spina_app.features.collector_route import (
    install_collector_route_feature as _wave79_install_collector_route_feature,
)

_wave79_install_collector_route_feature(
    globals().get("App"),
    namespace=globals(),
    log_exc=globals().get("_log_exc"),
    log_suppressed_once=globals().get("_log_suppressed_once"),
)
{INSTALL_END}'''


def _node_text(lines: list[str], node: ast.AST, *, dedent: bool = False) -> str:
    start = int(getattr(node, "lineno")) - 1
    end = int(getattr(node, "end_lineno"))
    text = "".join(lines[start:end]).rstrip() + "\n"
    return textwrap.dedent(text) if dedent else text


def _merge_ranges(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(set(ranges)):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _remove_ranges(source: str, ranges: Iterable[tuple[int, int]]) -> str:
    lines = source.splitlines(keepends=True)
    for start, end in reversed(_merge_ranges(ranges)):
        del lines[start - 1 : end]
    return "".join(lines)


def _replace_marked_block(source: str, start: str, end: str, replacement: str) -> str:
    if source.count(start) != 1 or source.count(end) != 1:
        raise AssertionError(
            f"Expected one marked block: {start!r}; "
            f"start={source.count(start)} end={source.count(end)}"
        )
    start_index = source.index(start)
    end_index = source.index(end, start_index) + len(end)
    return source[:start_index] + replacement + source[end_index:]


def _module_source(title: str, config_name: str, methods: dict[str, str]) -> str:
    method_names = tuple(methods)
    protected = {config_name, "COLLECTOR_ROUTE_METHOD_NAMES", *method_names}
    pieces = [
        f'"""{title} generated from the final active SPINA Wave 79 source."""\n',
        "from __future__ import annotations\n\n",
        f"_PROTECTED_GLOBALS = {protected!r}\n\n",
        f"def {config_name}(namespace):\n",
        "    for name, value in namespace.items():\n",
        "        if name not in _PROTECTED_GLOBALS and not str(name).startswith('__'):\n",
        "            globals()[name] = value\n\n\n",
    ]
    for name, text in methods.items():
        pieces.append(text.rstrip() + "\n\n\n")
    pieces.append(f"COLLECTOR_ROUTE_METHOD_NAMES = {method_names!r}\n")
    return "".join(pieces)


def _feature_source() -> str:
    return '''"""Complete Collector Route feature installer for SPINA Wave 79."""
from __future__ import annotations

from typing import Any, Mapping

from spina_app import collector_route_controller as _controller
from spina_app import collector_route_report as _report
from spina_app.collector_dialog_presentation import (
    configure_collector_dialog_dependencies,
    _spina_v27_collector_editor_dialog,
)
from spina_app.collector_refresh_presentation import (
    configure_collector_refresh_dependencies,
    refresh_collectors as _refresh_collectors,
)
from spina_app.collector_tab_presentation import (
    configure_collector_tab_dependencies,
    _spina_v27_build_collectors_tab,
)
from spina_app.tabs.collector_route import (
    configure_collector_route_dependencies,
    _spina_v27_hidden_collector_widgets,
    _spina_v27_update_route_cards,
)
from spina_app import tabs as _tabs_package
from spina_app.tabs import collectors as _editor
from spina_app.theme_palettes import _spina_v25_collector_colors

_EDITOR_METHOD_NAMES = (
    "_collectors_get_selected_name",
    "_collectors_toggle_sections",
    "_collectors_apply_markers",
    "_collectors_refresh_bulk_bar",
    "_collectors_clear_checked",
    "_collectors_start_inline_edit",
    "_collectors_load_inline_edit_fields",
    "_collectors_cancel_inline_edit",
    "_collectors_choose_areas",
    "_collectors_add_area_text",
    "_collectors_remove_area",
    "_collectors_move_area",
)


def _safe_log(callback, context, exc=None):
    if not callable(callback):
        return
    try:
        callback(context, exc)
    except Exception:
        pass


def _selected_collector(self, *_args, **_kwargs):
    """Final lightweight v27 selection behavior; the visible right panel stays removed."""
    name = ""
    try:
        tree = getattr(self, "collectors_tree", None)
        selected = tree.selection() if tree is not None else ()
        if selected:
            values = tree.item(selected[0], "values") or ()
            name = self._collectors_name_from_values(values)
    except Exception:
        name = ""
    try:
        self._selected_collector_name = str(name or "").strip()
    except Exception:
        pass
    try:
        if name and hasattr(self, "collector_route_table_status_var"):
            self.collector_route_table_status_var.set(f"Selected: {name}")
    except Exception:
        pass
    try:
        _spina_v27_update_route_cards(self)
    except Exception:
        pass
    return None


def install_collector_route_feature(
    app_class: type | None,
    *,
    namespace: Mapping[str, Any],
    log_exc=None,
    log_suppressed_once=None,
) -> bool:
    """Bind the complete Collector Route architecture exactly once."""
    if app_class is None:
        return False
    if bool(getattr(app_class, "_spina_collector_route_wave79_installed", False)):
        return True
    try:
        dependencies = dict(namespace)
        dependencies.update(
            {
                "_spina_v27_route_colors": _spina_v25_collector_colors,
                "_spina_v27_hidden_collector_widgets": _spina_v27_hidden_collector_widgets,
                "_spina_v27_update_route_cards": _spina_v27_update_route_cards,
                "_spina_v27_build_collectors_tab": _spina_v27_build_collectors_tab,
            }
        )
        configure_collector_route_dependencies(dependencies)
        configure_collector_dialog_dependencies(dependencies)
        configure_collector_refresh_dependencies(dependencies)
        configure_collector_tab_dependencies(dependencies)
        _controller.configure_collector_route_controller_dependencies(dependencies)
        _report.configure_collector_route_report_dependencies(dependencies)

        app_class._build_collectors_tab = _spina_v27_build_collectors_tab
        app_class._collector_editor_dialog = _spina_v27_collector_editor_dialog

        for name in _EDITOR_METHOD_NAMES:
            value = getattr(_editor, name, None)
            if callable(value):
                setattr(app_class, name, value)
        for name in _controller.COLLECTOR_ROUTE_METHOD_NAMES:
            value = getattr(_controller, name, None)
            if callable(value):
                setattr(app_class, name, value)
        for name in _report.COLLECTOR_ROUTE_METHOD_NAMES:
            value = getattr(_report, name, None)
            if callable(value):
                setattr(app_class, name, value)

        def refresh_with_cards(self, *args, **kwargs):
            result = _refresh_collectors(self, *args, **kwargs)
            try:
                _spina_v27_update_route_cards(self)
            except Exception:
                pass
            return result

        app_class.refresh_collectors = refresh_with_cards
        app_class._on_collectors_select = _selected_collector
        app_class._spina_collector_route_wave79_installed = True
        return True
    except Exception as exc:
        try:
            if callable(log_suppressed_once):
                log_suppressed_once(
                    "collector_route_wave79_install_failed",
                    "Wave 79 Collector Route installation failed",
                    exc,
                )
        except Exception:
            pass
        _safe_log(log_exc, "collector_route.wave79.install", exc)
        return False
'''


def _is_controller_name(name: str) -> bool:
    return name in CONTROLLER_EXPLICIT or name.startswith(CONTROLLER_PREFIXES)


def _is_report_name(name: str) -> bool:
    return name in REPORT_EXPLICIT or name.startswith(REPORT_PREFIXES)


def apply(source: str) -> tuple[str, str, str, str]:
    if source.count(INSTALL_START) == 1 and source.count(INSTALL_END) == 1:
        if any(start in source or end in source for start, end in MARKED_BLOCKS):
            raise AssertionError("Wave 79 installer exists beside legacy marked blocks")
        controller = CONTROLLER_PATH.read_text(encoding="utf-8")
        report = REPORT_PATH.read_text(encoding="utf-8")
        feature = FEATURE_PATH.read_text(encoding="utf-8")
        return source, controller, report, feature
    if INSTALL_START in source or INSTALL_END in source:
        raise AssertionError("Partial Wave 79 installer markers found")

    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)
    top_functions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    app_class: ast.ClassDef | None = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_functions.setdefault(node.name, []).append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "App":
            app_class = node

    controller_methods: dict[str, str] = {}
    report_methods: dict[str, str] = {}
    removal_ranges: list[tuple[int, int]] = []

    # Remove every duplicate definition but retain only the final active source in modules.
    for name, nodes in top_functions.items():
        if _is_report_name(name):
            for node in nodes:
                removal_ranges.append((node.lineno, node.end_lineno))
            report_methods[name] = _node_text(lines, nodes[-1])
        elif _is_controller_name(name) or name == "_build_collectors_tab":
            for node in nodes:
                removal_ranges.append((node.lineno, node.end_lineno))
            if name not in CONTROLLER_SKIP_EXPORT:
                controller_methods[name] = _node_text(lines, nodes[-1])

    if app_class is None:
        raise AssertionError("App class not found")
    class_nodes = {
        node.name: node
        for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in CLASS_METHODS
    }
    missing_class = CLASS_METHODS - set(class_nodes)
    if missing_class:
        raise AssertionError(f"Expected Collector Route App methods missing: {sorted(missing_class)}")
    for name, node in class_nodes.items():
        removal_ranges.append((node.lineno, node.end_lineno))
        if name not in CLASS_SKIP_EXPORT and name not in controller_methods:
            controller_methods[name] = _node_text(lines, node, dedent=True)

    required_controller = {
        "_collectors_name_from_values",
        "_on_collectors_tree_click",
        "_collectors_save_inline_edit",
        "_schedule_collectors_refresh",
        "_clear_collectors_search_filters",
        "_populate_collector_details",
        "_save_collector_notes",
        "_save_selected_collector_notes",
        "_show_conflicts",
        "_show_unassigned_areas",
        "_show_no_area_clients",
        "_delete_selected_collector",
        "_edit_selected_collector",
        "_add_collector",
        "_spina_v27_get_route_master_areas",
    }
    required_report = {
        "print_collector_route_daily_ledger",
        "print_full_daily_ledger",
        "_spina_route_balance_like_generate_report",
        "_spina_route_adv_marker_for",
        "_spina_save_closed_collector_route_copy_same_format",
    }
    if required_controller - set(controller_methods):
        raise AssertionError(
            f"Controller extraction incomplete: {sorted(required_controller - set(controller_methods))}"
        )
    if required_report - set(report_methods):
        raise AssertionError(
            f"Report extraction incomplete: {sorted(required_report - set(report_methods))}"
        )

    # Remove direct imports and binding statements superseded by the installer.
    binding_tokens = {
        "_configure_wave39_collector_refresh",
        "_wave39_refresh_collectors",
        "App.print_full_daily_ledger",
        "App.print_collector_route_daily_ledger",
        "archive_rowid_fix_bind",  # not removed unless an extracted name is also present
        "setattr(App, \"_populate_collector_details\"",
        "setattr(App, \"_on_collectors_select\"",
        "setattr(App, '_populate_collector_details'",
        "setattr(App, '_on_collectors_select'",
    }
    extracted_names = set(controller_methods) | set(report_methods) | {"_on_collectors_select"}
    for node in tree.body:
        segment = _node_text(lines, node)
        if isinstance(node, ast.ImportFrom) and (node.module or "") in COLLECTOR_MODULE_IMPORTS:
            removal_ranges.append((node.lineno, node.end_lineno))
            continue
        if any(token in segment for token in binding_tokens):
            if "archive_rowid_fix_bind" not in segment or any(name in segment for name in extracted_names):
                removal_ranges.append((node.lineno, node.end_lineno))
                continue
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr, ast.Try)):
            if "App" in segment and any(name in segment for name in extracted_names):
                if any(word in segment for word in ("setattr", "App.", "globals()[", "getattr(App")):
                    removal_ranges.append((node.lineno, node.end_lineno))

    updated = _remove_ranges(source, removal_ranges)
    first = True
    for start, end in MARKED_BLOCKS:
        updated = _replace_marked_block(updated, start, end, INSTALL_BLOCK if first else "")
        first = False

    controller_source = _module_source(
        "Collector Route controller and editor actions",
        "configure_collector_route_controller_dependencies",
        controller_methods,
    )
    report_source = _module_source(
        "Collector Route and Daily Ledger report engine",
        "configure_collector_route_report_dependencies",
        report_methods,
    )
    feature_source = _feature_source()

    forbidden = (
        "# --- BEGIN: v25 Modern Collector Route UI ---",
        "# --- BEGIN: v26 Collector Route remove visible right-side panel ---",
        "# --- BEGIN: v27 Modern Collector Route Overview + Better Route Editor ---",
        "def print_collector_route_daily_ledger(",
        "def print_full_daily_ledger(",
        "def _spina_route_balance_like_generate_report(",
        "def _spina_route_adv_marker_for(",
        "def _spina_save_closed_collector_route_copy_same_format(",
        "def _collectors_save_inline_edit(",
        "def _populate_collector_details(",
    )
    for token in forbidden:
        if token in updated:
            raise AssertionError(f"Legacy Collector Route token remains in desktop source: {token}")
    if updated.count(INSTALL_START) != 1 or updated.count(INSTALL_END) != 1:
        raise AssertionError("Wave 79 installer count mismatch")
    return updated, controller_source, report_source, feature_source


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    updated, controller, report, feature = apply(source)
    CONTROLLER_PATH.write_text(controller, encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    FEATURE_PATH.write_text(feature, encoding="utf-8")
    APP_PATH.write_text(updated, encoding="utf-8")

    # Prove committed/generation idempotence from the actual files.
    again = apply(updated)
    if again != (updated, controller, report, feature):
        raise AssertionError("Wave 79 extraction is not idempotent")
    print(
        "Wave 79 Collector Route extraction applied: "
        f"controller={controller.count('\\ndef ')} functions, "
        f"report={report.count('\\ndef ')} functions"
    )


if __name__ == "__main__":
    main()
