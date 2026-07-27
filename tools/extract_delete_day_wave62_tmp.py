from __future__ import annotations

import ast
import hashlib
import pprint
import textwrap
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE_PATH = Path("spina_app/databank_delete_day.py")
EXACT_TEST_PATH = Path("tools/test_databank_delete_day_wave_62.py")
BEHAVIOR_TEST_PATH = Path("tools/test_databank_delete_day_behavior_wave_62.py")
TARGET = "open_delete_day_dialog"
EXPECTED_LINES = 141
EXPECTED_SOURCE_SHA = "b41b22e7c18f2e7f391f4cd400a9f0034c9ca535d2c7b10a9045db35af3d0407"
EXPECTED_DEDENTED_SHA = "1947e0359e0dd97f49e90ac8fe3e3a9357a67213363416908d206b381ee076c0"
EXPECTED_SIGNATURE = "self"
EXPECTED_DB_CALLS = [
    "self.db.conn.cursor",
    "self.db.delete_transactions_for_day",
    "self.db.get_databank_day_close",
]
PROTECTED_WAVE61 = [
    "App._save_cell_edit = _wave61_save_cell_edit",
    "App.delete_selected_cell = _wave61_delete_selected_cell",
    "App._mark_missed_for_selected = _wave61_mark_missed_for_selected",
]


def sha(source: str) -> str:
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def main() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    app_lines = app_text.splitlines(keepends=True)
    tree = ast.parse(app_text)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    method = next(
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == TARGET
    )
    source = "".join(app_lines[method.lineno - 1:method.end_lineno])
    dedented = textwrap.dedent(source)
    calls = sorted({
        value for child in ast.walk(method)
        if isinstance(child, ast.Call)
        for value in [dotted(child.func)]
        if value
    })
    db_calls = sorted(call for call in calls if call.startswith("self.db."))
    strings = sorted({
        child.value for child in ast.walk(method)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    })
    metadata = {
        "lines": method.end_lineno - method.lineno + 1,
        "source_sha256": sha(source),
        "dedented_sha256": sha(dedented),
        "signature": ast.unparse(method.args),
        "calls": calls,
        "db_calls": db_calls,
        "strings": strings,
    }
    assert metadata["lines"] == EXPECTED_LINES, metadata
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA, metadata
    assert metadata["dedented_sha256"] == EXPECTED_DEDENTED_SHA, metadata
    assert metadata["signature"] == EXPECTED_SIGNATURE, metadata
    assert metadata["db_calls"] == EXPECTED_DB_CALLS, metadata
    for marker in PROTECTED_WAVE61:
        assert app_text.count(marker) == 1, marker

    module = (
        '"""Data Bank Delete Day destructive workflow extracted in Wave 62."""\n'
        "from __future__ import annotations\n\n"
        "_DATABANK_DELETE_DAY_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '_DATABANK_DELETE_DAY_DEPENDENCIES', '_PROTECTED_GLOBALS',\n"
        "    'configure_databank_delete_day_dependencies', 'open_delete_day_dialog',\n"
        "    'DATABANK_DELETE_DAY_METHOD',\n"
        "}\n\n"
        "def configure_databank_delete_day_dependencies(namespace):\n"
        "    _DATABANK_DELETE_DAY_DEPENDENCIES.clear()\n"
        "    _DATABANK_DELETE_DAY_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n"
        f"DATABANK_DELETE_DAY_METHOD = {pprint.pformat(metadata, width=120, sort_dicts=True)}\n\n"
        + dedented
    )
    MODULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODULE_PATH.write_text(module, encoding="utf-8")

    start = sum(len(line) for line in app_lines[:method.lineno - 1])
    end = sum(len(line) for line in app_lines[:method.end_lineno])
    patched = app_text[:start] + "\n" + app_text[end:]
    binding = (
        "\n# Wave 62: Data Bank Delete Day destructive workflow.\n"
        "from spina_app.databank_delete_day import (\n"
        "    configure_databank_delete_day_dependencies as _configure_wave62_databank_delete_day,\n"
        "    open_delete_day_dialog as _wave62_open_delete_day_dialog,\n"
        ")\n"
        "_configure_wave62_databank_delete_day(globals())\n"
        "App.open_delete_day_dialog = _wave62_open_delete_day_dialog\n\n"
    )
    marker = "def main():"
    assert patched.count(marker) == 1
    patched = patched.replace(marker, binding + marker, 1)
    APP_PATH.write_text(patched, encoding="utf-8")

    expected_repr = pprint.pformat(metadata, width=120, sort_dicts=True)
    exact_test = f'''"""Permanent exact-source regression for Wave 62 Delete Day."""
from __future__ import annotations

import ast
import hashlib
import importlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "databank_delete_day.py"
EXPECTED = {expected_repr}
PROTECTED_WAVE61 = {PROTECTED_WAVE61!r}


def sha(source: str) -> str:
    return hashlib.sha256(source.replace("\\r\\n", "\\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{{base}}.{{node.attr}}" if base else node.attr
    return None


def main() -> None:
    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines(keepends=True)
    module_tree = ast.parse(module_text)
    functions = {{node.name: node for node in module_tree.body if isinstance(node, ast.FunctionDef)}}
    node = functions["open_delete_day_dialog"]
    source = "".join(module_lines[node.lineno - 1:node.end_lineno])
    calls = sorted({{
        value for child in ast.walk(node)
        if isinstance(child, ast.Call)
        for value in [dotted(child.func)]
        if value
    }})
    strings = sorted({{
        child.value for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }})
    imported = importlib.import_module("spina_app.databank_delete_day")
    assert imported.DATABANK_DELETE_DAY_METHOD == EXPECTED
    assert node.end_lineno - node.lineno + 1 == EXPECTED["lines"]
    assert sha(textwrap.dedent(source)) == EXPECTED["dedented_sha256"]
    assert ast.unparse(node.args) == EXPECTED["signature"]
    assert calls == EXPECTED["calls"]
    assert sorted(call for call in calls if call.startswith("self.db.")) == EXPECTED["db_calls"]
    assert strings == EXPECTED["strings"]

    app_text = APP_PATH.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_methods = {{node.name for node in app_class.body if isinstance(node, ast.FunctionDef)}}
    assert "open_delete_day_dialog" not in app_methods
    assert app_text.count("configure_databank_delete_day_dependencies as _configure_wave62_databank_delete_day") == 1
    assert app_text.count("App.open_delete_day_dialog = _wave62_open_delete_day_dialog") == 1
    for marker in PROTECTED_WAVE61:
        assert app_text.count(marker) == 1
    print("Wave 62 exact Delete Day regression passed:", EXPECTED["lines"], "lines")


if __name__ == "__main__":
    main()
'''
    EXACT_TEST_PATH.write_text(exact_test, encoding="utf-8")

    behavior_test = '''"""Real-Tkinter and fake-database behavior regression for Wave 62 Delete Day."""
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
'''
    BEHAVIOR_TEST_PATH.write_text(behavior_test, encoding="utf-8")
    print("Prepared Wave 62 Delete Day extraction and tests")


if __name__ == "__main__":
    main()
