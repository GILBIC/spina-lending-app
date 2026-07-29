#!/usr/bin/env python3
"""Installer regression for the generated Collector Route Wave 79 architecture."""
from __future__ import annotations

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

    first = {name: getattr(DummyApp, name) for name in required}
    first_refresh = DummyApp.refresh_collectors
    assert install_collector_route_feature(DummyApp, namespace=namespace)
    assert DummyApp.refresh_collectors is first_refresh
    for name, value in first.items():
        assert getattr(DummyApp, name) is value, name

    print("Wave 79 Collector Route installer tests passed.")


if __name__ == "__main__":
    main()
