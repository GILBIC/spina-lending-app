"""Data Bank export actions extracted in SPINA Wave 82."""
from __future__ import annotations

import calendar
import json
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

_DEPENDENCIES: dict[str, Any] = {}
_PROTECTED = {"__name__", "__file__", "__package__", "__builtins__", "_DEPENDENCIES", "_PROTECTED", "configure_data_bank_export_dependencies"}


def configure_data_bank_export_dependencies(namespace: Mapping[str, Any]) -> None:
    _DEPENDENCIES.clear()
    _DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED:
            globals()[name] = value

def export_range_template(self):
    """Export an Excel template for payments over a chosen date range.
    Presets: This Month / This Year / Custom (YYYY-MM-DD)."""
    import datetime as _dt
    import calendar as _cal
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    try:
        from openpyxl import Workbook
    except Exception:
        messagebox.showwarning("Missing", "Install openpyxl to export the Excel template.")
        return

    # --- Preset dialog ---
    dlg = tk.Toplevel(self.root)
    dlg.title("Choose Export Range")
    dlg.transient(self.root)
    dlg.grab_set()
    dlg.resizable(False, False)

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)

    preset = tk.StringVar(value="month")  # 'month' | 'year' | 'custom'
    ttk.Label(frm, text="Preset:").grid(row=0, column=0, sticky="w")
    ttk.Radiobutton(frm, text="This Month", variable=preset, value="month").grid(row=0, column=1, sticky="w")
    ttk.Radiobutton(frm, text="This Year",  variable=preset, value="year").grid(row=0, column=2, sticky="w")
    ttk.Radiobutton(frm, text="Custom",     variable=preset, value="custom").grid(row=0, column=3, sticky="w")

    # Custom date inputs (StringVars survive after the dialog closes)
    sv_start = tk.StringVar()
    sv_end   = tk.StringVar()

    row1 = 1
    ttk.Label(frm, text="Start (YYYY-MM-DD):").grid(row=row1, column=0, sticky="e", pady=(8,0))
    e1 = ttk.Entry(frm, textvariable=sv_start, width=16); e1.grid(row=row1, column=1, sticky="w", pady=(8,0))
    ttk.Label(frm, text="End (YYYY-MM-DD):").grid(row=row1, column=2, sticky="e", pady=(8,0))
    e2 = ttk.Entry(frm, textvariable=sv_end, width=16);   e2.grid(row=row1, column=3, sticky="w", pady=(8,0))

    def _today_parts():
        t = _dt.date.today()
        return t.year, t.month, t.day

    def _apply_preset_fields(*_):
        y, m, _d = _today_parts()
        if preset.get() == "month":
            first = _dt.date(y, m, 1)
            import calendar as _cal2
            last  = _dt.date(y, m, _cal2.monthrange(y, m)[1])
            sv_start.set(first.strftime("%Y-%m-%d"))
            sv_end.set(last.strftime("%Y-%m-%d"))
            e1.configure(state="disabled"); e2.configure(state="disabled")
        elif preset.get() == "year":
            first = _dt.date(y, 1, 1)
            last  = _dt.date(y, 12, 31)
            sv_start.set(first.strftime("%Y-%m-%d"))
            sv_end.set(last.strftime("%Y-%m-%d"))
            e1.configure(state="disabled"); e2.configure(state="disabled")
        else:
            # custom
            e1.configure(state="normal"); e2.configure(state="normal")
            if not sv_start.get(): sv_start.set(_dt.date.today().strftime("%Y-%m-%d"))
            if not sv_end.get():   sv_end.set(_dt.date.today().strftime("%Y-%m-%d"))

    preset.trace_add("write", _apply_preset_fields)
    _apply_preset_fields()

    btns = ttk.Frame(frm); btns.grid(row=row1+1, column=0, columnspan=4, sticky="e", pady=(12,0))
    result = {"start": None, "end": None}

    def on_ok():
        s0 = sv_start.get().strip()
        s1 = sv_end.get().strip()
        # Basic validation
        try:
            ds = _dt.datetime.strptime(s0, "%Y-%m-%d").date()
            de = _dt.datetime.strptime(s1, "%Y-%m-%d").date()
        except Exception:
            messagebox.showwarning("Invalid date", "Use YYYY-MM-DD (e.g., 2025-10-15).")
            return
        if ds > de:
            ds, de = de, ds
        result["start"] = ds
        result["end"] = de
        dlg.destroy()

    def on_cancel():
        dlg.destroy()

    ttk.Button(btns, text="Cancel", command=on_cancel).pack(side="right", padx=6)
    ttk.Button(btns, text="OK", command=on_ok).pack(side="right")

    dlg.bind("<Return>", lambda e: on_ok())
    dlg.bind("<Escape>", lambda e: on_cancel())
    dlg.wait_window()

    # If cancelled
    if not result["start"] or not result["end"]:
        return

    ds, de = result["start"], result["end"]

    # Build the date list for headers (inclusive)
    days = []
    cur = ds
    while cur <= de:
        days.append(cur.strftime("%Y-%m-%d"))
        cur += _dt.timedelta(days=1)

    # Build workbook
    from openpyxl import Workbook as _WB
    wb = _WB()
    ws = wb.active
    ws.title = f"{ds.strftime('%Y-%m-%d')}..{de.strftime('%Y-%m-%d')}"

    headers = ["Client Name"] + days
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c, value=h)

    # Client names (fallbacks to existing search if present)
    term = ""
    try:
        search_term = getattr(self, "search_db_var", None)
        term = search_term.get().strip() if search_term else ""
    except Exception:
        term = ""

    try:
        clients = self.db.get_all_clients(search=term if term else None, loan_type=self._mode_filter(), search_by='all')
    except Exception:
        # Fallback to other likely method names in user project
        try:
            clients = self.db.fetch_all_clients(loan_type=self._mode_filter())
        except Exception:
            clients = []

    row = 2
    for item in clients:
        nm = item.get('name') if isinstance(item, dict) else str(item)
        ws.cell(row=row, column=1, value=nm)
        row += 1

    # Ask save path with auto filename: Export_<start>_to_<end>.xlsx
    default_name = f"Export_{ds.strftime('%Y-%m-%d')}_to_{de.strftime('%Y-%m-%d')}.xlsx"
    try:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Save Excel Template",
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")]
        )
    except Exception:
        path = default_name  # headless fallback

    if not path:
        return

    try:
        wb.save(path)
    except Exception as e:
        try:
            from tkinter import messagebox as _mb
            _mb.showerror("Save Error", str(e))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0581', 'suppressed exception excpass_0581', __spina_exc)
            pass
        return

    try:
        from tkinter import messagebox as _mb2
        _mb2.showinfo(
            "Template Saved",
            f"Excel template saved to:\n{path}\n\nFill payments and use 'Import from Excel' to load."
        )
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0582', 'suppressed exception excpass_0582', __spina_exc)
        pass
