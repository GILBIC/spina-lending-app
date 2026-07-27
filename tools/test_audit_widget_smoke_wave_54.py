from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import audit_presentation as audit


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


class FakeDB:
    def __init__(self):
        self.new_rows = [
            {
                "ts": "2026-07-27 09:00:00",
                "name": "Client Alpha",
                "loan_type": "Regular",
                "date_released": "2026-07-20",
                "payment_start_date": "2026-07-21",
                "principal": 5000,
                "area": "Area 1",
                "payment_term": "Daily",
                "payment_amount": 50,
                "source": "Desktop",
            },
            {
                "ts": "2026-07-27 10:00:00",
                "name": "Client Beta",
                "loan_type": "7x7",
                "date_released": "2026-07-22",
                "payment_start_date": "2026-07-23",
                "principal": 3000,
                "area": "Area 2",
                "payment_term": "Daily",
                "payment_amount": 30,
                "source": "Desktop",
            },
        ]
        self.renew_rows = [
            {
                "ts": "2026-07-27 11:00:00",
                "name": "Client Gamma",
                "loan_type": "Regular",
                "renew_date": "2026-07-27",
                "old_start_date": "2026-03-01",
                "new_start_date": "2026-07-28",
                "released_cash": 2500,
                "old_principal": 5000,
                "new_principal": 6000,
                "renew_count": 2,
                "source": "Desktop",
            }
        ]
        self.calls = []

    def get_audit_new_loan_rows(self, **kwargs):
        self.calls.append(("new", kwargs))
        return list(self.new_rows)

    def get_audit_renewal_rows(self, **kwargs):
        self.calls.append(("renew", kwargs))
        return list(self.renew_rows)


class DummyAuditApp:
    def __init__(self, root):
        self.root = root
        self.tab_audit = ttk.Frame(root, padding=12)
        self.tab_audit.pack(fill="both", expand=True)
        self.db = FakeDB()
        self.selected = []
        self.detail_messages = []
        self.filter_actions = []

    def _audit_tree_factory(self, parent, columns, headings, widths):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=6)
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            tree.column(column, width=width, stretch=False)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree

    def _audit_show_selected(self, kind):
        self.selected.append(kind)

    def _audit_set_today(self):
        self.filter_actions.append("today")

    def _audit_set_last7(self):
        self.filter_actions.append("last7")

    def _audit_set_all(self):
        self.filter_actions.append("all")

    def _audit_parse_date_filters(self):
        return "2026-07-01", "2026-07-31"

    def _audit_money_text(self, value):
        try:
            return f"${float(value or 0):,.2f}"
        except Exception:
            return "$0.00"

    def _audit_set_detail_text(self, text):
        self.detail_messages.append(str(text))


def button_by_text(root, text):
    for widget in walk(root):
        if isinstance(widget, ttk.Button):
            try:
                if str(widget.cget("text")) == text:
                    return widget
            except Exception:
                pass
    raise AssertionError(f"Missing button: {text}")


def main() -> None:
    root = tk.Tk()
    try:
        root.geometry("1280x800+20+20")
        app = DummyAuditApp(root)
        app.refresh_audit_tab = lambda: audit.refresh_audit_tab(app)

        audit._build_audit_tab(app)
        root.update_idletasks()

        texts = widget_texts(app.tab_audit)
        for expected in (
            "Audit & Logs",
            "Separate audit views for new client loans and renewals.",
            "Filters",
            "From",
            "To",
            "Client",
            "Refresh",
            "Today",
            "Last 7 Days",
            "All",
            "Selected Audit Row",
        ):
            assert expected in texts, (expected, texts)

        assert app.audit_nb.tab(app.audit_tab_new, "text") == "New Loans"
        assert app.audit_nb.tab(app.audit_tab_renew, "text") == "Renewals"
        assert app.audit_detail_text.cget("state") == "disabled"

        for label, expected in (("Today", "today"), ("Last 7 Days", "last7"), ("All", "all")):
            button_by_text(app.tab_audit, label).invoke()
            assert app.filter_actions[-1] == expected

        audit.refresh_audit_tab(app)
        root.update_idletasks()

        assert len(app.audit_new_tree.get_children()) == 2
        assert len(app.audit_renew_tree.get_children()) == 1
        assert app.db.calls == [
            ("new", {"start_date": "2026-07-01", "end_date": "2026-07-31", "limit": 3000}),
            ("renew", {"start_date": "2026-07-01", "end_date": "2026-07-31", "limit": 3000}),
        ]
        summary = app.audit_summary_var.get()
        assert "New Loans: 2" in summary
        assert "Total Principal: $8,000.00" in summary
        assert "Renewals: 1" in summary
        assert "Total Released Cash: $2,500.00" in summary
        assert app.selected[-1] == "new"

        app.audit_name_var.set("beta")
        audit.refresh_audit_tab(app)
        root.update_idletasks()
        assert len(app.audit_new_tree.get_children()) == 1
        assert len(app.audit_renew_tree.get_children()) == 0
        only = app.audit_new_tree.item(app.audit_new_tree.get_children()[0], "values")
        assert only[1] == "Client Beta"

        app.audit_name_var.set("missing")
        audit.refresh_audit_tab(app)
        root.update_idletasks()
        assert not app.audit_new_tree.get_children()
        assert not app.audit_renew_tree.get_children()
        assert app.detail_messages[-1] == "No audit rows found for the current filters."

        print("Wave 54 Audit real Tkinter smoke test passed.")
    finally:
        try:
            root.update_idletasks()
        except Exception:
            pass
        root.destroy()


if __name__ == "__main__":
    main()
