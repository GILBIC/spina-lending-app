"""Real Tkinter behavior test for Wave 58 System Data summary helpers."""
from __future__ import annotations

import tkinter as tk

import spina_app.system_data_summary_presentation as module


class FakeDB:
    def __init__(self):
        self.calls = []
        self.record = {
            "expected_amount": 3500,
            "actual_cash": 3450,
            "variance": -50,
            "variance_status": "Short",
            "variance_workflow_status": "Reviewed",
            "is_closed": 1,
            "note": "Safe test record",
        }

    def get_databank_daily_total(self, date_s, loan_type=None):
        self.calls.append(("total", date_s, loan_type))
        return 2500 if loan_type == "Regular" else 1000

    def get_databank_day_close(self, date_s):
        self.calls.append(("close", date_s))
        return self.record


class FakeApp:
    _system_data_get_date = module._system_data_get_date
    _system_data_use_focus_date = module._system_data_use_focus_date
    _system_data_refresh_summary = module._system_data_refresh_summary

    def __init__(self, root):
        self.root = root
        self.db = FakeDB()
        self.system_data_date_var = tk.StringVar(root, value="")
        self.system_data_summary_var = tk.StringVar(root, value="")

    def _get_databank_focus_date(self):
        return "2026-07-27"


def main() -> None:
    module.configure_system_data_summary_dependencies({
        "fmt_currency": lambda value: f"${float(value):,.2f}",
        "_log_suppressed_once": lambda *args, **kwargs: None,
    })
    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp(root)
        app._system_data_use_focus_date()
        assert app.system_data_date_var.get() == "2026-07-27"
        assert app._system_data_get_date() == "2026-07-27"

        app._system_data_refresh_summary()
        assert app.db.calls == [
            ("total", "2026-07-27", "Regular"),
            ("total", "2026-07-27", "7x7"),
            ("close", "2026-07-27"),
        ]
        summary = app.system_data_summary_var.get()
        for expected_line in (
            "Date: 2026-07-27",
            "Regular Expected:",
            "7x7 Expected:",
            "Total Expected:",
            "Actual Cash:",
            "Variance:",
            "Short",
            "Workflow: Reviewed | Status: Closed",
            "Note: Safe test record",
        ):
            assert expected_line in summary, (expected_line, summary)

        app.db.calls.clear()
        app.db.record = None
        app._system_data_refresh_summary()
        open_summary = app.system_data_summary_var.get()
        for expected_line in (
            "Date: 2026-07-27",
            "Regular Expected:",
            "7x7 Expected:",
            "Total Expected:",
            "No Daily Close record yet for this date.",
        ):
            assert expected_line in open_summary, (expected_line, open_summary)
        assert "Actual Cash:" not in open_summary
        print("Wave 58 real Tkinter System Data summary behavior test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
