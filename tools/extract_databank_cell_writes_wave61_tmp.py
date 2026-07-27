from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE_PATH = Path("spina_app/databank_cell_writes.py")
STATIC_TEST_PATH = Path("tools/test_databank_cell_writes_wave_61.py")
BEHAVIOR_TEST_PATH = Path("tools/test_databank_cell_writes_behavior_wave_61.py")
TARGETS = ["_save_cell_edit", "delete_selected_cell", "_mark_missed_for_selected"]
EXPECTED_LINES = {
    "_save_cell_edit": 84,
    "delete_selected_cell": 88,
    "_mark_missed_for_selected": 71,
}
EXPECTED_SOURCE_SHA = {
    "_save_cell_edit": "3f421b85935c6bdb2f9a5e53a689a81a362a3332889104b858d2b5e3689c7410",
    "delete_selected_cell": "218ac3dadc0dfd0540b27b1cac968da8a6cf1b2197f0973b90577810e7097d6a",
    "_mark_missed_for_selected": "df6545048882965daf68fca634445086426e358ca0b39fa4f319d865c648be67",
}
EXPECTED_DEDENTED_SHA = {
    "_save_cell_edit": "817aa342b4a960d1b53d0056589c2ce20ab7b26780c5675c7d76a4921337aead",
    "delete_selected_cell": "4d27860a520a0474b54ab11c46d3cdc67a0ff15ab3297dcba45c2813bcbf0df0",
    "_mark_missed_for_selected": "77c06f387f8902b78b683074d302cea98569535181549167fb42a88a9e391342",
}
EXPECTED_SIGNATURES = {
    "_save_cell_edit": "self, client, day, dt_str, ent_widget",
    "delete_selected_cell": "self, *_",
    "_mark_missed_for_selected": "self",
}
EXPECTED_PROTECTED_SHA = "b41b22e7c18f2e7f391f4cd400a9f0034c9ca535d2c7b10a9045db35af3d0407"


def normalized_sha(source: str) -> str:
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def method_metadata(node: ast.FunctionDef, source: str) -> dict[str, object]:
    calls = sorted({
        value
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        for value in [dotted(child.func)]
        if value
    })
    return {
        "lines": node.end_lineno - node.lineno + 1,
        "source_sha256": normalized_sha(source),
        "dedented_sha256": normalized_sha(textwrap.dedent(source)),
        "signature": ast.unparse(node.args),
        "calls": calls,
        "db_calls": sorted(call for call in calls if call.startswith("self.db.")),
    }


def build_module(metadata: dict[str, dict[str, object]], sources: dict[str, str]) -> str:
    protected = {
        "configure_databank_cell_write_dependencies",
        "DATABANK_CELL_WRITE_METHODS",
        "_DATABANK_CELL_WRITE_DEPENDENCIES",
        "_PROTECTED_GLOBALS",
        *TARGETS,
    }
    parts = [
        '"""Data Bank payment mutation helpers extracted in Wave 61."""\n',
        "from __future__ import annotations\n\n",
        "_DATABANK_CELL_WRITE_DEPENDENCIES = {}\n",
        f"_PROTECTED_GLOBALS = {protected!r}\n\n",
        "def configure_databank_cell_write_dependencies(namespace):\n",
        "    _DATABANK_CELL_WRITE_DEPENDENCIES.clear()\n",
        "    _DATABANK_CELL_WRITE_DEPENDENCIES.update(namespace)\n",
        "    for name, value in namespace.items():\n",
        "        if name not in _PROTECTED_GLOBALS:\n",
        "            globals()[name] = value\n\n",
        f"DATABANK_CELL_WRITE_METHODS = {metadata!r}\n\n",
    ]
    for name in TARGETS:
        parts.append(textwrap.dedent(sources[name]))
        parts.append("\n\n")
    return "".join(parts).rstrip() + "\n"


