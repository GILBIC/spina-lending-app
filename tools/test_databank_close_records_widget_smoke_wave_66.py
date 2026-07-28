from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from spina_app import databank_close_records_presentation as presentation


class FakeDB:
    def __init__(self):
        self.calls = []

    def list_databank_day_close_records(self, start_date, end_date):
        self.calls.append((start_date, end_date))
        return [
            {
                "close_date": "2026-07-01",
                "is_closed": 1,
                "variance_status": "Balanced",
                "regular_total": 1000,
                "x7_total": 200,
                "expected_amount": 1200,
                "actual_cash": 1200,
                "variance": 0,
                "closed_by": "Manager",
                "closed_at": "2026-07-01 18:00:00",
                "note": "Checked\nand balanced",
            },
            {
                "close_date": "2026-07-02",
                "is_closed": 0,
                "variance_status": "Short",
                "regular_total": 900,
                "x7_total": 100,
                "expected_amount": 1000,
                "actual_cash": 950,
                "variance": -50,
                "closed_by": "",
                "closed_at": "",
                "note": "Review",
            },
        ]


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.db = FakeDB()
        self.open_calls = []
        self.print_calls = []

    def _get_databank_focus_date(self):
        return "2026-07-02"

    def open_databank_close_dialog(self, close_date):
        self.open_calls.append(close_date)

    def print_databank_close_report(self, close_date):
        self.print_calls.append(close_date)


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def widget_by_text(root, widget_type, text):
    for widget in walk(root):
        if isinstance(widget, widget_type) and str(widget.cget("text")) == text:
            return widget
    raise AssertionError(f"Missing {widget_type.__name__}: {text}")


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    presentation.configure_databank_close_records_dependencies({
        "datetime": datetime,
        "fmt_currency": lambda value: f"{float(value or 0):,.2f}",
    })

    app = FakeApp(root)
    presentation.open_databank_close_records_dialog(app, "2026-07-01", "2026-07-02")
    root.update_idletasks()
    root.update()

    dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Daily Close Records"]
    assert len(dialogs) == 1
    dialog = dialogs[0]

    trees = [w for w in walk(dialog) if isinstance(w, ttk.Treeview)]
    assert len(trees) == 1
    tree = trees[0]
    assert tuple(tree.cget("columns")) == (
        "close_date", "lock_state", "status", "regular_total", "x7_total",
        "expected_amount", "actual_cash", "variance", "closed_by", "closed_at", "note",
    )
    rows = tree.get_children("")
    assert len(rows) == 2
    first_values = tuple(tree.item(rows[0], "values"))
    second_values = tuple(tree.item(rows[1], "values"))
    assert first_values[0:3] == ("2026-07-01", "CLOSED", "Balanced")
    assert first_values[-1] == "Checked and balanced"
    assert second_values[0:3] == ("2026-07-02", "OPEN", "Short")
    assert app.db.calls[-1] == ("2026-07-01", "2026-07-02")

    required_buttons = ["Load List", "Open Selected", "Print Selected", "Close Window"]
    for text in required_buttons:
        widget_by_text(dialog, ttk.Button, text)

    widget_by_text(dialog, ttk.Button, "Open Selected").invoke()
    root.update()
    assert app.open_calls == ["2026-07-01"]

    widget_by_text(dialog, ttk.Button, "Print Selected").invoke()
    root.update()
    assert app.print_calls == ["2026-07-01"]

    widget_by_text(dialog, ttk.Button, "Load List").invoke()
    root.update()
    assert len(app.db.calls) == 2

    widget_by_text(dialog, ttk.Button, "Close Window").invoke()
    root.update()
    assert not dialog.winfo_exists()
    root.destroy()
    print("Wave 66 Data Bank close-records Tkinter smoke regression passed")


if __name__ == "__main__":
    main()
