from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "collector_dialog_presentation.py"
TEST = ROOT / "tools" / "test_collector_dialog_presentation_wave_43.py"
WORKFLOW = ROOT / ".github" / "workflows" / "collector-dialog-presentation-wave-43.yml"

TARGET = "_spina_v27_collector_editor_dialog"
EXPECTED_LINES = 350
EXPECTED_SHA256 = "acc8e500cd9e62435bd24d7e998c0dc3c6145e396437f22ca4ee8781c3bbe0f6"
EXPECTED_SIGNATURE = "self, title='Collector', initial_name='', initial_areas=None, initial_notes=''"
EXPECTED_CALLBACKS = [
    "_panel", "_assigned_keys", "_refresh_lists", "_clean_assigned_display",
    "_add_selected", "_remove_selected", "_move_selected", "_move_top",
    "_move_bottom", "_add_all_visible", "_clear_assigned", "_save", "_cancel",
]
EXPECTED_HELPER_CALLS = [
    "_spina_v27_get_route_master_areas",
    "_spina_v27_route_button",
    "_spina_v27_route_colors",
    "messagebox.askyesno",
    "messagebox.showwarning",
]
EXPECTED_OLD_APP_METHOD_LINES = 136
EXPECTED_OLD_APP_METHOD_SHA256 = "3e8864685df23c9c8ac480be8ec411626a6b3680734209bf0a779c024c3b564a"
FORBIDDEN_CALL_SUFFIXES = {
    "commit", "rollback", "execute", "executemany", "run_write",
    "add_client", "update_client", "delete_client", "archive_client",
    "restore_client", "renew_client", "add_transaction", "update_transaction",
    "delete_transaction", "set_transaction", "set_client_note", "save_settings",
    "_save_client_notes", "close_databank_day", "reopen_databank_day",
    "write", "write_text", "write_bytes", "unlink", "remove", "rmtree",
    "rename", "replace", "dump", "dumps",
}
SQL_WRITE = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE TABLE",
)


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def call_name(node: ast.AST) -> str:
    return ".".join(chain(node))


def source_for(node: ast.AST, lines: list[str]) -> str:
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def inspect_function(node: ast.FunctionDef, lines: list[str]) -> tuple[str, list[str]]:
    source = source_for(node, lines)
    line_count = node.end_lineno - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise RuntimeError(f"Expected {EXPECTED_LINES} lines, found {line_count}")
    digest = hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Unexpected source hash: {digest}")
    signature = ast.unparse(node.args)
    if signature != EXPECTED_SIGNATURE:
        raise RuntimeError(f"Unexpected signature: {signature}")
    callbacks = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if callbacks != EXPECTED_CALLBACKS:
        raise RuntimeError(f"Unexpected callback inventory: {callbacks}")

    calls: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            full = call_name(item)
            if full.startswith("self.db"):
                raise RuntimeError(f"Forbidden database dependency: {full}")
        if isinstance(item, ast.Call):
            full = call_name(item.func)
            calls.add(full)
            suffix = full.split(".")[-1].lower() if full else ""
            if suffix in FORBIDDEN_CALL_SUFFIXES:
                raise RuntimeError(f"Forbidden persistence/mutation call: {full}")
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            upper = " ".join(item.value.upper().split())
            if any(token in upper for token in SQL_WRITE):
                raise RuntimeError(f"Forbidden SQL write text: {upper[:120]}")

    missing_helpers = [name for name in EXPECTED_HELPER_CALLS if name not in calls]
    if missing_helpers:
        raise RuntimeError(f"Missing expected helper calls: {missing_helpers}")
    return source, sorted(calls)


def inspect_old_app_method(tree: ast.Module, lines: list[str]) -> None:
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    methods = [
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == "_collector_editor_dialog"
    ]
    if len(methods) != 1:
        raise RuntimeError(f"Expected one original App collector editor, found {len(methods)}")
    method = methods[0]
    line_count = method.end_lineno - method.lineno + 1
    digest = hashlib.sha256(
        normalized(source_for(method, lines)).encode("utf-8")
    ).hexdigest()
    if line_count != EXPECTED_OLD_APP_METHOD_LINES or digest != EXPECTED_OLD_APP_METHOD_SHA256:
        raise RuntimeError(
            f"Unexpected original App method boundary: lines={line_count}, hash={digest}"
        )


