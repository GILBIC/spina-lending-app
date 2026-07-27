from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_editor_presentation.py"
TEST = ROOT / "tools" / "test_databank_editor_presentation_wave_60.py"
SMOKE = ROOT / "tools" / "test_databank_editor_widget_smoke_wave_60.py"
REPORT = ROOT / "artifacts" / "wave-60-databank-editor-extraction.json"

TARGET_CLASS = "App"
TARGETS = (
    "_pick_missed_reason",
    "_walk_widgets",
    "_begin_cell_edit",
    "_remember_cell_click",
)
EXPECTED = {
    "_pick_missed_reason": {
        "lines": 145,
        "source_sha256": "e75ed29b15ad4f421b70289378b7f3d7b3a653cb712a1f6fed8cd1bcda5471ec",
        "signature": "self, parent, prefill_text=''",
    },
    "_walk_widgets": {
        "lines": 7,
        "source_sha256": "ebb27216245c3fa0d345c84a720dfdd79654b052024ee1c9adb9d202a051dc7c",
        "signature": "self, widget",
    },
    "_begin_cell_edit": {
        "lines": 142,
        "source_sha256": "7e2a682544179556392ed7f291dba538bed362d57979b0a0319115bf87b59bb7",
        "signature": "self, event=None",
    },
    "_remember_cell_click": {
        "lines": 19,
        "source_sha256": "b58c42ff67630fdaeb8a3dd8dc15392bec19a6163524db2f461fdb59ecaa1c1d",
        "signature": "self, event",
    },
}
PROTECTED = (
    "_save_cell_edit",
    "delete_selected_cell",
    "_mark_missed_for_selected",
    "open_delete_day_dialog",
)
DIRECT_WRITE_MARKERS = (
    ".execute",
    ".executemany",
    ".commit",
    ".rollback",
    "add_or_update_transaction",
    "delete_transaction",
    "delete_transactions_for_day",
    "set_databank_day_close",
    "replace_databank_day_collectors",
    "close_day",
    "reopen_day",
)
BINDING_MARKER = "# Wave 60: Data Bank inline editor and missed-reason presentation."


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def source_for(node: ast.AST, lines: list[str]) -> str:
    end = getattr(node, "end_lineno", None)
    if end is None:
        raise SystemExit(f"Missing end line for {getattr(node, 'name', node)!r}")
    return "".join(lines[node.lineno - 1:end])


def metadata(node: ast.FunctionDef | ast.AsyncFunctionDef, source: str) -> dict[str, object]:
    calls = sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })
    lowered = "\n".join(calls).lower()
    direct_hits = [marker for marker in DIRECT_WRITE_MARKERS if marker.lower() in lowered]
    if direct_hits:
        raise SystemExit(f"Direct write markers found in {node.name}: {direct_hits}")
    db_calls = [call for call in calls if call.startswith("self.db.")]
    if db_calls:
        raise SystemExit(f"Direct DB calls found in {node.name}: {db_calls}")
    dedented = textwrap.dedent(source)
    return {
        "lines": int(node.end_lineno or node.lineno) - node.lineno + 1,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "dedented_sha256": hashlib.sha256(dedented.encode("utf-8")).hexdigest(),
        "signature": ast.unparse(node.args),
        "calls": calls,
        "db_calls": db_calls,
        "delegated_save": "self._save_cell_edit" in calls,
    }


def render_module(meta: dict[str, dict[str, object]], sources: dict[str, str]) -> str:
    protected_globals = {
        "__file__", "__builtins__", "__cached__", "__name__", "__package__",
        "__spec__", "__loader__", "__doc__", "_DATABANK_EDITOR_DEPENDENCIES",
        "_PROTECTED_GLOBALS", "configure_databank_editor_dependencies",
        "DATABANK_EDITOR_PRESENTATION_METHODS", *TARGETS,
    }
    chunks = [
        '"""Data Bank inline editor and missed-reason presentation extracted in Wave 60."""\n',
        "from __future__ import annotations\n\n",
        "_DATABANK_EDITOR_DEPENDENCIES = {}\n",
        f"_PROTECTED_GLOBALS = {protected_globals!r}\n\n",
        "def configure_databank_editor_dependencies(namespace):\n",
        "    _DATABANK_EDITOR_DEPENDENCIES.clear()\n",
        "    _DATABANK_EDITOR_DEPENDENCIES.update(namespace)\n",
        "    for name, value in namespace.items():\n",
        "        if name not in _PROTECTED_GLOBALS:\n",
        "            globals()[name] = value\n\n",
        f"DATABANK_EDITOR_PRESENTATION_METHODS = {meta!r}\n\n",
    ]
    for name in TARGETS:
        chunks.append(textwrap.dedent(sources[name]).rstrip() + "\n\n")
    return "".join(chunks)


