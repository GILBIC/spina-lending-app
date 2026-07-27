"""Real-Tkinter and fake-database behavior regression for Wave 62 Delete Day."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.simpledialog as simpledialog

from spina_app import databank_delete_day as delete_day


class FakeCursor:
    def __init__(self, db):
        self.db = db

    def execute(self, sql, params):
        self.db.query_calls.append((sql, params))
        if self.db.raise_query:
            raise self.db.raise_query
        return self

    def fetchone(self):
        return self.db.count_row


class FakeConn:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return FakeCursor(self.db)


class FakeDB:
    def __init__(self):
        self.conn = FakeConn(self)
        self.count_row = (2, 350.0)
        self.close_record = None
        self.query_calls = []
        self.close_calls = []
        self.delete_calls = []
        self.delete_result = {"deleted": 2, "import_log_cleared": 1, "backup_path": "C:/backup/test.zip"}
        self.raise_query = None
        self.raise_delete = None

    def get_databank_day_close(self, ds, loan_type=None):
        self.close_calls.append((ds, loan_type))
        return self.close_record

    def delete_transactions_for_day(self, ds, **kwargs):
        if self.raise_delete:
            raise self.raise_delete
        self.delete_calls.append((ds, kwargs))
        return self.delete_result


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.db = FakeDB()
        self.grid_year = 2026
        self.grid_month = 7
        self._dbank_last_day = 5
        self.user_name = "System User"
        self.password_ok = True
        self.password_calls = []
        self.refresh_grid = 0
        self.refresh_report = 0
        self.refresh_audit = 0

    def _prompt_current_password(self, **kwargs):
        self.password_calls.append(kwargs)
        return self.password_ok

    def refresh_data_grid(self):
        self.refresh_grid += 1

    def refresh_reports(self):
        self.refresh_report += 1

    def refresh_audit_tab(self):
        self.refresh_audit += 1


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    notices = []
    answers = {"date": "2026-07-05", "confirm": True}
    simpledialog.askstring = lambda *args, **kwargs: answers["date"]
    messagebox.askyesno = lambda *args, **kwargs: answers["confirm"]
    messagebox.showerror = lambda title, text, **kwargs: notices.append(("error", title, text))
    messagebox.showinfo = lambda title, text, **kwargs: notices.append(("info", title, text))

    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "encoder_import_log.json"
        log_path.write_text(json.dumps({
            "2026-07-05|Alice": {"date": "2026-07-05"},
            "2026-07-06|Bob": {"date": "2026-07-06"},
        }), encoding="utf-8")
        delete_day.configure_databank_delete_day_dependencies({
            "data_path": lambda name: str(log_path),
            "fmt_currency": lambda value: f"USD {value:,.2f}",
        })

        app = FakeApp(root)
        delete_day.open_delete_day_dialog(app)
        assert app.db.query_calls and app.db.close_calls == [("2026-07-05", None)]
        assert app.password_calls == [{
            "title": "Delete a Day",
            "prompt": "Enter your current account password to delete this day.",
        }]
        assert app.db.delete_calls == [(
            "2026-07-05",
            {"changed_by": "System User", "source": "databank:delete_day_button", "reset_close": True},
        )]
        assert (app.refresh_grid, app.refresh_report, app.refresh_audit) == (1, 1, 1)
        assert notices[-1][0:2] == ("info", "Delete a Day")
        assert "Deleted 2 Data Bank transaction row(s)" in notices[-1][2]
        assert "Encoder import-log cleared: 1" in notices[-1][2]
        assert "C:/backup/test.zip" in notices[-1][2]

        app = FakeApp(root)
        answers["date"] = None
        delete_day.open_delete_day_dialog(app)
        assert not app.db.delete_calls and not app.password_calls

        app = FakeApp(root)
        answers["date"] = "not-a-date"
        delete_day.open_delete_day_dialog(app)
        assert notices[-1] == ("error", "Delete a Day", "Invalid date. Use YYYY-MM-DD.")
        assert not app.db.delete_calls

        app = FakeApp(root)
        answers["date"] = "2026-07-05"
        answers["confirm"] = False
        delete_day.open_delete_day_dialog(app)
        assert not app.password_calls and not app.db.delete_calls

        app = FakeApp(root)
        answers["confirm"] = True
        app.password_ok = False
        delete_day.open_delete_day_dialog(app)
        assert app.password_calls and not app.db.delete_calls

        app = FakeApp(root)
        app.db.count_row = (0, 0.0)
        app.db.close_record = None
        log_path.write_text("{}", encoding="utf-8")
        delete_day.open_delete_day_dialog(app)
        assert notices[-1] == ("info", "Delete a Day", "No Data Bank entries or import-log markers found for 2026-07-05.")
        assert not app.password_calls and not app.db.delete_calls

        app = FakeApp(root)
        app.db.raise_delete = RuntimeError("backup failed")
        log_path.write_text(json.dumps({"2026-07-05|Alice": {"date": "2026-07-05"}}), encoding="utf-8")
        delete_day.open_delete_day_dialog(app)
        assert notices[-1][0:2] == ("error", "Delete a Day")
        assert "backup failed" in notices[-1][2]
        assert (app.refresh_grid, app.refresh_report, app.refresh_audit) == (0, 0, 0)

    root.destroy()
    print("Wave 62 Delete Day behavior passed")


if __name__ == "__main__":
    main()
