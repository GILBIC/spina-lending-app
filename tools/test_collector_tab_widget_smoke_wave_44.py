from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import collector_tab_presentation as presentation


COLORS = {
    "bg": "#f7f4f5",
    "panel": "#ffffff",
    "card": "#ffffff",
    "card2": "#f1ecef",
    "border": "#d8cdd3",
    "fg": "#241f22",
    "muted": "#6f6269",
    "soft": "#eadde3",
    "blue": "#4776d0",
    "green": "#338a5b",
    "orange": "#b56a21",
    "purple": "#7952a8",
    "red": "#b44343",
}


def _route_colors(_self):
    return COLORS


def _route_button(parent, text, command=None, kind="soft"):
    del kind
    return tk.Button(parent, text=text, command=command)


def _route_card(parent, title, value="—", subtitle="", accent=None):
    frame = tk.Frame(parent, bg=COLORS["card"])
    if accent:
        tk.Frame(frame, bg=accent, height=2).pack(fill="x")
    tk.Label(frame, text=title, bg=COLORS["card"]).pack(fill="x")
    value_label = tk.Label(frame, text=value, bg=COLORS["card"])
    value_label.pack(fill="x")
    subtitle_label = tk.Label(frame, text=subtitle, bg=COLORS["card"])
    subtitle_label.pack(fill="x")
    return frame, value_label, subtitle_label


def _style_route_trees(_self):
    style = ttk.Style()
    style.configure("ModernRoute.Treeview", rowheight=24)


def _hidden_widgets(self, parent):
    self._collector_route_hidden_panel = tk.Frame(parent, bg=COLORS["panel"])
    self.collector_route_selected_name_var = tk.StringVar(value="")
    self.collector_route_edit_name_var = tk.StringVar(value="")


def _update_cards(self):
    children = self.collectors_tree.get_children() if hasattr(self, "collectors_tree") else ()
    values = {
        "routes": str(len(children)),
        "unassigned": "0",
        "noarea": "0",
        "issues": "0",
    }
    for key, value in values.items():
        label, _subtitle = self._collector_route_cards[key]
        label.configure(text=value)


class FakeCollectorApp:
    def __init__(self, root):
        self.tab_collectors = tk.Frame(root)
        self.tab_collectors.pack(fill="both", expand=True)
        self.refresh_calls = 0
        self.actions = []

    def _record(self, action):
        self.actions.append(action)

    def print_collector_route_daily_ledger(self):
        self._record("print")

    def _edit_selected_collector(self):
        self._record("edit")

    def _add_collector(self):
        self._record("add")

    def _clear_collectors_search_filters(self):
        self.collector_route_search_var.set("")
        self.collector_route_filter_main_var.set("(All)")
        self._record("clear")

    def _show_unassigned_areas(self):
        self._record("unassigned")

    def _show_no_area_clients(self):
        self._record("no-area")

    def _show_conflicts(self):
        self._record("conflicts")

    def _delete_selected_collector(self):
        self._record("delete")

    def _collectors_name_from_values(self, values):
        return str(values[1]) if len(values) > 1 else ""

    def _schedule_collectors_refresh(self):
        self.refresh_collectors()

    def refresh_collectors(self):
        self.refresh_calls += 1
        tree = getattr(self, "collectors_tree", None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        tree.insert(
            "",
            "end",
            values=("", "Collector One", "2", "10", "Area A", "", "Ready", "Edit"),
        )


def main() -> None:
    errors = []
    logged = []
    root = tk.Tk()
    root.withdraw()
    try:
        logged_callback = lambda context, exc: logged.append((context, str(exc)))
        dependencies = {
            '_spina_v27_route_colors': _route_colors,
            '_spina_v27_route_button': _route_button,
            '_spina_v27_route_card': _route_card,
            '_spina_v27_style_route_trees': _style_route_trees,
            '_spina_v27_hidden_collector_widgets': _hidden_widgets,
            '_spina_v27_update_route_cards': _update_cards,
            '_log_exc': logged_callback,
        }
        presentation.configure_collector_tab_dependencies(dependencies)
        assert presentation._COLLECTOR_TAB_DEPENDENCIES == dependencies
        for name, value in dependencies.items():
            assert getattr(presentation, name) is value
        presentation.messagebox.showerror = lambda title, message: errors.append((title, message))

        app = FakeCollectorApp(root)
        presentation._spina_v27_build_collectors_tab(app)
        root.update_idletasks()
        root.update()

        assert not errors, errors
        assert not logged, logged
        assert app.refresh_calls >= 1
        assert app.collectors_tree.winfo_exists()
        assert tuple(app.collectors_tree["columns"]) == (
            "sel",
            "collector",
            "areas_count",
            "clients",
            "main_area",
            "sub_area",
            "details",
            "actions",
        )
        assert tuple(app.collectors_tree["displaycolumns"]) == (
            "collector",
            "areas_count",
            "clients",
            "main_area",
            "details",
            "actions",
        )
        assert len(app.collectors_tree.get_children()) == 1
        assert set(app._collector_route_cards) == {"routes", "unassigned", "noarea", "issues"}
        assert set(app._route_health_labels) == {"unassigned", "noarea", "unknown", "conflict"}
        assert app._collector_route_hidden_panel.winfo_exists()

        item = app.collectors_tree.get_children()[0]
        app.collectors_tree.selection_set(item)
        app.collectors_tree.focus(item)
        app.collectors_tree.event_generate("<<TreeviewSelect>>")
        root.update()
        assert app._selected_collector_name == "Collector One"

        refresh_before_search = app.refresh_calls
        app.collector_route_search_var.set("Collector")
        root.update()
        assert app.refresh_calls > refresh_before_search

        assert app._collector_route_cards["routes"][0].cget("text") == "1"
        print("Wave 44 collector-tab Tkinter widget smoke test passed.")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
