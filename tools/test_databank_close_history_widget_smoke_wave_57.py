"""Real Tkinter smoke test for Wave 57 Data Bank Close History presentation."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import spina_app.databank_close_history_presentation as module


class FakeDB:
    def __init__(self):
        self.calls = []

    def list_databank_day_close_history(self, date_s, loan_type=None):
        self.calls.append((date_s, loan_type))
        return [
            {
                "event_at": "2026-07-27 08:00:00",
                "action": "CLOSE",
                "workflow_status": "FINAL",
                "variance_status": "SHORT",
                "expected_amount": 1000,
                "actual_cash": 950,
                "variance": -50,
                "actor": "System",
                "note": "Safe test record",
            }
        ]


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.db = FakeDB()


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def main() -> None:
    module.configure_databank_close_history_presentation_dependencies({
        "fmt_currency": lambda value: f"${float(value):,.2f}",
    })
    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp(root)
        module.open_databank_close_history_dialog(app, "2026-07-27", loan_type="Regular")
        root.update_idletasks()
        assert app.db.calls == [("2026-07-27", "Regular")]

        tops = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]
        assert len(tops) == 1
        top = tops[0]
        assert top.title() == "Daily Close History - 2026-07-27"

        widgets = list(walk(top))
        labels = {str(widget.cget("text")) for widget in widgets if isinstance(widget, ttk.Label)}
        assert "Variance / Close History for 2026-07-27" in labels

        trees = [widget for widget in widgets if isinstance(widget, ttk.Treeview)]
        assert len(trees) == 1
        tree = trees[0]
        expected_columns = (
            "event_at", "action", "workflow", "variance_status", "expected",
            "actual", "variance", "actor", "note",
        )
        assert tuple(tree["columns"]) == expected_columns
        assert [tree.heading(column, "text") for column in expected_columns] == [
            "When", "Action", "Workflow", "Variance Type", "Expected",
            "Actual", "Variance", "By", "Note",
        ]
        rows = tree.get_children()
        assert len(rows) == 1
        assert tuple(tree.item(rows[0], "values")) == (
            "2026-07-27 08:00:00", "CLOSE", "FINAL", "SHORT",
            "$1,000.00", "$950.00", "$50.00", "System", "Safe test record",
        )

        close_buttons = [
            widget for widget in widgets
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Close"
        ]
        assert len(close_buttons) == 1
        close_buttons[0].invoke()
        root.update_idletasks()
        assert not top.winfo_exists()
        print("Wave 57 real Tkinter Data Bank Close History construction test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
