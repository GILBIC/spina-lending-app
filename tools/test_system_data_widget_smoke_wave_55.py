from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import system_data_presentation as system_data


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def widget_texts(widget):
    values = []
    for child in walk(widget):
        try:
            text = child.cget("text")
        except Exception:
            text = ""
        if text:
            values.append(str(text))
    return values


def button_by_text(root, text):
    for widget in walk(root):
        if isinstance(widget, ttk.Button):
            try:
                if str(widget.cget("text")) == text:
                    return widget
            except Exception:
                pass
    raise AssertionError(f"Missing button: {text}")


class FakeDB:
    def __init__(self):
        self.day_close = None
        self.total_calls = []
        self.close_calls = []

    def get_databank_daily_total(self, date_value, loan_type=None):
        self.total_calls.append((date_value, loan_type))
        return 1200 if loan_type == "Regular" else 300

    def get_databank_day_close(self, date_value):
        self.close_calls.append(date_value)
        return self.day_close


class DummySystemDataApp:
    def __init__(self, root):
        self.root = root
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True)
        self.tab_home = ttk.Frame(self.nb)
        self.tab_system_data = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_home, text="Home")
        self.nb.add(self.tab_system_data, text="Data")
        self.db = FakeDB()
        self.focus_date = "2026-07-27"
        self.routes = []

    def _get_databank_focus_date(self):
        return self.focus_date

    def open_databank_close_dialog(self, date_value):
        self.routes.append(("close", date_value))

    def open_databank_close_history_dialog(self, date_value):
        self.routes.append(("history", date_value))

    def open_databank_close_records_dialog(self, **kwargs):
        self.routes.append(("records", kwargs))

    def print_databank_close_report(self, date_value):
        self.routes.append(("print", date_value))


def bind_methods(app):
    for name in system_data.SYSTEM_DATA_PRESENTATION_TARGETS:
        setattr(app, name, lambda *args, _name=name, **kwargs: getattr(system_data, _name)(app, *args, **kwargs))


def stage(name):
    print(f"WAVE55_WIDGET_STAGE|{name}", flush=True)


def main() -> None:
    system_data.configure_system_data_presentation_dependencies(
        {
            "fmt_currency": lambda value: f"${float(value or 0):,.2f}",
            "_log_suppressed_once": lambda *args, **kwargs: None,
        }
    )

    root = tk.Tk()
    original_showerror = messagebox.showerror
    errors = []
    messagebox.showerror = lambda title, text, **kwargs: errors.append((title, text))
    try:
        stage("construct")
        root.geometry("1280x720+20+20")
        app = DummySystemDataApp(root)
        bind_methods(app)

        system_data._build_system_data_tab(app)
        root.update_idletasks()

        stage("labels")
        texts = widget_texts(app.tab_system_data)
        for expected in (
            "Data",
            "System account daily close / variance workspace",
            "Daily Close Tools",
            "Date",
            "Use Focus Date",
            "Refresh",
            "Open Daily Close / Variance",
            "History",
            "Records",
            "Print Report",
            "Summary",
        ):
            assert expected in texts, (expected, texts)

        stage("initial-summary")
        initial = app.system_data_summary_var.get()
        assert "Date: 2026-07-27" in initial
        assert "Regular Expected: $1,200.00" in initial
        assert "7x7 Expected: $300.00" in initial
        assert "Total Expected: $1,500.00" in initial
        assert "No Daily Close record yet" in initial
        assert app.db.total_calls[-2:] == [
            ("2026-07-27", "Regular"),
            ("2026-07-27", "7x7"),
        ]

        stage("focus-date")
        app.focus_date = "2026-07-26"
        button_by_text(app.tab_system_data, "Use Focus Date").invoke()
        assert app.system_data_date_var.get() == "2026-07-26"

        stage("closed-summary")
        app.system_data_date_var.set("2026-07-27")
        app.db.day_close = {
            "expected_amount": 1500,
            "actual_cash": 1480,
            "variance": -20,
            "variance_status": "Short",
            "variance_workflow_status": "For Review",
            "is_closed": 1,
            "note": "Collector count checked",
        }
        button_by_text(app.tab_system_data, "Refresh").invoke()
        closed = app.system_data_summary_var.get()
        assert "Total Expected: $1,500.00" in closed
        assert "Actual Cash: $1,480.00" in closed
        assert "Variance: $20.00 (Short)" in closed
        assert "Workflow: For Review | Status: Closed" in closed
        assert "Note: Collector count checked" in closed

        stage("routing")
        button_by_text(app.tab_system_data, "Open Daily Close / Variance").invoke()
        button_by_text(app.tab_system_data, "History").invoke()
        button_by_text(app.tab_system_data, "Records").invoke()
        button_by_text(app.tab_system_data, "Print Report").invoke()
        assert app.routes == [
            ("close", "2026-07-27"),
            ("history", "2026-07-27"),
            ("records", {"start_date": "2026-07-27", "end_date": "2026-07-27"}),
            ("print", "2026-07-27"),
        ]

        stage("invalid-date")
        app.system_data_date_var.set("bad-date")
        assert system_data._system_data_get_date(app) == ""
        assert errors[-1] == ("Data", "Use date format YYYY-MM-DD.")

        stage("hide-show")
        system_data._hide_system_data_tab(app)
        root.update_idletasks()
        assert str(app.tab_system_data) in set(app.nb.tabs())
        assert str(app.nb.tab(app.tab_system_data, "state")).lower() == "hidden"
        system_data._show_system_data_tab(app)
        root.update_idletasks()
        assert str(app.tab_system_data) in set(app.nb.tabs())
        assert str(app.nb.tab(app.tab_system_data, "state")).lower() != "hidden"
        assert app.nb.tab(app.tab_system_data, "text") == "Data"

        print("Wave 55 System Data real Tkinter smoke test passed.")
    finally:
        messagebox.showerror = original_showerror
        try:
            root.update_idletasks()
        except Exception:
            pass
        root.destroy()


if __name__ == "__main__":
    main()
