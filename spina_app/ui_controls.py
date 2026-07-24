"""Small Tkinter form and Treeview helpers extracted from SPINA."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from spina_app.theme_palettes import (
    _spina_v17_dash_colors,
    _spina_v21_cash_colors,
    _spina_v22_reports_colors as _spina_v23_clients_colors,
    _spina_v24_cilog_colors,
    _spina_v25_collector_colors as _spina_v27_route_colors,
)


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


def _spina_v24_cilog_button(parent, text, command=None, kind="normal", width=None):
    c = _spina_v24_cilog_colors()
    bg = c["card2"]
    fg = c["fg"]
    if kind == "primary":
        bg, fg = c["blue"], "#ffffff"
    elif kind == "success":
        bg, fg = c["green"], "#ffffff"
    elif kind == "danger":
        bg, fg = c["red"], "#ffffff"
    elif kind == "soft":
        bg, fg = c["soft"], c["fg"]

    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=bg,
        activeforeground=fg,
        relief="flat",
        bd=0,
        padx=14,
        pady=8,
        font=("Segoe UI", 9, "bold"),
        cursor="hand2",
        width=width,
    )


def _spina_v24_cilog_style_tree(self):
    try:
        c = _spina_v24_cilog_colors(self)
        st = ttk.Style()
        st.configure(
            "ModernCILog.Treeview",
            rowheight=31,
            font=("Segoe UI", 10),
            background=c["panel"],
            fieldbackground=c["panel"],
            foreground=c["fg"],
            borderwidth=0,
        )
        st.configure(
            "ModernCILog.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=c["card2"],
            foreground=c["fg"],
            relief="flat",
        )
        st.map("ModernCILog.Treeview", background=[("selected", c["blue"])])
    except Exception:
        pass


def _spina_v23_style_clients_tree(self):
    try:
        c = _spina_v23_clients_colors(self)
        st = ttk.Style()
        st.configure(
            "ModernClients.Treeview",
            rowheight=32,
            font=("Segoe UI", 10),
            background=c["panel"],
            fieldbackground=c["panel"],
            foreground=c["fg"],
            borderwidth=0,
        )
        st.configure(
            "ModernClients.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=c["card2"],
            foreground=c["fg"],
            relief="flat",
        )
        st.map("ModernClients.Treeview", background=[("selected", c["blue"])])
    except Exception:
        pass


def _spina_v27_style_route_trees(self):
    try:
        c = _spina_v27_route_colors(self)
        st = ttk.Style()
        st.configure(
            "ModernRoute.Treeview",
            rowheight=32,
            font=("Segoe UI", 10),
            background=c["panel"],
            fieldbackground=c["panel"],
            foreground=c["fg"],
            borderwidth=0,
        )
        st.configure(
            "ModernRoute.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=c["card2"],
            foreground=c["fg"],
            relief="flat",
        )
        st.map("ModernRoute.Treeview", background=[("selected", c["blue"])])
    except Exception:
        pass


def _spina_v17_update_filter_buttons(self):
    try:
        colors = _spina_v17_dash_colors(self)
        cur = str(getattr(self, "dashboard_loan_filter_var", tk.StringVar(value="All")).get() or "All")
        for key, btn in (getattr(self, "_dash_filter_buttons", {}) or {}).items():
            if key == cur:
                btn.configure(bg=colors["accent"], fg="#ffffff", activebackground=colors["accent"], activeforeground="#ffffff")
            else:
                btn.configure(bg=colors["card2"], fg=colors["fg"], activebackground=colors["soft"], activeforeground=colors["fg"])
    except Exception:
        pass


def _spina_v17_style_dashboard_table(self):
    try:
        st = ttk.Style()
        family = "Segoe UI"
        colors = _spina_v17_dash_colors(self)
        st.configure(
            "ModernDash.Treeview",
            rowheight=30,
            font=(family, 10),
            background=colors["panel"],
            fieldbackground=colors["panel"],
            foreground=colors["fg"],
            borderwidth=0,
        )
        st.configure(
            "ModernDash.Treeview.Heading",
            font=(family, 10, "bold"),
            background=colors["card2"],
            foreground=colors["fg"],
            relief="flat",
        )
        st.map("ModernDash.Treeview", background=[("selected", colors["accent"])])
    except Exception:
        pass
