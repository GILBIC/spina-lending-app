from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import dashboard_chart_presentation as charts

PALETTE = {
    "chart": "#111827",
    "chart_fg": "#ffffff",
    "chart_muted": "#cbd5e1",
    "track": "#334155",
    "blue": "#3b82f6",
    "green": "#22c55e",
    "yellow": "#f59e0b",
    "orange": "#fb923c",
    "red": "#ef4444",
    "purple": "#8b5cf6",
}


def round_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    del radius
    return canvas.create_rectangle(x1, y1, x2, y2, **kwargs)


class FakeApp:
    pass


def chart_frame(root, title):
    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True)
    label = tk.Label(frame, text=title)
    label.pack()
    canvas = tk.Canvas(frame, width=420, height=220)
    canvas.pack(fill="both", expand=True)
    return frame, label, canvas


def main() -> None:
    errors = []
    charts.configure_dashboard_chart_dependencies({
        "_log_exc": lambda context, exc=None: errors.append((context, str(exc))),
        "_spina_v18_dashboard_palette": lambda _self=None: PALETTE,
        "_spina_v18_draw_round_rect": round_rect,
        "_spina_v18_fmt_money_compact": lambda value: f"PHP {float(value):,.0f}",
        "_spina_v18_patch_dashboard_chart_cards": lambda _self: None,
        "_spina_v20_dash_palette": lambda _self=None: PALETTE,
        "_spina_v20_money": lambda value: f"PHP {float(value):,.2f}",
        "_spina_v20_round_rect": round_rect,
    })

    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp()
        _f1, label1, app.dashboard_gauge_canvas = chart_frame(root, "Collection Progress")
        _f2, label2, app.dashboard_status_canvas = chart_frame(root, "How many clients are in each condition")
        _f3, label3, app.dashboard_type_canvas = chart_frame(root, "Remaining by Loan Type")
        root.update_idletasks()
        root.update()

        rows = [
            {
                "name": "Regular Client",
                "loan_type": "Regular",
                "status": "In Progress",
                "total_to_pay": 12000.0,
                "paid": 4500.0,
                "remaining": 7500.0,
            },
            {
                "name": "Seven Client",
                "loan_type": "7x7",
                "status": "Due Soon",
                "total_to_pay": 7000.0,
                "paid": 3000.0,
                "remaining": 4000.0,
            },
            {
                "name": "Finishing Client",
                "loan_type": "Regular",
                "status": "Finishing Now",
                "total_to_pay": 5000.0,
                "paid": 4800.0,
                "remaining": 200.0,
            },
            {
                "name": "Overdue Client",
                "loan_type": "Regular",
                "status": "Overdue",
                "total_to_pay": 8000.0,
                "paid": 2000.0,
                "remaining": 6000.0,
            },
        ]

        charts._spina_v18_draw_dashboard_charts(app, rows)
        root.update_idletasks()
        root.update()
        v18_counts = [
            len(app.dashboard_gauge_canvas.find_all()),
            len(app.dashboard_status_canvas.find_all()),
            len(app.dashboard_type_canvas.find_all()),
        ]
        assert all(count > 0 for count in v18_counts), v18_counts

        charts._spina_v20_draw_dashboard_charts(app, rows)
        root.update_idletasks()
        root.update()
        v20_counts = [
            len(app.dashboard_gauge_canvas.find_all()),
            len(app.dashboard_status_canvas.find_all()),
            len(app.dashboard_type_canvas.find_all()),
        ]
        assert all(count > 0 for count in v20_counts), v20_counts
        assert label1.cget("text") == "Active Clients"
        assert label2.cget("text") == "All labels visible + easy counts"
        assert label3.cget("text") == "At-Risk Balance"
        assert not errors, errors
        print("Wave 51 dashboard-chart Tkinter smoke test passed.")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