def render_exact_test(meta: dict[str, dict[str, object]], protected_hashes: dict[str, str]) -> str:
    return f'''from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_editor_presentation.py"
TARGETS = {TARGETS!r}
EXPECTED = {meta!r}
PROTECTED_HASHES = {protected_hashes!r}
BINDING_MARKER = {BINDING_MARKER!r}


def _norm(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\\r\\n", "\\n")


def _source_map(text: str, class_name: str | None = None) -> dict[str, str]:
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    nodes = tree.body
    if class_name is not None:
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        nodes = cls.body
    out = {{}}
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno is not None:
            out[node.name] = "".join(lines[node.lineno - 1:node.end_lineno])
    return out


def main() -> None:
    app_text = _norm(APP)
    module_text = _norm(MODULE)
    app_methods = _source_map(app_text, "App")
    module_methods = _source_map(module_text)

    for name in TARGETS:
        assert name not in app_methods, f"{{name}} still exists on App"
        assert name in module_methods, f"{{name}} missing from module"
        source = module_methods[name]
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == EXPECTED[name]["dedented_sha256"]
        node = ast.parse(source).body[0]
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        assert ast.unparse(node.args) == EXPECTED[name]["signature"]

    for name, expected_hash in PROTECTED_HASHES.items():
        assert name in app_methods, f"protected method {{name}} missing"
        actual = hashlib.sha256(app_methods[name].encode("utf-8")).hexdigest()
        assert actual == expected_hash, f"protected method {{name}} changed"

    assert BINDING_MARKER in app_text
    assert "configure_databank_editor_dependencies" in app_text
    for name in TARGETS:
        assert f"App.{{name}} = _wave60{{name}}" in app_text

    tree = ast.parse(module_text)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in TARGETS:
            continue
        calls = []
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                func = call.func
                parts = []
                while isinstance(func, ast.Attribute):
                    parts.append(func.attr)
                    func = func.value
                if isinstance(func, ast.Name):
                    parts.append(func.id)
                if parts:
                    calls.append(".".join(reversed(parts)))
        assert not [call for call in calls if call.startswith("self.db.")]
        lowered = "\\n".join(calls).lower()
        for marker in {DIRECT_WRITE_MARKERS!r}:
            assert marker.lower() not in lowered, (node.name, marker)

    print("Wave 60 exact Data Bank editor extraction regression passed")


if __name__ == "__main__":
    main()
'''


