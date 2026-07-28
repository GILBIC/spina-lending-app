from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_close_records_presentation.py"
STRUCT_TEST = ROOT / "tools" / "test_databank_close_records_presentation_wave_66.py"
SMOKE_TEST = ROOT / "tools" / "test_databank_close_records_widget_smoke_wave_66.py"

EXPECTED_LINES = 224
EXPECTED_SOURCE_SHA = "2b3050213b1861f3b0a085742a1b9d277dd0cb2999337b8f5df83fc832435c74"
EXPECTED_SIGNATURE = "self, start_date=None, end_date=None"
EXPECTED_DB_CALLS = ["self.db.list_databank_day_close_records"]
BINDING_BLOCK = """# Wave 66: Data Bank close-records presentation.\nfrom spina_app.databank_close_records_presentation import (\n    configure_databank_close_records_dependencies as _configure_wave66_databank_close_records,\n    open_databank_close_records_dialog as _wave66_open_databank_close_records_dialog,\n)\n_configure_wave66_databank_close_records(globals())\nApp.open_databank_close_records_dialog = _wave66_open_databank_close_records_dialog\n\n\n"""


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


def find_method(text: str):
    tree = ast.parse(text)
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    node = next(
        n for n in app.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "open_databank_close_records_dialog"
    )
    lines = text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1:node.end_lineno])
    return node, source, lines


def build_module(node: ast.FunctionDef, source: str) -> str:
    dedented = textwrap.dedent(source)
    calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    metadata = {
        "lines": node.end_lineno - node.lineno + 1,
        "source_sha256": sha(source),
        "dedented_sha256": sha(dedented),
        "signature": ast.unparse(node.args),
        "calls": calls,
        "db_calls": db_calls,
    }
    return (
        '"""Data Bank close-records presentation extracted in Wave 66."""\n'
        "from __future__ import annotations\n\n"
        "_DATABANK_CLOSE_RECORDS_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '__name__', '__doc__', '__package__', '__loader__', '__spec__',\n"
        "    '__file__', '__cached__', '__builtins__',\n"
        "    '_DATABANK_CLOSE_RECORDS_DEPENDENCIES', '_PROTECTED_GLOBALS',\n"
        "    'DATABANK_CLOSE_RECORDS_PRESENTATION_METHODS',\n"
        "    'configure_databank_close_records_dependencies',\n"
        "    'open_databank_close_records_dialog',\n"
        "}\n\n"
        "def configure_databank_close_records_dependencies(namespace):\n"
        "    _DATABANK_CLOSE_RECORDS_DEPENDENCIES.clear()\n"
        "    _DATABANK_CLOSE_RECORDS_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n"
        f"DATABANK_CLOSE_RECORDS_PRESENTATION_METHODS = {json.dumps({'open_databank_close_records_dialog': metadata}, ensure_ascii=False, sort_keys=True)}\n\n"
        + dedented.rstrip() + "\n"
    )


def build_structural_test() -> str:
    return r'''from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_close_records_presentation.py"
EXPECTED_LINES = 224
EXPECTED_SOURCE_SHA = "2b3050213b1861f3b0a085742a1b9d277dd0cb2999337b8f5df83fc832435c74"
EXPECTED_SIGNATURE = "self, start_date=None, end_date=None"
EXPECTED_DB_CALLS = ["self.db.list_databank_day_close_records"]


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
        if isinstance(n, ast.FunctionDef) and n.name == "open_databank_close_records_dialog"
    )
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["DATABANK_CLOSE_RECORDS_PRESENTATION_METHODS"]["open_databank_close_records_dialog"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert ast.unparse(function.args) == EXPECTED_SIGNATURE == metadata["signature"]

    calls = sorted({dotted(c.func) for c in ast.walk(function) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == EXPECTED_DB_CALLS == metadata["db_calls"]
    assert not any(term in call.lower() for call in db_calls for term in ("add", "insert", "update", "delete", "save", "commit", "rollback"))

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(
        isinstance(n, ast.FunctionDef) and n.name == "open_databank_close_records_dialog"
        for n in app.body
    )
    assert app_text.count("configure_databank_close_records_dependencies as _configure_wave66_databank_close_records") == 1
    assert app_text.count("_configure_wave66_databank_close_records(globals())") == 1
    assert app_text.count("App.open_databank_close_records_dialog = _wave66_open_databank_close_records_dialog") == 1

    remaining = {n.name for n in app.body if isinstance(n, ast.FunctionDef)}
    assert "open_databank_close_dialog" in remaining
    assert "print_databank_close_report" in remaining
    print("Wave 66 Data Bank close-records structural regression passed")


if __name__ == "__main__":
    main()
'''