def build_static_test(metadata: dict[str, dict[str, object]]) -> str:
    return f'''"""Permanent exact-source regression for Wave 61 Data Bank writes."""
from __future__ import annotations

import ast
import hashlib
import importlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "databank_cell_writes.py"
TARGETS = {TARGETS!r}
EXPECTED = {metadata!r}
PROTECTED_SHA = {EXPECTED_PROTECTED_SHA!r}


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
    module_functions = {{
        node.name: node for node in module_tree.body if isinstance(node, ast.FunctionDef)
    }}
    imported = importlib.import_module("spina_app.databank_cell_writes")
    assert imported.DATABANK_CELL_WRITE_METHODS == EXPECTED

    for name in TARGETS:
        node = module_functions[name]
        source = "".join(module_lines[node.lineno - 1: node.end_lineno])
        data = EXPECTED[name]
        assert node.end_lineno - node.lineno + 1 == data["lines"]
        assert sha(textwrap.dedent(source)) == data["dedented_sha256"]
        assert ast.unparse(node.args) == data["signature"]
        calls = sorted({{
            value for child in ast.walk(node)
            if isinstance(child, ast.Call)
            for value in [dotted(child.func)]
            if value
        }})
        assert calls == data["calls"]
        assert sorted(call for call in calls if call.startswith("self.db.")) == data["db_calls"]

    app_text = APP_PATH.read_text(encoding="utf-8")
    app_lines = app_text.splitlines(keepends=True)
    app_tree = ast.parse(app_text)
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_methods = {{
        node.name: node for node in app_class.body if isinstance(node, ast.FunctionDef)
    }}
    assert all(name not in app_methods for name in TARGETS)
    protected = app_methods["open_delete_day_dialog"]
    protected_source = "".join(app_lines[protected.lineno - 1: protected.end_lineno])
    assert sha(protected_source) == PROTECTED_SHA

    assert app_text.count("configure_databank_cell_write_dependencies as _configure_wave61_databank_writes") == 1
    for name in TARGETS:
        alias = {{
            "_save_cell_edit": "_wave61_save_cell_edit",
            "delete_selected_cell": "_wave61_delete_selected_cell",
            "_mark_missed_for_selected": "_wave61_mark_missed_for_selected",
        }}[name]
        assert app_text.count(f"App.{{name}} = {{alias}}") == 1

    print("Wave 61 exact write-boundary regression passed:", sum(data["lines"] for data in EXPECTED.values()), "lines")


if __name__ == "__main__":
    main()
'''


def build_behavior_test() -> str:
    return '''"""Behavior regression for Wave 61 Data Bank payment mutations."""
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
'''


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    if "# Wave 61: Data Bank cell write actions." in text:
        raise SystemExit("Wave 61 binding already exists")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    methods = {
        node.name: node
        for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = [name for name in TARGETS + ["open_delete_day_dialog"] if name not in methods]
    if missing:
        raise SystemExit(f"Missing expected App methods: {missing}")

    sources: dict[str, str] = {}
    metadata: dict[str, dict[str, object]] = {}
    for name in TARGETS:
        node = methods[name]
        assert isinstance(node, ast.FunctionDef)
        source = "".join(lines[node.lineno - 1: node.end_lineno])
        data = method_metadata(node, source)
        if data["lines"] != EXPECTED_LINES[name]:
            raise SystemExit(f"{name}: expected {EXPECTED_LINES[name]} lines, found {data['lines']}")
        if data["source_sha256"] != EXPECTED_SOURCE_SHA[name]:
            raise SystemExit(f"{name}: source hash changed")
        if data["dedented_sha256"] != EXPECTED_DEDENTED_SHA[name]:
            raise SystemExit(f"{name}: dedented source hash changed")
        if data["signature"] != EXPECTED_SIGNATURES[name]:
            raise SystemExit(f"{name}: signature changed")
        sources[name] = source
        metadata[name] = data

    protected = methods["open_delete_day_dialog"]
    protected_source = "".join(lines[protected.lineno - 1: protected.end_lineno])
    if normalized_sha(protected_source) != EXPECTED_PROTECTED_SHA:
        raise SystemExit("Protected Delete Day source changed")

    MODULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODULE_PATH.write_text(build_module(metadata, sources), encoding="utf-8")
    STATIC_TEST_PATH.write_text(build_static_test(metadata), encoding="utf-8")
    BEHAVIOR_TEST_PATH.write_text(build_behavior_test(), encoding="utf-8")

    for name in sorted(TARGETS, key=lambda item: methods[item].lineno, reverse=True):
        node = methods[name]
        del lines[node.lineno - 1: node.end_lineno]
    new_text = "".join(lines)
    anchor = "def main():\n"
    if anchor not in new_text:
        raise SystemExit("Could not find main() binding anchor")
    binding = '''# Wave 61: Data Bank cell write actions.
from spina_app.databank_cell_writes import (
    configure_databank_cell_write_dependencies as _configure_wave61_databank_writes,
    _save_cell_edit as _wave61_save_cell_edit,
    delete_selected_cell as _wave61_delete_selected_cell,
    _mark_missed_for_selected as _wave61_mark_missed_for_selected,
)
_configure_wave61_databank_writes(globals())
App._save_cell_edit = _wave61_save_cell_edit
App.delete_selected_cell = _wave61_delete_selected_cell
App._mark_missed_for_selected = _wave61_mark_missed_for_selected

'''
    new_text = new_text.replace(anchor, binding + anchor, 1)
    APP_PATH.write_text(new_text, encoding="utf-8")

    print(json.dumps({"methods": metadata, "protected_delete_day_sha": EXPECTED_PROTECTED_SHA}, indent=2))


if __name__ == "__main__":
    main()
