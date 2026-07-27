"""Dashboard chart presentation extracted in Wave 51."""
from __future__ import annotations

import tkinter as tk

_DASHBOARD_CHART_DEPENDENCIES = {}
DASHBOARD_CHART_TARGETS = ('_spina_v18_draw_dashboard_charts', '_spina_v20_fix_chart_titles', '_spina_v20_draw_dashboard_charts')
DASHBOARD_CHART_SOURCE_LINES = {'_spina_v18_draw_dashboard_charts': 112, '_spina_v20_fix_chart_titles': 28, '_spina_v20_draw_dashboard_charts': 134}
DASHBOARD_CHART_SOURCE_SHA256 = {'_spina_v18_draw_dashboard_charts': 'd8c62b3f57ba4de33e2fe5b2c3d706e7cf0f7213b2edfedfb20ffa39fbb31c5d', '_spina_v20_fix_chart_titles': 'f545fb2e927fe39486312e806bb6df12b58fc501fa2baa12dbd9835b469fe1c1', '_spina_v20_draw_dashboard_charts': 'cc50e2f5571433e55685fa621d92a8e304110b87200808b40a88b951673945a6'}
DASHBOARD_CHART_SIGNATURES = {'_spina_v18_draw_dashboard_charts': 'self, rows', '_spina_v20_fix_chart_titles': 'self', '_spina_v20_draw_dashboard_charts': 'self, rows'}
DASHBOARD_CHART_CALLS = {'_spina_v18_draw_dashboard_charts': ['_log_exc', '_spina_v18_dashboard_palette', '_spina_v18_draw_round_rect', '_spina_v18_fmt_money_compact', '_spina_v18_patch_dashboard_chart_cards', 'counts.get', 'counts.values', 'cv.configure', 'cv.create_arc', 'cv.create_oval', 'cv.create_text', 'cv.delete', 'cv.winfo_height', 'cv.winfo_width', 'enumerate', 'float', 'format', 'getattr', 'int', 'list', 'lower', 'max', 'min', 'r.get', 'replace', 'str', 'sum'], '_spina_v20_fix_chart_titles': ['child.cget', 'child.configure', 'getattr', 'isinstance', 'parent.winfo_children', 'str'], '_spina_v20_draw_dashboard_charts': ['_log_exc', '_spina_v20_dash_palette', '_spina_v20_fix_chart_titles', '_spina_v20_money', '_spina_v20_round_rect', 'balances.get', 'balances.values', 'counts.get', 'cv.configure', 'cv.create_text', 'cv.delete', 'cv.winfo_height', 'cv.winfo_width', 'float', 'getattr', 'int', 'len', 'list', 'lower', 'max', 'r.get', 'replace', 'str', 'sum']}
DASHBOARD_CHART_REQUIRED_DEPENDENCIES = ('_log_exc', '_spina_v18_dashboard_palette', '_spina_v18_draw_round_rect', '_spina_v18_fmt_money_compact', '_spina_v18_patch_dashboard_chart_cards', '_spina_v20_dash_palette', '_spina_v20_money', '_spina_v20_round_rect')
_PROTECTED_GLOBALS = {
    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',
    '__name__', '__package__', '__spec__', 'tk', '_PROTECTED_GLOBALS',
    '_DASHBOARD_CHART_DEPENDENCIES', 'configure_dashboard_chart_dependencies',
    'DASHBOARD_CHART_TARGETS', 'DASHBOARD_CHART_SOURCE_LINES',
    'DASHBOARD_CHART_SOURCE_SHA256', 'DASHBOARD_CHART_SIGNATURES',
    'DASHBOARD_CHART_CALLS', 'DASHBOARD_CHART_REQUIRED_DEPENDENCIES',
}


def configure_dashboard_chart_dependencies(namespace):
    _DASHBOARD_CHART_DEPENDENCIES.clear()
    missing = []
    for name in DASHBOARD_CHART_REQUIRED_DEPENDENCIES:
        if name not in namespace:
            missing.append(name)
            continue
        value = namespace[name]
        _DASHBOARD_CHART_DEPENDENCIES[name] = value
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value
    if missing:
        raise RuntimeError('Missing dashboard chart dependencies: ' + ', '.join(missing))


