from __future__ import annotations

from pathlib import Path

from apply_hierarchical_area_ui_phase2 import inspect

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
UI = Path("spina_app/area_hierarchy_ui.py")
OPS = Path("spina_app/area_hierarchy_ops.py")
STORAGE = Path("spina_app/area_hierarchy.py")


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    assert inspect(source) == "patched"
    assert 'readonly=False)\n    area_box.grid(row=0, column=2' not in source
    assert "def _add_area_quick():" not in source
    assert 'def add_area_quick():\n        nm = simpledialog.askstring("Add Area"' not in source
    assert source.count("build_area_selector_field(") == 1
    assert source.count("build_simple_area_selector(self, outer, area_var, width=34)") == 1
    assert source.count("App.open_areas_manager = _spina_area_open_manager") == 1

    ui_source = UI.read_text(encoding="utf-8")
    assert ui_source.count('text="Manage Areas"') == 2
    assert ui_source.count("command=lambda: open_area_manager(app, owner)") == 2
    assert "def open_area_manager(app: Any, parent: Any = None)" in ui_source
    assert '_FOLDER_CLOSED = "📁"' in ui_source
    assert '_FOLDER_OPEN = "📂"' in ui_source
    assert 'text="Expand All"' in ui_source
    assert 'text="Collapse All"' in ui_source
    assert 'tree.heading("#0", text="Area folders")' in ui_source
    assert "search_var.trace_add(\"write\", render)" in ui_source
    assert "state[\"nodes\"] = list_area_nodes" in ui_source
    assert "_refresh_app_area_views(app)\n        if current" not in ui_source

    ops_source = OPS.read_text(encoding="utf-8")
    assert "ensure_area_hierarchy_ready(conn)" in ops_source
    assert "def _client_count_for_nodes(" in ops_source
    assert "area_uid IN (" in ops_source
    assert "migrate_flat_areas(conn)" in ops_source

    storage_source = STORAGE.read_text(encoding="utf-8")
    assert "_READY_CONNECTION_IDS" in storage_source
    assert "def ensure_area_hierarchy_ready(" in storage_source

    compile(source, str(APP), "exec")
    compile(ui_source, str(UI), "exec")
    compile(ops_source, str(OPS), "exec")
    compile(storage_source, str(STORAGE), "exec")
    print("Hierarchical Area UI Phase 2 source checks passed")


if __name__ == "__main__":
    main()
