from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REVIEW_SOURCE = ROOT / "docs" / "wave68-backup-history-source.txt"
MODULE = ROOT / "spina_app" / "backup_history_presentation.py"
STRUCT_TEST = ROOT / "tools" / "test_backup_history_presentation_wave_68.py"
WIDGET_TEST = ROOT / "tools" / "test_backup_history_widget_smoke_wave_68.py"
TARGET = "open_backup_history_window"
EXPECTED_LINES = 182
EXPECTED_SHA256 = "c05501298b2aa308c66f0f668bb482a96de8dc221b098f88705fa6d452c6d59f"
EXPECTED_SIGNATURE = "self"


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    method = next(
        n for n in app.body
        if isinstance(n, ast.FunctionDef) and n.name == TARGET
    )
    main_function = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "main"
    )
    lines = text.splitlines(keepends=True)
    source = "".join(lines[method.lineno - 1:method.end_lineno]).replace("\r\n", "\n")
    assert method.end_lineno - method.lineno + 1 == EXPECTED_LINES
    assert sha(source) == EXPECTED_SHA256
    assert ast.unparse(method.args) == EXPECTED_SIGNATURE
    assert REVIEW_SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n") == source

    calls = sorted({
        dotted(item.func)
        for item in ast.walk(method)
        if isinstance(item, ast.Call) and dotted(item.func)
    })
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert db_calls == []
    assert not any(
        isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        and any(token in " ".join(item.value.upper().split()) for token in (
            "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE",
            "ALTER TABLE", "DROP TABLE", "TRUNCATE TABLE",
        ))
        for item in ast.walk(method)
    )

    dedented = textwrap.dedent(source)
    metadata = {
        TARGET: {
            "calls": calls,
            "db_calls": db_calls,
            "dedented_sha256": sha(dedented),
            "lines": EXPECTED_LINES,
            "signature": EXPECTED_SIGNATURE,
            "source_sha256": EXPECTED_SHA256,
        }
    }
    module_text = (
        '"""Backup-history presentation extracted in Wave 68."""\n'
        "from __future__ import annotations\n\n"
        "_BACKUP_HISTORY_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '__name__', '__doc__', '__package__', '__loader__', '__spec__',\n"
        "    '__file__', '__cached__', '__builtins__',\n"
        "    '_BACKUP_HISTORY_DEPENDENCIES', '_PROTECTED_GLOBALS',\n"
        "    'BACKUP_HISTORY_PRESENTATION_METHODS',\n"
        "    'configure_backup_history_dependencies',\n"
        "    'open_backup_history_window',\n"
        "}\n\n"
        "def configure_backup_history_dependencies(namespace):\n"
        "    _BACKUP_HISTORY_DEPENDENCIES.clear()\n"
        "    _BACKUP_HISTORY_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n"
        f"BACKUP_HISTORY_PRESENTATION_METHODS = {metadata!r}\n\n"
        f"{dedented}"
    )
    ast.parse(module_text)
    MODULE.write_text(module_text, encoding="utf-8")

    del lines[method.lineno - 1:method.end_lineno]
    insert_at = main_function.lineno - 1
    if method.end_lineno < main_function.lineno:
        insert_at -= EXPECTED_LINES
    binding = (
        "\nfrom spina_app.backup_history_presentation import (\n"
        "    configure_backup_history_dependencies as _configure_wave68_backup_history,\n"
        "    open_backup_history_window as _wave68_open_backup_history_window,\n"
        ")\n"
        "_configure_wave68_backup_history(globals())\n"
        "App.open_backup_history_window = _wave68_open_backup_history_window\n\n"
    )
    assert "_configure_wave68_backup_history" not in text
    lines[insert_at:insert_at] = binding.splitlines(keepends=True)
    new_app = "".join(lines)
    ast.parse(new_app)
    APP.write_text(new_app, encoding="utf-8")

    STRUCT_TEST.write_text(STRUCTURAL_TEST_SOURCE, encoding="utf-8")
    WIDGET_TEST.write_text(WIDGET_TEST_SOURCE, encoding="utf-8")
    print(f"Extracted {TARGET}: {EXPECTED_LINES} lines, {EXPECTED_SHA256}")


STRUCTURAL_TEST_SOURCE = r'''from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "backup_history_presentation.py"
EXPECTED_LINES = 182
EXPECTED_SOURCE_SHA = "c05501298b2aa308c66f0f668bb482a96de8dc221b098f88705fa6d452c6d59f"
EXPECTED_SIGNATURE = "self"


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    function = next(
        n for n in module_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "open_backup_history_window"
    )
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["BACKUP_HISTORY_PRESENTATION_METHODS"]["open_backup_history_window"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert sha(textwrap.indent(source, "    ")) == EXPECTED_SOURCE_SHA
    assert ast.unparse(function.args) == EXPECTED_SIGNATURE == metadata["signature"]

    calls = sorted({
        dotted(item.func)
        for item in ast.walk(function)
        if isinstance(item, ast.Call) and dotted(item.func)
    })
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == [] == metadata["db_calls"]
    assert "self._verify_postgres_backup_file" in calls
    assert "self._restore_backup_to_test_database" in calls
    assert "self._run_long_task" in calls
    assert "spina_restore_test" in module_text
    assert "self.db" not in module_text

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(
        isinstance(n, ast.FunctionDef) and n.name == "open_backup_history_window"
        for n in app.body
    )
    assert app_text.count(
        "configure_backup_history_dependencies as _configure_wave68_backup_history"
    ) == 1
    assert app_text.count("_configure_wave68_backup_history(globals())") == 1
    assert app_text.count(
        "App.open_backup_history_window = _wave68_open_backup_history_window"
    ) == 1
    assert "App._run_long_task = _wave42_run_long_task" in app_text
    print("Wave 68 backup-history structural regression passed")


if __name__ == "__main__":
    main()
'''


WIDGET_TEST_SOURCE = r'''from __future__ import annotations

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
'''


if __name__ == "__main__":
    main()
