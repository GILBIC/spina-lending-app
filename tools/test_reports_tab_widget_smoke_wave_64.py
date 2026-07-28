from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from spina_app import reports_tab_presentation as presentation


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.tab_reports = ttk.Frame(root)
        self.tab_reports.pack(fill="both", expand=True)
        self.calls = []

    def refresh_reports(self):
        self.calls.append("refresh")

    def generate_pdf_selected(self):
        self.calls.append("generate")

    def open_report_generation_log(self):
        self.calls.append("logs")

    def _open_note_dialog(self):
        self.calls.append("notes")

    def _auto_load_report_note(self):
        self.calls.append("auto_note")

    def _configure_tree_stripes(self, tree):
        tree.tag_configure("even")
        tree.tag_configure("odd")

    def _load_report_note_for_client(self):
        self.calls.append("load_note")

    def _save_dated_note_for_client(self):
        self.calls.append("save_date_note")

    def _save_report_note_for_client(self):
        self.calls.append("save_default_note")

    def _set_report_note_text(self, text):
        self.calls.append(("set_note", text))


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def button(app, text):
    for widget in walk(app.tab_reports):
        if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
            return widget
    raise AssertionError(f"Missing button: {text}")


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    prefs = {"reports_page_size": "Folio 8.5 x 13"}

    presentation.configure_reports_tab_dependencies({
        "tk": tk,
        "ttk": ttk,
        "date": date,
        "messagebox": messagebox,
        "pick_date": lambda *a, **k: None,
        "pick_date_range": lambda *a, **k: None,
        "_load_ledger_prefs": lambda: dict(prefs),
        "_save_ledger_prefs": lambda value: prefs.update(value),
        "_log_ignored": lambda *a, **k: None,
        "_log_suppressed_once": lambda *a, **k: None,
    })

    app = FakeApp(root)
    presentation._build_reports_tab(app)
    root.update_idletasks()

    assert tuple(app.reports_tree["columns"]) == (
        "name", "contact", "loan_type", "term", "day_due", "payment", "mode",
        "linked", "area", "principal", "total", "released", "due",
    )
    assert app.report_page_size_var.get() == "Folio 8.5 x 13"
    assert app.date_range_var.get().endswith(date.today().strftime("%Y-%m-%d"))
    assert not app.reports_notes_box.winfo_manager()

    button(app, "Generate Report").invoke()
    button(app, "Report Logs").invoke()
    button(app, "Notes…").invoke()
    assert "generate" in app.calls
    assert "logs" in app.calls
    assert "notes" in app.calls

    before = app.calls.count("refresh")
    button(app, "Today").invoke()
    root.update_idletasks()
    assert app.start_date_var.get() == date.today().strftime("%Y-%m-%d")
    assert app.end_date_var.get() == date.today().strftime("%Y-%m-%d")
    assert app.calls.count("refresh") > before

    app.report_page_size_var.set("Legal 8.5 x 14")
    root.update()
    assert prefs["reports_page_size"] == "Legal 8.5 x 14"

    app.search_reports_var.set("sample")
    root.update()
    assert app.calls.count("refresh") > before

    root.destroy()
    print("Wave 64 Reports tab Tkinter smoke regression passed")


if __name__ == "__main__":
    main()