def _spina_v18_draw_dashboard_charts(self, rows):
    try:
        _spina_v18_patch_dashboard_chart_cards(self)
        p = _spina_v18_dashboard_palette(self)
        rows = list(rows or [])

        total = sum(float(r.get("total_to_pay") or 0) for r in rows)
        paid = sum(float(r.get("paid") or 0) for r in rows)
        remaining = sum(float(r.get("remaining") or 0) for r in rows)
        pct = (paid / total * 100.0) if total > 0 else 0.0
        pct_clamped = min(100.0, max(0.0, pct))

        # 1) Progress gauge - high contrast
        cv = getattr(self, "dashboard_gauge_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(300, int(cv.winfo_width() or 300))
            h = max(180, int(cv.winfo_height() or 180))
            cv.configure(bg=p["chart"])

            cx, cy = w // 2, 82
            r = min(58, max(42, min(w, h) // 3))
            box = (cx-r, cy-r, cx+r, cy+r)

            cv.create_oval(*box, outline=p["track"], width=18)
            cv.create_arc(*box, start=90, extent=-pct_clamped * 3.6, outline=p["green"], width=18, style="arc")
            cv.create_text(cx, cy-6, text="{:.0f}%".format(pct), fill=p["chart_fg"], font=("Segoe UI", 24, "bold"))
            cv.create_text(cx, cy+24, text="collected", fill=p["chart_muted"], font=("Segoe UI", 9, "bold"))

            # Mini progress line
            x1, y1, x2, y2 = 28, h - 46, w - 28, h - 30
            _spina_v18_draw_round_rect(cv, x1, y1, x2, y2, 8, fill=p["track"], outline="")
            _spina_v18_draw_round_rect(cv, x1, y1, x1 + ((x2-x1) * pct_clamped / 100.0), y2, 8, fill=p["green"], outline="")
            cv.create_text(x1, h-66, text="Paid: " + _spina_v18_fmt_money_compact(paid), fill=p["chart_muted"], anchor="w", font=("Segoe UI", 9, "bold"))
            cv.create_text(x2, h-66, text="Remaining: " + _spina_v18_fmt_money_compact(remaining), fill=p["chart_muted"], anchor="e", font=("Segoe UI", 9, "bold"))

        # 2) Status chart - visible labels and counts
        cv = getattr(self, "dashboard_status_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(360, int(cv.winfo_width() or 360))
            h = max(180, int(cv.winfo_height() or 180))
            cv.configure(bg=p["chart"])

            statuses = [
                ("Finishing Now", p["green"]),
                ("Near Completion", p["yellow"]),
                ("Due Soon", p["orange"]),
                ("Overdue", p["red"]),
                ("Complete", p["blue"]),
            ]
            counts = {s: 0 for s, _ in statuses}
            for r in rows:
                s = str(r.get("status") or "")
                if s in counts:
                    counts[s] += 1
            max_count = max([1] + list(counts.values()))

            top = 18
            gap = 29
            label_x = 18
            bar_x = 146
            bar_right = w - 48
            for i, (s, color) in enumerate(statuses):
                y = top + i * gap
                n = counts.get(s, 0)
                cv.create_text(label_x, y+8, text=s, fill=p["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))
                _spina_v18_draw_round_rect(cv, bar_x, y, bar_right, y+17, 8, fill=p["track"], outline="")
                bw = max(5, int((bar_right - bar_x) * (n / max_count))) if n else 0
                if bw:
                    _spina_v18_draw_round_rect(cv, bar_x, y, bar_x + bw, y+17, 8, fill=color, outline="")
                cv.create_text(w - 18, y+8, text=str(n), fill=p["chart_fg"], anchor="e", font=("Segoe UI", 9, "bold"))

        # 3) Loan type remaining - easier comparison
        cv = getattr(self, "dashboard_type_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(340, int(cv.winfo_width() or 340))
            h = max(180, int(cv.winfo_height() or 180))
            cv.configure(bg=p["chart"])

            by_type = {"Regular": 0.0, "7x7": 0.0}
            count_by_type = {"Regular": 0, "7x7": 0}
            for r in rows:
                lt_raw = str(r.get("loan_type") or "").lower().replace("×", "x").replace(" ", "")
                lt = "7x7" if lt_raw == "7x7" else "Regular"
                by_type[lt] += float(r.get("remaining") or 0)
                count_by_type[lt] += 1

            max_val = max(1.0, by_type["Regular"], by_type["7x7"])
            x0, x2 = 34, w - 30
            bar_w = x2 - x0

            for idx, (label, color) in enumerate((("Regular", p["blue"]), ("7x7", p["purple"]))):
                y = 36 + idx * 70
                val = by_type[label]
                bw = int(bar_w * (val / max_val))
                cv.create_text(x0, y-16, text=f"{label} ({count_by_type[label]})", fill=p["chart_fg"], anchor="w", font=("Segoe UI", 10, "bold"))
                cv.create_text(x2, y-16, text=_spina_v18_fmt_money_compact(val), fill=p["chart_muted"], anchor="e", font=("Segoe UI", 10, "bold"))
                _spina_v18_draw_round_rect(cv, x0, y, x2, y+31, 10, fill=p["track"], outline="")
                if bw:
                    _spina_v18_draw_round_rect(cv, x0, y, x0+bw, y+31, 10, fill=color, outline="")
                share = (val / max(1.0, by_type["Regular"] + by_type["7x7"]) * 100.0)
                cv.create_text(x0+10, y+15, text="{:.0f}% of remaining".format(share), fill="#ffffff", anchor="w", font=("Segoe UI", 9, "bold"))

            cv.create_text(x0, h-17, text="Total visible remaining: " + _spina_v18_fmt_money_compact(by_type["Regular"] + by_type["7x7"]), fill=p["chart_muted"], anchor="w", font=("Segoe UI", 9, "bold"))

    except Exception as e:
        try:
            _log_exc("v18.draw_dashboard_charts", e)
        except Exception:
            pass


def _spina_v20_fix_chart_titles(self):
    """Rename the chart labels without rebuilding the whole tab."""
    try:
        label_map = {
            "Collection Progress": "Active Clients",
            "Paid vs. total payable": "Regular / 7x7 count",
            "Remaining by Loan Type": "At-Risk Balance",
            "Regular vs. 7x7 remaining balance": "Overdue / due soon / finishing balance",
            "How many clients are in each condition": "All labels visible + easy counts",
        }

        for canvas_name in ("dashboard_gauge_canvas", "dashboard_status_canvas", "dashboard_type_canvas"):
            cv = getattr(self, canvas_name, None)
            if cv is None:
                continue
            parent = getattr(cv, "master", None)
            if parent is None:
                continue
            for child in parent.winfo_children():
                try:
                    if isinstance(child, tk.Label):
                        txt = str(child.cget("text") or "")
                        if txt in label_map:
                            child.configure(text=label_map[txt])
                except Exception:
                    pass
    except Exception:
        pass


def _spina_v20_draw_dashboard_charts(self, rows):
    """Replace old progress/remaining charts with more useful active-client charts."""
    try:
        p = _spina_v20_dash_palette(self)
        rows = list(rows or [])

        _spina_v20_fix_chart_titles(self)

        # Ensure canvases are high contrast.
        for cv in (
            getattr(self, "dashboard_gauge_canvas", None),
            getattr(self, "dashboard_status_canvas", None),
            getattr(self, "dashboard_type_canvas", None),
        ):
            try:
                cv.configure(bg=p["chart"], highlightthickness=0, bd=0)
            except Exception:
                pass

        total_active = len(rows)
        regular_count = sum(1 for r in rows if str(r.get("loan_type") or "") == "Regular")
        seven_count = sum(1 for r in rows if str(r.get("loan_type") or "").lower().replace("×", "x").replace(" ", "") == "7x7")
        remaining_all = sum(float(r.get("remaining") or 0) for r in rows)

        # Chart 1: Active Clients count/mix (more relevant than paid % of all loans)
        cv = getattr(self, "dashboard_gauge_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(320, int(cv.winfo_width() or 320))
            h = max(180, int(cv.winfo_height() or 180))
            cv.configure(bg=p["chart"])

            cv.create_text(w//2, 42, text=str(total_active), fill=p["chart_fg"], font=("Segoe UI", 32, "bold"))
            cv.create_text(w//2, 75, text="active loan records", fill=p["chart_muted"], font=("Segoe UI", 10, "bold"))

            x1, x2 = 34, w - 34
            total_for_mix = max(1, regular_count + seven_count)
            reg_w = int((x2-x1) * (regular_count / total_for_mix))
            y = 108
            _spina_v20_round_rect(cv, x1, y, x2, y+28, 12, fill=p["track"], outline="")
            if reg_w:
                _spina_v20_round_rect(cv, x1, y, x1+reg_w, y+28, 12, fill=p["blue"], outline="")
            if seven_count:
                _spina_v20_round_rect(cv, x1+reg_w, y, x2, y+28, 12, fill=p["purple"], outline="")

            cv.create_text(x1, y+48, text=f"Regular: {regular_count}", fill=p["chart_fg"], anchor="w", font=("Segoe UI", 10, "bold"))
            cv.create_text(x2, y+48, text=f"7x7: {seven_count}", fill=p["chart_fg"], anchor="e", font=("Segoe UI", 10, "bold"))

        # Chart 2: Client Status with visible labels
        cv = getattr(self, "dashboard_status_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(390, int(cv.winfo_width() or 390))
            cv.configure(bg=p["chart"])

            statuses = [
                ("In Progress", p["blue"]),
                ("Finishing Now", p["green"]),
                ("Near Completion", p["yellow"]),
                ("Due Soon", p["orange"]),
                ("Overdue", p["red"]),
                ("Complete", p["purple"]),
            ]
            counts = {s: 0 for s, _ in statuses}
            for r in rows:
                s = str(r.get("status") or "In Progress")
                counts[s] = counts.get(s, 0) + 1

            max_count = max([1] + [counts.get(s, 0) for s, _ in statuses])
            label_x = 18
            bar_x = 152
            bar_right = w - 54
            y = 14
            gap = 26
            for s, color in statuses:
                n = counts.get(s, 0)
                cv.create_text(label_x, y+8, text=s, fill=p["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))
                _spina_v20_round_rect(cv, bar_x, y, bar_right, y+17, 8, fill=p["track"], outline="")
                bw = int((bar_right - bar_x) * (n / max_count)) if n else 0
                if bw > 0:
                    _spina_v20_round_rect(cv, bar_x, y, bar_x + max(5, bw), y+17, 8, fill=color, outline="")
                cv.create_text(w - 18, y+8, text=str(n), fill=p["chart_fg"], anchor="e", font=("Segoe UI", 9, "bold"))
                y += gap

        # Chart 3: At-risk remaining balance (more useful than remaining by loan type)
        cv = getattr(self, "dashboard_type_canvas", None)
        if cv is not None:
            cv.delete("all")
            w = max(360, int(cv.winfo_width() or 360))
            h = max(180, int(cv.winfo_height() or 180))
            cv.configure(bg=p["chart"])

            risk_defs = [
                ("Overdue", p["red"]),
                ("Due Soon", p["orange"]),
                ("Near Completion", p["yellow"]),
                ("Finishing Now", p["green"]),
                ("Other Active", p["blue"]),
            ]
            balances = {k: 0.0 for k, _ in risk_defs}
            counts = {k: 0 for k, _ in risk_defs}
            for r in rows:
                st = str(r.get("status") or "In Progress")
                key = st if st in balances else "Other Active"
                balances[key] += float(r.get("remaining") or 0)
                counts[key] += 1

            total_risk = sum(balances.values()) or 1.0
            max_bal = max([1.0] + list(balances.values()))
            x0, x2 = 34, w - 32
            y = 24
            for label, color in risk_defs:
                val = balances.get(label, 0.0)
                if val <= 0 and label not in ("Overdue", "Due Soon", "Near Completion"):
                    continue

                cv.create_text(x0, y-2, text=f"{label} ({counts.get(label, 0)})", fill=p["chart_fg"], anchor="w", font=("Segoe UI", 9, "bold"))
                cv.create_text(x2, y-2, text=_spina_v20_money(val), fill=p["chart_muted"], anchor="e", font=("Segoe UI", 9, "bold"))
                ybar = y + 11
                _spina_v20_round_rect(cv, x0, ybar, x2, ybar+18, 8, fill=p["track"], outline="")
                bw = int((x2-x0) * (val / max_bal)) if val else 0
                if bw > 0:
                    _spina_v20_round_rect(cv, x0, ybar, x0+max(4, bw), ybar+18, 8, fill=color, outline="")
                y += 35
                if y > h - 22:
                    break

            cv.create_text(x0, h-14, text="Visible remaining total: " + _spina_v20_money(remaining_all), fill=p["chart_muted"], anchor="w", font=("Segoe UI", 9, "bold"))

    except Exception as e:
        try:
            _log_exc("v20.draw_dashboard_charts", e)
        except Exception:
            pass
