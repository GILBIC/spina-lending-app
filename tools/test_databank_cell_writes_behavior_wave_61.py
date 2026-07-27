"""Behavior regression for Wave 61 Data Bank payment mutations."""
from __future__ import annotations

import tkinter.messagebox as messagebox
import tkinter.simpledialog as simpledialog

from spina_app import databank_cell_writes as writes


_MISSING = object()


class FakeEntry:
    def __init__(self, value: str):
        self.value = value
        self.destroyed = False

    def get(self):
        return self.value

    def destroy(self):
        self.destroyed = True


class FakeTree:
    def __init__(self):
        self.rows = {"row1": {"client": "Alice", "d5": "100"}}

    def get_children(self):
        return list(self.rows)

    def set(self, item, column, value=_MISSING):
        if value is _MISSING:
            return self.rows[item].get(column, "")
        self.rows[item][column] = value
        return value


class FakeDB:
    def __init__(self):
        self.next_row = None
        self.get_calls = []
        self.add_calls = []
        self.delete_calls = []
        self.raise_add = None
        self.raise_delete = None

    def get_transaction(self, client, dt, **kwargs):
        self.get_calls.append((client, dt, kwargs))
        return self.next_row

    def add_or_update_transaction(self, client, dt, amount, description="", loan_type=None):
        if self.raise_add:
            raise self.raise_add
        self.add_calls.append((client, dt, amount, description, loan_type))

    def delete_transaction(self, client, dt):
        if self.raise_delete:
            raise self.raise_delete
        self.delete_calls.append((client, dt))


class FakeApp:
    def __init__(self):
        self.db = FakeDB()
        self.root = object()
        self.days_tree = FakeTree()
        self.grid_year = 2026
        self.grid_month = 7
        self._dbank_last_client = "Alice"
        self._dbank_last_day = 5
        self.refreshes = 0
        self.toolbar_updates = 0
        self.picked_reason = "Sick"
        self.prefills = []
        self.mode = "Regular"

    def refresh_data_grid(self):
        self.refreshes += 1

    def _update_data_toolbar(self):
        self.toolbar_updates += 1

    def _pick_missed_reason(self, parent, prefill_text=""):
        self.prefills.append((parent, prefill_text))
        return self.picked_reason

    def _mode_filter(self):
        return self.mode


def main() -> None:
    notices = []
    messagebox.showerror = lambda title, text: notices.append(("error", title, text))
    messagebox.showinfo = lambda title, text: notices.append(("info", title, text))
    simpledialog.askstring = lambda *args, **kwargs: kwargs.get("initialvalue", "")
    writes.configure_databank_cell_write_dependencies({"_log_suppressed_once": lambda *args, **kwargs: None})

    app = FakeApp()
    app.db.next_row = {"payment": 75.0, "description": "Old note"}
    entry = FakeEntry("125.50")
    writes._save_cell_edit(app, "Alice", 5, "2026-07-05", entry)
    assert app.db.add_calls == [("Alice", "2026-07-05", 125.5, "", None)]
    assert entry.destroyed and app.refreshes == 1

    app = FakeApp()
    app.db.next_row = {"payment": 0.0, "description": "Old reason"}
    app.picked_reason = "Sick; Out of town"
    entry = FakeEntry("0")
    writes._save_cell_edit(app, "Alice", 5, "2026-07-05", entry)
    assert app.prefills[-1][1] == "Old reason"
    assert app.db.add_calls == [("Alice", "2026-07-05", 0.0, "Sick; Out of town", None)]
    assert entry.destroyed and app.refreshes == 1

    app = FakeApp()
    app.picked_reason = None
    entry = FakeEntry("")
    writes._save_cell_edit(app, "Alice", 5, "2026-07-05", entry)
    assert not app.db.add_calls and entry.destroyed and app.refreshes == 0

    app = FakeApp()
    entry = FakeEntry("not-a-number")
    writes._save_cell_edit(app, "Alice", 5, "2026-07-05", entry)
    assert not app.db.add_calls and entry.destroyed
    assert notices[-1][:2] == ("error", "Invalid")

    app = FakeApp()
    app.db.next_row = None
    writes.delete_selected_cell(app)
    assert not app.db.delete_calls
    assert app.days_tree.rows["row1"]["d5"] == ""
    assert app.toolbar_updates == 1

    app = FakeApp()
    app.db.next_row = {"payment": 100.0, "description": ""}
    writes.delete_selected_cell(app)
    assert app.db.delete_calls == [("Alice", "2026-07-05")]
    assert app.days_tree.rows["row1"]["d5"] == ""
    assert app.toolbar_updates == 1 and app.refreshes == 0

    app = FakeApp()
    app.db.next_row = {"payment": 100.0, "description": ""}
    app.days_tree.rows["row1"]["client"] = "Bob"
    writes.delete_selected_cell(app)
    assert app.db.delete_calls == [("Alice", "2026-07-05")]
    assert app.refreshes == 1 and app.toolbar_updates == 1

    app = FakeApp()
    app._dbank_last_client = None
    writes.delete_selected_cell(app)
    assert notices[-1] == ("info", "Delete", "Click a payment cell first (right grid).")

    app = FakeApp()
    app.mode = "7x7"
    app.db.next_row = {"payment": 0.0, "description": "Prior reason"}
    app.picked_reason = "Out of town"
    writes._mark_missed_for_selected(app)
    assert app.db.get_calls == [("Alice", "2026-07-05", {"loan_type": "7x7"})]
    assert app.prefills[-1] == (app.root, "Prior reason")
    assert app.db.add_calls == [("Alice", "2026-07-05", 0.0, "Out of town", "7x7")]
    assert app.refreshes == 1

    app = FakeApp()
    app.picked_reason = None
    writes._mark_missed_for_selected(app)
    assert not app.db.add_calls and app.refreshes == 0

    app = FakeApp()
    app._dbank_last_day = None
    writes._mark_missed_for_selected(app)
    assert notices[-1] == ("info", "Missed Payment", "Click a day cell first (right grid).")

    print("Wave 61 payment mutation behavior passed")


if __name__ == "__main__":
    main()
