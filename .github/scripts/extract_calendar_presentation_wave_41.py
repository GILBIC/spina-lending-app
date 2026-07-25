from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "calendar_presentation.py"
TEST = ROOT / "tools" / "test_calendar_presentation_wave_41.py"
WORKFLOW = ROOT / ".github" / "workflows" / "calendar-presentation-wave-41.yml"

TARGETS = ["_CalendarPopup", "_CalendarRangePopup", "pick_date_range", "pick_date"]
EXPECTED_LINES = {
    "_CalendarPopup": 129,
    "_CalendarRangePopup": 196,
    "pick_date_range": 44,
    "pick_date": 30,
}
EXPECTED_METHODS = {
    "_CalendarPopup": [
        "__init__", "_build_ui", "_render", "_pick", "_prev_month",
        "_next_month", "_today", "_clear", "_close",
    ],
    "_CalendarRangePopup": [
        "__init__", "_build_ui", "_render", "_refresh_info", "_pick",
        "_apply", "_prev_month", "_next_month", "_today", "_clear", "_close",
    ],
}
FORBIDDEN_CALL_SUFFIXES = {
    "add_client", "add_transaction", "archive_client", "close_databank_day",
    "commit", "cursor", "delete_client", "delete_transaction", "execute",
    "executemany", "renew_client", "reopen_databank_day", "restore_client",
    "rollback", "set_client_note", "set_transaction", "update_client",
    "update_transaction", "write", "write_bytes", "write_text",
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


def source_for(node: ast.AST, lines: list[str]) -> str:
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def inspect_targets(tree: ast.Module, text: str) -> tuple[list[ast.AST], dict[str, str], dict[str, list[str]]]:
    top_level = [
        node for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    matches: list[ast.AST] = []
    indexes: list[int] = []
    for target in TARGETS:
        found = [node for node in top_level if node.name == target]
        if len(found) != 1:
            raise RuntimeError(f"Expected exactly one top-level {target}, found {len(found)}")
        matches.append(found[0])
        indexes.append(tree.body.index(found[0]))

    expected_indexes = list(range(indexes[0], indexes[0] + len(indexes)))
    if indexes != expected_indexes:
        raise RuntimeError(f"Wave 41 targets are no longer consecutive: {indexes}")

    lines = text.splitlines(keepends=True)
    hashes: dict[str, str] = {}
    methods: dict[str, list[str]] = {}
    for node in matches:
        name = node.name
        line_count = node.end_lineno - node.lineno + 1
        if line_count != EXPECTED_LINES[name]:
            raise RuntimeError(
                f"Unexpected {name} line count: expected {EXPECTED_LINES[name]}, found {line_count}"
            )
        src = source_for(node, lines)
        hashes[name] = hashlib.sha256(normalized(src).encode("utf-8")).hexdigest()
        if isinstance(node, ast.ClassDef):
            actual_methods = [
                item.name for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if actual_methods != EXPECTED_METHODS[name]:
                raise RuntimeError(
                    f"Unexpected {name} method inventory: {actual_methods}"
                )
            methods[name] = actual_methods

        for item in ast.walk(node):
            if isinstance(item, ast.Attribute):
                chain = ".".join(call_chain(item))
                if chain.startswith("self.db"):
                    raise RuntimeError(f"Forbidden database dependency in {name}: {chain}")
            if isinstance(item, ast.Call):
                parts = call_chain(item.func)
                suffix = parts[-1].lower() if parts else ""
                if suffix in FORBIDDEN_CALL_SUFFIXES:
                    raise RuntimeError(
                        f"Forbidden mutation/database call in {name}: {'.'.join(parts)}"
                    )
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                upper = " ".join(item.value.upper().split())
                if any(token in upper for token in FORBIDDEN_SQL_TOKENS):
                    raise RuntimeError(f"Forbidden SQL text in {name}: {upper[:120]}")

    return matches, hashes, methods


def build_module(definitions: str, hashes: dict[str, str], methods: dict[str, list[str]]) -> str:
    metadata_lines = {
        name: EXPECTED_LINES[name] for name in TARGETS
    }
    return (
        '"""Calendar and date-picker presentation extracted in Wave 41."""\n'
        "from __future__ import annotations\n\n"
        "import calendar\n"
        "from datetime import date, datetime, timedelta\n"
        "import tkinter as tk\n"
        "from tkinter import messagebox, ttk\n\n"
        "_CALENDAR_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',\n"
        "    '__name__', '__package__', '__spec__', '_CALENDAR_DEPENDENCIES',\n"
        "    '_PROTECTED_GLOBALS', 'configure_calendar_dependencies',\n"
        "    'CALENDAR_TARGETS', 'CALENDAR_SOURCE_LINES', 'CALENDAR_SOURCE_SHA256',\n"
        "    'CALENDAR_METHODS', 'calendar', 'date', 'datetime', 'timedelta',\n"
        "    'tk', 'ttk', 'messagebox',\n"
        "}\n\n\n"
        "def configure_calendar_dependencies(namespace):\n"
        "    _CALENDAR_DEPENDENCIES.clear()\n"
        "    _CALENDAR_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n\n"
        f"CALENDAR_TARGETS = {TARGETS!r}\n"
        f"CALENDAR_SOURCE_LINES = {metadata_lines!r}\n"
        f"CALENDAR_SOURCE_SHA256 = {hashes!r}\n"
        f"CALENDAR_METHODS = {methods!r}\n\n"
        + definitions.rstrip()
        + "\n"
    )


def build_test(hashes: dict[str, str], methods: dict[str, list[str]]) -> str:
    return f'''from __future__ import annotations

import ast
import hashlib
import importlib.util
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "calendar_presentation.py"
TARGETS = {TARGETS!r}
EXPECTED_LINES = {EXPECTED_LINES!r}
EXPECTED_SHA256 = {hashes!r}
EXPECTED_METHODS = {methods!r}
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
    spec = importlib.util.spec_from_file_location("wave41_calendar_import_smoke", MODULE)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    assert issubclass(imported._CalendarPopup, imported.tk.Toplevel)
    assert issubclass(imported._CalendarRangePopup, imported.tk.Toplevel)
    assert callable(imported.pick_date_range)
    assert callable(imported.pick_date)

    module_text = MODULE.read_text(encoding="utf-8")
    mtree = ast.parse(module_text)
    lines = module_text.splitlines(keepends=True)
    found = {{
        node.name: node for node in mtree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in TARGETS
    }}
    assert list(name for name in TARGETS if name in found) == TARGETS
    assert len(found) == len(TARGETS)

    for name in TARGETS:
        node = found[name]
        source = "".join(lines[node.lineno - 1 : node.end_lineno])
        assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES[name]
        assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256[name]
        if isinstance(node, ast.ClassDef):
            actual_methods = [
                item.name for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            assert actual_methods == EXPECTED_METHODS[name], actual_methods

        for item in ast.walk(node):
            if isinstance(item, ast.Attribute):
                chain = ".".join(call_chain(item))
                assert not chain.startswith("self.db"), chain
            if isinstance(item, ast.Call):
                parts = call_chain(item.func)
                suffix = parts[-1].lower() if parts else ""
                assert suffix not in FORBIDDEN_CALL_SUFFIXES, ".".join(parts)
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                upper = " ".join(item.value.upper().split())
                assert not any(token in upper for token in FORBIDDEN_SQL_TOKENS), upper

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    dtree = ast.parse(desktop_text)
    originals = [
        node.name for node in dtree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in TARGETS
    ]
    assert not originals, originals
    assert "_configure_wave41_calendar(globals())" in desktop_text
    for name in TARGETS:
        assert f"{{name}} = _wave41{{name}}" in desktop_text
    assert desktop_text.count("pick_date(") >= 1
    print("Wave 41 calendar presentation regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
'''


def build_workflow() -> str:
    return '''name: Calendar presentation Wave 41
on: [pull_request]
permissions:
  contents: read
jobs:
  validate:
    if: github.head_ref == 'agent/calendar-presentation-wave-41'
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
          python -m py_compile spina_app\calendar_presentation.py
          python -m py_compile tools\test_calendar_presentation_wave_41.py
          python -m compileall -q spina_app
      - name: Run exact calendar-presentation regression
        shell: cmd
        run: python tools\test_calendar_presentation_wave_41.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts\wave-41-redundancy.json
          python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts\wave-41-quality.json
      - name: Upload Wave 41 reports
        uses: actions/upload-artifact@v4
        with:
          name: calendar-presentation-wave-41-reports
          path: |
            artifacts/wave-41-redundancy.json
            artifacts/wave-41-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(desktop_text)
    matches, hashes, methods = inspect_targets(tree, desktop_text)
    lines = desktop_text.splitlines(keepends=True)

    first = matches[0]
    last = matches[-1]
    definitions = "".join(lines[first.lineno - 1 : last.end_lineno])

    import_block = (
        "from spina_app.calendar_presentation import (\n"
        "    configure_calendar_dependencies as _configure_wave41_calendar,\n"
        "    _CalendarPopup as _wave41_CalendarPopup,\n"
        "    _CalendarRangePopup as _wave41_CalendarRangePopup,\n"
        "    pick_date_range as _wave41pick_date_range,\n"
        "    pick_date as _wave41pick_date,\n"
        ")\n"
        "_configure_wave41_calendar(globals())\n"
        "_CalendarPopup = _wave41_CalendarPopup\n"
        "_CalendarRangePopup = _wave41_CalendarRangePopup\n"
        "pick_date_range = _wave41pick_date_range\n"
        "pick_date = _wave41pick_date\n"
    )

    updated_desktop = (
        "".join(lines[: first.lineno - 1])
        + import_block
        + "".join(lines[last.end_lineno :])
    )

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    TEST.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(build_module(definitions, hashes, methods), encoding="utf-8")
    TEST.write_text(build_test(hashes, methods), encoding="utf-8")
    WORKFLOW.write_text(build_workflow(), encoding="utf-8")
    DESKTOP.write_text(updated_desktop, encoding="utf-8")

    result = {
        "targets": TARGETS,
        "lines": EXPECTED_LINES,
        "hashes": hashes,
        "methods": methods,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
