"""Small Tkinter form and Treeview helpers extracted from SPINA."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from spina_app.theme_palettes import _spina_v21_cash_colors


def _spina_v21_build_labeled_entry(parent, label, var, width=14):
    c = _spina_v21_cash_colors()
    box = tk.Frame(parent, bg=c["panel"])
    tk.Label(box, text=label, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
    ent = ttk.Entry(box, textvariable=var, width=width)
    ent.pack(fill="x", pady=(3, 0))
    return box, ent


def _spina_v21_style_cash_table(self):
    try:
        colors = _spina_v21_cash_colors(self)
        st = ttk.Style()
        st.configure(
            "ModernCash.Treeview",
            rowheight=30,
            font=("Segoe UI", 10),
            background=colors["panel"],
            fieldbackground=colors["panel"],
            foreground=colors["fg"],
            borderwidth=0,
        )
        st.configure(
            "ModernCash.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=colors["card2"],
            foreground=colors["fg"],
            relief="flat",
        )
        st.map("ModernCash.Treeview", background=[("selected", colors["button"])])
    except Exception:
        pass
