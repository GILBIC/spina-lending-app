from __future__ import annotations

from datetime import date
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

from spina_app import databank_editor_presentation as presentation

presentation.configure_databank_editor_dependencies({
    'date': date,
    '_log_suppressed_once': lambda *_args, **_kwargs: None,
})


class StubApp:
    pass


def _button_texts(widget):
    values = []
    for child in widget.winfo_children():
        try:
            if isinstance(child, ttk.Button):
                values.append(str(child.cget("text")))
        except Exception:
            pass
        values.extend(_button_texts(child))
    return values


def test_missed_reason_dialog(root: tk.Tk) -> None:
    app = StubApp()
    app.root = root
    app._walk_widgets = lambda widget: presentation._walk_widgets(app, widget)
    original_wait = tk.Toplevel.wait_window
    tk.Toplevel.wait_window = lambda self: None
    try:
        result = presentation._pick_missed_reason(app, root, prefill_text="Weather")
    finally:
        tk.Toplevel.wait_window = original_wait
    assert result is None
    tops = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert tops, "missed reason dialog was not constructed"
    top = tops[-1]
    assert top.title() == "Missed Payment - Select reason(s)"
    texts = _button_texts(top)
    assert "Cancel" in texts and "OK" in texts
    checkbuttons = []
    entries = []
    for widget in presentation._walk_widgets(app, top):
        if isinstance(widget, ttk.Checkbutton):
            checkbuttons.append(widget)
        if isinstance(widget, ttk.Entry):
            entries.append(widget)
    assert len(checkbuttons) == 5
    assert len(entries) >= 3
    top.destroy()
    root.update_idletasks()


def test_inline_editor(root: tk.Tk) -> None:
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    columns = ("client", "area", "d1", "d2")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=4)
    for name, text, width in (("client", "Client Name", 180), ("area", "Area", 100), ("d1", "1", 90), ("d2", "2", 90)):
        tree.heading(name, text=text)
        tree.column(name, width=width, stretch=False)
    iid = tree.insert("", "end", values=("Test Client", "Area A", "125.00", ""))
    tree.pack(fill="both", expand=True)
    root.geometry("700x240+0+0")
    root.update_idletasks()
    root.update()

    app = StubApp()
    app.root = root
    app._walk_widgets = lambda widget: presentation._walk_widgets(app, widget)
    app.days_tree = tree
    app.grid_year = 2026
    app.grid_month = 7
    app.current_entry = None
    app._dbank_last_client = None
    app._dbank_last_day = None
    app.toolbar_updates = 0
    app.saved = []
    app._mk_tk_entry = lambda parent, **kwargs: ttk.Entry(parent, **kwargs)
    app._save_cell_edit = lambda client, day, dt, entry: app.saved.append((client, day, dt, entry.get()))
    app._update_data_toolbar = lambda: setattr(app, "toolbar_updates", app.toolbar_updates + 1)

    bbox = tree.bbox(iid, "#3")
    assert bbox, "day cell has no bbox"
    event = SimpleNamespace(x=bbox[0] + 5, y=bbox[1] + 5)
    presentation._remember_cell_click(app, event)
    assert app._dbank_last_client == "Test Client"
    assert app._dbank_last_day == 1
    assert app.toolbar_updates == 1

    presentation._begin_cell_edit(app, event)
    assert isinstance(app.current_entry, ttk.Entry)
    assert app.current_entry.get() == "125.00"
    assert app.current_entry.bind("<Return>")
    app.current_entry.delete(0, "end")
    app.current_entry.insert(0, "150")
    assert app.current_entry.bind("<KP_Enter>")
    assert app.current_entry.bind("<Escape>")
    assert app.current_entry.bind("<FocusOut>")
    app._save_cell_edit("Test Client", 1, "2026-07-01", app.current_entry)
    assert app.saved == [("Test Client", 1, "2026-07-01", "150")]

    walked = list(presentation._walk_widgets(app, frame))
    assert tree in walked
    frame.destroy()
    root.update_idletasks()


def main() -> None:
    root = tk.Tk()
    try:
        test_missed_reason_dialog(root)
        test_inline_editor(root)
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    print("Wave 60 real Tkinter Data Bank editor behavior test passed")


if __name__ == "__main__":
    main()