def build_smoke_test() -> str:
    return r'''from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from spina_app import databank_close_records_presentation as presentation


class FakeDB:
    def __init__(self):
        self.calls = []

    def list_databank_day_close_records(self, start_date, end_date):
        self.calls.append((start_date, end_date))
        return [
            {
                "close_date": "2026-07-01",
                "is_closed": 1,
                "variance_status": "Balanced",
                "regular_total": 1000,
                "x7_total": 200,
                "expected_amount": 1200,
                "actual_cash": 1200,
                "variance": 0,
                "closed_by": "Manager",
                "closed_at": "2026-07-01 18:00:00",
                "note": "Checked\nand balanced",
            },
            {
                "close_date": "2026-07-02",
                "is_closed": 0,
                "variance_status": "Short",
                "regular_total": 900,
                "x7_total": 100,
                "expected_amount": 1000,
                "actual_cash": 950,
                "variance": -50,
                "closed_by": "",
                "closed_at": "",
                "note": "Review",
            },
        ]


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.db = FakeDB()
        self.open_calls = []
        self.print_calls = []

    def _get_databank_focus_date(self):
        return "2026-07-02"

    def open_databank_close_dialog(self, close_date):
        self.open_calls.append(close_date)

    def print_databank_close_report(self, close_date):
        self.print_calls.append(close_date)


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def widget_by_text(root, widget_type, text):
    for widget in walk(root):
        if isinstance(widget, widget_type) and str(widget.cget("text")) == text:
            return widget
    raise AssertionError(f"Missing {widget_type.__name__}: {text}")


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    presentation.configure_databank_close_records_dependencies({
        "datetime": datetime,
        "fmt_currency": lambda value: f"{float(value or 0):,.2f}",
    })

    app = FakeApp(root)
    presentation.open_databank_close_records_dialog(app, "2026-07-01", "2026-07-02")
    root.update_idletasks()
    root.update()

    dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Daily Close Records"]
    assert len(dialogs) == 1
    dialog = dialogs[0]

    trees = [w for w in walk(dialog) if isinstance(w, ttk.Treeview)]
    assert len(trees) == 1
    tree = trees[0]
    assert tuple(tree.cget("columns")) == (
        "close_date", "lock_state", "status", "regular_total", "x7_total",
        "expected_amount", "actual_cash", "variance", "closed_by", "closed_at", "note",
    )
    rows = tree.get_children("")
    assert len(rows) == 2
    first_values = tuple(tree.item(rows[0], "values"))
    second_values = tuple(tree.item(rows[1], "values"))
    assert first_values[0:3] == ("2026-07-01", "CLOSED", "Balanced")
    assert first_values[-1] == "Checked and balanced"
    assert second_values[0:3] == ("2026-07-02", "OPEN", "Short")
    assert app.db.calls[-1] == ("2026-07-01", "2026-07-02")

    required_buttons = ["Load List", "Open Selected", "Print Selected", "Close Window"]
    for text in required_buttons:
        widget_by_text(dialog, ttk.Button, text)

    widget_by_text(dialog, ttk.Button, "Open Selected").invoke()
    root.update()
    assert app.open_calls == ["2026-07-01"]

    widget_by_text(dialog, ttk.Button, "Print Selected").invoke()
    root.update()
    assert app.print_calls == ["2026-07-01"]

    widget_by_text(dialog, ttk.Button, "Load List").invoke()
    root.update()
    assert len(app.db.calls) == 2

    widget_by_text(dialog, ttk.Button, "Close Window").invoke()
    root.update()
    assert not dialog.winfo_exists()
    root.destroy()
    print("Wave 66 Data Bank close-records Tkinter smoke regression passed")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    if "App.open_databank_close_records_dialog = _wave66_open_databank_close_records_dialog" in text:
        print("Wave 66 Data Bank close-records extraction already applied")
        return

    node, source, lines = find_method(text)
    line_count = node.end_lineno - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise RuntimeError(f"Expected {EXPECTED_LINES} lines, found {line_count}")
    actual_sha = sha(source)
    if actual_sha != EXPECTED_SOURCE_SHA:
        raise RuntimeError(f"Unexpected close-records source SHA: {actual_sha}")
    signature = ast.unparse(node.args)
    if signature != EXPECTED_SIGNATURE:
        raise RuntimeError(f"Unexpected close-records signature: {signature}")

    calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    if db_calls != EXPECTED_DB_CALLS:
        raise RuntimeError(f"Unexpected close-records DB calls: {db_calls}")

    MODULE.write_text(build_module(node, source), encoding="utf-8")
    STRUCT_TEST.write_text(build_structural_test(), encoding="utf-8")
    SMOKE_TEST.write_text(build_smoke_test(), encoding="utf-8")

    remaining = "".join(lines[:node.lineno - 1] + lines[node.end_lineno:])
    marker = "\ndef main():"
    insert_at = remaining.rfind(marker)
    if insert_at < 0:
        raise RuntimeError("Could not locate final main() binding point")
    updated = remaining[:insert_at + 1] + BINDING_BLOCK + remaining[insert_at + 1:]
    APP.write_text(updated, encoding="utf-8")
    print("Applied Wave 66 224-line Data Bank close-records extraction")


if __name__ == "__main__":
    main()
