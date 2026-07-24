"""Client Information Log presentation extracted from the SPINA desktop entry module.

Database row fetching and application logging remain owned by the desktop application.
This module owns only CILog tab construction, charts, cards, rendering, and refresh orchestration.
"""

from __future__ import annotations

from datetime import date, timedelta
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Mapping

from spina_app.theme_palettes import _spina_v24_cilog_colors
from spina_app.ui_cards import _spina_v24_cilog_card
from spina_app.ui_controls import _spina_v24_cilog_button, _spina_v24_cilog_style_tree
from spina_app.ui_helpers import _spina_v24_cilog_round_rect, _spina_v24_cilog_set_card
from spina_app.utilities.dates import _spina_v24_cilog_parse_day

_REQUIRED_DEPENDENCIES = (
    "_log_exc",
    "_spina_cilog_fetch_rows",
)


def configure_client_info_logs_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind application-owned callbacks used by the CILog presentation module."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)


def _spina_v24_cilog_action_color(action, colors):
    a = str(action or "").upper()
    if a == "ADD":
        return colors["green"]
    if a in ("EDIT", "AREA UPDATE"):
        return colors["blue"]
    if a == "RENEW":
        return colors["orange"]
    if a == "LINK":
        return colors["purple"]
    if a in ("ARCHIVE", "DELETE"):
        return colors["red"]
    if a == "RESTORE":
        return colors["green"]
    if a == "PICTURE":
        return colors["yellow"]
    return colors["muted"]

def _spina_v24_cilog_stats(rows):
    rows = list(rows or [])
    clients = set()
    actions = {}
    fields = {}
    today_count = 0
    today = date.today()
    for r in rows:
        name = str(r.get("client") or "").strip()
        if name:
            clients.add(name.lower())
        a = str(r.get("action") or "CHANGE").upper()
        actions[a] = actions.get(a, 0) + 1
        f = str(r.get("field") or "Record")
        fields[f] = fields.get(f, 0) + 1
        if _spina_v24_cilog_parse_day(r.get("when")) == today:
            today_count += 1
    return {
        "total": len(rows),
        "clients": len(clients),
        "today": today_count,
        "actions": actions,
        "fields": fields,
    }

