from __future__ import annotations

from pathlib import Path

from apply_hierarchical_area_ui_phase2 import inspect

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
UI = Path("spina_app/area_hierarchy_ui.py")


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    assert inspect(source) == "patched"
    assert 'readonly=False)\n    area_box.grid(row=0, column=2' not in source
    assert "def _add_area_quick():" not in source
    assert 'def add_area_quick():\n        nm = simpledialog.askstring("Add Area"' not in source
    assert source.count("build_area_selector_field(") == 1
    assert source.count("build_simple_area_selector(self, outer, area_var, width=34)") == 1
    assert source.count("App.open_areas_manager = _spina_area_open_manager") == 1

    # The modern client form must expose Area Management beside Select and Clear.
    ui_source = UI.read_text(encoding="utf-8")
    assert ui_source.count('text="Manage Areas"') == 1
    assert "command=lambda: open_area_manager(app)" in ui_source
    compile(source, str(APP), "exec")
    compile(ui_source, str(UI), "exec")
    print("Hierarchical Area UI Phase 2 source checks passed")


if __name__ == "__main__":
    main()
