"""Modern Reports tab presentation extracted from the SPINA desktop entry module.

Business calculations, PDF generation, report totals, database access, and report-log
operations remain owned by the desktop application. This module owns only the modern
Reports tab construction and display refresh helpers.
"""

from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Mapping

from spina_app.theme_palettes import _spina_v22_reports_colors

_REQUIRED_DEPENDENCIES = (
    '_load_ledger_prefs',
    '_save_ledger_prefs',
    '_log_exc',
    'pick_date',
    'pick_date_range',
)


def configure_reports_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind application-owned callbacks used by the Reports presentation module."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)


def _spina_v22_style_reports_tree(self):
    try:
        colors = _spina_v22_reports_colors(self)
        st = ttk.Style()
        st.configure(
            "ModernReports.Treeview",
            rowheight=32,
            font=("Segoe UI", 10),
            background=colors["panel"],
            fieldbackground=colors["panel"],
            foreground=colors["fg"],
            borderwidth=0,
        )
        st.configure(
            "ModernReports.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=colors["card2"],
            foreground=colors["fg"],
            relief="flat",
        )
        st.map("ModernReports.Treeview", background=[("selected", colors["blue"])])
    except Exception:
        pass

def _spina_v22_button(parent, text, command=None, kind="normal", width=None):
    c = _spina_v22_reports_colors()
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

    btn = tk.Button(
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
    return btn

def _spina_v22_report_card(parent, title, value="—", subtitle="", accent=None):
    c = _spina_v22_reports_colors()
    frame = tk.Frame(parent, bg=c["card"], highlightbackground=c["border"], highlightthickness=1, bd=0)
    if accent:
        tk.Frame(frame, bg=accent, height=4).pack(fill="x", side="top")
    tk.Label(frame, text=title, bg=c["card"], fg=c["muted"], font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
    value_lbl = tk.Label(frame, text=value, bg=c["card"], fg=c["fg"], font=("Segoe UI", 16, "bold"), anchor="w")
    value_lbl.pack(fill="x", padx=14, pady=(4, 0))
    sub_lbl = tk.Label(frame, text=subtitle, bg=c["card"], fg=c["muted"], font=("Segoe UI", 8), anchor="w")
    sub_lbl.pack(fill="x", padx=14, pady=(2, 10))
    return frame, value_lbl, sub_lbl

def _spina_v22_build_reports_tab(self):
    try:
        frm = self.tab_reports
        try:
            for w in frm.winfo_children():
                w.destroy()
        except Exception:
            pass

        c = _spina_v22_reports_colors(self)
        _spina_v22_style_reports_tree(self)

        self.search_reports_var = tk.StringVar()
        self.show_archived_reports_var = tk.BooleanVar(value=False)
        self.start_date_var = tk.StringVar(value=date.today().replace(day=1).strftime("%Y-%m-%d"))
        self.end_date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        self.date_range_var = tk.StringVar()
        self.report_summary_var = tk.StringVar(value="0 clients")
        self._reports_stat_labels = {}

        outer = tk.Frame(frm, bg=c["bg"])
        outer.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(outer, bg=c["bg"])
        header.pack(fill="x", padx=18, pady=(16, 10))

        titlebox = tk.Frame(header, bg=c["bg"])
        titlebox.pack(side="left", fill="x", expand=True)
        tk.Label(titlebox, text="Reports", bg=c["bg"], fg=c["fg"], font=("Segoe UI", 20, "bold"), anchor="w").pack(fill="x")
        tk.Label(
            titlebox,
            text="Generate clean client statements with notes, date range, page size, and report history.",
            bg=c["bg"],
            fg=c["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        _spina_v22_button(header, "Generate PDF", command=self.generate_pdf_selected, kind="primary").pack(side="right", padx=(8, 0))
        _spina_v22_button(header, "Report Logs", command=self.open_report_generation_log, kind="soft").pack(side="right", padx=(8, 0))

        # Filter panel
        controls = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        controls.pack(fill="x", padx=18, pady=(0, 12))

        row1 = tk.Frame(controls, bg=c["panel"])
        row1.pack(fill="x", padx=12, pady=(10, 6))

        # Search
        search_box = tk.Frame(row1, bg=c["panel"])
        search_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(search_box, text="Search Client / Area / Contact", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        search_line = tk.Frame(search_box, bg=c["panel"])
        search_line.pack(fill="x", pady=(3, 0))
        ent = ttk.Entry(search_line, textvariable=self.search_reports_var)
        ent.pack(side="left", fill="x", expand=True)
        _spina_v22_button(search_line, "Clear", command=lambda: self.search_reports_var.set(""), kind="soft").pack(side="left", padx=(8, 0))

        try:
            self.search_reports_var.trace_add("write", lambda *_: self.refresh_reports())
        except Exception:
            pass

        # Date range functions
        def _sync_reports_range(*_):
            sd = (self.start_date_var.get() or "").strip()
            ed = (self.end_date_var.get() or "").strip()
            if sd and ed:
                try:
                    from datetime import datetime as _dt
                    dsd = _dt.strptime(sd[:10], "%Y-%m-%d").date()
                    ded = _dt.strptime(ed[:10], "%Y-%m-%d").date()
                    if ded < dsd:
                        self.date_range_var.set(f"{ed} to {sd}")
                    else:
                        self.date_range_var.set(f"{sd} to {ed}")
                except Exception:
                    self.date_range_var.set("Invalid date")
            elif sd:
                self.date_range_var.set(sd)
            elif ed:
                self.date_range_var.set(ed)
            else:
                self.date_range_var.set("All dates")

        def _apply_report_range_from_fields(*_):
            sd = (self.start_date_var.get() or "").strip()
            ed = (self.end_date_var.get() or "").strip()
            try:
                from datetime import datetime as _dt
                ds = _dt.strptime(sd[:10], "%Y-%m-%d").date() if sd else None
                de = _dt.strptime(ed[:10], "%Y-%m-%d").date() if ed else None
            except Exception:
                messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD for Start/End dates.")
                _sync_reports_range()
                return "break"
            if ds and de and de < ds:
                ds, de = de, ds
                self.start_date_var.set(ds.strftime("%Y-%m-%d"))
                self.end_date_var.set(de.strftime("%Y-%m-%d"))
            _sync_reports_range()
            try:
                self.refresh_reports()
            except Exception:
                pass
            return "break"

        def _pick_reports_range():
            pick_date_range(self.root, self.start_date_var, self.end_date_var, title="Select Report Date Range")
            _apply_report_range_from_fields()

        def _clear_reports_range():
            self.start_date_var.set("")
            self.end_date_var.set("")
            _sync_reports_range()
            try:
                self.refresh_reports()
            except Exception:
                pass

        def _set_this_month():
            self.start_date_var.set(date.today().replace(day=1).strftime("%Y-%m-%d"))
            self.end_date_var.set(date.today().strftime("%Y-%m-%d"))
            _apply_report_range_from_fields()

        def _set_today():
            self.start_date_var.set(date.today().strftime("%Y-%m-%d"))
            self.end_date_var.set(date.today().strftime("%Y-%m-%d"))
            _apply_report_range_from_fields()

        try:
            self.start_date_var.trace_add("write", _sync_reports_range)
            self.end_date_var.trace_add("write", _sync_reports_range)
        except Exception:
            pass
        _sync_reports_range()

        row2 = tk.Frame(controls, bg=c["panel"])
        row2.pack(fill="x", padx=12, pady=(0, 10))

        def labeled_entry(parent, label, var, width=12):
            box = tk.Frame(parent, bg=c["panel"])
            tk.Label(box, text=label, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
            e = ttk.Entry(box, textvariable=var, width=width)
            e.pack(fill="x", pady=(3, 0))
            try:
                e.bind("<Return>", _apply_report_range_from_fields)
                e.bind("<FocusOut>", _apply_report_range_from_fields)
            except Exception:
                pass
            return box

        labeled_entry(row2, "Start Date", self.start_date_var, 12).pack(side="left", padx=(0, 8))
        labeled_entry(row2, "End Date", self.end_date_var, 12).pack(side="left", padx=(0, 8))

        _spina_v22_button(row2, "Calendar", command=_pick_reports_range, kind="soft").pack(side="left", padx=(0, 8), pady=(12, 0))
        _spina_v22_button(row2, "This Month", command=_set_this_month, kind="soft").pack(side="left", padx=(0, 8), pady=(12, 0))
        _spina_v22_button(row2, "Today", command=_set_today, kind="soft").pack(side="left", padx=(0, 8), pady=(12, 0))
        _spina_v22_button(row2, "Clear Range", command=_clear_reports_range, kind="soft").pack(side="left", padx=(0, 14), pady=(12, 0))

        # Page size
        page_box = tk.Frame(row2, bg=c["panel"])
        page_box.pack(side="left", padx=(0, 8))
        tk.Label(page_box, text="Page Size", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        try:
            _prefs = _load_ledger_prefs()
        except Exception:
            _prefs = {}
        _ps_values = ["A4", "Letter 8.5 x 11", "Folio 8.5 x 13", "Legal 8.5 x 14"]
        _default_ps = (_prefs.get("reports_page_size") or "A4")
        if _default_ps not in _ps_values:
            _default_ps = "A4"
        self.report_page_size_var = tk.StringVar(value=_default_ps)
        _ps_cb = ttk.Combobox(page_box, textvariable=self.report_page_size_var, values=_ps_values, width=16, state="readonly")
        _ps_cb.pack(fill="x", pady=(3, 0))

        def _save_reports_page_size(*_):
            try:
                p = _load_ledger_prefs()
                p["reports_page_size"] = (self.report_page_size_var.get() or "A4")
                _save_ledger_prefs(p)
            except Exception:
                pass

        try:
            self.report_page_size_var.trace_add("write", lambda *_: _save_reports_page_size())
        except Exception:
            try:
                _ps_cb.bind("<<ComboboxSelected>>", lambda e: _save_reports_page_size())
            except Exception:
                pass

        self.report_notes_btn = _spina_v22_button(row2, "Notes", kind="soft")
        self.report_notes_btn.pack(side="left", padx=(0, 8), pady=(12, 0))

        # show archived
        arch_box = tk.Frame(row2, bg=c["panel"])
        arch_box.pack(side="left", padx=(0, 8), pady=(12, 0))
        ttk.Checkbutton(arch_box, text="Show Archived", variable=self.show_archived_reports_var, command=self.refresh_reports).pack(side="left")

        # Current range pill
        range_pill = tk.Frame(row2, bg=c["card2"], highlightbackground=c["border"], highlightthickness=1)
        range_pill.pack(side="right", padx=(10, 0), pady=(12, 0))
        tk.Label(range_pill, textvariable=self.date_range_var, bg=c["card2"], fg=c["fg"], font=("Segoe UI", 9, "bold"), padx=12, pady=7).pack()

        # Summary cards
        cards = tk.Frame(outer, bg=c["bg"])
        cards.pack(fill="x", padx=18, pady=(0, 12))
        for i in range(4):
            cards.columnconfigure(i, weight=1, uniform="reportcard")

        for i, (key, title, value, sub, accent) in enumerate([
            ("clients", "Clients Listed", "0", "Current view", c["blue"]),
            ("view", "Loan View", "Regular", "Regular / 7x7 switch", c["purple"]),
            ("range", "Report Range", "This Month", "Used when generating PDF", c["green"]),
            ("page", "Page Size", _default_ps, "Saved preference", c["orange"]),
        ]):
            card, val, sublbl = _spina_v22_report_card(cards, title, value, sub, accent)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0), ipady=2)
            self._reports_stat_labels[key] = (val, sublbl)

        # Table card
        table_card = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        table_card.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        table_head = tk.Frame(table_card, bg=c["panel"])
        table_head.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(table_head, text="Client Report List", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
        tk.Label(table_head, textvariable=self.report_summary_var, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 9), anchor="e").pack(side="right")

        cols = ("name", "contact", "loan_type", "term", "day_due", "payment", "mode", "linked", "area", "principal", "total", "released", "due")
        tree_frame = tk.Frame(table_card, bg=c["panel"])
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.reports_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=18, style="ModernReports.Treeview")
        try:
            self.reports_tree.bind("<<TreeviewSelect>>", lambda e: (self._auto_load_report_note(), _spina_v22_reports_selection_status(self)))
        except Exception:
            pass

        _hdr = {
            "name": "Client",
            "contact": "Contact",
            "loan_type": "Loan Type",
            "term": "Term",
            "day_due": "Day Due",
            "payment": "Payment",
            "mode": "Mode",
            "linked": "Also Has",
            "area": "Area",
            "principal": "Principal",
            "total": "Total To Pay",
            "released": "Date Released",
            "due": "Due Date",
        }
        _w = {
            "name": 260,
            "contact": 130,
            "loan_type": 106,
            "term": 84,
            "day_due": 110,
            "payment": 105,
            "mode": 90,
            "linked": 126,
            "area": 190,
            "principal": 110,
            "total": 118,
            "released": 110,
            "due": 110,
        }
        _anchor = {
            "name": "w", "contact": "center", "loan_type": "center", "term": "center",
            "day_due": "center", "payment": "e", "mode": "center", "linked": "center",
            "area": "w", "principal": "e", "total": "e", "released": "center", "due": "center",
        }
        for col in cols:
            self.reports_tree.heading(col, text=_hdr.get(col, col.title()))
            self.reports_tree.column(col, width=_w.get(col, 100), anchor=_anchor.get(col, "w"), stretch=True)

        try:
            self.reports_tree.tag_configure("even", background=c["panel"])
            self.reports_tree.tag_configure("odd", background=c["card2"])
        except Exception:
            pass

        vscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.reports_tree.yview)
        hscroll = ttk.Scrollbar(table_card, orient="horizontal", command=self.reports_tree.xview)
        self.reports_tree.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        self.reports_tree.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")
        hscroll.pack(side="bottom", fill="x", padx=12, pady=(0, 10))

        # Notes drawer, hidden by default.
        self.reports_notes_sep = tk.Frame(outer, bg=c["border"], height=1)
        self.reports_notes_box = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)

        def _toggle_reports_notes_panel():
            try:
                shown = bool(self.reports_notes_box.winfo_manager())
                if shown:
                    self.reports_notes_box.pack_forget()
                    self.reports_notes_sep.pack_forget()
                    self.report_notes_btn.configure(text="Notes")
                else:
                    self.reports_notes_sep.pack(fill="x", padx=18, pady=(0, 6))
                    self.reports_notes_box.pack(fill="x", padx=18, pady=(0, 18))
                    self.report_notes_btn.configure(text="Hide Notes")
                    try:
                        self._auto_load_report_note()
                    except Exception:
                        pass
            except Exception:
                pass

        self.report_notes_btn.configure(command=self._open_note_dialog)

        notes_top = tk.Frame(self.reports_notes_box, bg=c["panel"])
        notes_top.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(notes_top, text="Report Notes", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")

        self.note_date_var = tk.StringVar(value=(self.end_date_var.get() or date.today().strftime("%Y-%m-%d")))
        self.report_note_var = tk.StringVar(value="")
        self.report_note_status_var = tk.StringVar(value="Select a client to view notes.")

        note_tools = tk.Frame(self.reports_notes_box, bg=c["panel"])
        note_tools.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(note_tools, text="Note Date", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Entry(note_tools, textvariable=self.note_date_var, width=12).pack(side="left", padx=(6, 4))
        _spina_v22_button(note_tools, "Calendar", command=lambda: pick_date(self.root, self.note_date_var, initial=self.note_date_var.get(), title="Select Note Date"), kind="soft").pack(side="left", padx=(0, 6))
        _spina_v22_button(note_tools, "Load", command=self._load_report_note_for_client, kind="soft").pack(side="left", padx=(0, 6))
        _spina_v22_button(note_tools, "Save Date", command=self._save_dated_note_for_client, kind="primary").pack(side="left", padx=(0, 6))
        _spina_v22_button(note_tools, "Save Default", command=self._save_report_note_for_client, kind="soft").pack(side="left", padx=(0, 6))
        _spina_v22_button(note_tools, "Clear", command=lambda: self._set_report_note_text(""), kind="soft").pack(side="left", padx=(0, 6))
        tk.Label(note_tools, textvariable=self.report_note_status_var, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 9), anchor="e").pack(side="right", fill="x", expand=True)

        note_text_row = tk.Frame(self.reports_notes_box, bg=c["panel"])
        note_text_row.pack(fill="x", padx=12, pady=(0, 12))
        self.report_note_txt = tk.Text(
            note_text_row,
            height=4,
            wrap="word",
            undo=True,
            relief="flat",
            borderwidth=0,
            bg=c["entry"],
            fg=c["fg"],
            insertbackground=c["fg"],
            font=("Segoe UI", 10),
        )
        self.report_note_txt.pack(side="left", fill="x", expand=True)
        note_scroll = ttk.Scrollbar(note_text_row, orient="vertical", command=self.report_note_txt.yview)
        self.report_note_txt.configure(yscrollcommand=note_scroll.set)
        note_scroll.pack(side="right", fill="y")

        try:
            self.note_date_var.trace_add("write", lambda *_: self._auto_load_report_note())
        except Exception:
            pass

        self.refresh_reports()

    except Exception as e:
        try:
            _log_exc("v22.reports.build_tab", e)
        except Exception:
            pass
        try:
            messagebox.showerror("Reports", f"Unable to build Reports tab.\n\n{e}")
        except Exception:
            pass

def _spina_v22_reports_selection_status(self):
    try:
        sel = self.reports_tree.selection()
        if not sel:
            return
        vals = self.reports_tree.item(sel[0], "values") or []
        if vals and hasattr(self, "report_note_status_var"):
            self.report_note_status_var.set(f"Selected: {vals[0]}")
    except Exception:
        pass

def _spina_v22_update_report_cards(self):
    try:
        cards = getattr(self, "_reports_stat_labels", {}) or {}
        children = []
        try:
            children = self.reports_tree.get_children()
        except Exception:
            children = []
        count = len(children)

        mode = "All"
        try:
            mode = str(self._mode_filter() or "All")
        except Exception:
            pass

        sd = ""
        ed = ""
        try:
            sd = (self.start_date_var.get() or "").strip()
            ed = (self.end_date_var.get() or "").strip()
        except Exception:
            pass
        if sd and ed:
            range_text = f"{sd} → {ed}"
        elif sd:
            range_text = f"From {sd}"
        elif ed:
            range_text = f"Until {ed}"
        else:
            range_text = "Default"

        page = ""
        try:
            page = self.report_page_size_var.get() or "A4"
        except Exception:
            page = "A4"

        data = {
            "clients": (str(count), "Clients currently listed"),
            "view": (mode, "Matches Regular / 7x7 switch"),
            "range": (range_text, "Used when generating PDF"),
            "page": (page, "Saved report paper size"),
        }
        for key, (value, sub) in data.items():
            try:
                val_lbl, sub_lbl = cards.get(key, (None, None))
                if val_lbl is not None:
                    val_lbl.configure(text=value)
                if sub_lbl is not None:
                    sub_lbl.configure(text=sub)
            except Exception:
                pass
    except Exception:
        pass

__all__ = [
    'configure_reports_dependencies',
    '_spina_v22_style_reports_tree',
    '_spina_v22_button',
    '_spina_v22_report_card',
    '_spina_v22_build_reports_tab',
    '_spina_v22_reports_selection_status',
    '_spina_v22_update_report_cards',
]