def _spina_v24_cilog_draw_charts(self, rows):
    try:
        c = _spina_v24_cilog_colors(self)
        rows = list(rows or [])
        stats = _spina_v24_cilog_stats(rows)

        # Chart 1: Action breakdown
        cv = getattr(self, "cilog_action_canvas", None)
        if cv is not None:
            cv.delete("all")
            cv.configure(bg=c["chart"])
            w = max(360, int(cv.winfo_width() or 360))
            h = max(180, int(cv.winfo_height() or 180))
            actions_sorted = sorted(stats["actions"].items(), key=lambda kv: (-kv[1], kv[0]))[:6]
            if not actions_sorted:
                cv.create_text(w//2, h//2, text="No logs yet", fill=c["chart_muted"], font=("Segoe UI", 11, "bold"))
            else:
                maxv = max(1, max(v for _, v in actions_sorted))
                x0, x2 = 24, w - 34
                y = 18
                for action, count in actions_sorted:
                    color = _spina_v24_cilog_action_color(action, c)
                    cv.create_text(x0, y+8, text=action, fill=c["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))
                    cv.create_text(x2, y+8, text=str(count), fill=c["chart_fg"], anchor="e", font=("Segoe UI", 9, "bold"))
                    ybar = y + 20
                    _spina_v24_cilog_round_rect(cv, x0, ybar, x2, ybar+16, 8, fill=c["track"], outline="")
                    bw = int((x2 - x0) * (count / maxv))
                    _spina_v24_cilog_round_rect(cv, x0, ybar, x0 + max(5, bw), ybar+16, 8, fill=color, outline="")
                    y += 39
                    if y > h - 22:
                        break

        # Chart 2: Most changed fields
        cv = getattr(self, "cilog_field_canvas", None)
        if cv is not None:
            cv.delete("all")
            cv.configure(bg=c["chart"])
            w = max(360, int(cv.winfo_width() or 360))
            h = max(180, int(cv.winfo_height() or 180))
            fields_sorted = sorted(stats["fields"].items(), key=lambda kv: (-kv[1], kv[0]))[:5]
            if not fields_sorted:
                cv.create_text(w//2, h//2, text="No field changes", fill=c["chart_muted"], font=("Segoe UI", 11, "bold"))
            else:
                maxv = max(1, max(v for _, v in fields_sorted))
                x0, x2 = 24, w - 34
                y = 20
                for field, count in fields_sorted:
                    txt = str(field or "Field")
                    if len(txt) > 24:
                        txt = txt[:21] + "..."
                    cv.create_text(x0, y+8, text=txt, fill=c["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))
                    cv.create_text(x2, y+8, text=str(count), fill=c["chart_fg"], anchor="e", font=("Segoe UI", 9, "bold"))
                    ybar = y + 20
                    _spina_v24_cilog_round_rect(cv, x0, ybar, x2, ybar+16, 8, fill=c["track"], outline="")
                    bw = int((x2 - x0) * (count / maxv))
                    _spina_v24_cilog_round_rect(cv, x0, ybar, x0 + max(5, bw), ybar+16, 8, fill=c["blue"], outline="")
                    y += 42
                    if y > h - 22:
                        break

        # Chart 3: Timeline, last 7 days
        cv = getattr(self, "cilog_timeline_canvas", None)
        if cv is not None:
            cv.delete("all")
            cv.configure(bg=c["chart"])
            w = max(360, int(cv.winfo_width() or 360))
            h = max(180, int(cv.winfo_height() or 180))
            days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
            counts = {d: 0 for d in days}
            for r in rows:
                d = _spina_v24_cilog_parse_day(r.get("when"))
                if d in counts:
                    counts[d] += 1
            maxv = max(1, max(counts.values()))
            x0, x2 = 28, w - 24
            ybase = h - 34
            usable_h = h - 62
            gap = (x2 - x0) / max(1, len(days))
            bw = max(14, int(gap * 0.55))
            for idx, d in enumerate(days):
                n = counts.get(d, 0)
                cx = x0 + gap * idx + gap / 2
                bh = int(usable_h * (n / maxv)) if n else 2
                color = c["green"] if n else c["track"]
                _spina_v24_cilog_round_rect(cv, cx - bw/2, ybase - bh, cx + bw/2, ybase, 7, fill=color, outline="")
                cv.create_text(cx, ybase - bh - 10, text=str(n), fill=c["chart_fg"], font=("Segoe UI", 8, "bold"))
                cv.create_text(cx, ybase + 14, text=d.strftime("%m/%d"), fill=c["chart_muted"], font=("Segoe UI", 8))
            cv.create_text(x0, 14, text="Last 7 days", fill=c["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))

    except Exception as e:
        try:
            _log_exc("v24.cilog.draw_charts", e)
        except Exception:
            pass

def _spina_v24_cilog_update_cards(self, view_rows, all_rows=None):
    try:
        all_rows = list(all_rows if all_rows is not None else getattr(self, "_spina_cilog_all_rows", []) or [])
        view_rows = list(view_rows or [])
        vstats = _spina_v24_cilog_stats(view_rows)
        astats = _spina_v24_cilog_stats(all_rows)

        _spina_v24_cilog_set_card(self, "changes", f"{len(view_rows):,}", f"{len(all_rows):,} total loaded")
        _spina_v24_cilog_set_card(self, "clients", f"{vstats.get('clients', 0):,}", "Unique clients in current view")
        _spina_v24_cilog_set_card(self, "today", f"{vstats.get('today', 0):,}", "Changes made today")

        top_action = "—"
        if vstats["actions"]:
            top_action = max(vstats["actions"].items(), key=lambda kv: kv[1])[0]
        _spina_v24_cilog_set_card(self, "top", top_action, "Most common action")

        try:
            if hasattr(self, "cilog_count_var"):
                self.cilog_count_var.set(f"Showing {len(view_rows):,} field change(s) / {len(all_rows):,} total")
        except Exception:
            pass

        _spina_v24_cilog_draw_charts(self, view_rows)
    except Exception:
        pass

def _spina_v24_build_client_info_logs_tab(self):
    try:
        if getattr(self, "_spina_client_info_logs_built", False):
            return
        self._spina_client_info_logs_built = True

        c = _spina_v24_cilog_colors(self)
        _spina_v24_cilog_style_tree(self)

        self.tab_client_info_logs = ttk.Frame(self.nb)
        try:
            tabs = list(self.nb.tabs())
            insert_at = len(tabs)
            for idx, tid in enumerate(tabs):
                try:
                    if self.nb.tab(tid, "text") == "Clients":
                        insert_at = idx + 1
                        break
                except Exception:
                    pass
            self.nb.insert(insert_at, self.tab_client_info_logs, text="Client Info Logs")
        except Exception:
            self.nb.add(self.tab_client_info_logs, text="Client Info Logs")

        self.cilog_search_var = tk.StringVar(value="")
        self.cilog_action_var = tk.StringVar(value="All")
        self.cilog_loan_var = tk.StringVar(value="All")
        self.cilog_period_var = tk.StringVar(value="All Time")
        self.cilog_count_var = tk.StringVar(value="Showing 0 changes")
        self.cilog_detail_var = tk.StringVar(value="Select a row to see the exact before and after change.")
        self._spina_cilog_all_rows = []
        self._spina_cilog_view_rows = []
        self._cilog_cards = {}

        outer = tk.Frame(self.tab_client_info_logs, bg=c["bg"])
        outer.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(outer, bg=c["bg"])
        header.pack(fill="x", padx=18, pady=(16, 10))

        titlebox = tk.Frame(header, bg=c["bg"])
        titlebox.pack(side="left", fill="x", expand=True)
        tk.Label(titlebox, text="Client Info Logs", bg=c["bg"], fg=c["fg"], font=("Segoe UI", 20, "bold"), anchor="w").pack(fill="x")
        tk.Label(
            titlebox,
            text="Audit trail for client information changes: edits, renewals, links, pictures, archive/restore, and changed fields.",
            bg=c["bg"],
            fg=c["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        _spina_v24_cilog_button(header, "Refresh Logs", command=self.refresh_client_info_logs, kind="primary").pack(side="right", padx=(8, 0))

        # Explanation panel
        explain = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        explain.pack(fill="x", padx=18, pady=(0, 12))
        tk.Label(explain, text="How to read this page", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(
            explain,
            text="Each row shows one changed field. Use Before → After to verify exactly what changed in the client's application record.",
            bg=c["panel"],
            fg=c["muted"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=14, pady=(3, 10))

        # Controls
        controls = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        controls.pack(fill="x", padx=18, pady=(0, 12))
        row = tk.Frame(controls, bg=c["panel"])
        row.pack(fill="x", padx=12, pady=10)

        search_box = tk.Frame(row, bg=c["panel"])
        search_box.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(search_box, text="Search Client / Field / Before / After / Note", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        search_line = tk.Frame(search_box, bg=c["panel"])
        search_line.pack(fill="x", pady=(3, 0))
        ttk.Entry(search_line, textvariable=self.cilog_search_var).pack(side="left", fill="x", expand=True)
        _spina_v24_cilog_button(search_line, "Clear", command=lambda: self.cilog_search_var.set(""), kind="soft").pack(side="left", padx=(8, 0))

        def combo_box(parent, label, var, values, width=14):
            box = tk.Frame(parent, bg=c["panel"])
            tk.Label(box, text=label, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
            cb = ttk.Combobox(box, textvariable=var, values=values, width=width, state="readonly")
            cb.pack(fill="x", pady=(3, 0))
            return box

        combo_box(row, "Action", self.cilog_action_var, ("All", "ADD", "EDIT", "RENEW", "LINK", "AREA UPDATE", "PICTURE", "ARCHIVE", "RESTORE", "DELETE", "SNAPSHOT"), 15).pack(side="left", padx=(0, 10))
        combo_box(row, "Loan", self.cilog_loan_var, ("All", "Regular", "7x7"), 10).pack(side="left", padx=(0, 10))
        combo_box(row, "Period", self.cilog_period_var, ("All Time", "Today", "Last 7 Days", "Last 30 Days"), 13).pack(side="left", padx=(0, 10))

        # Summary cards
        cards = tk.Frame(outer, bg=c["bg"])
        cards.pack(fill="x", padx=18, pady=(0, 12))
        for i in range(4):
            cards.columnconfigure(i, weight=1, uniform="cilogcards")

        for i, (key, title, value, sub, accent) in enumerate([
            ("changes", "Field Changes", "0", "Current view", c["blue"]),
            ("clients", "Clients Affected", "0", "Unique clients", c["purple"]),
            ("today", "Changed Today", "0", "Today's audit activity", c["green"]),
            ("top", "Top Action", "—", "Most common action", c["orange"]),
        ]):
            card, val, sublbl = _spina_v24_cilog_card(cards, title, value, sub, accent)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0), ipady=2)
            self._cilog_cards[key] = (val, sublbl)

        # Charts
        charts = tk.Frame(outer, bg=c["bg"])
        charts.pack(fill="x", padx=18, pady=(0, 12))
        for i in range(3):
            charts.columnconfigure(i, weight=1, uniform="cilogcharts")

        def chart_box(parent, title, subtitle):
            frame = tk.Frame(parent, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
            tk.Label(frame, text=title, bg=c["panel"], fg=c["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 0))
            tk.Label(frame, text=subtitle, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=14, pady=(1, 4))
            cv = tk.Canvas(frame, height=180, bg=c["chart"], highlightthickness=0, bd=0)
            cv.pack(fill="both", expand=True, padx=8, pady=(0, 10))
            return frame, cv

        f1, self.cilog_action_canvas = chart_box(charts, "Action Breakdown", "What type of changes happened")
        f1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        f2, self.cilog_field_canvas = chart_box(charts, "Most Changed Fields", "Which client information changes most")
        f2.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        f3, self.cilog_timeline_canvas = chart_box(charts, "Recent Activity", "Field changes over the last 7 days")
        f3.grid(row=0, column=2, sticky="nsew")

        # Table
        table_card = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        table_card.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        table_head = tk.Frame(table_card, bg=c["panel"])
        table_head.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(table_head, text="Change Log", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
        tk.Label(table_head, textvariable=self.cilog_count_var, bg=c["panel"], fg=c["muted"], font=("Segoe UI", 9), anchor="e").pack(side="right")

        body = tk.Frame(table_card, bg=c["panel"])
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        cols = ("when", "client", "loan", "action", "field", "before", "after", "note")
        self.cilog_tree = ttk.Treeview(body, columns=cols, show="headings", height=13, style="ModernCILog.Treeview")
        headings = {
            "when": ("When", 155, "w"),
            "client": ("Client", 220, "w"),
            "loan": ("Loan", 75, "center"),
            "action": ("Action", 110, "center"),
            "field": ("Changed Field", 165, "w"),
            "before": ("Before", 210, "w"),
            "after": ("After", 210, "w"),
            "note": ("Note / Source", 250, "w"),
        }
        for col in cols:
            label, width, anchor = headings[col]
            self.cilog_tree.heading(col, text=label)
            self.cilog_tree.column(col, width=width, minwidth=60, anchor=anchor, stretch=(col in ("client", "before", "after", "note")))

        y = ttk.Scrollbar(body, orient="vertical", command=self.cilog_tree.yview)
        x = ttk.Scrollbar(table_card, orient="horizontal", command=self.cilog_tree.xview)
        self.cilog_tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.cilog_tree.pack(side="left", fill="both", expand=True)
        y.pack(side="right", fill="y")
        x.pack(side="bottom", fill="x", padx=12, pady=(0, 10))

        # action tags
        try:
            self.cilog_tree.tag_configure("ADD", foreground=c["green"])
            self.cilog_tree.tag_configure("EDIT", foreground=c["blue"])
            self.cilog_tree.tag_configure("RENEW", foreground=c["orange"])
            self.cilog_tree.tag_configure("LINK", foreground=c["purple"])
            self.cilog_tree.tag_configure("AREA UPDATE", foreground=c["blue"])
            self.cilog_tree.tag_configure("PICTURE", foreground=c["yellow"])
            self.cilog_tree.tag_configure("ARCHIVE", foreground=c["orange"])
            self.cilog_tree.tag_configure("RESTORE", foreground=c["green"])
            self.cilog_tree.tag_configure("DELETE", foreground=c["red"])
            self.cilog_tree.tag_configure("SNAPSHOT", foreground=c["muted"])
        except Exception:
            pass

        # Details panel
        details = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, bd=0)
        details.pack(fill="x", padx=18, pady=(0, 18))
        tk.Label(details, text="Selected Change Details", bg=c["panel"], fg=c["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(details, textvariable=self.cilog_detail_var, bg=c["panel"], fg=c["fg"], font=("Segoe UI", 10), anchor="w", justify="left", wraplength=1200).pack(fill="x", padx=14, pady=(4, 10))

        def _on_select(_=None):
            try:
                sel = self.cilog_tree.selection()
                if not sel:
                    return
                idx = int(sel[0])
                rows = getattr(self, "_spina_cilog_view_rows", []) or []
                if idx < 0 or idx >= len(rows):
                    return
                r = rows[idx]
                before = r.get("before", "")
                after = r.get("after", "")
                note_source = " / ".join([x for x in [r.get("note") or "", r.get("source") or ""] if x])
                self.cilog_detail_var.set(
                    f"{r.get('when','')}  |  {r.get('client','')} ({r.get('loan_type','')})\n"
                    f"Action: {r.get('action','')}  •  Field: {r.get('field','')}\n"
                    f"Before: {before if before != '' else 'blank'}\n"
                    f"After: {after if after != '' else 'blank'}"
                    + (f"\nNote/Source: {note_source}" if note_source else "")
                )
            except Exception:
                pass

        self.cilog_tree.bind("<<TreeviewSelect>>", _on_select)

        def _filter_trigger(*_):
            try:
                self.render_client_info_logs()
            except Exception:
                pass
        try:
            self.cilog_search_var.trace_add("write", _filter_trigger)
            self.cilog_action_var.trace_add("write", _filter_trigger)
            self.cilog_loan_var.trace_add("write", _filter_trigger)
            self.cilog_period_var.trace_add("write", _filter_trigger)
        except Exception:
            pass

        for cv in (self.cilog_action_canvas, self.cilog_field_canvas, self.cilog_timeline_canvas):
            try:
                cv.bind("<Configure>", lambda e: _spina_v24_cilog_draw_charts(self, getattr(self, "_spina_cilog_view_rows", []) or []))
            except Exception:
                pass

        try:
            self.nb.bind(
                "<<NotebookTabChanged>>",
                lambda e: self.refresh_client_info_logs() if self.nb.select() == str(self.tab_client_info_logs) else None,
                add="+",
            )
        except Exception:
            pass

        self.refresh_client_info_logs()

    except Exception as e:
        try:
            _log_exc("v24.client_info_logs.build", e)
        except Exception:
            pass
        try:
            messagebox.showerror("Client Info Logs", f"Unable to build Client Info Logs.\n\n{e}")
        except Exception:
            pass

def _spina_v24_render_client_info_logs(self):
    try:
        tree = getattr(self, "cilog_tree", None)
        if tree is None:
            return

        q = (getattr(self, "cilog_search_var", tk.StringVar(value="")).get() or "").strip().lower()
        act = (getattr(self, "cilog_action_var", tk.StringVar(value="All")).get() or "All").strip().upper()
        loan = (getattr(self, "cilog_loan_var", tk.StringVar(value="All")).get() or "All").strip()
        period = (getattr(self, "cilog_period_var", tk.StringVar(value="All Time")).get() or "All Time").strip()

        cutoff = None
        if period == "Today":
            cutoff = date.today()
        elif period == "Last 7 Days":
            cutoff = date.today() - timedelta(days=6)
        elif period == "Last 30 Days":
            cutoff = date.today() - timedelta(days=29)

        all_rows = getattr(self, "_spina_cilog_all_rows", []) or []
        view = []

        for r in all_rows:
            if act != "ALL" and str(r.get("action") or "").upper() != act:
                continue
            if loan != "All" and str(r.get("loan_type") or "") != loan:
                continue
            if cutoff is not None:
                d = _spina_v24_cilog_parse_day(r.get("when"))
                if d is None or d < cutoff:
                    continue
            hay = " ".join(str(r.get(k) or "") for k in ("when", "client", "loan_type", "action", "field", "before", "after", "source", "note")).lower()
            if q and q not in hay:
                continue
            view.append(r)

        self._spina_cilog_view_rows = view
        try:
            tree.delete(*tree.get_children())
        except Exception:
            for iid in tree.get_children():
                tree.delete(iid)

        for i, r in enumerate(view):
            note_source = " / ".join([x for x in [r.get("note") or "", r.get("source") or ""] if x])
            action = str(r.get("action") or "")
            tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    r.get("when") or "",
                    r.get("client") or "",
                    r.get("loan_type") or "",
                    action,
                    r.get("field") or "",
                    r.get("before") or "",
                    r.get("after") or "",
                    note_source,
                ),
                tags=(action,),
            )

        _spina_v24_cilog_update_cards(self, view, all_rows)

        if view:
            try:
                tree.selection_set("0")
                tree.focus("0")
                tree.see("0")
            except Exception:
                pass
        else:
            try:
                self.cilog_detail_var.set("No matching client information changes.")
            except Exception:
                pass

    except Exception as e:
        try:
            _log_exc("v24.client_info_logs.render", e)
        except Exception:
            pass

def _spina_v24_refresh_client_info_logs(self):
    try:
        if not getattr(self, "_spina_client_info_logs_built", False):
            return
        try:
            self._spina_cilog_all_rows = _spina_cilog_fetch_rows(self.db, limit=5000)
        except Exception as e:
            try:
                _log_exc("v24.client_info_logs.fetch", e)
            except Exception:
                pass
            self._spina_cilog_all_rows = []
        self.render_client_info_logs()
        try:
            if hasattr(self, "status_var"):
                self.status_var.set("Client Info Logs refreshed.")
        except Exception:
            pass
    except Exception as e:
        try:
            _log_exc("v24.client_info_logs.refresh", e)
        except Exception:
            pass
