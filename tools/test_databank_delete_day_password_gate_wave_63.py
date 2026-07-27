"""Regression for the Wave 63 fail-closed Delete Day password gate."""
from __future__ import annotations

import tkinter.messagebox as messagebox
import tkinter.simpledialog as simpledialog

from spina_app import databank_delete_day as delete_day


class FakeCursor:
    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        return self

    def fetchone(self):
        return (1, 100.0)


class FakeConn:
    def cursor(self):
        return FakeCursor()


class FakeDB:
    def __init__(self):
        self.conn = FakeConn()
        self.delete_calls = []

    def get_databank_day_close(self, ds, loan_type=None):
        return None

    def delete_transactions_for_day(self, ds, **kwargs):
        self.delete_calls.append((ds, kwargs))
        return {"deleted": 1}


class FakeApp:
    def __init__(self):
        self.root = object()
        self.db = FakeDB()
        self.grid_year = 2026
        self.grid_month = 7
        self._dbank_last_day = 27
        self.user_name = "System User"
        self.refresh_calls = []

    def _prompt_current_password(self, **kwargs):
        raise RuntimeError("password service unavailable")

    def refresh_data_grid(self):
        self.refresh_calls.append("grid")

    def refresh_reports(self):
        self.refresh_calls.append("reports")

    def refresh_audit_tab(self):
        self.refresh_calls.append("audit")


def main() -> None:
    notices = []
    original_askstring = simpledialog.askstring
    original_askyesno = messagebox.askyesno
    original_showerror = messagebox.showerror
    original_showinfo = messagebox.showinfo
    try:
        simpledialog.askstring = lambda *args, **kwargs: "2026-07-27"
        messagebox.askyesno = lambda *args, **kwargs: True
        messagebox.showerror = lambda title, text, **kwargs: notices.append(("error", title, text))
        messagebox.showinfo = lambda title, text, **kwargs: notices.append(("info", title, text))
        delete_day.configure_databank_delete_day_dependencies({
            "data_path": lambda name: "",
            "fmt_currency": lambda value: f"USD {value:,.2f}",
        })

        app = FakeApp()
        delete_day.open_delete_day_dialog(app)

        assert app.db.delete_calls == []
        assert app.refresh_calls == []
        assert notices == [(
            "error",
            "Delete a Day",
            "Password verification failed:\npassword service unavailable",
        )]
    finally:
        simpledialog.askstring = original_askstring
        messagebox.askyesno = original_askyesno
        messagebox.showerror = original_showerror
        messagebox.showinfo = original_showinfo

    print("Wave 63 Delete Day password gate passed")


if __name__ == "__main__":
    main()
