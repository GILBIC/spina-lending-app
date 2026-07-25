from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "note_editor_presentation.py"
TEST = ROOT / "tools" / "test_note_editor_presentation_wave_40.py"
WORKFLOW = ROOT / ".github" / "workflows" / "note-editor-presentation-wave-40.yml"

TARGET = "NoteEditorDialog"
EXPECTED_LINES = 638
EXPECTED_METHODS = [
    "__init__",
    "_migrate_legacy_notes_if_needed",
    "_title_text",
    "_set_dirty",
    "_note_date_value",
    "_sig_for_text",
    "_validate_date_or_warn",
    "_auto_choose_scope",
    "_scope_label",
    "_format_list_item",
    "_focus_search",
    "_build_ui",
    "_collect_items",
    "_refresh_list",
    "_on_list_select",
    "_pick_date",
    "_jump_today",
    "_jump_default",
    "_clear_text",
    "_open_notes_file",
    "_load_note",
    "_save_note",
    "_delete_note",
    "_on_text_modified",
    "_schedule_autosave",
    "_confirm_before_switch",
    "_save_and_close",
    "_close",
]
FORBIDDEN_CALL_SUFFIXES = {
    "execute",
    "executemany",
    "commit",
    "rollback",
    "cursor",
    "add_client",
    "update_client",
    "renew_client",
    "delete_client",
    "archive_client",
    "restore_client",
    "add_transaction",
    "update_transaction",
    "delete_transaction",
    "set_transaction",
    "close_databank_day",
    "reopen_databank_day",
}
FORBIDDEN_SQL_TOKENS = (
    "INSERT INTO",
    "UPDATE ",
    "DELETE FROM",
    "CREATE TABLE",
    "ALTER TABLE",
    "DROP TABLE",
    "TRUNCATE TABLE",
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


def validate_target(node: ast.ClassDef, source: str) -> tuple[str, list[str]]:
    line_count = node.end_lineno - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise AssertionError(f"Expected {EXPECTED_LINES} lines for {TARGET}, found {line_count}")

    methods = [
        item.name
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if methods != EXPECTED_METHODS:
        raise AssertionError(f"Unexpected {TARGET} method inventory: {methods!r}")

    calls: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            chain = ".".join(call_chain(item))
            if chain.startswith("self.db"):
                raise AssertionError(f"Direct database dependency in {TARGET}: {chain}")
        if isinstance(item, ast.Call):
            chain_parts = call_chain(item.func)
            chain = ".".join(chain_parts)
            suffix = chain_parts[-1].lower() if chain_parts else ""
            calls.add(chain)
            if suffix in FORBIDDEN_CALL_SUFFIXES:
                raise AssertionError(f"Forbidden business/database call in {TARGET}: {chain}")
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            upper = " ".join(item.value.upper().split())
            for token in FORBIDDEN_SQL_TOKENS:
                if token in upper:
                    raise AssertionError(f"SQL mutation token {token!r} found in {TARGET}")

    digest = hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()
    return digest, sorted(call for call in calls if call)


def build_module(class_source: str, digest: str, calls: list[str]) -> str:
    header = f'''"""Client-note editor presentation extracted in Wave 40."""
from __future__ import annotations

_NOTE_EDITOR_DEPENDENCIES = {{}}
_PROTECTED_GLOBALS = {{
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "_NOTE_EDITOR_DEPENDENCIES",
    "_PROTECTED_GLOBALS", "configure_note_editor_dependencies",
    "NOTE_EDITOR_SOURCE_SHA256", "NOTE_EDITOR_SOURCE_LINES",
    "NOTE_EDITOR_TARGET", "NOTE_EDITOR_METHODS", "NOTE_EDITOR_CALLS",
}}


def configure_note_editor_dependencies(namespace):
    _NOTE_EDITOR_DEPENDENCIES.clear()
    _NOTE_EDITOR_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


NOTE_EDITOR_TARGET = {TARGET!r}
NOTE_EDITOR_SOURCE_SHA256 = {digest!r}
NOTE_EDITOR_SOURCE_LINES = {EXPECTED_LINES}
NOTE_EDITOR_METHODS = {EXPECTED_METHODS!r}
NOTE_EDITOR_CALLS = {calls!r}

'''
    return header + normalized(class_source)


def build_test(digest: str) -> str:
    return f'''from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "note_editor_presentation.py"
TARGET = {TARGET!r}
EXPECTED_LINES = {EXPECTED_LINES}
EXPECTED_SHA256 = {digest!r}
EXPECTED_METHODS = {EXPECTED_METHODS!r}
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
    module_text = MODULE.read_text(encoding="utf-8")
    mtree = ast.parse(module_text)
    classes = [n for n in mtree.body if isinstance(n, ast.ClassDef) and n.name == TARGET]
    assert len(classes) == 1, len(classes)
    node = classes[0]
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1 : node.end_lineno])
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256

    methods = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert methods == EXPECTED_METHODS, methods

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
    originals = [n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == TARGET]
    assert not originals
    assert "_configure_wave40_note_editor(globals())" in desktop_text
    assert "NoteEditorDialog = _wave40_NoteEditorDialog" in desktop_text
    assert desktop_text.count("NoteEditorDialog(") >= 1
    print("Wave 40 note-editor regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
'''


def build_workflow() -> str:
    return '''name: Note editor presentation Wave 40
on: [pull_request]
permissions:
  contents: read
jobs:
  validate:
    if: github.head_ref == 'agent/note-editor-presentation-wave-40'
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
          python -m py_compile spina_app/note_editor_presentation.py
          python -m py_compile tools/test_note_editor_presentation_wave_40.py
          python -m compileall -q spina_app
      - name: Run exact note-editor regression
        shell: cmd
        run: python tools/test_note_editor_presentation_wave_40.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-40-redundancy.json
          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-40-quality.json
      - name: Upload Wave 40 reports
        uses: actions/upload-artifact@v4
        with:
          name: note-editor-presentation-wave-40-reports
          path: |
            artifacts/wave-40-redundancy.json
            artifacts/wave-40-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    matches = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == TARGET]
    if len(matches) != 1:
        raise AssertionError(f"Expected one top-level {TARGET}, found {len(matches)}")
    node = matches[0]
    lines = text.splitlines(keepends=True)
    class_source = "".join(lines[node.lineno - 1 : node.end_lineno])
    digest, calls = validate_target(node, class_source)

    replacement = '''# Wave 40: client-note editor presentation.
from spina_app.note_editor_presentation import (
    configure_note_editor_dependencies as _configure_wave40_note_editor,
    NoteEditorDialog as _wave40_NoteEditorDialog,
)
_configure_wave40_note_editor(globals())
NoteEditorDialog = _wave40_NoteEditorDialog
'''
    new_text = "".join(lines[: node.lineno - 1]) + replacement + "".join(lines[node.end_lineno :])

    parsed = ast.parse(new_text)
    remaining = [n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == TARGET]
    if remaining:
        raise AssertionError(f"Original {TARGET} remained after extraction")

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    TEST.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW.parent.mkdir(parents=True, exist_ok=True)

    MODULE.write_text(build_module(class_source, digest, calls), encoding="utf-8", newline="\n")
    TEST.write_text(build_test(digest), encoding="utf-8", newline="\n")
    WORKFLOW.write_text(build_workflow(), encoding="utf-8", newline="\n")
    DESKTOP.write_text(new_text, encoding="utf-8", newline="\n")

    print(json.dumps({
        "target": TARGET,
        "lines": EXPECTED_LINES,
        "sha256": digest,
        "methods": EXPECTED_METHODS,
        "calls": calls,
        "module": str(MODULE.relative_to(ROOT)),
        "test": str(TEST.relative_to(ROOT)),
        "workflow": str(WORKFLOW.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