def build_module(source: str, calls: list[str]) -> str:
    return (
        '"""Active collector editor dialog presentation extracted in Wave 43."""\n'
        "from __future__ import annotations\n\n"
        "import re\n"
        "import tkinter as tk\n"
        "from tkinter import messagebox, ttk\n\n"
        "_COLLECTOR_DIALOG_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',\n"
        "    '__name__', '__package__', '__spec__',\n"
        "    '_COLLECTOR_DIALOG_DEPENDENCIES', '_PROTECTED_GLOBALS',\n"
        "    'configure_collector_dialog_dependencies',\n"
        "    'COLLECTOR_DIALOG_TARGET', 'COLLECTOR_DIALOG_SOURCE_LINES',\n"
        "    'COLLECTOR_DIALOG_SOURCE_SHA256', 'COLLECTOR_DIALOG_SIGNATURE',\n"
        "    'COLLECTOR_DIALOG_NESTED_CALLBACKS', 'COLLECTOR_DIALOG_CALLS',\n"
        "    're', 'tk', 'messagebox', 'ttk',\n"
        "}\n\n\n"
        "def configure_collector_dialog_dependencies(namespace):\n"
        "    _COLLECTOR_DIALOG_DEPENDENCIES.clear()\n"
        "    _COLLECTOR_DIALOG_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n\n"
        f"COLLECTOR_DIALOG_TARGET = {TARGET!r}\n"
        f"COLLECTOR_DIALOG_SOURCE_LINES = {EXPECTED_LINES!r}\n"
        f"COLLECTOR_DIALOG_SOURCE_SHA256 = {EXPECTED_SHA256!r}\n"
        f"COLLECTOR_DIALOG_SIGNATURE = {EXPECTED_SIGNATURE!r}\n"
        f"COLLECTOR_DIALOG_NESTED_CALLBACKS = {EXPECTED_CALLBACKS!r}\n"
        f"COLLECTOR_DIALOG_CALLS = {calls!r}\n\n"
        + source.rstrip()
        + "\n"
    )


def build_test(calls: list[str]) -> str:
    return f'''from __future__ import annotations

import ast
import hashlib
import importlib.util
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "collector_dialog_presentation.py"
TARGET = {TARGET!r}
EXPECTED_LINES = {EXPECTED_LINES!r}
EXPECTED_SHA256 = {EXPECTED_SHA256!r}
EXPECTED_SIGNATURE = {EXPECTED_SIGNATURE!r}
EXPECTED_CALLBACKS = {EXPECTED_CALLBACKS!r}
EXPECTED_CALLS = {calls!r}
EXPECTED_HELPER_CALLS = {EXPECTED_HELPER_CALLS!r}
EXPECTED_OLD_APP_METHOD_LINES = {EXPECTED_OLD_APP_METHOD_LINES!r}
EXPECTED_OLD_APP_METHOD_SHA256 = {EXPECTED_OLD_APP_METHOD_SHA256!r}
FORBIDDEN_CALL_SUFFIXES = {sorted(FORBIDDEN_CALL_SUFFIXES)!r}
SQL_WRITE = {SQL_WRITE!r}


def normalized(source):
    return textwrap.dedent(source).strip() + "\\n"


def chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def call_name(node):
    return ".".join(chain(node))


def source_for(node, lines):
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def main():
    spec = importlib.util.spec_from_file_location("wave43_collector_dialog_import", MODULE)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    assert callable(imported._spina_v27_collector_editor_dialog)
    assert imported.tk.Toplevel is not None
    assert imported.ttk.Entry is not None
    assert imported.messagebox.showwarning is not None

    module_text = MODULE.read_text(encoding="utf-8")
    mtree = ast.parse(module_text)
    funcs = [n for n in mtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert len(funcs) == 1, len(funcs)
    node = funcs[0]
    lines = module_text.splitlines(keepends=True)
    source = source_for(node, lines)
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256
    assert ast.unparse(node.args) == EXPECTED_SIGNATURE
    callbacks = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert callbacks == EXPECTED_CALLBACKS, callbacks

    calls = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            full = call_name(item)
            assert not full.startswith("self.db"), full
        if isinstance(item, ast.Call):
            full = call_name(item.func)
            calls.add(full)
            suffix = full.split(".")[-1].lower() if full else ""
            assert suffix not in FORBIDDEN_CALL_SUFFIXES, full
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            upper = " ".join(item.value.upper().split())
            assert not any(token in upper for token in SQL_WRITE), upper
    assert sorted(calls) == EXPECTED_CALLS
    for helper in EXPECTED_HELPER_CALLS:
        assert helper in calls

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    dtree = ast.parse(desktop_text)
    originals = [
        n for n in dtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET
    ]
    assert not originals, originals
    assert "_configure_wave43_collector_dialog(globals())" in desktop_text
    assert f"{{TARGET}} = _wave43_collector_editor_dialog" in desktop_text
    binding = "App._collector_editor_dialog = _spina_v27_collector_editor_dialog"
    assert desktop_text.count(binding) == 1

    app = next(n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    old_methods = [
        n for n in app.body
        if isinstance(n, ast.FunctionDef) and n.name == "_collector_editor_dialog"
    ]
    assert len(old_methods) == 1
    old = old_methods[0]
    dlines = desktop_text.splitlines(keepends=True)
    old_source = source_for(old, dlines)
    assert old.end_lineno - old.lineno + 1 == EXPECTED_OLD_APP_METHOD_LINES
    assert hashlib.sha256(normalized(old_source).encode("utf-8")).hexdigest() == EXPECTED_OLD_APP_METHOD_SHA256

    binding_line = desktop_text[:desktop_text.index(binding)].count("\\n") + 1
    assert old.end_lineno < binding_line
    print("Wave 43 collector dialog regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
'''


