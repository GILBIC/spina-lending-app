#!/usr/bin/env python3
"""Committed/generated architecture checks for Collector Route Wave 79."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
CONTROLLER_PATH = ROOT / "spina_app" / "collector_route_controller.py"
REPORT_PATH = ROOT / "spina_app" / "collector_route_report.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "collector_route.py"

INSTALL_START = "# --- BEGIN: Collector Route feature installer Wave 79 ---"
INSTALL_END = "# --- END: Collector Route feature installer Wave 79 ---"


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    controller_source = CONTROLLER_PATH.read_text(encoding="utf-8")
    report_source = REPORT_PATH.read_text(encoding="utf-8")
    feature_source = FEATURE_PATH.read_text(encoding="utf-8")

    assert app_source.count(INSTALL_START) == 1
    assert app_source.count(INSTALL_END) == 1
    assert app_source.count("_wave79_install_collector_route_feature(") == 1

    forbidden_main = (
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
        "App.print_full_daily_ledger",
        "App.print_collector_route_daily_ledger",
        "_configure_wave39_collector_refresh",
        "_wave39_refresh_collectors",
    )
    for token in forbidden_main:
        assert token not in app_source, token

    tree = ast.parse(app_source)
    app_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_method_names = {
        node.name
        for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for removed in (
        "_build_collectors_tab",
        "_show_conflicts",
        "_show_unassigned_areas",
        "_show_no_area_clients",
        "_delete_selected_collector",
        "_edit_selected_collector",
        "_add_collector",
    ):
        assert removed not in app_method_names, removed

    required_controller = (
        "def _collectors_name_from_values(",
        "def _on_collectors_tree_click(",
        "def _collectors_save_inline_edit(",
        "def _schedule_collectors_refresh(",
        "def _clear_collectors_search_filters(",
        "def _populate_collector_details(",
        "def _save_collector_notes(",
        "def _save_selected_collector_notes(",
        "def _show_conflicts(",
        "def _show_unassigned_areas(",
        "def _show_no_area_clients(",
        "def _delete_selected_collector(",
        "def _edit_selected_collector(",
        "def _add_collector(",
        "def _spina_v27_get_route_master_areas(",
        "COLLECTOR_ROUTE_METHOD_NAMES",
    )
    for token in required_controller:
        assert token in controller_source, token

    required_report = (
        "def print_collector_route_daily_ledger(",
        "def print_full_daily_ledger(",
        "def _spina_route_balance_like_generate_report(",
        "def _spina_route_adv_marker_for(",
        "def _spina_save_closed_collector_route_copy_same_format(",
        "COLLECTOR_ROUTE_METHOD_NAMES",
        "_route_payment_two_cols = True",
        "_ledger_forced_collector_name",
        "Closed_Collector_Routes",
    )
    for token in required_report:
        assert token in report_source, token

    required_feature = (
        "def install_collector_route_feature(",
        "app_class._build_collectors_tab = _spina_v27_build_collectors_tab",
        "app_class.refresh_collectors = refresh_with_cards",
        "app_class._on_collectors_select = _selected_collector",
        "app_class._spina_collector_route_wave79_installed = True",
    )
    for token in required_feature:
        assert token in feature_source, token

    # The generated report engine is intentionally substantial; a tiny stub is not acceptable.
    assert len(report_source.splitlines()) > 2500
    assert len(controller_source.splitlines()) > 500
    print("Wave 79 Collector Route extraction tests passed.")


if __name__ == "__main__":
    main()
