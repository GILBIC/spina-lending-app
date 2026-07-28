from __future__ import annotations

import os
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from spina_app import backup_history_presentation as presentation


class Dialogs:
    def __init__(self):
        self.warnings = []
        self.infos = []
        self.errors = []
        self.questions = []

    def showwarning(self, *args, **kwargs):
        self.warnings.append((args, kwargs))

    def showinfo(self, *args, **kwargs):
        self.infos.append((args, kwargs))

    def showerror(self, *args, **kwargs):
        self.errors.append((args, kwargs))

    def askyesno(self, *args, **kwargs):
        self.questions.append((args, kwargs))
        return True


class FakeApp:
    def __init__(self, root, backup_path: Path, role="Admin"):
        self.root = root
        self.user_role = role
        self.backup_path = backup_path
        self.calls = []

    def _list_postgres_backup_files(self):
        self.calls.append("list")
        return [{
            "mtime": self.backup_path.stat().st_mtime,
            "name": self.backup_path.name,
            "size": self.backup_path.stat().st_size,
            "path": str(self.backup_path),
        }]

    def _postgres_backup_dir(self):
        return str(self.backup_path.parent)

    def _format_bytes(self, value):
        return f"{int(value or 0)} B"

    def _verify_postgres_backup_file(self, path, cancel_event=None):
        self.calls.append(("verify", path, cancel_event))
        return "Backup verification completed."

    def _restore_backup_to_test_database(self, path, cancel_event=None):
        self.calls.append(("restore", path, cancel_event))
        return "Restore test completed."

    def _run_long_task(
        self, title, work_fn, on_success=None, on_error=None,
        allow_cancel=True, timeout_s=None,
    ):
        self.calls.append(("long_task", title, allow_cancel, timeout_s))
        try:
            result = work_fn(cancel_event=None)
        except Exception as exc:
            if on_error:
                on_error(exc)
            return
        if on_success:
            on_success(result)


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def button(window, text):
    for widget in walk(window):
        if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
            return widget
    raise AssertionError(f"Missing button: {text}")


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    dialogs = Dialogs()
    opened = []
    logged = []

    presentation.configure_backup_history_dependencies({
        "tk": tk,
        "ttk": ttk,
        "messagebox": dialogs,
        "os": os,
        "_open_path": lambda path: opened.append(path),
        "_log_exc": lambda *args: logged.append(args),
    })

    with tempfile.TemporaryDirectory() as tmp:
        backup_path = Path(tmp) / "spina-test.backup"
        backup_path.write_bytes(b"wave68")

        unauthorized = FakeApp(root, backup_path, role="Collector")
        before = set(root.winfo_children())
        presentation.open_backup_history_window(unauthorized)
        root.update_idletasks()
        assert dialogs.warnings
        assert set(root.winfo_children()) == before

        app = FakeApp(root, backup_path, role="Admin")
        presentation.open_backup_history_window(app)
        root.update()
        windows = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert windows
        win = windows[-1]
        assert win.title() == "PostgreSQL Backup History"
        tree = app._backup_history_tree
        assert tuple(tree["columns"]) == ("created", "filename", "size", "path")
        rows = tree.get_children("")
        assert len(rows) == 1
        values = tree.item(rows[0], "values")
        assert values[1] == backup_path.name
        assert values[3] == str(backup_path)
        tree.selection_set(rows[0])
        tree.focus(rows[0])

        button(win, "Open Backup Folder").invoke()
        button(win, "Verify Selected").invoke()
        button(win, "Restore Test DB").invoke()
        button(win, "Refresh").invoke()
        root.update_idletasks()

        assert opened == [str(backup_path.parent)]
        assert any(call[0] == "verify" for call in app.calls if isinstance(call, tuple))
        assert any(call[0] == "restore" for call in app.calls if isinstance(call, tuple))
        assert any(call[0] == "long_task" for call in app.calls if isinstance(call, tuple))
        assert dialogs.questions
        assert len(dialogs.infos) >= 2
        assert not dialogs.errors
        button(win, "Close").invoke()

    root.destroy()
    print("Wave 68 backup-history Tkinter regression passed")


if __name__ == "__main__":
    main()