def build_workflow() -> str:
    return '''name: Collector dialog presentation Wave 43
on: [pull_request]
permissions:
  contents: read
concurrency:
  group: collector-dialog-wave-43-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  validate:
    if: github.head_ref == 'agent/collector-dialog-presentation-wave-43'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 45
    steps:
      - name: Check out exact PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0
      - name: Compile application, module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app/collector_dialog_presentation.py
          python -m py_compile tools/test_collector_dialog_presentation_wave_43.py
          python -m compileall -q spina_app
      - name: Run exact collector-dialog regression
        shell: cmd
        run: python tools/test_collector_dialog_presentation_wave_43.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-43-redundancy.json
          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-43-quality.json
      - name: Upload Wave 43 reports
        uses: actions/upload-artifact@v4
        with:
          name: collector-dialog-presentation-wave-43-reports
          path: |
            artifacts/wave-43-redundancy.json
            artifacts/wave-43-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(desktop_text)
    lines = desktop_text.splitlines(keepends=True)
    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == TARGET
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one top-level {TARGET}, found {len(matches)}")
    node = matches[0]
    source, calls = inspect_function(node, lines)
    inspect_old_app_method(tree, lines)

    binding_text = "App._collector_editor_dialog = _spina_v27_collector_editor_dialog"
    if desktop_text.count(binding_text) != 1:
        raise RuntimeError("Expected exactly one final collector-dialog binding")
    binding_line = desktop_text[:desktop_text.index(binding_text)].count("\n") + 1
    if node.end_lineno >= binding_line:
        raise RuntimeError("Collector dialog definition is not before final App binding")

    import_block = (
        "from spina_app.collector_dialog_presentation import (\n"
        "    configure_collector_dialog_dependencies as _configure_wave43_collector_dialog,\n"
        "    _spina_v27_collector_editor_dialog as _wave43_collector_editor_dialog,\n"
        ")\n"
        "_configure_wave43_collector_dialog(globals())\n"
        "_spina_v27_collector_editor_dialog = _wave43_collector_editor_dialog\n"
    )
    updated_desktop = (
        "".join(lines[: node.lineno - 1])
        + import_block
        + "".join(lines[node.end_lineno :])
    )

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    TEST.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(build_module(source, calls), encoding="utf-8")
    TEST.write_text(build_test(calls), encoding="utf-8")
    WORKFLOW.write_text(build_workflow(), encoding="utf-8")
    DESKTOP.write_text(updated_desktop, encoding="utf-8")

    print(json.dumps({
        "target": TARGET,
        "lines": EXPECTED_LINES,
        "sha256": EXPECTED_SHA256,
        "callbacks": EXPECTED_CALLBACKS,
        "calls": calls,
    }, indent=2))


if __name__ == "__main__":
    main()
