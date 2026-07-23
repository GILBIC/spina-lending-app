from __future__ import annotations

import argparse
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")

MODERN_OLD = '''    try:\n        areas = list(self.db.get_all_areas() or [])\n    except Exception:\n        areas = []\n    area_box, area_cb = _spina_v23_entry(sec1, "Area / Route", area_var, 24, kind="combo", values=([""] + areas), readonly=False)\n    area_box.grid(row=0, column=2, sticky="ew", pady=(0, 8))\n'''
MODERN_NEW = '''    from spina_app.area_hierarchy_ui import build_area_selector_field\n    area_box, area_cb = build_area_selector_field(\n        sec1, self, win, area_var, label="Area / Route", width=24\n    )\n    area_box.grid(row=0, column=2, sticky="ew", pady=(0, 8))\n'''

LEGACY_START = "    # Area dropdown\n    area_frame = ttk.Frame(outer)\n"
LEGACY_END = '    row("Area:", area_frame, r); r += 1\n'
LEGACY_NEW = '''    # Managed hierarchical Area selector\n    from spina_app.area_hierarchy_ui import build_simple_area_selector\n    area_frame = build_simple_area_selector(self, win, area_var, width=34)\n    row("Area:", area_frame, r); r += 1\n'''

QUICK_START = "            def _add_area_quick():\n"
QUICK_END = "            ttk.Button(_area_row, text='Add...', command=_add_area_quick).pack(side='left', padx=4)\n"
QUICK_NEW = "            ttk.Label(_area_row, text='Managed Areas only').pack(side='left', padx=4)\n"

MAIN_MARKER = "def main():\n"
OVERRIDE = '''# === Phase 2: hierarchical Area manager override ===\nfrom spina_app.area_hierarchy_ui import open_area_manager as _spina_area_open_manager\nApp.open_areas_manager = _spina_area_open_manager\n# === END Phase 2 hierarchical Area manager override ===\n\n\n'''


def _between(text: str, start: str, end: str) -> tuple[int, int]:
    if text.count(start) != 1:
        raise RuntimeError(f"Expected one start marker, found {text.count(start)}: {start!r}")
    start_index = text.index(start)
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"End marker was not found: {end!r}")
    return start_index, end_index + len(end)


def inspect(text: str) -> str:
    source_flags = [
        MODERN_OLD in text,
        LEGACY_START in text,
        QUICK_START in text,
        OVERRIDE not in text,
    ]
    patched_flags = [
        MODERN_NEW in text,
        LEGACY_NEW in text,
        QUICK_NEW in text,
        OVERRIDE in text,
    ]
    if all(source_flags) and not any(patched_flags):
        if text.count(MODERN_OLD) != 1:
            raise RuntimeError("Modern free-typing Area block is not unique")
        _between(text, LEGACY_START, LEGACY_END)
        _between(text, QUICK_START, QUICK_END)
        if text.count(MAIN_MARKER) != 1:
            raise RuntimeError("Expected exactly one main() marker")
        return "source"
    if all(patched_flags) and not any(source_flags):
        if text.count(MODERN_NEW) != 1:
            raise RuntimeError("Modern managed Area selector block is not unique")
        if text.count(LEGACY_NEW) != 1:
            raise RuntimeError("Legacy managed Area selector block is not unique")
        if text.count(QUICK_NEW) != 1:
            raise RuntimeError("Legacy managed-only label is not unique")
        if text.count(OVERRIDE) != 1:
            raise RuntimeError("Area manager override is not unique")
        return "patched"
    raise RuntimeError(
        "Mixed or unexpected Phase 2 Area UI state: "
        f"source={source_flags}, patched={patched_flags}"
    )


def apply(text: str) -> str:
    if inspect(text) == "patched":
        return text
    text = text.replace(MODERN_OLD, MODERN_NEW, 1)

    start, end = _between(text, LEGACY_START, LEGACY_END)
    text = text[:start] + LEGACY_NEW + text[end:]

    start, end = _between(text, QUICK_START, QUICK_END)
    text = text[:start] + QUICK_NEW + text[end:]

    text = text.replace(MAIN_MARKER, OVERRIDE + MAIN_MARKER, 1)
    compile(text, str(APP), "exec")
    if inspect(text) != "patched":
        raise RuntimeError("Phase 2 Area UI patch did not reach the patched state")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    source = APP.read_text(encoding="utf-8")
    state = inspect(source)
    if args.apply and state == "source":
        APP.write_text(apply(source), encoding="utf-8")
        state = inspect(APP.read_text(encoding="utf-8"))
        print("Applied hierarchical Area UI Phase 2")
    else:
        print(f"Hierarchical Area UI Phase 2 state: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
