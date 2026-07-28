from __future__ import annotations

import ast
import hashlib
import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "reports_tab_presentation.py"
STRUCT_TEST = ROOT / "tools" / "test_reports_tab_presentation_wave_64.py"
SMOKE_TEST = ROOT / "tools" / "test_reports_tab_widget_smoke_wave_64.py"

EXPECTED_LINES = 338
EXPECTED_SOURCE_SHA = "7ee5ddb185c7dd34a0bd60c3219e72d1c5cbe2314b547b91f2946bca13a95bb3"
BINDING_BLOCK = """# Wave 64: Reports tab presentation.\nfrom spina_app.reports_tab_presentation import (\n    configure_reports_tab_dependencies as _configure_wave64_reports_tab,\n    _build_reports_tab as _wave64_build_reports_tab,\n)\n_configure_wave64_reports_tab(globals())\nApp._build_reports_tab = _wave64_build_reports_tab\n\n\n"""


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
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_build_reports_tab"
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
        '"""Reports tab presentation extracted in Wave 64."""\n'
        "from __future__ import annotations\n\n"
        "_REPORTS_TAB_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '__name__', '__doc__', '__package__', '__loader__', '__spec__',\n"
        "    '__file__', '__cached__', '__builtins__',\n"
        "    '_REPORTS_TAB_DEPENDENCIES', '_PROTECTED_GLOBALS',\n"
        "    'REPORTS_TAB_PRESENTATION_METHODS',\n"
        "    'configure_reports_tab_dependencies', '_build_reports_tab',\n"
        "}\n\n"
        "def configure_reports_tab_dependencies(namespace):\n"
        "    _REPORTS_TAB_DEPENDENCIES.clear()\n"
        "    _REPORTS_TAB_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n"
        f"REPORTS_TAB_PRESENTATION_METHODS = {json.dumps({'_build_reports_tab': metadata}, ensure_ascii=False, sort_keys=True)}\n\n"
        + dedented.rstrip() + "\n"
    )


def build_structural_test() -> str:
    return r'''from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "reports_tab_presentation.py"
EXPECTED_LINES = 338
EXPECTED_SOURCE_SHA = "7ee5ddb185c7dd34a0bd60c3219e72d1c5cbe2314b547b91f2946bca13a95bb3"


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
    function = next(n for n in module_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_build_reports_tab")
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["REPORTS_TAB_PRESENTATION_METHODS"]["_build_reports_tab"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert ast.unparse(function.args) == "self"

    calls = sorted({dotted(c.func) for c in ast.walk(function) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == [] == metadata["db_calls"]

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "_build_reports_tab" for n in app.body)
    assert app_text.count("configure_reports_tab_dependencies as _configure_wave64_reports_tab") == 1
    assert app_text.count("_configure_wave64_reports_tab(globals())") == 1
    assert app_text.count("App._build_reports_tab = _wave64_build_reports_tab") == 1
    print("Wave 64 Reports tab structural regression passed")


if __name__ == "__main__":
    main()
'''


def build_smoke_test() -> str:
    return r'''from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from spina_app import reports_tab_presentation as presentation


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.tab_reports = ttk.Frame(root)
        self.tab_reports.pack(fill="both", expand=True)
        self.calls = []

    def refresh_reports(self):
        self.calls.append("refresh")

    def generate_pdf_selected(self):
        self.calls.append("generate")

    def open_report_generation_log(self):
        self.calls.append("logs")

    def _open_note_dialog(self):
        self.calls.append("notes")

    def _auto_load_report_note(self):
        self.calls.append("auto_note")

    def _configure_tree_stripes(self, tree):
        tree.tag_configure("even")
        tree.tag_configure("odd")

    def _load_report_note_for_client(self):
        self.calls.append("load_note")

    def _save_dated_note_for_client(self):
        self.calls.append("save_date_note")

    def _save_report_note_for_client(self):
        self.calls.append("save_default_note")

    def _set_report_note_text(self, text):
        self.calls.append(("set_note", text))


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def button(app, text):
    for widget in walk(app.tab_reports):
        if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
            return widget
    raise AssertionError(f"Missing button: {text}")


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    prefs = {"reports_page_size": "Folio 8.5 x 13"}

    presentation.configure_reports_tab_dependencies({
        "tk": tk,
        "ttk": ttk,
        "date": date,
        "messagebox": messagebox,
        "pick_date": lambda *a, **k: None,
        "pick_date_range": lambda *a, **k: None,
        "_load_ledger_prefs": lambda: dict(prefs),
        "_save_ledger_prefs": lambda value: prefs.update(value),
        "_log_ignored": lambda *a, **k: None,
        "_log_suppressed_once": lambda *a, **k: None,
    })

    app = FakeApp(root)
    presentation._build_reports_tab(app)
    root.update_idletasks()

    assert tuple(app.reports_tree["columns"]) == (
        "name", "contact", "loan_type", "term", "day_due", "payment", "mode",
        "linked", "area", "principal", "total", "released", "due",
    )
    assert app.report_page_size_var.get() == "Folio 8.5 x 13"
    assert app.date_range_var.get().endswith(date.today().strftime("%Y-%m-%d"))
    assert not app.reports_notes_box.winfo_manager()

    button(app, "Generate Report").invoke()
    button(app, "Report Logs").invoke()
    button(app, "Notes…").invoke()
    assert "generate" in app.calls
    assert "logs" in app.calls
    assert "notes" in app.calls

    before = app.calls.count("refresh")
    button(app, "Today").invoke()
    root.update_idletasks()
    assert app.start_date_var.get() == date.today().strftime("%Y-%m-%d")
    assert app.end_date_var.get() == date.today().strftime("%Y-%m-%d")
    assert app.calls.count("refresh") > before

    app.report_page_size_var.set("Legal 8.5 x 14")
    root.update()
    assert prefs["reports_page_size"] == "Legal 8.5 x 14"

    app.search_reports_var.set("sample")
    root.update()
    assert app.calls.count("refresh") > before

    root.destroy()
    print("Wave 64 Reports tab Tkinter smoke regression passed")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    if "App._build_reports_tab = _wave64_build_reports_tab" in text:
        print("Wave 64 Reports tab extraction already applied")
        return

    node, source, lines = find_method(text)
    line_count = node.end_lineno - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise RuntimeError(f"Expected {EXPECTED_LINES} lines, found {line_count}")
    if sha(source) != EXPECTED_SOURCE_SHA:
        raise RuntimeError(f"Unexpected Reports tab source SHA: {sha(source)}")

    MODULE.write_text(build_module(node, source), encoding="utf-8")
    STRUCT_TEST.write_text(build_structural_test(), encoding="utf-8")
    SMOKE_TEST.write_text(build_smoke_test(), encoding="utf-8")

    new_lines = lines[:node.lineno - 1] + lines[node.end_lineno:]
    new_text = "".join(new_lines)
    marker = re.search(r"(?m)^def main\(.*$", new_text)
    if not marker:
        raise RuntimeError("Could not find top-level main() insertion point")
    new_text = new_text[:marker.start()] + BINDING_BLOCK + new_text[marker.start():]
    APP.write_text(new_text, encoding="utf-8")
    print("Applied Wave 64 338-line Reports tab extraction")


if __name__ == "__main__":
    main()
