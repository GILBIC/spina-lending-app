from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "area_picker_presentation.py"
TARGET = '_area_picker_dialog'
EXPECTED_LINES = 511
EXPECTED_SHA256 = 'a4c345a42eba11320782ef12cba951c1a5d365bbb0d70e1139c2343aa98624c1'
ALLOWED_DB_CALLS = {'conn.cursor', 'get_all_areas'}
FORBIDDEN_TEXT = ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'TRUNCATE ', 'ON CONFLICT', '.COMMIT(', '.ROLLBACK(', 'WRITE_TEXT(', 'WRITE_BYTES(', '.UNLINK(', 'SAVE_SETTINGS(', '_WRITE_JSON_ATOMIC(', 'ADD_TRANSACTION(', 'UPDATE_TRANSACTION(', 'DELETE_TRANSACTION(', 'SET_CLIENT_NOTE(', 'ADD_CLIENT(', 'UPDATE_CLIENT(', 'DELETE_CLIENT(', 'ADD_AREA(', 'UPDATE_AREA(', 'DELETE_AREA(')


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def digest(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def call_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def main() -> None:
    module_source = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_source, filename=str(MODULE))
    funcs = {
        node.name: node for node in module_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert TARGET in funcs
    node = funcs[TARGET]
    segment = ast.get_source_segment(module_source, node)
    assert segment
    assert (node.end_lineno or node.lineno) - node.lineno + 1 == EXPECTED_LINES
    assert digest(segment) == EXPECTED_SHA256

    upper = segment.upper()
    for token in FORBIDDEN_TEXT:
        assert token not in upper, token

    db_calls = set()
    select_count = 0
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        chain = call_chain(item.func)
        if len(chain) >= 3 and chain[:2] == ["self", "db"]:
            db_calls.add(".".join(chain[2:]))
        if chain and chain[-1] == "execute":
            assert item.args
            sql_node = item.args[0]
            assert isinstance(sql_node, ast.Constant) and isinstance(sql_node.value, str)
            sql = " ".join(sql_node.value.split()).upper()
            assert sql.startswith("SELECT ")
            assert " FROM CLIENTS" in sql
            select_count += 1
        if isinstance(item.func, ast.Name):
            assert item.func.id != "open"
    assert db_calls == ALLOWED_DB_CALLS
    assert select_count == 1

    desktop_source = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_source, filename=str(DESKTOP))
    app = next(
        node for node in desktop_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == TARGET
        for node in app.body
    )

    rebound = False
    for top in desktop_tree.body:
        if not isinstance(top, ast.Assign) or top.lineno <= (app.end_lineno or 0):
            continue
        for target in top.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
                and target.attr == TARGET
            ):
                rebound = True
    assert rebound
    assert "from spina_app.area_picker_presentation import (" in desktop_source

    print("Wave 37 area-picker presentation regression passed.")


if __name__ == "__main__":
    main()
