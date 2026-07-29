#!/usr/bin/env python3
"""Verify Wave 26/39/44/52 capabilities through the Wave 79 architecture."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "spina_app" / "tabs" / "collectors.py"
REFRESH = ROOT / "spina_app" / "collector_refresh_presentation.py"
TAB = ROOT / "spina_app" / "collector_tab_presentation.py"
DIALOG = ROOT / "spina_app" / "collector_dialog_presentation.py"
CONTROLLER = ROOT / "spina_app" / "collector_route_controller.py"
REPORT = ROOT / "spina_app" / "collector_route_report.py"
FEATURE = ROOT / "spina_app" / "features" / "collector_route.py"
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


def functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> None:
    editor_functions = functions(EDITOR)
    required_editor = {
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
    }
    assert required_editor <= editor_functions

    assert {
        "configure_collector_refresh_dependencies",
        "refresh_collectors",
    } <= functions(REFRESH)
    assert {
        "configure_collector_tab_dependencies",
        "_spina_v27_build_collectors_tab",
    } <= functions(TAB)
    assert {
        "configure_collector_dialog_dependencies",
        "_spina_v27_collector_editor_dialog",
    } <= functions(DIALOG)

    controller_source = CONTROLLER.read_text(encoding="utf-8")
    for name in (
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
    ):
        assert f"def {name}(" in controller_source, name

    report_source = REPORT.read_text(encoding="utf-8")
    for name in (
        "print_collector_route_daily_ledger",
        "print_full_daily_ledger",
        "_spina_route_balance_like_generate_report",
        "_spina_route_adv_marker_for",
        "_spina_save_closed_collector_route_copy_same_format",
    ):
        assert f"def {name}(" in report_source, name

    feature_source = FEATURE.read_text(encoding="utf-8")
    required_wiring = (
        "from spina_app.tabs import collectors as _editor",
        "configure_collector_refresh_dependencies(dependencies)",
        "configure_collector_tab_dependencies(dependencies)",
        "configure_collector_dialog_dependencies(dependencies)",
        "app_class._build_collectors_tab = _spina_v27_build_collectors_tab",
        "app_class._collector_editor_dialog = _spina_v27_collector_editor_dialog",
        "app_class.refresh_collectors = refresh_with_cards",
        "app_class._on_collectors_select = _selected_collector",
    )
    for token in required_wiring:
        assert token in feature_source, token

    app_source = APP.read_text(encoding="utf-8")
    assert app_source.count("# --- BEGIN: Collector Route feature installer Wave 79 ---") == 1
    assert "# --- BEGIN: v25 Modern Collector Route UI ---" not in app_source
    assert "# --- BEGIN: v27 Modern Collector Route Overview + Better Route Editor ---" not in app_source
    assert "App.print_full_daily_ledger" not in app_source
    assert "_configure_wave39_collector_refresh(globals())" not in app_source
    print("Wave 79 legacy Collector Route capability checks passed.")


if __name__ == "__main__":
    main()
