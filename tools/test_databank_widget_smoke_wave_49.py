from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import databank_presentation as databank


def widget_texts(widget):
    found = []
    for child in widget.winfo_children():
        try:
            text = child.cget("text")
        except Exception:
            text = ""
        if text:
            found.append(str(text))
        found.extend(widget_texts(child))
    return found


class DummyApp:
    def __init__(self, root):
        self.root = root
        self.tab_data = ttk.Frame(root)
        self.tab_data.pack(fill="both", expand=True)
        self.ui_theme = "light"
        self._ui_colors = {
            "bg": "#f6f7fb",
            "panel": "#ffffff",
            "fg": "#17181c",
            "muted": "#6b7280",
            "accent": "#ffd1e6",
            "border": "#e5e7eb",
            "button_active": "#f3f4f6",
        }
        self.refresh_count = 0
        self.toolbar_count = 0

    def _theme_palette(self):
        return dict(self._ui_colors)

    def _month_label(self):
        return "July 2026"

    def _mode_filter(self):
        return "Regular"

    def prev_month(self):
        pass

    def goto_current_month(self):
        pass

    def next_month(self):
        pass

    def open_databank_close_dialog(self):
        pass

    def open_delete_day_dialog(self):
        pass

    def open_databank_close_records_dialog(self):
        pass

    def refresh_data_grid(self):
        self.refresh_count += 1
        if getattr(self, "name_tree", None) is not None:
            return
        self.name_tree = ttk.Treeview(
            self.inner,
            columns=("client", "area"),
            show="headings",
            height=5,
        )
        self.name_tree.heading("client", text="Client")
        self.name_tree.heading("area", text="Area")
        self.name_tree.column("client", width=150)
        self.name_tree.column("area", width=100)
        self.name_tree.insert("", "end", values=("Client A", "Area 1"))
        self.name_tree.pack(fill="x")

        self.days_tree = ttk.Treeview(
            self.inner,
            columns=("d1", "d2"),
            show="headings",
            height=5,
        )
        self.days_tree.heading("d1", text="1")
        self.days_tree.heading("d2", text="2")
        self.days_tree.column("d1", width=40)
        self.days_tree.column("d2", width=40)
        self.days_tree.pack(fill="both", expand=True)

    def _update_data_toolbar(self):
        self.toolbar_count += 1


def main() -> None:
    root = tk.Tk()
    try:
        root.geometry("1200x760+20+20")
        app = DummyApp(root)

        databank._spina_v15_build_data_tab(app)
        root.update_idletasks()

        texts = widget_texts(app.tab_data)
        for expected in (
            "Data Bank",
            "Payment Grid",
            "Daily Close / View",
            "Delete Day",
            "Close Records",
            "CLIENTS",
            "CURRENT VIEW",
            "MONTH",
            "DAY CLOSE STATUS",
        ):
            assert expected in texts, (expected, texts)

        assert app.refresh_count >= 1
        assert app.toolbar_count == 1
        assert app._db_card_clients_var.get() == "1 client"
        assert app._db_card_view_var.get() == "Regular"
        assert app._db_card_month_var.get() == "July 2026"
        assert app._db_card_close_var.get() == "Select a payment day"
        assert app.db_search_entry.winfo_exists()

        before = app.refresh_count
        app.search_db_var.set("Client A")
        root.update_idletasks()
        assert app.refresh_count > before

        databank._spina_v16_apply_bigger_payment_grid(app)
        root.update_idletasks()
        assert int(app.name_tree.cget("height")) == 31
        assert int(app.days_tree.cget("height")) == 31
        assert int(app.name_tree.column("client", "width")) == 330
        assert int(app.name_tree.column("area", "width")) == 185
        assert int(app.days_tree.column("d1", "width")) == 86
        assert int(app.days_tree.column("d2", "width")) == 86

        app._db_close_info_var.set("Closed")
        databank._spina_v15_update_databank_cards(app)
        assert app._db_card_close_var.get() == "Closed"

        app.ui_theme = "dark"
        app._ui_colors = {
            "bg": "#111217",
            "panel": "#181a20",
            "fg": "#ffffff",
            "muted": "#a9a9b3",
            "accent": "#ffd1e6",
            "border": "#30323a",
            "button_active": "#2a2d36",
        }
        databank._spina_v15_setup_databank_styles(app)
        root.update_idletasks()
        style = ttk.Style()
        assert style.lookup("DataBank.Treeview", "background")
        assert style.lookup("DataBank.Treeview", "foreground")

        print("Wave 49 Data Bank Tkinter smoke test passed.")
    finally:
        try:
            root.update_idletasks()
        except Exception:
            pass
        root.destroy()


if __name__ == "__main__":
    main()