def render_smoke_test() -> str:
    return r'''from __future__ import annotations

from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

from spina_app import databank_editor_presentation as presentation


class StubApp:
    pass


def _button_texts(widget):
    values = []
    for child in widget.winfo_children():
        try:
            if isinstance(child, ttk.Button):
                values.append(str(child.cget("text")))
        except Exception:
            pass
        values.extend(_button_texts(child))
    return values


def test_missed_reason_dialog(root: tk.Tk) -> None:
    app = StubApp()
    app.root = root
    original_wait = tk.Toplevel.wait_window
    tk.Toplevel.wait_window = lambda self: None
    try:
        result = presentation._pick_missed_reason(app, root, prefill_text="Weather")
    finally:
        tk.Toplevel.wait_window = original_wait
    assert result is None
    tops = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert tops, "missed reason dialog was not constructed"
    top = tops[-1]
    assert top.title() == "Missed Payment - Select reason(s)"
    texts = _button_texts(top)
    assert "Cancel" in texts and "OK" in texts
    checkbuttons = []
    entries = []
    for widget in presentation._walk_widgets(app, top):
        if isinstance(widget, ttk.Checkbutton):
            checkbuttons.append(widget)
        if isinstance(widget, ttk.Entry):
            entries.append(widget)
    assert len(checkbuttons) == 5
    assert len(entries) >= 3
    top.destroy()
    root.update_idletasks()


def test_inline_editor(root: tk.Tk) -> None:
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    columns = ("client", "area", "d1", "d2")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=4)
    for name, text, width in (("client", "Client Name", 180), ("area", "Area", 100), ("d1", "1", 90), ("d2", "2", 90)):
        tree.heading(name, text=text)
        tree.column(name, width=width, stretch=False)
    iid = tree.insert("", "end", values=("Test Client", "Area A", "125.00", ""))
    tree.pack(fill="both", expand=True)
    root.geometry("700x240+0+0")
    root.update_idletasks()
    root.update()

    app = StubApp()
    app.root = root
    app.days_tree = tree
    app.grid_year = 2026
    app.grid_month = 7
    app.current_entry = None
    app._dbank_last_client = None
    app._dbank_last_day = None
    app.toolbar_updates = 0
    app.saved = []
    app._mk_tk_entry = lambda parent, **kwargs: ttk.Entry(parent, **kwargs)
    app._save_cell_edit = lambda client, day, dt, entry: app.saved.append((client, day, dt, entry.get()))
    app._update_data_toolbar = lambda: setattr(app, "toolbar_updates", app.toolbar_updates + 1)

    bbox = tree.bbox(iid, "#3")
    assert bbox, "day cell has no bbox"
    event = SimpleNamespace(x=bbox[0] + 5, y=bbox[1] + 5)
    presentation._remember_cell_click(app, event)
    assert app._dbank_last_client == "Test Client"
    assert app._dbank_last_day == 1
    assert app.toolbar_updates == 1

    presentation._begin_cell_edit(app, event)
    assert isinstance(app.current_entry, ttk.Entry)
    assert app.current_entry.get() == "125.00"
    assert app.current_entry.bind("<Return>")
    app.current_entry.delete(0, "end")
    app.current_entry.insert(0, "150")
    app.current_entry.event_generate("<Return>")
    root.update_idletasks()
    root.update()
    assert app.saved == [("Test Client", 1, "2026-07-01", "150")]

    walked = list(presentation._walk_widgets(app, frame))
    assert tree in walked
    frame.destroy()
    root.update_idletasks()


def main() -> None:
    root = tk.Tk()
    try:
        test_missed_reason_dialog(root)
        test_inline_editor(root)
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    print("Wave 60 real Tkinter Data Bank editor behavior test passed")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    raw = APP.read_bytes()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    decoded = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in decoded else "\n"
    text = decoded.replace("\r\n", "\n")
    if BINDING_MARKER in text:
        raise SystemExit("Wave 60 binding already exists")

    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    app_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS)
    methods = {
        node.name: node for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(TARGETS + PROTECTED) - set(methods))
    if missing:
        raise SystemExit(f"Missing Wave 60 methods: {missing}")

    sources: dict[str, str] = {}
    meta: dict[str, dict[str, object]] = {}
    for name in TARGETS:
        node = methods[name]
        source = source_for(node, lines)
        info = metadata(node, source)
        expected = EXPECTED[name]
        for key in ("lines", "source_sha256", "signature"):
            if info[key] != expected[key]:
                raise SystemExit(f"Wave 60 guard mismatch for {name} {key}: {info[key]!r} != {expected[key]!r}")
        sources[name] = source
        meta[name] = info

    protected_hashes = {
        name: hashlib.sha256(source_for(methods[name], lines).encode("utf-8")).hexdigest()
        for name in PROTECTED
    }

    for node in sorted((methods[name] for name in TARGETS), key=lambda item: item.lineno, reverse=True):
        if node.end_lineno is None:
            raise SystemExit(f"Missing end line for {node.name}")
        del lines[node.lineno - 1:node.end_lineno]
    app_text = "".join(lines)

    import_names = ",\n    ".join(
        f"{name} as _wave60{name}" for name in TARGETS
    )
    bindings = "\n\n" + BINDING_MARKER + "\n" + (
        "from spina_app.databank_editor_presentation import (\n"
        "    configure_databank_editor_dependencies as _configure_wave60_databank_editor,\n"
        f"    {import_names},\n"
        ")\n"
        "_configure_wave60_databank_editor(globals())\n"
        + "\n".join(f"App.{name} = _wave60{name}" for name in TARGETS)
        + "\n"
    )
    marker = "\ndef main():"
    pos = app_text.find(marker)
    if pos < 0:
        raise SystemExit("Could not locate def main() binding point")
    app_text = app_text[:pos] + bindings + app_text[pos:]

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    TEST.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(render_module(meta, sources), encoding="utf-8", newline="\n")
    TEST.write_text(render_exact_test(meta, protected_hashes), encoding="utf-8", newline="\n")
    SMOKE.write_text(render_smoke_test(), encoding="utf-8", newline="\n")

    encoded = app_text.replace("\n", newline).encode("utf-8")
    if had_bom:
        encoded = b"\xef\xbb\xbf" + encoded
    APP.write_bytes(encoded)

    report = {
        "base_commit": "a4c6fbaefc5c366270261b887e67a7fca819ccdd",
        "targets": meta,
        "protected_hashes": protected_hashes,
        "total_lines": sum(int(info["lines"]) for info in meta.values()),
        "module": str(MODULE.relative_to(ROOT)),
        "tests": [str(TEST.relative_to(ROOT)), str(SMOKE.relative_to(ROOT))],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
