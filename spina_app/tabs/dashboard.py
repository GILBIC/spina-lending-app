"""Legacy Dashboard feature extracted from the SPINA desktop source.

The five public helpers retain their original names so existing App patching and
callbacks continue to work. Database row loading and application logging remain
owned by the desktop entry module and are supplied through a small late-bound
bridge to avoid circular imports.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from spina_app.theme_palettes import _spina_v17_dash_colors
from spina_app.ui_cards import _spina_v17_make_card
from spina_app.ui_controls import (
    _spina_v17_style_dashboard_table,
    _spina_v17_update_filter_buttons,
)
from spina_app.ui_helpers import _spina_v17_set_card
from spina_app.utilities.formatting import (
    _spina_dash__fmt_money,
    _spina_dash__fmt_pct,
    _spina_v17_fmt_short_money,
)

_dashboard_fetch_rows = None
_dashboard_log_exc = None


def configure_legacy_dashboard_feature(*, fetch_rows=None, log_exc=None):
    """Attach main-module services without importing the large entry module."""
    global _dashboard_fetch_rows, _dashboard_log_exc
    if fetch_rows is not None:
        _dashboard_fetch_rows = fetch_rows
    if log_exc is not None:
        _dashboard_log_exc = log_exc


def _spina_dashboard_fetch_rows(self):
    if not callable(_dashboard_fetch_rows):
        return []
    return _dashboard_fetch_rows(self)


def _log_exc(context, exc=None):
    if callable(_dashboard_log_exc):
        return _dashboard_log_exc(context, exc)
    return None


def _spina_v17_visible_dashboard_rows(self):
    try:
        rows = list(getattr(self, "_dashboard_rows", []) or [])
        loan_filter = str(getattr(self, "dashboard_loan_filter_var", tk.StringVar(value="All")).get() or "All")
        status_filter = str(getattr(self, "dashboard_status_filter_var", tk.StringVar(value="Priority")).get() or "Priority")
        search = str(getattr(self, "dashboard_search_var", tk.StringVar(value="")).get() or "").strip().lower()

        if loan_filter != "All":
            rows = [r for r in rows if str(r.get("loan_type") or "") == loan_filter]

        if status_filter in ("Priority", "Finishing Priority"):
            rows = [r for r in rows if r.get("status") in ("Finishing Now", "Near Completion", "Due Soon", "Overdue")]
        elif status_filter not in ("All", "All Active"):
            rows = [r for r in rows if str(r.get("status") or "") == status_filter]

        if search:
            rows = [
                r for r in rows
                if search in str(r.get("name") or "").lower()
                or search in str(r.get("area") or "").lower()
                or search in str(r.get("status") or "").lower()
            ]

        return rows
    except Exception:
        return list(getattr(self, "_dashboard_rows", []) or [])


def _spina_v17_build_dashboard_tab(self):
    try:
        if not hasattr(self, "nb") or self.nb is None:
            return

        if not hasattr(self, "tab_dashboard") or self.tab_dashboard is None:
            self.tab_dashboard = ttk.Frame(self.nb)
            try:
                self.nb.insert(1, self.tab_dashboard, text="Dashboard")
            except Exception:
                self.nb.add(self.tab_dashboard, text="Dashboard")
        else:
            try:
                for w in self.tab_dashboard.winfo_children():
                    w.destroy()
            except Exception:
                pass

        colors = _spina_v17_dash_colors(self)
        self._dash_cards = {}
        self._dash_filter_buttons = {}

        outer = tk.Frame(self.tab_dashboard, bg=colors["bg"])
        outer.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(outer, bg=colors["bg"])
        header.pack(fill="x", padx=18, pady=(16, 10))

        titlebox = tk.Frame(header, bg=colors["bg"])
        titlebox.pack(side="left", fill="x", expand=True)
        tk.Label(
            titlebox,
            text="Dashboard",
            bg=colors["bg"],
            fg=colors["fg"],
            font=("Segoe UI", 20, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            titlebox,
            text="Quick view of all active clients, loan progress, due risk, and remaining balance.",
            bg=colors["bg"],
            fg=colors["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        tk.Button(
            header,
            text="Refresh",
            command=self.refresh_dashboard,
            bg=colors["accent"],
            fg="#ffffff",
            activebackground=colors["accent"],
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            font=("Segoe UI", 10, "bold"),
            padx=18,
            pady=9,
            cursor="hand2",
        ).pack(side="right", padx=(10, 0))

        # Controls card
        controls = tk.Frame(outer, bg=colors["panel"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
        controls.pack(fill="x", padx=18, pady=(0, 12))

        left_controls = tk.Frame(controls, bg=colors["panel"])
        left_controls.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        tk.Label(left_controls, text="View", bg=colors["panel"], fg=colors["muted"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))

        self.dashboard_loan_filter_var = tk.StringVar(value="All")

        def set_loan(value):
            try:
                self.dashboard_loan_filter_var.set(value)
                _spina_v17_update_filter_buttons(self)
                self._populate_dashboard_tree()
            except Exception:
                pass

        for label, value in (("All", "All"), ("Regular", "Regular"), ("7x7", "7x7")):
            btn = tk.Button(
                left_controls,
                text=label,
                command=lambda v=value: set_loan(v),
                relief="flat",
                bd=0,
                padx=14,
                pady=7,
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
            )
            btn.pack(side="left", padx=(0, 6))
            self._dash_filter_buttons[value] = btn

        tk.Label(left_controls, text="Show", bg=colors["panel"], fg=colors["muted"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(18, 8))
        self.dashboard_status_filter_var = tk.StringVar(value="All Active")
        cb = ttk.Combobox(
            left_controls,
            textvariable=self.dashboard_status_filter_var,
            values=["All Active", "Priority", "Finishing Now", "Near Completion", "Due Soon", "Overdue", "Complete"],
            state="readonly",
            width=18,
        )
        cb.pack(side="left")
        try:
            cb.bind("<<ComboboxSelected>>", lambda e: self._populate_dashboard_tree())
        except Exception:
            pass

        right_controls = tk.Frame(controls, bg=colors["panel"])
        right_controls.pack(side="right", padx=12, pady=10)
        tk.Label(right_controls, text="Search", bg=colors["panel"], fg=colors["muted"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        self.dashboard_search_var = tk.StringVar(value="")
        search_ent = ttk.Entry(right_controls, textvariable=self.dashboard_search_var, width=28)
        search_ent.pack(side="left")
        try:
            self.dashboard_search_var.trace_add("write", lambda *_: self._populate_dashboard_tree())
        except Exception:
            pass

        # KPI cards
        cards = tk.Frame(outer, bg=colors["bg"])
        cards.pack(fill="x", padx=18, pady=(0, 12))
        for i in range(4):
            cards.columnconfigure(i, weight=1, uniform="dashcard")

        card_defs = [
            ("active", "Active Loans", "—", "Current visible loans"),
            ("priority", "Needs Attention", "—", "Finishing, due soon, or overdue"),
            ("paid", "Paid Since Latest", "—", "Payments in current cycle"),
            ("remaining", "Remaining Balance", "—", "Still to collect"),
        ]
        for i, (key, title, value, sub) in enumerate(card_defs):
            card, val_lbl, sub_lbl = _spina_v17_make_card(cards, title, value, sub)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0), ipady=4)
            self._dash_cards[key] = (val_lbl, sub_lbl)

        # Charts
        charts = tk.Frame(outer, bg=colors["bg"])
        charts.pack(fill="x", padx=18, pady=(0, 12))
        charts.columnconfigure(0, weight=1, uniform="chart")
        charts.columnconfigure(1, weight=1, uniform="chart")
        charts.columnconfigure(2, weight=1, uniform="chart")

        def chart_card(parent, title, subtitle):
            frame = tk.Frame(parent, bg=colors["panel"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
            tk.Label(frame, text=title, bg=colors["panel"], fg=colors["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 0))
            tk.Label(frame, text=subtitle, bg=colors["panel"], fg=colors["muted"], font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=14, pady=(1, 4))
            cv = tk.Canvas(frame, height=180, bg=colors["panel"], highlightthickness=0, bd=0)
            cv.pack(fill="both", expand=True, padx=8, pady=(0, 10))
            return frame, cv

        c1, self.dashboard_gauge_canvas = chart_card(charts, "Active Clients", "Regular / 7x7 count")
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        c2, self.dashboard_status_canvas = chart_card(charts, "Client Status", "All labels visible + easy counts")
        c2.grid(row=0, column=1, sticky="nsew", padx=(0, 8))

        c3, self.dashboard_type_canvas = chart_card(charts, "At-Risk Balance", "Overdue / due soon / finishing balance")
        c3.grid(row=0, column=2, sticky="nsew")

        # Table
        table_wrap = tk.Frame(outer, bg=colors["panel"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
        table_wrap.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        table_header = tk.Frame(table_wrap, bg=colors["panel"])
        table_header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(table_header, text="All Active Client List", bg=colors["panel"], fg=colors["fg"], font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
        self.dashboard_summary_var = tk.StringVar(value="All active clients will show here after refresh.")
        tk.Label(table_header, textvariable=self.dashboard_summary_var, bg=colors["panel"], fg=colors["muted"], font=("Segoe UI", 9), anchor="e").pack(side="right")

        _spina_v17_style_dashboard_table(self)
        cols = ("status", "name", "loan_type", "area", "paid", "completion", "remaining", "days_left")
        self.dashboard_tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=11, style="ModernDash.Treeview")
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.dashboard_tree.yview)
        self.dashboard_tree.configure(yscrollcommand=yscroll.set)
        self.dashboard_tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        yscroll.pack(side="right", fill="y", padx=(0, 12), pady=(0, 12))

        heads = {
            "status": "Status",
            "name": "Client",
            "loan_type": "Type",
            "area": "Area",
            "paid": "Paid",
            "completion": "Done",
            "remaining": "Remaining",
            "days_left": "Days Left",
        }
        widths = {
            "status": 140,
            "name": 220,
            "loan_type": 70,
            "area": 190,
            "paid": 120,
            "completion": 80,
            "remaining": 120,
            "days_left": 80,
        }
        for col in cols:
            self.dashboard_tree.heading(col, text=heads[col])
            self.dashboard_tree.column(
                col,
                width=widths[col],
                minwidth=60,
                anchor=("e" if col in ("paid", "completion", "remaining", "days_left") else "w"),
                stretch=True,
            )

        try:
            self.dashboard_tree.tag_configure("finish", background="#234b33" if colors["bg"].startswith("#11") else "#dcfce7", foreground=colors["fg"] if colors["bg"].startswith("#11") else "#14532d")
            self.dashboard_tree.tag_configure("near", background="#4a3a16" if colors["bg"].startswith("#11") else "#fef3c7", foreground=colors["fg"] if colors["bg"].startswith("#11") else "#78350f")
            self.dashboard_tree.tag_configure("due", background="#4a311c" if colors["bg"].startswith("#11") else "#ffedd5", foreground=colors["fg"] if colors["bg"].startswith("#11") else "#7c2d12")
            self.dashboard_tree.tag_configure("overdue", background="#4a2424" if colors["bg"].startswith("#11") else "#fee2e2", foreground=colors["fg"] if colors["bg"].startswith("#11") else "#7f1d1d")
            self.dashboard_tree.tag_configure("complete", background="#22394c" if colors["bg"].startswith("#11") else "#dbeafe", foreground=colors["fg"] if colors["bg"].startswith("#11") else "#1e3a8a")
        except Exception:
            pass

        def redraw_on_resize(_event=None):
            try:
                if getattr(self, "_dash_redraw_after_id", None):
                    try:
                        self.root.after_cancel(self._dash_redraw_after_id)
                    except Exception:
                        pass
                self._dash_redraw_after_id = self.root.after(120, lambda: _spina_v17_draw_dashboard_charts(self, _spina_v17_visible_dashboard_rows(self)))
            except Exception:
                pass

        for cv in (self.dashboard_gauge_canvas, self.dashboard_status_canvas, self.dashboard_type_canvas):
            try:
                cv.bind("<Configure>", redraw_on_resize)
            except Exception:
                pass

        _spina_v17_update_filter_buttons(self)
        self.refresh_dashboard()

    except Exception as e:
        try:
            _log_exc("v17.build_dashboard_tab", e)
        except Exception:
            pass


def _spina_v17_draw_dashboard_charts(self, rows):
    try:
        colors = _spina_v17_dash_colors(self)
        rows = list(rows or [])

        total = sum(float(r.get("total_to_pay") or 0) for r in rows)
        paid = sum(float(r.get("paid") or 0) for r in rows)
        remaining = sum(float(r.get("remaining") or 0) for r in rows)
        pct = (paid / total * 100.0) if total > 0 else 0.0

        # Gauge chart
        cv = getattr(self, "dashboard_gauge_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(260, int(cv.winfo_width() or 260))
            h = max(170, int(cv.winfo_height() or 170))
            cx, cy = w // 2, 88
            r = min(62, max(45, min(w, h) // 3))
            box = (cx - r, cy - r, cx + r, cy + r)
            cv.create_oval(*box, outline=colors["track"], width=18)
            cv.create_arc(*box, start=90, extent=-min(360, max(0, pct) * 3.6), outline=colors["accent2"], width=18, style="arc")
            cv.create_text(cx, cy - 5, text="{:.0f}%".format(min(999, pct)), fill=colors["fg"], font=("Segoe UI", 22, "bold"))
            cv.create_text(cx, cy + 25, text="collected", fill=colors["muted"], font=("Segoe UI", 9))
            cv.create_text(16, h - 38, text="Paid: " + _spina_v17_fmt_short_money(paid), fill=colors["muted"], anchor="w", font=("Segoe UI", 9))
            cv.create_text(16, h - 18, text="Remaining: " + _spina_v17_fmt_short_money(remaining), fill=colors["muted"], anchor="w", font=("Segoe UI", 9))

        # Status horizontal bars
        cv = getattr(self, "dashboard_status_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(300, int(cv.winfo_width() or 300))
            statuses = ["Finishing Now", "Near Completion", "Due Soon", "Overdue", "Complete"]
            counts = {s: 0 for s in statuses}
            for r in rows:
                s = str(r.get("status") or "")
                if s in counts:
                    counts[s] += 1
            max_count = max([1] + list(counts.values()))
            y = 20
            status_colors = {
                "Finishing Now": colors["accent2"],
                "Near Completion": colors["warn"],
                "Due Soon": "#fb923c",
                "Overdue": colors["danger"],
                "Complete": colors["accent"],
            }
            for s in statuses:
                n = counts.get(s, 0)
                cv.create_text(14, y + 8, text=s, fill=colors["fg"], anchor="w", font=("Segoe UI", 9, "bold"))
                bar_x = 135
                bar_w = max(4, int((w - bar_x - 48) * (n / max_count)))
                cv.create_rectangle(bar_x, y, w - 42, y + 16, fill=colors["track"], outline="")
                cv.create_rectangle(bar_x, y, bar_x + bar_w, y + 16, fill=status_colors.get(s, colors["bar"]), outline="")
                cv.create_text(w - 18, y + 8, text=str(n), fill=colors["fg"], anchor="e", font=("Segoe UI", 9, "bold"))
                y += 30

        # Remaining by type bars
        cv = getattr(self, "dashboard_type_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(280, int(cv.winfo_width() or 280))
            h = max(170, int(cv.winfo_height() or 170))
            by_type = {"Regular": 0.0, "7x7": 0.0}
            count_by_type = {"Regular": 0, "7x7": 0}
            for r in rows:
                lt = "7x7" if str(r.get("loan_type") or "").lower().replace("×", "x") == "7x7" else "Regular"
                by_type[lt] += float(r.get("remaining") or 0)
                count_by_type[lt] += 1
            max_val = max(1.0, max(by_type.values() or [1.0]))
            x0 = 34
            bar_area_w = max(80, w - 90)
            y = 42
            for label, col in (("Regular", colors["bar"]), ("7x7", colors["bar2"])):
                val = by_type.get(label, 0.0)
                bw = int(bar_area_w * (val / max_val)) if max_val else 0
                cv.create_text(x0, y - 14, text=f"{label} ({count_by_type.get(label, 0)})", fill=colors["fg"], anchor="w", font=("Segoe UI", 10, "bold"))
                cv.create_rectangle(x0, y, x0 + bar_area_w, y + 28, fill=colors["track"], outline="")
                cv.create_rectangle(x0, y, x0 + bw, y + 28, fill=col, outline="")
                cv.create_text(x0 + 8, y + 14, text=_spina_v17_fmt_short_money(val), fill="#ffffff", anchor="w", font=("Segoe UI", 9, "bold"))
                y += 68
            cv.create_text(x0, h - 16, text="Total visible remaining: " + _spina_v17_fmt_short_money(sum(by_type.values())), fill=colors["muted"], anchor="w", font=("Segoe UI", 9))

    except Exception as e:
        try:
            _log_exc("v17.draw_dashboard_charts", e)
        except Exception:
            pass


def _spina_v17_populate_dashboard_tree(self):
    try:
        _spina_v17_update_filter_buttons(self)
        rows = _spina_v17_visible_dashboard_rows(self)

        total_rows = list(getattr(self, "_dashboard_rows", []) or [])
        total = sum(float(r.get("total_to_pay") or 0) for r in rows)
        paid = sum(float(r.get("paid") or 0) for r in rows)
        remaining = sum(float(r.get("remaining") or 0) for r in rows)
        priority = sum(1 for r in rows if r.get("status") in ("Finishing Now", "Near Completion", "Due Soon", "Overdue"))
        complete = sum(1 for r in rows if r.get("status") == "Complete")
        pct = (paid / total * 100.0) if total > 0 else 0.0

        _spina_v17_set_card(self, "active", str(len(rows)), f"{len(total_rows)} total loaded")
        _spina_v17_set_card(self, "priority", str(priority), f"{complete} complete")
        _spina_v17_set_card(self, "paid", _spina_v17_fmt_short_money(paid), f"{pct:.0f}% of visible total")
        _spina_v17_set_card(self, "remaining", _spina_v17_fmt_short_money(remaining), "Visible filter")

        try:
            self.dashboard_summary_var.set(f"Showing {len(rows)} of {len(total_rows)} loans")
        except Exception:
            pass

        tree = getattr(self, "dashboard_tree", None)
        if tree is not None:
            for iid in tree.get_children():
                tree.delete(iid)

            # Prioritize the most important rows first.
            rows_sorted = sorted(
                rows,
                key=lambda r: (
                    r.get("priority", 99),
                    -float(r.get("remaining") or 0),
                    -float(r.get("completion_pct") or 0),
                    str(r.get("name") or ""),
                ),
            )

            for r in rows_sorted[:300]:
                status = r.get("status") or ""
                tag = ""
                if status == "Finishing Now":
                    tag = "finish"
                elif status == "Near Completion":
                    tag = "near"
                elif status == "Due Soon":
                    tag = "due"
                elif status == "Overdue":
                    tag = "overdue"
                elif status == "Complete":
                    tag = "complete"
                days_left = r.get("days_left")
                tree.insert(
                    "",
                    "end",
                    values=(
                        status,
                        r.get("name") or "",
                        r.get("loan_type") or "",
                        r.get("area") or "",
                        _spina_dash__fmt_money(r.get("paid") or 0),
                        _spina_dash__fmt_pct(r.get("completion_pct") or 0),
                        _spina_dash__fmt_money(r.get("remaining") or 0),
                        "" if days_left is None else str(days_left),
                    ),
                    tags=(tag,) if tag else (),
                )

        try:
            root = getattr(self, "root", None) or getattr(self, "master", None)
            if root is not None:
                root.after(50, lambda: _spina_v17_draw_dashboard_charts(self, rows))
            else:
                _spina_v17_draw_dashboard_charts(self, rows)
        except Exception:
            _spina_v17_draw_dashboard_charts(self, rows)

    except Exception as e:
        try:
            _log_exc("v17.populate_dashboard", e)
        except Exception:
            pass


def _spina_v17_refresh_dashboard(self):
    try:
        if not hasattr(self, "tab_dashboard"):
            return
        self._dashboard_rows = _spina_dashboard_fetch_rows(self)
        _spina_v17_populate_dashboard_tree(self)
        try:
            self.status_var.set("Dashboard refreshed.")
        except Exception:
            pass
    except Exception as e:
        try:
            _log_exc("v17.refresh_dashboard", e)
        except Exception:
            pass
        try:
            self.status_var.set("Dashboard refresh failed. See data/spina_app.log.")
        except Exception:
            pass

# Dashboard visibility filters extracted in Wave 24.

def _spina_dashboard_visible_rows(self):
    try:
        rows = list(getattr(self, '_dashboard_rows', []) or [])
        loan_filter = str(getattr(self, 'dashboard_loan_filter_var', tk.StringVar(value='All')).get() or 'All')
        status_filter = str(getattr(self, 'dashboard_status_filter_var', tk.StringVar(value='Finishing Priority')).get() or 'Finishing Priority')
        search = str(getattr(self, 'dashboard_search_var', tk.StringVar(value='')).get() or '').strip().lower()

        if loan_filter != 'All':
            rows = [r for r in rows if r.get('loan_type') == loan_filter]
        if status_filter == 'Finishing Priority':
            rows = [r for r in rows if r.get('status') in ('Finishing Now', 'Near Completion', 'Due Soon', 'Overdue')]
        elif status_filter != 'All Active':
            rows = [r for r in rows if r.get('status') == status_filter]
        if search:
            rows = [r for r in rows if search in str(r.get('name') or '').lower() or search in str(r.get('area') or '').lower()]
        return rows
    except Exception:
        return list(getattr(self, '_dashboard_rows', []) or [])


def _spina_v19_visible_dashboard_rows(self):
    """Dashboard should show all active clients by default, not only priority clients."""
    try:
        rows = list(getattr(self, "_dashboard_rows", []) or [])

        loan_filter = str(getattr(self, "dashboard_loan_filter_var", tk.StringVar(value="All")).get() or "All")
        status_filter = str(getattr(self, "dashboard_status_filter_var", tk.StringVar(value="All Active")).get() or "All Active")
        search = str(getattr(self, "dashboard_search_var", tk.StringVar(value="")).get() or "").strip().lower()

        if loan_filter != "All":
            rows = [r for r in rows if str(r.get("loan_type") or "") == loan_filter]

        # All Active / All = keep every active row loaded by _spina_dashboard_fetch_rows().
        # Priority = filter only clients that need attention.
        if status_filter == "Priority":
            rows = [r for r in rows if r.get("status") in ("Finishing Now", "Near Completion", "Due Soon", "Overdue")]
        elif status_filter not in ("All", "All Active", "All Clients"):
            rows = [r for r in rows if str(r.get("status") or "") == status_filter]

        if search:
            rows = [
                r for r in rows
                if search in str(r.get("name") or "").lower()
                or search in str(r.get("area") or "").lower()
                or search in str(r.get("status") or "").lower()
            ]

        return rows
    except Exception:
        return list(getattr(self, "_dashboard_rows", []) or [])


def _spina_v20_visible_rows(self):
    try:
        # Use v19 default behavior: All Active by default.
        return _spina_v19_visible_dashboard_rows(self)
    except Exception:
        try:
            return list(getattr(self, "_dashboard_rows", []) or [])
        except Exception:
            return []
