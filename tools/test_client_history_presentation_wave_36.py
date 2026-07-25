from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_history_presentation.py"
TARGET = '_app_open_client_history_dialog'
EXPECTED_SHA256 = '570a2e0946cd702bfcdcbc1d3433b72ab9aed73fd61fba56be70e1ebb53555b8'
EXPECTED_LINES = 514
ALLOWED_DB_READS = ['get_client_history', 'get_client_uid', 'get_linked_client_uids', 'get_transaction_history_for_client_uids', 'get_transactions_for_client_uids']
FORBIDDEN_TEXT = ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'TRUNCATE ', 'ON CONFLICT', '.COMMIT(', '.ROLLBACK(', 'WRITE_TEXT(', 'WRITE_BYTES(', '.UNLINK(', 'SAVE_SETTINGS(', '_WRITE_JSON_ATOMIC(', 'ADD_TRANSACTION(', 'UPDATE_TRANSACTION(', 'DELETE_TRANSACTION(', 'SET_CLIENT_NOTE(', 'ADD_CLIENT(', 'UPDATE_CLIENT(')
FORBIDDEN_MUTATING_ATTRS = ['commit', 'copy', 'copy2', 'makedirs', 'mkdir', 'move', 'rename', 'rmdir', 'rollback', 'touch', 'unlink', 'write', 'write_bytes', 'write_text']


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def digest(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def call_chain(node: ast.AST) -> list[str]:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text, filename=str(MODULE))
    funcs = {
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert TARGET in funcs
    node = funcs[TARGET]
    segment = ast.get_source_segment(module_text, node)
    assert segment
    assert digest(segment) == EXPECTED_SHA256
    actual_lines = (node.end_lineno or node.lineno) - node.lineno + 1
    assert actual_lines == EXPECTED_LINES, (actual_lines, EXPECTED_LINES)

    upper = segment.upper()
    for token in FORBIDDEN_TEXT:
        assert token not in upper, token
    db_calls = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        chain = call_chain(item.func)
        if len(chain) >= 3 and chain[:2] == ["self", "db"]:
            db_calls.add(chain[2])
            assert chain[2] in ALLOWED_DB_READS, chain
        if isinstance(item.func, ast.Attribute):
            assert item.func.attr.lower() not in FORBIDDEN_MUTATING_ATTRS, item.func.attr
        elif isinstance(item.func, ast.Name):
            assert item.func.id.lower() not in FORBIDDEN_MUTATING_ATTRS, item.func.id
            assert item.func.id.lower() != "open", item.func.id
    assert db_calls == set(ALLOWED_DB_READS), sorted(db_calls)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text, filename=str(DESKTOP))
    top_defs = {
        node.name
        for node in desktop_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert TARGET not in top_defs
    imported = False
    rebound = False
    for node in desktop_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.client_history_presentation":
            imported = any(alias.name == TARGET for alias in node.names)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == TARGET:
                    rebound = True
    assert imported
    assert rebound
    assert "def open_client_history_dialog" in desktop_text
    print(f"Wave 36 client-history regression passed: {TARGET} / {actual_lines} lines.")


if __name__ == "__main__":
    main()
