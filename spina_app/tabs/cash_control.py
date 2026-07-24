"""Cash Control presentation shell extracted from the SPINA desktop entry module.

Collection totals, reserve calculations, refresh orchestration, and database access remain
owned by the desktop application. This module owns tab construction and chart rendering only.
"""

from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk
from typing import Any, Mapping

from spina_app.theme_palettes import _spina_v21_cash_colors
from spina_app.ui_cards import _spina_v21_cash_card
from spina_app.ui_controls import _spina_v21_build_labeled_entry, _spina_v21_style_cash_table

_REQUIRED_DEPENDENCIES = (
    "_log_exc",
    "_spina_v21_cash_money_short",
    "_spina_v21_cash_round_rect",
)


def configure_cash_control_dependencies(namespace: Mapping[str, Any]) -> tuple[str, ...]:
    """Bind application-owned display and logging helpers used by Cash Control."""
    missing = []
    for name in _REQUIRED_DEPENDENCIES:
        value = namespace.get(name)
        if value is None:
            missing.append(name)
            continue
        globals()[name] = value
    return tuple(missing)


def _spina_v21_cash_build_tab(self):
    try:
        if not hasattr(self, "nb") or self.nb is None:
            return

        if hasattr(self, "tab_cash_control") and self.tab_cash_control is not None:
            try:
                for w in self.tab_cash_control.winfo_children():
                    w.destroy()
            except Exception:
                pass
        else:
            self.tab_cash_control = ttk.Frame(self.nb)
            try:
                self.nb.insert(2, self.tab_cash_control, text="Cash Control")
            except Exception:
                self.nb.add(self.tab_cash_control, text="Cash Control")

        colors = _spina_v21_cash_colors(self)

        self.cashctl_date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        self.cashctl_cash_on_hand_var = tk.StringVar(value="0.00")
        self.cashctl_forecast_days_var = tk.StringVar(value="14")
        self.cashctl_avg_window_days_var = tk.StringVar(value="30")
        self.cashctl_buffer_percent_var = tk.StringVar(value="10")

        self.cashctl_collection_var = tk.StringVar(value="Today Collection: PHP 0.00")
        self.cashctl_breakdown_var = tk.StringVar(value="Regular: PHP 0.00 • 7x7: PHP 0.00")
        self.cashctl_avg_collection_var = tk.StringVar(value="Average Daily Collection: PHP 0.00")
        self.cashctl_future_cash_var = tk.StringVar(value="Forecast Collection: PHP 0.00")
        self.cashctl_current_available_var = tk.StringVar(value="Current Available: PHP 0.00")
        self.cashctl_forecast_available_var = tk.StringVar(value="Forecast Available: PHP 0.00")
        self.cashctl_reserve_var = tk.StringVar(value="Renewal Release Reserve: PHP 0.00")
        self.cashctl_renewal_payoff_var = tk.StringVar(value="Expected Renewal Payoff: PHP 0.00")
        self.cashctl_net_renewal_var = tk.StringVar(value="Net Renewal Cash Need: PHP 0.00")
        self.cashctl_buffer_amount_var = tk.StringVar(value="Emergency Buffer: PHP 0.00")
        self.cashctl_safe_now_var = tk.StringVar(value="Safe Now: PHP 0.00")
        self.cashctl_forecast_safe_var = tk.StringVar(value="Forecast Safe: PHP 0.00")
        self.cashctl_safe_var = self.cashctl_forecast_safe_var
        self.cashctl_decision_var = tk.StringVar(value="Enter cash on hand, then refresh to calculate safe release amount.")

        self._cashctl_last_data = {}

        outer = tk.Frame(self.tab_cash_control, bg=colors["bg"])
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=colors["bg"])
        header.pack(fill="x", padx=18, pady=(16, 10))

        titlebox = tk.Frame(header, bg=colors["bg"])
        titlebox.pack(side="left", fill="x", expand=True)
        tk.Label(titlebox, text="Cash Control", bg=colors["bg"], fg=colors["fg"], font=("Segoe UI", 20, "bold"), anchor="w").pack(fill="x")
        tk.Label(
            titlebox,
            text="Know how much cash is safe to release after collection, renewals, and emergency buffer.",
            bg=colors["bg"],
            fg=colors["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        tk.Button(
            header,
            text="Refresh / Calculate",
            command=self.refresh_cash_control,
            bg=colors["button"],
            fg="#ffffff",
            activebackground=colors["button"],
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=18,
            pady=9,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        ).pack(side="right")

        # Formula/explanation panel
        formula = tk.Frame(outer, bg=colors["panel"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
        formula.pack(fill="x", padx=18, pady=(0, 12))
        tk.Label(
            formula,
            text="Formula",
            bg=colors["panel"],
            fg=colors["fg"],
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(
            formula,
            text="Safe Now = Cash On Hand + Today Collection − Net Renewal Cash Need − Emergency Buffer",
            bg=colors["panel"],
            fg=colors["fg"],
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(4, 0))
        tk.Label(
            formula,
            text="Forecast Safe adds average future collection separately. It is not mixed with real cash so you can decide safely.",
            bg=colors["panel"],
            fg=colors["muted"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=14, pady=(3, 10))

        controls = tk.Frame(outer, bg=colors["panel"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
        controls.pack(fill="x", padx=18, pady=(0, 12))
        controls_inner = tk.Frame(controls, bg=colors["panel"])
        controls_inner.pack(fill="x", padx=12, pady=10)
        for i in range(7):
            controls_inner.columnconfigure(i, weight=1)

        widgets = [
            ("Date", self.cashctl_date_var, 13),
            ("Cash On Hand", self.cashctl_cash_on_hand_var, 15),
            ("Forecast Days", self.cashctl_forecast_days_var, 8),
            ("Average Window", self.cashctl_avg_window_days_var, 8),
            ("Emergency Buffer %", self.cashctl_buffer_percent_var, 8),
        ]
        for i, (label, var, width) in enumerate(widgets):
            box, _ent = _spina_v21_build_labeled_entry(controls_inner, label, var, width)
            box.grid(row=0, column=i, sticky="ew", padx=(0, 10))

        tk.Button(
            controls_inner,
            text="Today",
            command=lambda: (self.cashctl_date_var.set(date.today().strftime("%Y-%m-%d")), self.refresh_cash_control()),
            bg=colors["card2"],
            fg=colors["fg"],
            activebackground=colors["soft"],
            activeforeground=colors["fg"],
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).grid(row=0, column=5, sticky="ew", padx=(0, 8), pady=(12, 0))

        tk.Button(
            controls_inner,
            text="Calculate",
            command=self.refresh_cash_control,
            bg=colors["green"],
            fg="#ffffff",
            activebackground=colors["green"],
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).grid(row=0, column=6, sticky="ew", pady=(12, 0))

        # KPI cards
        cards = tk.Frame(outer, bg=colors["bg"])
        cards.pack(fill="x", padx=18, pady=(0, 12))
        for i in range(4):
            cards.columnconfigure(i, weight=1, uniform="cashcards")

        self._cashctl_cards = {}
        card_defs = [
            ("safe_now", "Safe Amount Now", "PHP 0.00", "Real cash only", colors["green"]),
            ("forecast_safe", "Forecast Safe Amount", "PHP 0.00", "Includes forecast collection", colors["blue"]),
            ("collection", "Today Collection", "PHP 0.00", "Regular + 7x7", colors["cyan"]),
            ("net_need", "Net Renewal Need", "PHP 0.00", "Reserve minus expected payoff", colors["orange"]),
            ("reserve", "Renewal Reserve", "PHP 0.00", "All active clients", colors["purple"]),
            ("buffer", "Emergency Buffer", "PHP 0.00", "Safety hold", colors["red"]),
            ("average", "Average Daily Collection", "PHP 0.00", "Based on active collection days", colors["yellow"]),
            ("available", "Current Available", "PHP 0.00", "Cash on hand + today", colors["blue"]),
        ]
        for i, (key, title, val, sub, accent) in enumerate(card_defs):
            card, v_lbl, s_lbl = _spina_v21_cash_card(cards, title, val, sub, accent=accent)
            card.grid(row=i // 4, column=i % 4, sticky="nsew", padx=(0 if i % 4 == 0 else 8, 0), pady=(0 if i < 4 else 8, 0), ipady=2)
            self._cashctl_cards[key] = (v_lbl, s_lbl)

        # Charts
        charts = tk.Frame(outer, bg=colors["bg"])
        charts.pack(fill="x", padx=18, pady=(0, 12))
        for i in range(3):
            charts.columnconfigure(i, weight=1, uniform="cashcharts")

        def chart_box(parent, title, subtitle):
            frame = tk.Frame(parent, bg=colors["panel"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
            tk.Label(frame, text=title, bg=colors["panel"], fg=colors["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 0))
            tk.Label(frame, text=subtitle, bg=colors["panel"], fg=colors["muted"], font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=14, pady=(1, 4))
            cv = tk.Canvas(frame, height=185, bg=colors["chart"], highlightthickness=0, bd=0)
            cv.pack(fill="both", expand=True, padx=8, pady=(0, 10))
            return frame, cv

        f1, self.cashctl_flow_canvas = chart_box(charts, "Cash Safety Flow", "Where today's cash goes")
        f1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        f2, self.cashctl_collection_canvas = chart_box(charts, "Today Collection Split", "Regular vs 7x7 collection")
        f2.grid(row=0, column=1, sticky="nsew", padx=(0, 8))

        f3, self.cashctl_risk_canvas = chart_box(charts, "Renewal Pressure", "Reserve needed by priority status")
        f3.grid(row=0, column=2, sticky="nsew")

        # Decision / explanation
        decision = tk.Frame(outer, bg=colors["panel"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
        decision.pack(fill="x", padx=18, pady=(0, 12))
        tk.Label(decision, text="Decision Guide", bg=colors["panel"], fg=colors["fg"], font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(decision, textvariable=self.cashctl_decision_var, bg=colors["panel"], fg=colors["fg"], font=("Segoe UI", 10, "bold"), anchor="w", justify="left", wraplength=1200).pack(fill="x", padx=14, pady=(4, 10))

        # Table
        table_wrap = tk.Frame(outer, bg=colors["panel"], highlightbackground=colors["border"], highlightthickness=1, bd=0)
        table_wrap.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        top = tk.Frame(table_wrap, bg=colors["panel"])
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="All Active Clients included in Renewal Reserve", bg=colors["panel"], fg=colors["fg"], font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")
        self.cashctl_table_summary_var = tk.StringVar(value="Refresh to calculate.")
        tk.Label(top, textvariable=self.cashctl_table_summary_var, bg=colors["panel"], fg=colors["muted"], font=("Segoe UI", 9), anchor="e").pack(side="right")

        _spina_v21_style_cash_table(self)
        cols = ("status", "name", "loan_type", "area", "principal", "completion", "remaining", "due_date", "days_left", "reserve", "reason")
        self.cashctl_tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=10, style="ModernCash.Treeview")
        vsb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.cashctl_tree.yview)
        hsb = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.cashctl_tree.xview)
        self.cashctl_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.cashctl_tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        vsb.pack(side="right", fill="y", padx=(0, 12), pady=(0, 12))
        hsb.pack(side="bottom", fill="x", padx=12)

        headings = {
            "status": "Status", "name": "Client", "loan_type": "Type", "area": "Area",
            "principal": "Principal", "completion": "Done", "remaining": "Remaining",
            "due_date": "Due Date", "days_left": "Days Left", "reserve": "Reserve", "reason": "Reason / Priority"
        }
        widths = {"status": 135, "name": 220, "loan_type": 70, "area": 180, "principal": 110, "completion": 80, "remaining": 110, "due_date": 105, "days_left": 80, "reserve": 110, "reason": 220}
        for col in cols:
            self.cashctl_tree.heading(col, text=headings.get(col, col))
            anchor = "e" if col in ("principal", "completion", "remaining", "days_left", "reserve") else "w"
            self.cashctl_tree.column(col, width=widths.get(col, 100), minwidth=60, anchor=anchor, stretch=True)

        try:
            self.cashctl_tree.tag_configure("finish", background="#234b33" if str(getattr(self, "ui_theme", "dark")).lower().startswith("d") else "#dcfce7")
            self.cashctl_tree.tag_configure("near", background="#4a3a16" if str(getattr(self, "ui_theme", "dark")).lower().startswith("d") else "#fef3c7")
            self.cashctl_tree.tag_configure("due", background="#4a311c" if str(getattr(self, "ui_theme", "dark")).lower().startswith("d") else "#ffedd5")
            self.cashctl_tree.tag_configure("overdue", background="#4a2424" if str(getattr(self, "ui_theme", "dark")).lower().startswith("d") else "#fee2e2")
        except Exception:
            pass

        def redraw(_event=None):
            try:
                data = getattr(self, "_cashctl_last_data", {}) or {}
                _spina_v21_cash_draw_charts(self, data)
            except Exception:
                pass

        for cv in (self.cashctl_flow_canvas, self.cashctl_collection_canvas, self.cashctl_risk_canvas):
            try:
                cv.bind("<Configure>", redraw)
            except Exception:
                pass

        for var in (
            self.cashctl_date_var,
            self.cashctl_cash_on_hand_var,
            self.cashctl_forecast_days_var,
            self.cashctl_avg_window_days_var,
            self.cashctl_buffer_percent_var,
        ):
            try:
                var.trace_add("write", lambda *_: self.refresh_cash_control())
            except Exception:
                pass

        self.refresh_cash_control()

    except Exception as e:
        try:
            _log_exc("v21.cash_control.build_tab", e)
        except Exception:
            pass


def _spina_v21_cash_draw_charts(self, data):
    try:
        c = _spina_v21_cash_colors(self)
        data = data or {}

        current_available = float(data.get("current_available") or 0)
        net_need = float(data.get("net_need") or 0)
        buffer_now = float(data.get("buffer_now") or 0)
        safe_now = float(data.get("safe_now") or 0)
        reg = float(data.get("regular") or 0)
        x7 = float(data.get("7x7") or 0)
        other = float(data.get("other") or 0)
        reserve_rows = list(data.get("reserve_rows") or [])

        # Chart 1: Cash safety flow
        cv = getattr(self, "cashctl_flow_canvas", None)
        if cv is not None:
            cv.delete("all")
            cv.configure(bg=c["chart"])
            w = max(330, int(cv.winfo_width() or 330))
            h = max(180, int(cv.winfo_height() or 180))
            x0, x2 = 28, w - 28
            bar_w = x2 - x0
            maxv = max(1.0, current_available, net_need, buffer_now, max(0.0, safe_now))
            items = [
                ("Available", current_available, c["blue"]),
                ("Renewal Need", net_need, c["orange"]),
                ("Buffer", buffer_now, c["red"]),
                ("Safe Now", max(0.0, safe_now), c["green"]),
            ]
            y = 26
            for label, val, color in items:
                cv.create_text(x0, y + 8, text=label, fill=c["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))
                cv.create_text(x2, y + 8, text=_spina_v21_cash_money_short(val), fill=c["chart_muted"], anchor="e", font=("Segoe UI", 9, "bold"))
                ybar = y + 20
                _spina_v21_cash_round_rect(cv, x0, ybar, x2, ybar + 16, 8, fill=c["track"], outline="")
                bw = int(bar_w * (max(0.0, val) / maxv)) if val > 0 else 0
                if bw:
                    _spina_v21_cash_round_rect(cv, x0, ybar, x0 + max(4, bw), ybar + 16, 8, fill=color, outline="")
                y += 38

            if safe_now <= 0:
                cv.create_text(x0, h - 10, text="Warning: no safe amount after reserve and buffer.", fill=c["red"], anchor="w", font=("Segoe UI", 9, "bold"))
            else:
                cv.create_text(x0, h - 10, text="Safe amount uses real cash only.", fill=c["chart_muted"], anchor="w", font=("Segoe UI", 9, "bold"))

        # Chart 2: collection split
        cv = getattr(self, "cashctl_collection_canvas", None)
        if cv is not None:
            cv.delete("all")
            cv.configure(bg=c["chart"])
            w = max(330, int(cv.winfo_width() or 330))
            h = max(180, int(cv.winfo_height() or 180))
            total = max(0.0, reg + x7 + other)
            x0, x2 = 34, w - 34
            y = 56
            cv.create_text(w // 2, 26, text=_spina_v21_cash_money_short(total), fill=c["chart_fg"], font=("Segoe UI", 22, "bold"))
            cv.create_text(w // 2, 50, text="today collected", fill=c["chart_muted"], font=("Segoe UI", 9, "bold"))
            _spina_v21_cash_round_rect(cv, x0, y + 25, x2, y + 55, 12, fill=c["track"], outline="")

            run_x = x0
            parts = [("Regular", reg, c["blue"]), ("7x7", x7, c["purple"]), ("Other", other, c["yellow"])]
            if total > 0:
                for label, val, color in parts:
                    if val <= 0:
                        continue
                    bw = int((x2 - x0) * (val / total))
                    _spina_v21_cash_round_rect(cv, run_x, y + 25, min(x2, run_x + max(3, bw)), y + 55, 12, fill=color, outline="")
                    run_x += bw

            left_text = "Regular: {} ({:.0f}%)".format(_spina_v21_cash_money_short(reg), (reg / total * 100) if total else 0)
            right_text = "7x7: {} ({:.0f}%)".format(_spina_v21_cash_money_short(x7), (x7 / total * 100) if total else 0)
            cv.create_text(x0, y + 82, text=left_text, fill=c["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))
            cv.create_text(x2, y + 82, text=right_text, fill=c["chart_fg"], anchor="e", font=("Segoe UI", 9, "bold"))
            if other > 0:
                cv.create_text(x0, h - 12, text="Other / unclassified: " + _spina_v21_cash_money_short(other), fill=c["chart_muted"], anchor="w", font=("Segoe UI", 9, "bold"))

        # Chart 3: reserve pressure by status
        cv = getattr(self, "cashctl_risk_canvas", None)
        if cv is not None:
            cv.delete("all")
            cv.configure(bg=c["chart"])
            w = max(340, int(cv.winfo_width() or 340))
            h = max(180, int(cv.winfo_height() or 180))
            groups = [
                ("Finishing Now", c["green"]),
                ("Near Completion", c["yellow"]),
                ("Due Soon", c["orange"]),
                ("Overdue", c["red"]),
                ("Other Active", c["blue"]),
            ]
            totals = {g: 0.0 for g, _ in groups}
            counts = {g: 0 for g, _ in groups}
            for r in reserve_rows:
                st = str(r.get("status") or "Other Active")
                key = st if st in totals else "Other Active"
                totals[key] += float(r.get("reserve_amount") or 0.0)
                counts[key] += 1

            maxv = max([1.0] + list(totals.values()))
            x0, x2 = 30, w - 30
            y = 20
            for label, color in groups:
                val = totals.get(label, 0.0)
                n = counts.get(label, 0)
                if val <= 0 and n <= 0 and label == "Other Active":
                    continue
                cv.create_text(x0, y, text=f"{label} ({n})", fill=c["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))
                cv.create_text(x2, y, text=_spina_v21_cash_money_short(val), fill=c["chart_muted"], anchor="e", font=("Segoe UI", 9, "bold"))
                ybar = y + 11
                _spina_v21_cash_round_rect(cv, x0, ybar, x2, ybar + 16, 8, fill=c["track"], outline="")
                bw = int((x2 - x0) * (val / maxv)) if val > 0 else 0
                if bw:
                    _spina_v21_cash_round_rect(cv, x0, ybar, x0 + max(4, bw), ybar + 16, 8, fill=color, outline="")
                y += 34
                if y > h - 18:
                    break

    except Exception as e:
        try:
            _log_exc("v21.cash_control.draw_charts", e)
        except Exception:
            pass
