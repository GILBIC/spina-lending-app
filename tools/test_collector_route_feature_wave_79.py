#!/usr/bin/env python3
"""Installer regression for the generated Collector Route Wave 79 architecture."""
from __future__ import annotations

from spina_app import collector_tab_presentation as _tab_presentation
from spina_app.features.collector_route import install_collector_route_feature


def main() -> None:
    class DummyApp:
        def __init__(self, *_args, **_kwargs):
            self.initialized = True

    namespace = {
        "os": __import__("os"),
        "json": __import__("json"),
        "sqlite3": __import__("sqlite3"),
        "split_area_main_sub": lambda value: (str(value or ""), ""),
        "DATA_DIR": ".",
        "data_path": lambda name: name,
        "_write_json_atomic": lambda _path, _data: True,
        "_read_json_file": lambda _path: {},
        "_log_exc": lambda *_args, **_kwargs: None,
        "_log_suppressed_once": lambda *_args, **_kwargs: None,
    }
    assert install_collector_route_feature(DummyApp, namespace=namespace)
    assert DummyApp._spina_collector_route_wave79_installed is True

    required = (
        "_build_collectors_tab",
        "_collector_editor_dialog",
        "refresh_collectors",
        "_on_collectors_select",
        "_collectors_name_from_values",
        "_on_collectors_tree_click",
        "_collectors_save_inline_edit",
        "_show_conflicts",
        "_show_unassigned_areas",
        "_show_no_area_clients",
        "_delete_selected_collector",
        "_edit_selected_collector",
        "_add_collector",
        "print_collector_route_daily_ledger",
        "print_full_daily_ledger",
        "_spina_route_balance_like_generate_report",
        "_spina_route_adv_marker_for",
        "_spina_save_closed_collector_route_copy_same_format",
    )
    for name in required:
        assert callable(getattr(DummyApp, name, None)), name

    # The modern tab calls these helpers as module globals. Wave 79 must bind all
    # of them explicitly because their former main-file imports were extracted.
    presentation_helpers = (
        "_spina_v27_route_button",
        "_spina_v27_route_card",
        "_spina_v27_style_route_trees",
        "_spina_v27_route_colors",
        "_spina_v27_hidden_collector_widgets",
        "_spina_v27_update_route_cards",
    )
    for name in presentation_helpers:
        assert callable(getattr(_tab_presentation, name, None)), name

    first = {name: getattr(DummyApp, name) for name in required}
    first_refresh = DummyApp.refresh_collectors
    assert install_collector_route_feature(DummyApp, namespace=namespace)
    assert DummyApp.refresh_collectors is first_refresh
    for name, value in first.items():
        assert getattr(DummyApp, name) is value, name

    print("Wave 79 Collector Route installer tests passed.")


if __name__ == "__main__":
    main()
