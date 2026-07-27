from __future__ import annotations

import ast
import codecs
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_close_history_presentation.py"
EXACT_TEST = ROOT / "tools" / "test_databank_close_history_presentation_wave_57.py"
WIDGET_TEST = ROOT / "tools" / "test_databank_close_history_widget_smoke_wave_57.py"
REPORT = ROOT / "artifacts" / "wave-57-close-history-extraction.json"
TARGET_CLASS = "App"
TARGET_METHOD = "open_databank_close_history_dialog"
EXPECTED_LINES = 71
EXPECTED_SHA256 = "b08b9c7f4afe8513597a0ec0f0814a92e2bbd816b2ff06fcdc488da39eabfeed"
EXPECTED_SIGNATURE = "self, date_s, loan_type=None"
EXPECTED_CALLS = [
    "abs", "anchors.get", "float", "fmt_currency", "grid", "hasattr",
    "headings.get", "hsb.grid", "outer.columnconfigure", "outer.pack",
    "outer.rowconfigure", "rec.get", "self.db.list_databank_day_close_history",
    "strip", "tk.Toplevel", "top.geometry", "top.grab_set", "top.title",
    "top.transient", "tree.column", "tree.configure", "tree.grid",
    "tree.heading", "tree.insert", "ttk.Button", "ttk.Frame", "ttk.Label",
    "ttk.Scrollbar", "ttk.Treeview", "vsb.grid", "widths.get",
]
WRITE_MARKERS = (
    ".execute", ".executemany", ".commit", ".rollback",
    "set_databank_day_close", "replace_databank_day_collectors",
    "delete_transactions_for_day", "delete_transaction",
    "add_or_update_transaction", "close_day", "reopen_day", "backup",
    "restore", "password", "write_text", "write_bytes", "unlink",
)


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def find_target(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == TARGET_METHOD:
                    return child
    raise SystemExit(f"Missing {TARGET_CLASS}.{TARGET_METHOD}")


def render_module(dedented: str, metadata: dict[str, object]) -> str:
    protected = {
        "__name__", "__file__", "__package__", "__loader__", "__spec__",
        "__builtins__", "__cached__", "__doc__",
        "_CLOSE_HISTORY_PRESENTATION_DEPENDENCIES", "_PROTECTED_GLOBALS",
        "configure_databank_close_history_presentation_dependencies", TARGET_METHOD,
    }
    protected.update(metadata)
    lines = [
        '"""Data Bank Close History dialog presentation extracted in Wave 57."""',
        "from __future__ import annotations",
        "",
        "_CLOSE_HISTORY_PRESENTATION_DEPENDENCIES = {}",
        f"_PROTECTED_GLOBALS = {protected!r}",
        "",
        "def configure_databank_close_history_presentation_dependencies(namespace):",
        "    _CLOSE_HISTORY_PRESENTATION_DEPENDENCIES.clear()",
        "    _CLOSE_HISTORY_PRESENTATION_DEPENDENCIES.update(namespace)",
        "    for name, value in namespace.items():",
        "        if name not in _PROTECTED_GLOBALS:",
        "            globals()[name] = value",
        "",
    ]
    for name, value in metadata.items():
        lines.append(f"{name} = {value!r}")
    lines.extend(["", dedented.rstrip(), ""])
    return "\n".join(lines)


def render_exact_test(metadata: dict[str, object]) -> str:
    return f'''"""Exact-source regression for Wave 57 Data Bank Close History presentation."""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


def main() -> None:
    import spina_app.databank_close_history_presentation as module

    assert module.CLOSE_HISTORY_PRESENTATION_TARGET == {TARGET_METHOD!r}
    assert module.CLOSE_HISTORY_PRESENTATION_SOURCE_LINES == {EXPECTED_LINES}
    assert module.CLOSE_HISTORY_PRESENTATION_SOURCE_SHA256 == {EXPECTED_SHA256!r}
    assert module.CLOSE_HISTORY_PRESENTATION_DEDENTED_SHA256 == {metadata['CLOSE_HISTORY_PRESENTATION_DEDENTED_SHA256']!r}
    assert module.CLOSE_HISTORY_PRESENTATION_SIGNATURE == {EXPECTED_SIGNATURE!r}
    assert module.CLOSE_HISTORY_PRESENTATION_CALLS == {EXPECTED_CALLS!r}
    assert module.CLOSE_HISTORY_PRESENTATION_DB_CALLS == ["self.db.list_databank_day_close_history"]

    module_source = inspect.getsource(module.open_databank_close_history_dialog)
    assert len(module_source.splitlines()) == {EXPECTED_LINES}
    assert hashlib.sha256(module_source.encode("utf-8")).hexdigest() == module.CLOSE_HISTORY_PRESENTATION_DEDENTED_SHA256

    app_text = APP.read_text(encoding="utf-8-sig")
    tree = ast.parse(app_text, filename=str(APP))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            assert not any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == {TARGET_METHOD!r}
                for child in node.body
            )

    assert app_text.count("_configure_wave57_close_history_presentation(globals())") == 1
    assert app_text.count("App.open_databank_close_history_dialog = _wave57_open_databank_close_history_dialog") == 1
    lowered = "\\n".join(module.CLOSE_HISTORY_PRESENTATION_CALLS).lower()
    assert not [fragment for fragment in {WRITE_MARKERS!r} if fragment in lowered]
    print("Wave 57 exact Data Bank Close History extraction regression passed")


if __name__ == "__main__":
    main()
'''


def render_widget_test() -> str:
    return '''"""Real Tkinter smoke test for Wave 57 Data Bank Close History presentation."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import spina_app.databank_close_history_presentation as module


class FakeDB:
    def __init__(self):
        self.calls = []

    def list_databank_day_close_history(self, date_s, loan_type=None):
        self.calls.append((date_s, loan_type))
        return [
            {
                "event_at": "2026-07-27 08:00:00",
                "action": "CLOSE",
                "workflow_status": "FINAL",
                "variance_status": "SHORT",
                "expected_amount": 1000,
                "actual_cash": 950,
                "variance": -50,
                "actor": "System",
                "note": "Safe test record",
            }
        ]


class FakeApp:
    def __init__(self, root):
        self.root = root
        self.db = FakeDB()


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def main() -> None:
    module.configure_databank_close_history_presentation_dependencies({
        "fmt_currency": lambda value: f"${float(value):,.2f}",
    })
    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp(root)
        module.open_databank_close_history_dialog(app, "2026-07-27", loan_type="Regular")
        root.update_idletasks()
        assert app.db.calls == [("2026-07-27", "Regular")]

        tops = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]
        assert len(tops) == 1
        top = tops[0]
        assert top.title() == "Daily Close History - 2026-07-27"

        widgets = list(walk(top))
        labels = {str(widget.cget("text")) for widget in widgets if isinstance(widget, ttk.Label)}
        assert "Variance / Close History for 2026-07-27" in labels

        trees = [widget for widget in widgets if isinstance(widget, ttk.Treeview)]
        assert len(trees) == 1
        tree = trees[0]
        expected_columns = (
            "event_at", "action", "workflow", "variance_status", "expected",
            "actual", "variance", "actor", "note",
        )
        assert tuple(tree["columns"]) == expected_columns
        assert [tree.heading(column, "text") for column in expected_columns] == [
            "When", "Action", "Workflow", "Variance Type", "Expected",
            "Actual", "Variance", "By", "Note",
        ]
        rows = tree.get_children()
        assert len(rows) == 1
        assert tuple(tree.item(rows[0], "values")) == (
            "2026-07-27 08:00:00", "CLOSE", "FINAL", "SHORT",
            "$1,000.00", "$950.00", "$50.00", "System", "Safe test record",
        )

        close_buttons = [
            widget for widget in widgets
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Close"
        ]
        assert len(close_buttons) == 1
        close_buttons[0].invoke()
        root.update_idletasks()
        assert not top.winfo_exists()
        print("Wave 57 real Tkinter Data Bank Close History construction test passed")
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
    target = find_target(tree)
    if target.end_lineno is None:
        raise SystemExit("Target end line missing")

    source = "".join(lines[target.lineno - 1 : target.end_lineno])
    if target.end_lineno - target.lineno + 1 != EXPECTED_LINES:
        raise SystemExit("Wave 57 line boundary changed")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Wave 57 source hash changed: {digest}")
    signature = ast.unparse(target.args)
    if signature != EXPECTED_SIGNATURE:
        raise SystemExit(f"Wave 57 signature changed: {signature}")
    calls = sorted({
        dotted(node.func)
        for node in ast.walk(target)
        if isinstance(node, ast.Call) and dotted(node.func)
    })
    if calls != EXPECTED_CALLS:
        raise SystemExit(f"Wave 57 call set changed: {calls}")
    lowered = "\n".join(calls).lower()
    hits = [fragment for fragment in WRITE_MARKERS if fragment in lowered]
    if hits:
        raise SystemExit(f"Protected write calls detected: {hits}")

    dedented = textwrap.dedent(source)
    dedented_sha = hashlib.sha256(dedented.encode("utf-8")).hexdigest()
    metadata = {
        "CLOSE_HISTORY_PRESENTATION_TARGET": TARGET_METHOD,
        "CLOSE_HISTORY_PRESENTATION_SOURCE_LINES": EXPECTED_LINES,
        "CLOSE_HISTORY_PRESENTATION_SOURCE_SHA256": EXPECTED_SHA256,
        "CLOSE_HISTORY_PRESENTATION_DEDENTED_SHA256": dedented_sha,
        "CLOSE_HISTORY_PRESENTATION_SIGNATURE": EXPECTED_SIGNATURE,
        "CLOSE_HISTORY_PRESENTATION_CALLS": calls,
        "CLOSE_HISTORY_PRESENTATION_DB_CALLS": [
            call for call in calls if call.startswith("self.db.")
        ],
    }
    MODULE.write_text(render_module(dedented, metadata), encoding="utf-8")
    EXACT_TEST.write_text(render_exact_test(metadata), encoding="utf-8")
    WIDGET_TEST.write_text(render_widget_test(), encoding="utf-8")

    new_text = "".join(lines[: target.lineno - 1] + lines[target.end_lineno :])
    marker = "\ndef main():"
    if marker not in new_text:
        raise SystemExit("Wave 57 startup marker missing")
    if "_configure_wave57_close_history_presentation" in new_text:
        raise SystemExit("Wave 57 binding already exists")
    binding = '''\n\n# Wave 57: Data Bank Close History dialog presentation.\nfrom spina_app.databank_close_history_presentation import (\n    configure_databank_close_history_presentation_dependencies as _configure_wave57_close_history_presentation,\n    open_databank_close_history_dialog as _wave57_open_databank_close_history_dialog,\n)\n_configure_wave57_close_history_presentation(globals())\nApp.open_databank_close_history_dialog = _wave57_open_databank_close_history_dialog\n'''
    new_text = new_text.replace(marker, binding + marker, 1)
    if newline == "\r\n":
        new_text = new_text.replace("\n", "\r\n")
    encoded = new_text.encode("utf-8")
    if had_bom:
        encoded = codecs.BOM_UTF8 + encoded
    APP.write_bytes(encoded)

    report = {
        "target": f"{TARGET_CLASS}.{TARGET_METHOD}",
        "lines": EXPECTED_LINES,
        "sha256": EXPECTED_SHA256,
        "dedented_sha256": dedented_sha,
        "signature": EXPECTED_SIGNATURE,
        "calls": calls,
        "database_calls": metadata["CLOSE_HISTORY_PRESENTATION_DB_CALLS"],
        "write_markers": [],
        "classification": "ui_read_only",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
