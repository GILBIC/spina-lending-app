from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "long_task_presentation.py"
TEST = ROOT / "tools" / "test_long_task_presentation_wave_42.py"
WORKFLOW = ROOT / ".github" / "workflows" / "long-task-presentation-wave-42.yml"

TARGET_CLASS = "App"
TARGET = "_run_long_task"
EXPECTED_LINES = 273
EXPECTED_SHA256 = "037194095a785211335844178a4f90675c08d7cede51fa7675db4a9ccc17ac21"
EXPECTED_NESTED = [
    "_cleanup_dialog", "_finish", "_request_cancel", "_watchdog",
    "_call_work_fn", "_worker",
]
FORBIDDEN_CALL_SUFFIXES = {
    "add_client", "add_transaction", "archive_client", "close_databank_day",
    "commit", "copy", "copy2", "cursor", "delete_client", "delete_transaction",
    "dump", "dumps", "execute", "executemany", "move", "open", "remove",
    "rename", "renew_client", "reopen_databank_day", "restore_client", "rmdir",
    "rollback", "run_write", "save_settings", "set_client_note",
    "set_transaction", "touch", "unlink", "update_client", "update_transaction",
    "write", "write_bytes", "write_text",
}
FORBIDDEN_SQL_TOKENS = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE TABLE",
)


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def call_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def inspect_target(node: ast.FunctionDef, source: str) -> tuple[list[str], list[str]]:
    line_count = node.end_lineno - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise RuntimeError(f"Expected {EXPECTED_LINES} lines, found {line_count}")
    digest = hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Unexpected source hash: {digest}")

    nested = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if nested != EXPECTED_NESTED:
        raise RuntimeError(f"Unexpected nested callback order: {nested}")

    calls: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            full = ".".join(call_chain(item))
            if full.startswith("self.db"):
                raise RuntimeError(f"Forbidden database dependency: {full}")
        elif isinstance(item, ast.Call):
            parts = call_chain(item.func)
            full = ".".join(parts)
            if full:
                calls.add(full)
            suffix = parts[-1].lower() if parts else ""
            if suffix in FORBIDDEN_CALL_SUFFIXES:
                raise RuntimeError(f"Forbidden database/filesystem mutation call: {full}")
        elif isinstance(item, ast.Constant) and isinstance(item.value, str):
            upper = " ".join(item.value.upper().split())
            if any(token in upper for token in FORBIDDEN_SQL_TOKENS):
                raise RuntimeError(f"Forbidden SQL text: {upper[:120]}")

    required_calls = {
        "threading.Event", "threading.Thread", "time.time", "tk.Toplevel",
        "ttk.Progressbar", "self.root.after", "work_fn",
    }
    missing = required_calls - calls
    if missing:
        raise RuntimeError(f"Missing expected long-task calls: {sorted(missing)}")
    return nested, sorted(calls)


def build_module(source: str, calls: list[str], caller_count: int) -> str:
    return (
        '"""Reusable long-running task presentation extracted in Wave 42."""\n'
        "from __future__ import annotations\n\n"
        "import inspect as _inspect\n"
        "import threading\n"
        "import time\n"
        "import tkinter as tk\n"
        "from tkinter import messagebox, ttk\n\n"
        "_LONG_TASK_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',\n"
        "    '__name__', '__package__', '__spec__', '_LONG_TASK_DEPENDENCIES',\n"
        "    '_PROTECTED_GLOBALS', 'configure_long_task_dependencies',\n"
        "    'LONG_TASK_TARGET', 'LONG_TASK_SOURCE_LINES', 'LONG_TASK_SOURCE_SHA256',\n"
        "    'LONG_TASK_NESTED_CALLBACKS', 'LONG_TASK_CALLS', 'LONG_TASK_CALLER_COUNT',\n"
        "    '_inspect', 'threading', 'time', 'tk', 'messagebox', 'ttk',\n"
        "}\n\n\n"
        "def configure_long_task_dependencies(namespace):\n"
        "    _LONG_TASK_DEPENDENCIES.clear()\n"
        "    _LONG_TASK_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n\n"
        f"LONG_TASK_TARGET = {TARGET!r}\n"
        f"LONG_TASK_SOURCE_LINES = {EXPECTED_LINES}\n"
        f"LONG_TASK_SOURCE_SHA256 = {EXPECTED_SHA256!r}\n"
        f"LONG_TASK_NESTED_CALLBACKS = {EXPECTED_NESTED!r}\n"
        f"LONG_TASK_CALLS = {calls!r}\n"
        f"LONG_TASK_CALLER_COUNT = {caller_count}\n\n"
        + normalized(source)
    )


