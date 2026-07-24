"""Collectors summary presentation helpers extracted from the SPINA desktop entry module.

Collector records, route assignment, database access, printing, notes, and calculations remain
owned by the desktop application. This module owns only summary-card construction, Treeview
styling, and display-card refresh behavior.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from spina_app.theme_palettes import _spina_v25_collector_colors
from spina_app.utilities.numbers import _spina_v25_parse_count_from_var

def _spina_v25_collector_card(parent, title, value="—", subtitle="", accent=None):
    c = _spina_v25_collector_colors()
    frame = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    if accent:
        tk.Frame(frame, bg=accent, height=4).pack(fill="x", side="top")
    tk.Label(frame, text=title, bg=c["card"], fg=c["muted"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    value_lbl = tk.Label(frame, text=value, bg=c["card"], fg=c["fg"], font=("Segoe UI", 16, "bold"), anchor="w")
    value_lbl.pack(fill="x", padx=14, pady=(4, 0))
    sub_lbl = tk.Label(frame, text=subtitle, bg=c["card"], fg=c["muted"], font=("Segoe UI", 8), anchor="w")
    sub_lbl.pack(fill="x", padx=14, pady=(2, 10))
    return frame, value_lbl, sub_lbl


def _spina_v25_style_collector_trees(self):
    try:
        c = _spina_v25_collector_colors(self)
        st = ttk.Style()
        st.configure(
            "ModernCollector.Treeview",
            rowheight=32,
            font=("Segoe UI", 10),
            background=c["panel"],
            fieldbackground=c["panel"],
            foreground=c["fg"],
            borderwidth=0,
        )
        st.configure(
            "ModernCollector.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=c["card2"],
            foreground=c["fg"],
            relief="flat",
        )
        st.map("ModernCollector.Treeview", background=[("selected", c["blue"])])
    except Exception:
        pass


def _spina_v25_update_collector_cards(self):
    try:
        cards = getattr(self, "_collector_route_cards", {}) or {}
        tree = getattr(self, "collectors_tree", None)
        shown = 0
        try:
            shown = len(tree.get_children()) if tree is not None else 0
        except Exception:
            shown = 0

        unassigned = _spina_v25_parse_count_from_var(getattr(self, "collector_route_unassigned_var", tk.StringVar(value="0")).get())
        noarea = _spina_v25_parse_count_from_var(getattr(self, "collector_route_noarea_var", tk.StringVar(value="0")).get())
        unknown = _spina_v25_parse_count_from_var(getattr(self, "collector_route_unknown_var", tk.StringVar(value="0")).get())
        conflicts = _spina_v25_parse_count_from_var(getattr(self, "collector_route_conflict_var", tk.StringVar(value="0")).get())

        selected = str(getattr(self, "_selected_collector_name", "") or "").strip()
        view_sub = "Current filtered list"
        try:
            q = str(getattr(self, "collector_route_search_var", tk.StringVar(value="")).get() or "").strip()
            main_filter = str(getattr(self, "collector_route_filter_main_var", tk.StringVar(value="(All)")).get() or "(All)")
            filters = []
            if q:
                filters.append("search")
            if main_filter and main_filter != "(All)":
                filters.append(main_filter)
            if bool(getattr(self, "collector_route_filter_conflicts_var", tk.BooleanVar(value=False)).get()):
                filters.append("conflicts")
            if bool(getattr(self, "collector_route_filter_unknown_var", tk.BooleanVar(value=False)).get()):
                filters.append("unknown")
            if filters:
                view_sub = "Filter: " + ", ".join(filters[:3])
        except Exception:
            pass

        data = {
            "routes": (str(shown), view_sub),
            "unassigned": (str(unassigned), "Active areas not routed"),
            "noarea": (str(noarea), "Active clients needing area"),
            "issues": (str(int(unknown) + int(conflicts)), f"Unknown {unknown} • Conflict {conflicts}"),
            "selected": (selected or "—", "Selected collector"),
        }

        for key, (value, sub) in data.items():
            try:
                val, sublbl = cards.get(key, (None, None))
                if val is not None:
                    val.configure(text=value)
                if sublbl is not None:
                    sublbl.configure(text=sub)
            except Exception:
                pass
    except Exception:
        pass
