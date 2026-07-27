"""Real Tkinter behavior test for Wave 59 Data Bank grid presentation."""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date as _date
from tkinter import ttk

import spina_app.databank_grid_presentation as module


class FixedDate(_date):
    @classmethod
    def today(cls):
        return cls(2026, 7, 27)


class FakeDB:
    def __init__(self):
        self.calls = []

    def get_all_clients(self, search=None, loan_type=None, search_by=None):
        self.calls.append(("get_all_clients", search, loan_type, search_by))
        return [
            {"name": "ALPHA CLIENT", "area": "AREA A"},
            {"name": "BETA CLIENT", "area": "AREA B"},
        ]

    def get_client_info(self, name, loan_type=None):
        self.calls.append(("get_client_info", name, loan_type))
        return {"area": "FALLBACK"}

    def get_transaction(self, name, date_s):
        self.calls.append(("get_transaction", name, date_s))
        if name == "ALPHA CLIENT" and date_s == "2026-07-01":
            return {"payment": 100}
        if name == "BETA CLIENT" and date_s == "2026-07-02":
            return {"payment": 0}
        return None


class FakeApp:
    goto_current_month = module.goto_current_month
    prev_month = module.prev_month
    next_month = module.next_month
    refresh_data_grid = module.refresh_data_grid

    def __init__(self, root):
        self.root = root
        self.db = FakeDB()
        self.grid_year = 2026
        self.grid_month = 7
        self.inner = ttk.Frame(root)
        self.inner.pack(fill="both", expand=True)
        self.month_lbl = ttk.Label(root, text="")
        self.month_lbl.pack()
        self.status_var = tk.StringVar(root, value="")
        self.search_db_var = tk.StringVar(root, value="")
        self._db_rows_var = tk.StringVar(root, value="")
        self.resize_calls = 0
        self.toolbar_calls = 0
        self.binding_calls = 0

    def _configure_tree_stripes(self, tree):
        tree.tag_configure("odd")
        tree.tag_configure("even")

    def _ensure_databank_edit_bindings(self):
        self.binding_calls += 1

    def _mode_filter(self):
        return "Regular"

    def _month_label(self):
        return f"{calendar.month_name[self.grid_month]} {self.grid_year}"

    def _remember_cell_click(self, event=None):
        return None

    def _resize_databank_columns(self, event=None):
        self.resize_calls += 1

    def _update_data_toolbar(self):
        self.toolbar_calls += 1

    def _begin_cell_edit(self, event=None):
        return None

    def delete_selected_cell(self, event=None):
        return None

    def _on_mousewheel_sync(self, event=None):
        return None

    def _mark_missed_for_selected(self):
        return None


def main() -> None:
    module.configure_databank_grid_dependencies({
        "calendar": calendar,
        "date": FixedDate,
        "tk": tk,
        "ttk": ttk,
        "fmt_currency": lambda value: f"${float(value):,.2f}",
        "_log_suppressed_once": lambda *args, **kwargs: None,
        "_log_ignored": lambda *args, **kwargs: None,
    })
    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp(root)
        app.refresh_data_grid()
        root.update_idletasks()

        assert app.status_var.get() == "Data Bank is view-only. Encode in Excel, then Import."
        assert app.name_tree.winfo_exists()
        assert app.days_tree.winfo_exists()
        assert app.name_tree.get_children() == ("r0", "r1")
        assert app.days_tree.get_children() == ("r0", "r1")
        assert len(app.days_tree["columns"]) == 33
        assert app.name_tree.item("r0", "values") == ("ALPHA CLIENT", "AREA A")
        first = app.days_tree.item("r0", "values")
        second = app.days_tree.item("r1", "values")
        assert first[2] == "$100.00"
        assert second[3] == "0"
        assert app._db_rows_var.get() == "2 rows • Regular • July 2026"
        assert app.resize_calls >= 1
        assert app.toolbar_calls == 1
        assert app.binding_calls == 1
        assert app._db_menu.index("end") == 2
        assert not [call for call in app.db.calls if call[0] not in {"get_all_clients", "get_client_info", "get_transaction"}]

        app.prev_month()
        assert (app.grid_year, app.grid_month) == (2026, 6)
        assert app.month_lbl.cget("text") == "June 2026"
        app.next_month()
        assert (app.grid_year, app.grid_month) == (2026, 7)
        assert app.month_lbl.cget("text") == "July 2026"
        app.grid_year, app.grid_month = 2024, 1
        app.goto_current_month()
        assert (app.grid_year, app.grid_month) == (2026, 7)
        print("Wave 59 real Tkinter Data Bank grid behavior test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
