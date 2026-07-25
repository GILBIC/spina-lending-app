from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_form_presentation.py"
TARGET = '_app__client_form'
EXPECTED_LINES = 649
EXPECTED_SHA256 = '27275a78cce0db295c824d3156f5dedb3945881ccf0de4ed25a075a2d31579b4'
FORBIDDEN_TEXT = ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'TRUNCATE ', 'ON CONFLICT', '.COMMIT(', '.ROLLBACK(', 'WRITE_TEXT(', 'WRITE_BYTES(', '.UNLINK(', 'SAVE_SETTINGS(', '_WRITE_JSON_ATOMIC(', 'ADD_TRANSACTION(', 'UPDATE_TRANSACTION(', 'DELETE_TRANSACTION(', 'SET_CLIENT_NOTE(', 'ADD_CLIENT(', 'UPDATE_CLIENT(', 'DELETE_CLIENT(')
FORBIDDEN_CALL_SUFFIXES = ['_spina_pg_write_json', '_write_json_atomic', 'add_client', 'add_transaction', 'commit', 'copy', 'copy2', 'delete_client', 'delete_transaction', 'makedirs', 'mkdir', 'move', 'rename', 'rmdir', 'rollback', 'save_settings', 'set_client_note', 'touch', 'unlink', 'update_client', 'update_transaction', 'write', 'write_bytes', 'write_text']


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
    module_text = MODULE.read_text(encoding="utf-8")
    mtree = ast.parse(module_text)
    funcs = [n for n in mtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert len(funcs) == 1, len(funcs)
    node = funcs[0]
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1: node.end_lineno])
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256
    upper = source.upper()
    for token in FORBIDDEN_TEXT:
        assert token not in upper, token
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            chain = call_chain(item)
            assert not (len(chain) >= 2 and chain[:2] == ["self", "db"]), chain
        if isinstance(item, ast.Call):
            chain = call_chain(item.func)
            assert not (chain and chain[-1].lower() in FORBIDDEN_CALL_SUFFIXES), chain

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    dtree = ast.parse(desktop_text)
    originals = [n for n in dtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert not originals
    assert "_configure_wave38_client_form(globals())" in desktop_text
    assert "_app__client_form = _wave38_app__client_form" in desktop_text
    assert "def _app_add_client_dialog" in desktop_text
    assert "def _app_on_client_edit" in desktop_text
    print("Wave 38 client-form regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
