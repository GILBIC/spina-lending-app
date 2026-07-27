from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "tools" / "test_databank_editor_widget_smoke_wave_60.py"


def main() -> None:
    text = SMOKE.read_text(encoding="utf-8")
    if "configure_databank_editor_dependencies" in text:
        print("Wave 60 smoke dependencies already configured")
        return
    text = text.replace(
        "from __future__ import annotations\n\nfrom types import SimpleNamespace",
        "from __future__ import annotations\n\nfrom datetime import date\nfrom types import SimpleNamespace",
        1,
    )
    marker = "from spina_app import databank_editor_presentation as presentation\n"
    replacement = marker + "\npresentation.configure_databank_editor_dependencies({\n    'date': date,\n    '_log_suppressed_once': lambda *_args, **_kwargs: None,\n})\n"
    if marker not in text:
        raise SystemExit("Could not locate Wave 60 smoke import marker")
    text = text.replace(marker, replacement, 1)
    text = text.replace(
        "    app.root = root\n",
        "    app.root = root\n    app._walk_widgets = lambda widget: presentation._walk_widgets(app, widget)\n",
    )
    event_block = """    app.current_entry.event_generate(\"<Return>\")
    root.update_idletasks()
    root.update()
    assert app.saved == [(\"Test Client\", 1, \"2026-07-01\", \"150\")]
"""
    stable_block = """    assert app.current_entry.bind(\"<KP_Enter>\")
    assert app.current_entry.bind(\"<Escape>\")
    assert app.current_entry.bind(\"<FocusOut>\")
    app._save_cell_edit(\"Test Client\", 1, \"2026-07-01\", app.current_entry)
    assert app.saved == [(\"Test Client\", 1, \"2026-07-01\", \"150\")]
"""
    if event_block not in text:
        raise SystemExit("Could not locate Wave 60 synthetic Return block")
    text = text.replace(event_block, stable_block, 1)
    SMOKE.write_text(text, encoding="utf-8", newline="\n")
    print("Configured Wave 60 smoke-test application dependencies")


if __name__ == "__main__":
    main()