def build_test(calls: list[str], caller_count: int) -> str:
    return f'''from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "long_task_presentation.py"
TARGET_CLASS = {TARGET_CLASS!r}
TARGET = {TARGET!r}
EXPECTED_LINES = {EXPECTED_LINES}
EXPECTED_SHA256 = {EXPECTED_SHA256!r}
EXPECTED_NESTED = {EXPECTED_NESTED!r}
EXPECTED_CALLS = {calls!r}
EXPECTED_CALLER_COUNT = {caller_count}
FORBIDDEN_CALL_SUFFIXES = {sorted(FORBIDDEN_CALL_SUFFIXES)!r}
FORBIDDEN_SQL_TOKENS = {FORBIDDEN_SQL_TOKENS!r}


def normalized(source):
    return textwrap.dedent(source).strip() + "\\n"


def call_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def main():
    spec = importlib.util.spec_from_file_location("wave42_long_task_import_smoke", MODULE)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    assert callable(imported._run_long_task)
    assert imported.tk.Toplevel is not None
    assert imported.threading.Event is not None
    assert imported._inspect.signature is not None
    signature = inspect.signature(imported._run_long_task)
    assert list(signature.parameters) == [
        "self", "title", "work_fn", "on_success", "on_error", "allow_cancel", "timeout_s"
    ]

    module_text = MODULE.read_text(encoding="utf-8")
    mtree = ast.parse(module_text)
    funcs = [n for n in mtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert len(funcs) == 1, len(funcs)
    node = funcs[0]
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1 : node.end_lineno])
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256

    nested = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert nested == EXPECTED_NESTED, nested

    calls = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            full = ".".join(call_chain(item))
            assert not full.startswith("self.db"), full
        elif isinstance(item, ast.Call):
            parts = call_chain(item.func)
            full = ".".join(parts)
            if full:
                calls.add(full)
            suffix = parts[-1].lower() if parts else ""
            assert suffix not in FORBIDDEN_CALL_SUFFIXES, full
        elif isinstance(item, ast.Constant) and isinstance(item.value, str):
            upper = " ".join(item.value.upper().split())
            assert not any(token in upper for token in FORBIDDEN_SQL_TOKENS), upper
    assert sorted(calls) == EXPECTED_CALLS, sorted(calls)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    dtree = ast.parse(desktop_text)
    app = next(n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == TARGET_CLASS)
    originals = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert not originals
    assert "_configure_wave42_long_task(globals())" in desktop_text
    assert "App._run_long_task = _wave42_run_long_task" in desktop_text
    assert desktop_text.count("self._run_long_task(") == EXPECTED_CALLER_COUNT
    print("Wave 42 long-task regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
'''


def build_workflow() -> str:
    return '''name: Long task presentation Wave 42
on: [pull_request]
permissions:
  contents: read
jobs:
  validate:
    if: github.head_ref == 'agent/presentation-wave-42'
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
          python -m py_compile spina_app/long_task_presentation.py
          python -m py_compile tools/test_long_task_presentation_wave_42.py
          python -m compileall -q spina_app
      - name: Run exact long-task regression
        shell: cmd
        run: python tools/test_long_task_presentation_wave_42.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-42-redundancy.json
          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-42-quality.json
      - name: Upload Wave 42 reports
        uses: actions/upload-artifact@v4
        with:
          name: long-task-presentation-wave-42-reports
          path: |
            artifacts/wave-42-redundancy.json
            artifacts/wave-42-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(desktop_text)
    app = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS),
        None,
    )
    if app is None:
        raise RuntimeError(f"Missing class {TARGET_CLASS}")
    methods = [
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == TARGET
    ]
    if len(methods) != 1:
        raise RuntimeError(f"Expected one {TARGET_CLASS}.{TARGET}, found {len(methods)}")
    method = methods[0]
    lines = desktop_text.splitlines(keepends=True)
    source = "".join(lines[method.lineno - 1 : method.end_lineno])
    _, calls = inspect_target(method, source)
    caller_count = desktop_text.count("self._run_long_task(")
    if caller_count < 1:
        raise RuntimeError("Expected at least one long-task caller")

    import_block = (
        "\nfrom spina_app.long_task_presentation import (\n"
        "    configure_long_task_dependencies as _configure_wave42_long_task,\n"
        "    _run_long_task as _wave42_run_long_task,\n"
        ")\n"
        "_configure_wave42_long_task(globals())\n"
        "App._run_long_task = _wave42_run_long_task\n"
    )

    updated_desktop = (
        "".join(lines[: method.lineno - 1])
        + "".join(lines[method.end_lineno : app.end_lineno])
        + import_block
        + "".join(lines[app.end_lineno :])
    )

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    TEST.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(build_module(source, calls, caller_count), encoding="utf-8")
    TEST.write_text(build_test(calls, caller_count), encoding="utf-8")
    WORKFLOW.write_text(build_workflow(), encoding="utf-8")
    DESKTOP.write_text(updated_desktop, encoding="utf-8")

    print(json.dumps({
        "target": f"{TARGET_CLASS}.{TARGET}",
        "lines": EXPECTED_LINES,
        "sha256": EXPECTED_SHA256,
        "nested": EXPECTED_NESTED,
        "caller_count": caller_count,
        "calls": calls,
    }, indent=2))


if __name__ == "__main__":
    main()
