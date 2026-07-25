from __future__ import annotations

import ast
import hashlib
import importlib.util
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "note_editor_presentation.py"
TARGET = 'NoteEditorDialog'
EXPECTED_LINES = 638
EXPECTED_SHA256 = 'dac0182a8bd3d55f588d4075758b48a1d8ec1f9072c7af7c1488fd68ae966f3d'
EXPECTED_METHODS = ['__init__', '_migrate_legacy_notes_if_needed', '_title_text', '_set_dirty', '_note_date_value', '_sig_for_text', '_validate_date_or_warn', '_auto_choose_scope', '_scope_label', '_format_list_item', '_focus_search', '_build_ui', '_collect_items', '_refresh_list', '_on_list_select', '_pick_date', '_jump_today', '_jump_default', '_clear_text', '_open_notes_file', '_load_note', '_save_note', '_delete_note', '_on_text_modified', '_schedule_autosave', '_confirm_before_switch', '_save_and_close', '_close']
FORBIDDEN_CALL_SUFFIXES = ['add_client', 'add_transaction', 'archive_client', 'close_databank_day', 'commit', 'cursor', 'delete_client', 'delete_transaction', 'execute', 'executemany', 'renew_client', 'reopen_databank_day', 'restore_client', 'rollback', 'set_transaction', 'update_client', 'update_transaction']
FORBIDDEN_SQL_TOKENS = ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'TRUNCATE TABLE')


def normalized(source):
    return textwrap.dedent(source).strip() + "\n"


def call_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def main():
    spec = importlib.util.spec_from_file_location(
        "wave40_note_editor_import_smoke", MODULE
    )
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    assert issubclass(imported.NoteEditorDialog, imported.tk.Toplevel)

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
