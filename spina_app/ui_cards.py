"""Display-only Tkinter card constructors extracted from SPINA."""

from __future__ import annotations

import tkinter as tk

from spina_app.theme_palettes import (
    _spina_v17_dash_colors,
    _spina_v21_cash_colors,
    _spina_v24_cilog_colors,
    _spina_v25_collector_colors as _spina_v27_route_colors,
)


def _spina_v21_cash_card(parent, title, value="—", subtitle="", accent=None):
    c = _spina_v21_cash_colors()
    frame = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    if accent:
        tk.Frame(frame, bg=accent, height=4).pack(fill="x", side="top")
    tk.Label(frame, text=title, bg=c["card"], fg=c["muted"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    value_lbl = tk.Label(frame, text=value, bg=c["card"], fg=c["fg"], font=("Segoe UI", 17, "bold"), anchor="w")
    value_lbl.pack(fill="x", padx=14, pady=(4, 0))
    sub_lbl = tk.Label(frame, text=subtitle, bg=c["card"], fg=c["muted"], font=("Segoe UI", 8), anchor="w", justify="left")
    sub_lbl.pack(fill="x", padx=14, pady=(2, 10))
    return frame, value_lbl, sub_lbl


def _spina_v24_cilog_card(parent, title, value="—", subtitle="", accent=None):
    c = _spina_v24_cilog_colors()
    frame = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    if accent:
        tk.Frame(frame, bg=accent, height=4).pack(fill="x", side="top")
    tk.Label(frame, text=title, bg=c["card"], fg=c["muted"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    value_lbl = tk.Label(frame, text=value, bg=c["card"], fg=c["fg"], font=("Segoe UI", 16, "bold"), anchor="w")
    value_lbl.pack(fill="x", padx=14, pady=(4, 0))
    sub_lbl = tk.Label(frame, text=subtitle, bg=c["card"], fg=c["muted"], font=("Segoe UI", 8), anchor="w")
    sub_lbl.pack(fill="x", padx=14, pady=(2, 10))
    return frame, value_lbl, sub_lbl


def _spina_v27_route_card(parent, title, value="—", subtitle="", accent=None):
    c = _spina_v27_route_colors()
    frame = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    if accent:
        tk.Frame(frame, bg=accent, height=4).pack(fill="x", side="top")
    tk.Label(frame, text=title, bg=c["card"], fg=c["muted"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    value_lbl = tk.Label(frame, text=value, bg=c["card"], fg=c["fg"], font=("Segoe UI", 17, "bold"), anchor="w")
    value_lbl.pack(fill="x", padx=14, pady=(4, 0))
    sub_lbl = tk.Label(frame, text=subtitle, bg=c["card"], fg=c["muted"], font=("Segoe UI", 8), anchor="w")
    sub_lbl.pack(fill="x", padx=14, pady=(2, 10))
    return frame, value_lbl, sub_lbl
