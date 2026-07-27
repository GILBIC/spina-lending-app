from __future__ import annotations

import ast
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import databank_presentation as databank
from tools.test_databank_widget_smoke_wave_49 import DummyApp

MODULE = ROOT / "spina_app" / "databank_presentation.py"


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def buttons_with_text(widget, text: str):
    matches = []
    for child in walk(widget):
        try:
            if isinstance(child, ttk.Button) and str(child.cget("text")) == text:
                matches.append(child)
        except Exception:
            pass
    return matches


def static_checks() -> None:
    text = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(text)

    original = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_spina_v15_build_data_tab"
    ]
    assert len(original) == 1

    wrappers = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_spina_v53_build_data_tab_with_import_control"
    ]
    restorers = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_spina_v53_restore_databank_import_control"
    ]
    assert len(wrappers) == 1
    assert len(restorers) == 1

    assignments = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_spina_v15_build_data_tab" for target in node.targets)
        and isinstance(node.value, ast.Name)
        and node.value.id == "_spina_v53_build_data_tab_with_import_control"
    ]
    assert len(assignments) == 1

    restorer_text = ast.get_source_segment(text, restorers[0]) or ""
    assert "_import_from_excel_entry" in restorer_text
    assert 'text="Import Excel"' in restorer_text
    assert '"Daily Close / View"' in restorer_text
    assert ".execute(" not in restorer_text
    assert "connect_db" not in restorer_text
    assert "principal" not in restorer_text.lower()
    assert "interest" not in restorer_text.lower()
    assert "balance" not in restorer_text.lower()


def widget_checks() -> None:
    root = tk.Tk()
    try:
        root.geometry("1200x760+20+20")
        app = DummyApp(root)
        calls = []
        app._import_from_excel_entry = lambda: calls.append("import")

        databank._spina_v15_build_data_tab(app)
        root.update_idletasks()

        buttons = buttons_with_text(app.tab_data, "Import Excel")
        assert len(buttons) == 1, len(buttons)
        assert buttons[0] is getattr(app, "_db_import_excel_btn", None)
        buttons[0].invoke()
        root.update_idletasks()
        assert calls == ["import"]

        # Rebuilding destroys the old page and must still create exactly one control.
        databank._spina_v15_build_data_tab(app)
        root.update_idletasks()
        buttons = buttons_with_text(app.tab_data, "Import Excel")
        assert len(buttons) == 1, len(buttons)
        buttons[0].invoke()
        assert calls == ["import", "import"]

        print("Wave 53 Data Bank Import Excel control regression passed.")
    finally:
        try:
            root.update_idletasks()
        except Exception:
            pass
        root.destroy()


def main() -> None:
    static_checks()
    widget_checks()


if __name__ == "__main__":
    main()

# Connector-authored trigger after bot finalization.
