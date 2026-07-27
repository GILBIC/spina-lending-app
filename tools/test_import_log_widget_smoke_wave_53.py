from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from spina_app import import_log_presentation as presentation


def descendants(widget):
    out = []
    for child in widget.winfo_children():
        out.append(child)
        out.extend(descendants(child))
    return out


def main() -> None:
    opened: list[str] = []
    suppressed: list[tuple] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        presentation.configure_import_log_dependencies(
            {
                "_log_suppressed_once": lambda *args, **kwargs: suppressed.append(args),
                "_open_path": lambda path: opened.append(str(path)),
                "DATA_DIR": str(tmp_path),
            }
        )

        root = tk.Tk()
        root.withdraw()

        class Dummy:
            pass

        app = Dummy()
        app.root = root
        presentation._show_import_log_window(
            app,
            "Import Results",
            "Inserted: 1 | Updated: 1 | Errors: 1",
            [
                "START: sample.xlsx",
                "INSERTED: Alice",
                "UPDATED: Bob",
                "SKIP_DUP: Carla",
                "SKIP_UNKNOWN: Diego",
                "ERROR: invalid payment",
                "OTHER: finished",
            ],
        )
        root.update_idletasks()
        root.update()

        tops = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]
        assert len(tops) == 1
        win = tops[0]
        assert win.title() == "Import Results"

        widgets = descendants(win)
        notebooks = [widget for widget in widgets if isinstance(widget, ttk.Notebook)]
        assert len(notebooks) == 1
        notebook = notebooks[0]
        tab_names = [notebook.tab(tab_id, "text") for tab_id in notebook.tabs()]
        assert len(tab_names) == 9
        assert any(name.startswith("All (7)") for name in tab_names)
        assert any(name.startswith("Inserted (1)") for name in tab_names)
        assert any(name.startswith("Errors (1)") for name in tab_names)
        assert any(name.startswith("Skipped Duplicates (1)") for name in tab_names)

        texts = [widget for widget in widgets if isinstance(widget, tk.Text)]
        assert len(texts) == 9
        combined = "\n".join(text.get("1.0", "end") for text in texts)
        assert "INSERTED: Alice" in combined
        assert "ERROR: invalid payment" in combined
        assert "SKIP_UNKNOWN: Diego" in combined

        buttons = [widget for widget in widgets if isinstance(widget, ttk.Button)]
        labels = {button.cget("text") for button in buttons}
        assert {
            "Copy Visible",
            "Copy All",
            "Save Visible…",
            "Save All…",
            "Open Saved Log",
            "Open Data Folder",
            "Close",
        } <= labels

        copy_all = next(button for button in buttons if button.cget("text") == "Copy All")
        copy_all.invoke()
        root.update()
        clipboard = root.clipboard_get()
        assert "== CHRONOLOGICAL ==" in clipboard
        assert "== ORGANIZED ==" in clipboard
        assert "ERROR: invalid payment" in clipboard

        win.destroy()
        root.update_idletasks()
        root.destroy()

        fallback_path = tmp_path / "fallback-import-log.txt"
        original_toplevel = presentation.tk.Toplevel

        def fail_toplevel(*_args, **_kwargs):
            raise RuntimeError("headless smoke")

        presentation.tk.Toplevel = fail_toplevel
        try:
            presentation._show_import_log_window(
                Dummy(),
                "Fallback",
                "Summary line",
                ["INSERTED: One", "ERROR: Two"],
                str(fallback_path),
            )
        finally:
            presentation.tk.Toplevel = original_toplevel

        saved = fallback_path.read_text(encoding="utf-8")
        assert "Summary line" in saved
        assert "INSERTED: One" in saved
        assert "ERROR: Two" in saved

    assert not suppressed
    print("Wave 53 Import Log real-Tk and headless-save smoke test passed.")


if __name__ == "__main__":
    main()
