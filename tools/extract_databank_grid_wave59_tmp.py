from __future__ import annotations

import ast
import codecs
import hashlib
import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_grid_presentation.py"
EXACT_TEST = ROOT / "tools" / "test_databank_grid_presentation_wave_59.py"
WIDGET_TEST = ROOT / "tools" / "test_databank_grid_widget_smoke_wave_59.py"
REPORT = ROOT / "artifacts" / "wave-59-databank-grid-extraction.json"
TARGET_CLASS = "App"
TARGETS = {
    "goto_current_month": {
        "lines": 5,
        "sha256": "42ecd7e7b76492b3e568621109b166249426f32199a9ed8d3c3966b7f9d44a96",
        "signature": "self",
        "calls": ["date.today", "self.refresh_data_grid"],
    },
    "prev_month": {
        "lines": 4,
        "sha256": "e0b005e9000e608a411637ef7996cbd886c0d11babfad98f3679cb68ad217753",
        "signature": "self",
        "calls": ["self._month_label", "self.month_lbl.config", "self.refresh_data_grid"],
    },
    "next_month": {
        "lines": 4,
        "sha256": "7e03166f967729a5f940e707332ce385e194f07c6f3a119bfd4ed9f48bfab41b",
        "signature": "self",
        "calls": ["self._month_label", "self.month_lbl.config", "self.refresh_data_grid"],
    },
    "refresh_data_grid": {
        "lines": 271,
        "sha256": "e3ecfaae3f958c4d06ac7aa75b41ab5f0f0ab027b2dcc58dafa9e197779b31aa",
        "signature": "self",
        "calls": [
            "_log_ignored", "_log_suppressed_once", "_sync_selection", "c.get",
            "calendar.monthrange", "date", "enumerate", "float", "fmt_currency",
            "from_tv.selection", "grid.grid", "grid.grid_columnconfigure",
            "grid.grid_rowconfigure", "h.grid", "hasattr", "info.get", "int",
            "isinstance", "len", "range", "self._configure_tree_stripes",
            "self._db_menu.add_command", "self._db_menu.add_separator",
            "self._db_menu.grab_release", "self._db_menu.tk_popup",
            "self._db_rows_var.set", "self._ensure_databank_edit_bindings",
            "self._mode_filter", "self._month_label", "self._remember_cell_click",
            "self._resize_databank_columns", "self._update_data_toolbar",
            "self.days_tree.bind", "self.days_tree.column", "self.days_tree.configure",
            "self.days_tree.focus", "self.days_tree.grid", "self.days_tree.heading",
            "self.days_tree.identify_row", "self.days_tree.insert",
            "self.days_tree.selection_set", "self.days_tree.yview",
            "self.db.get_all_clients", "self.db.get_client_info",
            "self.db.get_transaction", "self.inner.bind",
            "self.inner.grid_columnconfigure", "self.inner.grid_rowconfigure",
            "self.inner.winfo_children", "self.name_tree.bind", "self.name_tree.column",
            "self.name_tree.configure", "self.name_tree.focus", "self.name_tree.grid",
            "self.name_tree.heading", "self.name_tree.identify_row",
            "self.name_tree.insert", "self.name_tree.selection_set",
            "self.name_tree.yview", "self.root.bell", "self.search_db_var.get",
            "self.status_var.set", "str", "strftime", "strip", "tk.Menu",
            "to_tv.focus", "to_tv.selection", "to_tv.selection_set", "ttk.Frame",
            "ttk.Scrollbar", "ttk.Treeview", "tuple", "tv.bind", "v.grid",
            "vals.append", "w.destroy",
        ],
    },
}
PROTECTED_MARKERS = (
    ".execute", ".executemany", ".commit", ".rollback",
    "set_databank_day_close", "replace_databank_day_collectors",
    "delete_transactions_for_day", "delete_transaction",
    "add_or_update_transaction", "close_day", "reopen_day", "backup", "restore",
    "password", "print_databank_close_report", "write_text", "write_bytes", "unlink",
    "_save_cell_edit", "_import_from_excel", "open_delete_day_dialog",
)
PROTECTED_APP_METHODS = (
    "_begin_cell_edit", "_save_cell_edit", "delete_selected_cell",
    "_mark_missed_for_selected", "open_delete_day_dialog",
    "_import_from_excel_entry", "open_databank_close_dialog",
)


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def find_targets(tree: ast.Module) -> tuple[ast.ClassDef, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            found = {
                child.name: child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name in TARGETS
            }
            missing = sorted(set(TARGETS) - set(found))
            if missing:
                raise SystemExit(f"Missing Wave 59 Data Bank methods: {missing}")
            return node, found
    raise SystemExit(f"Missing class {TARGET_CLASS}")


def render_module(dedented_sources: dict[str, str], metadata: dict[str, dict[str, object]]) -> str:
    protected = {
        "__name__", "__file__", "__package__", "__loader__", "__spec__",
        "__builtins__", "__cached__", "__doc__",
        "_DATABANK_GRID_DEPENDENCIES", "_PROTECTED_GLOBALS",
        "configure_databank_grid_dependencies",
        "DATABANK_GRID_PRESENTATION_METHODS", *TARGETS,
    }
    lines = [
        '"""Data Bank month navigation and grid presentation extracted in Wave 59."""',
        "from __future__ import annotations",
        "",
        "_DATABANK_GRID_DEPENDENCIES = {}",
        f"_PROTECTED_GLOBALS = {protected!r}",
        "",
        "def configure_databank_grid_dependencies(namespace):",
        "    _DATABANK_GRID_DEPENDENCIES.clear()",
        "    _DATABANK_GRID_DEPENDENCIES.update(namespace)",
        "    for name, value in namespace.items():",
        "        if name not in _PROTECTED_GLOBALS:",
        "            globals()[name] = value",
        "",
        f"DATABANK_GRID_PRESENTATION_METHODS = {metadata!r}",
        "",
    ]
    for name in TARGETS:
        lines.extend([dedented_sources[name].rstrip(), ""])
    return "\n".join(lines)


def render_exact_test(metadata: dict[str, dict[str, object]]) -> str:
    expected = {
        name: {
            "lines": TARGETS[name]["lines"],
            "source_sha256": TARGETS[name]["sha256"],
            "dedented_sha256": metadata[name]["dedented_sha256"],
            "signature": TARGETS[name]["signature"],
            "calls": TARGETS[name]["calls"],
            "db_calls": metadata[name]["db_calls"],
        }
        for name in TARGETS
    }
    return f'''"""Exact-source regression for Wave 59 Data Bank grid presentation."""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
EXPECTED = {expected!r}
PROTECTED_MARKERS = {PROTECTED_MARKERS!r}
PROTECTED_APP_METHODS = {PROTECTED_APP_METHODS!r}


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def main() -> None:
    import spina_app.databank_grid_presentation as module

    assert module.DATABANK_GRID_PRESENTATION_METHODS == EXPECTED
    app_text = APP.read_text(encoding="utf-8-sig")
    app_tree = ast.parse(app_text, filename=str(APP))
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {{child.name for child in app_class.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}}

    for name, expected in EXPECTED.items():
        assert name not in remaining
        function = getattr(module, name)
        source = inspect.getsource(function)
        assert len(source.splitlines()) == expected["lines"]
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == expected["dedented_sha256"]
        node = ast.parse(source).body[0]
        assert ast.unparse(node.args) == expected["signature"]
        calls = sorted({{dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)}})
        assert calls == expected["calls"]
        assert [call for call in calls if call.startswith("self.db.")] == expected["db_calls"]
        lowered = "\\n".join(calls).lower()
        assert not [marker for marker in PROTECTED_MARKERS if marker in lowered]

    assert all(name in remaining for name in PROTECTED_APP_METHODS)
    assert app_text.count("_configure_wave59_databank_grid(globals())") == 1
    for name in EXPECTED:
        assert app_text.count(f"App.{{name}} = _wave59_{{name}}") == 1
    print("Wave 59 exact Data Bank grid extraction regression passed")


if __name__ == "__main__":
    main()
'''


def render_widget_test() -> str:
    return '''"""Real Tkinter behavior test for Wave 59 Data Bank grid presentation."""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date as _date
from tkinter import ttk

import spina_app.databank_grid_presentation as module


class FixedDate(_date):
    @classmethod
    def today(cls):
        return cls(2026, 7, 27)


class FakeDB:
    def __init__(self):
        self.calls = []

    def get_all_clients(self, search=None, loan_type=None, search_by=None):
        self.calls.append(("get_all_clients", search, loan_type, search_by))
        return [
            {"name": "ALPHA CLIENT", "area": "AREA A"},
            {"name": "BETA CLIENT", "area": "AREA B"},
        ]

    def get_client_info(self, name, loan_type=None):
        self.calls.append(("get_client_info", name, loan_type))
        return {"area": "FALLBACK"}

    def get_transaction(self, name, date_s):
        self.calls.append(("get_transaction", name, date_s))
        if name == "ALPHA CLIENT" and date_s == "2026-07-01":
            return {"payment": 100}
        if name == "BETA CLIENT" and date_s == "2026-07-02":
            return {"payment": 0}
        return None


class FakeApp:
    goto_current_month = module.goto_current_month
    prev_month = module.prev_month
    next_month = module.next_month
    refresh_data_grid = module.refresh_data_grid

    def __init__(self, root):
        self.root = root
        self.db = FakeDB()
        self.grid_year = 2026
        self.grid_month = 7
        self.inner = ttk.Frame(root)
        self.inner.pack(fill="both", expand=True)
        self.month_lbl = ttk.Label(root, text="")
        self.month_lbl.pack()
        self.status_var = tk.StringVar(root, value="")
        self.search_db_var = tk.StringVar(root, value="")
        self._db_rows_var = tk.StringVar(root, value="")
        self.resize_calls = 0
        self.toolbar_calls = 0
        self.binding_calls = 0

    def _configure_tree_stripes(self, tree):
        tree.tag_configure("odd")
        tree.tag_configure("even")

    def _ensure_databank_edit_bindings(self):
        self.binding_calls += 1

    def _mode_filter(self):
        return "Regular"

    def _month_label(self):
        return f"{calendar.month_name[self.grid_month]} {self.grid_year}"

    def _remember_cell_click(self, event=None):
        return None

    def _resize_databank_columns(self, event=None):
        self.resize_calls += 1

    def _update_data_toolbar(self):
        self.toolbar_calls += 1

    def _begin_cell_edit(self, event=None):
        return None

    def delete_selected_cell(self, event=None):
        return None

    def _on_mousewheel_sync(self, event=None):
        return None

    def _mark_missed_for_selected(self):
        return None


def main() -> None:
    module.configure_databank_grid_dependencies({
        "calendar": calendar,
        "date": FixedDate,
        "tk": tk,
        "ttk": ttk,
        "fmt_currency": lambda value: f"${float(value):,.2f}",
        "_log_suppressed_once": lambda *args, **kwargs: None,
        "_log_ignored": lambda *args, **kwargs: None,
    })
    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp(root)
        app.refresh_data_grid()
        root.update_idletasks()

        assert app.status_var.get() == "Data Bank is view-only. Encode in Excel, then Import."
        assert app.name_tree.winfo_exists()
        assert app.days_tree.winfo_exists()
        assert app.name_tree.get_children() == ("r0", "r1")
        assert app.days_tree.get_children() == ("r0", "r1")
        assert len(app.days_tree["columns"]) == 33
        assert app.name_tree.item("r0", "values") == ("ALPHA CLIENT", "AREA A")
        first = app.days_tree.item("r0", "values")
        second = app.days_tree.item("r1", "values")
        assert first[2] == "$100.00"
        assert second[3] == "0"
        assert app._db_rows_var.get() == "2 rows • Regular • July 2026"
        assert app.resize_calls >= 1
        assert app.toolbar_calls == 1
        assert app.binding_calls == 1
        assert app._db_menu.index("end") == 2
        assert not [call for call in app.db.calls if call[0] not in {"get_all_clients", "get_client_info", "get_transaction"}]

        app.prev_month()
        assert (app.grid_year, app.grid_month) == (2026, 6)
        assert app.month_lbl.cget("text") == "June 2026"
        app.next_month()
        assert (app.grid_year, app.grid_month) == (2026, 7)
        assert app.month_lbl.cget("text") == "July 2026"
        app.grid_year, app.grid_month = 2024, 1
        app.goto_current_month()
        assert (app.grid_year, app.grid_month) == (2026, 7)
        print("Wave 59 real Tkinter Data Bank grid behavior test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
'''


def main() -> None:
    raw = APP.read_bytes()
    had_bom = raw.startswith(codecs.BOM_UTF8)
    original_text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in original_text else "\n"
    text = original_text.replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    app_class, nodes = find_targets(tree)

    dedented_sources: dict[str, str] = {}
    metadata: dict[str, dict[str, object]] = {}
    ranges: list[tuple[int, int]] = []
    for name, expected in TARGETS.items():
        node = nodes[name]
        if node.end_lineno is None:
            raise SystemExit(f"Missing end line for {name}")
        source = "".join(lines[node.lineno - 1:node.end_lineno])
        line_count = node.end_lineno - node.lineno + 1
        if line_count != expected["lines"]:
            raise SystemExit(f"{name} line boundary changed: {line_count}")
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if digest != expected["sha256"]:
            raise SystemExit(f"{name} source hash changed: {digest}")
        signature = ast.unparse(node.args)
        if signature != expected["signature"]:
            raise SystemExit(f"{name} signature changed: {signature}")
        calls = sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        })
        if calls != expected["calls"]:
            raise SystemExit(f"{name} call set changed: {calls}")
        lowered = "\n".join(calls).lower()
        hits = [marker for marker in PROTECTED_MARKERS if marker in lowered]
        if hits:
            raise SystemExit(f"{name} protected calls detected: {hits}")
        dedented = textwrap.dedent(source)
        dedented_sources[name] = dedented
        metadata[name] = {
            "lines": line_count,
            "source_sha256": digest,
            "dedented_sha256": hashlib.sha256(dedented.encode("utf-8")).hexdigest(),
            "signature": signature,
            "calls": calls,
            "db_calls": [call for call in calls if call.startswith("self.db.")],
        }
        ranges.append((node.lineno - 1, node.end_lineno))

    protected_names = {
        child.name for child in app_class.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing_protected = sorted(set(PROTECTED_APP_METHODS) - protected_names)
    if missing_protected:
        raise SystemExit(f"Protected Data Bank methods missing before extraction: {missing_protected}")

    new_lines = list(lines)
    for start, end in sorted(ranges, reverse=True):
        del new_lines[start:end]
    new_text = "".join(new_lines)

    binding_block = '''\n\n# Wave 59: Data Bank month navigation and grid presentation.\nfrom spina_app.databank_grid_presentation import (\n    configure_databank_grid_dependencies as _configure_wave59_databank_grid,\n    goto_current_month as _wave59_goto_current_month,\n    prev_month as _wave59_prev_month,\n    next_month as _wave59_next_month,\n    refresh_data_grid as _wave59_refresh_data_grid,\n)\n_configure_wave59_databank_grid(globals())\nApp.goto_current_month = _wave59_goto_current_month\nApp.prev_month = _wave59_prev_month\nApp.next_month = _wave59_next_month\nApp.refresh_data_grid = _wave59_refresh_data_grid\n'''
    if "_configure_wave59_databank_grid" in new_text:
        raise SystemExit("Wave 59 binding already present")
    matches = list(re.finditer(r"^def main\(\):", new_text, flags=re.MULTILINE))
    if len(matches) != 1:
        raise SystemExit(f"Expected one global def main(), found {len(matches)}")
    pos = matches[0].start()
    new_text = new_text[:pos] + binding_block + "\n" + new_text[pos:]

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(render_module(dedented_sources, metadata), encoding="utf-8", newline="\n")
    EXACT_TEST.write_text(render_exact_test(metadata), encoding="utf-8", newline="\n")
    WIDGET_TEST.write_text(render_widget_test(), encoding="utf-8", newline="\n")

    output = new_text.replace("\n", newline)
    encoded = output.encode("utf-8")
    if had_bom:
        encoded = codecs.BOM_UTF8 + encoded
    APP.write_bytes(encoded)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "base_commit": "3ecada5ab18eaa38f237160b6cc981e0ec3da8b1",
        "total_lines": sum(int(item["lines"]) for item in TARGETS.values()),
        "methods": metadata,
        "protected_methods_preserved": list(PROTECTED_APP_METHODS),
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total_lines": 284, "methods": list(TARGETS), "status": "extracted"}, indent=2))


if __name__ == "__main__":
    main()
