"""Collector Route presentation helpers extracted from the SPINA desktop entry module.

Collector records, route assignments, PostgreSQL access, printing, notes, closing, and all
payment or balance calculations remain owned by the desktop application. This module owns only
route summary-card refresh and hidden compatibility widget construction.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Mapping

from spina_app.utilities.numbers import _spina_v27_count_from_text

_REQUIRED_DEPENDENCIES = ("_spina_v27_route_colors",)


def configure_collector_route_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind the desktop-owned Collector Route palette helper."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)

def _spina_v27_update_route_cards(self):
    try:
        c = _spina_v27_route_colors(self)
        cards = getattr(self, "_collector_route_cards", {}) or {}
        tree = getattr(self, "collectors_tree", None)
        shown = 0
        try:
            shown = len(tree.get_children()) if tree is not None else 0
        except Exception:
            shown = 0

        unassigned = _spina_v27_count_from_text(getattr(self, "collector_route_unassigned_var", tk.StringVar(value="0")).get())
        noarea = _spina_v27_count_from_text(getattr(self, "collector_route_noarea_var", tk.StringVar(value="0")).get())
        unknown = _spina_v27_count_from_text(getattr(self, "collector_route_unknown_var", tk.StringVar(value="0")).get())
        conflicts = _spina_v27_count_from_text(getattr(self, "collector_route_conflict_var", tk.StringVar(value="0")).get())

        vals = {
            "routes": (str(shown), "Collectors shown"),
            "unassigned": (str(unassigned), "Active areas not assigned"),
            "noarea": (str(noarea), "Active clients with blank area"),
            "issues": (str(unknown + conflicts), f"Unknown {unknown} • Conflict {conflicts}"),
        }
        for key, (value, sub) in vals.items():
            try:
                val, sublbl = cards.get(key, (None, None))
                if val is not None:
                    val.configure(text=value)
                if sublbl is not None:
                    sublbl.configure(text=sub)
            except Exception:
                pass

        # Route health checklist
        try:
            health = getattr(self, "_route_health_labels", {}) or {}
            items = {
                "unassigned": ("All active areas are assigned", unassigned == 0, f"{unassigned} active area(s) are not assigned"),
                "noarea": ("All active clients have area", noarea == 0, f"{noarea} active client(s) have no area"),
                "unknown": ("No unknown route areas", unknown == 0, f"{unknown} unknown route area(s)"),
                "conflict": ("No duplicate area assignment", conflicts == 0, f"{conflicts} conflict area(s)"),
            }
            for key, (good_text, good, bad_text) in items.items():
                lbl = health.get(key)
                if lbl is not None:
                    lbl.configure(
                        text=("✓ " + good_text) if good else ("⚠ " + bad_text),
                        fg=c["green"] if good else c["orange"],
                    )
        except Exception:
            pass

        try:
            if hasattr(self, "collector_route_table_status_var"):
                self.collector_route_table_status_var.set(f"{shown} collector route(s) shown. Double-click a route to edit.")
        except Exception:
            pass
    except Exception:
        pass


def _spina_v27_hidden_collector_widgets(self, parent):
    """Keep hidden compatibility widgets for legacy helper functions."""
    c = _spina_v27_route_colors(self)
    self._collector_route_hidden_panel = tk.Frame(parent, bg=c["panel"])

    self.collector_route_selected_name_var = tk.StringVar(value="")
    self.collector_route_edit_name_var = tk.StringVar(value="")
    self.collector_route_selected_stats_var = tk.StringVar(value="")
    self.collector_route_selected_name_lbl = tk.Label(self._collector_route_hidden_panel, textvariable=self.collector_route_selected_name_var, bg=c["panel"], fg=c["fg"])
    self.collector_route_selected_name_ent = ttk.Entry(self._collector_route_hidden_panel, textvariable=self.collector_route_edit_name_var, width=28)

    self.collector_route_btn_edit = tk.Button(self._collector_route_hidden_panel, text="Edit")
    self.collector_route_btn_save = tk.Button(self._collector_route_hidden_panel, text="Save")
    self.collector_route_btn_cancel = tk.Button(self._collector_route_hidden_panel, text="Cancel")
    self._collectors_inline_editing = False

    self.collector_route_show_areas_var = tk.BooleanVar(value=True)
    self.collector_route_show_notes_var = tk.BooleanVar(value=True)

    self.collector_route_areas_box = tk.Frame(self._collector_route_hidden_panel, bg=c["panel"])
    self.collector_route_area_tree = ttk.Treeview(
        self.collector_route_areas_box,
        columns=("clients",),
        show="tree headings",
        selectmode="browse",
        height=1,
        style="ModernRoute.Treeview",
    )
    self.collector_route_area_tree.heading("#0", text="Main / Sub Area")
    self.collector_route_area_tree.heading("clients", text="Clients")

    self.collector_route_areas_edit_frm = tk.Frame(self.collector_route_areas_box, bg=c["panel"])
    self.collector_route_areas_lb = tk.Listbox(self.collector_route_areas_edit_frm, height=1)
    self.collector_route_area_add_var = tk.StringVar(value="")
    self.collector_route_notes_box = tk.Frame(self._collector_route_hidden_panel, bg=c["panel"])
    self.collector_route_notes_txt = tk.Text(self.collector_route_notes_box, height=1)
    self._areas_drag_index = None
