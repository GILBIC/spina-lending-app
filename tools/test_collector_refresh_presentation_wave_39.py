from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "collector_refresh_presentation.py"
TARGET_CLASS = 'App'
TARGET = 'refresh_collectors'
EXPECTED_LINES = 608
EXPECTED_SHA256 = '58bcc1ef246ac707440418d1ccf34006f653aa6d3a8e2ac9122f05d233a4b1dd'
EXPECTED_DB_CALLS = ['self.db.conn.cursor', 'self.db.get_all_areas']
EXPECTED_SQL = ["SELECT DISTINCT TRIM(area) AS a FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 ORDER BY a COLLATE NOCASE", "SELECT COUNT(*) AS c FROM clients WHERE IFNULL(TRIM(area),'')='' AND COALESCE(is_archived,0)=0", "SELECT TRIM(area) AS area, loan_type, COUNT(*) AS c FROM clients WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 GROUP BY TRIM(area), loan_type"]
EXPECTED_MAKEDIRS_COUNT = 1
FORBIDDEN_CALL_SUFFIXES = ['_spina_pg_write_json', '_write_json_atomic', 'add_client', 'add_transaction', 'commit', 'copy', 'copy2', 'delete_client', 'delete_transaction', 'dump', 'dumps', 'move', 'remove', 'rename', 'rmdir', 'rollback', 'save_collector_routes', 'save_collectors', 'save_settings', 'set_client_note', 'touch', 'unlink', 'update_client', 'update_transaction', 'write', 'write_bytes', 'write_text']


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
    source = "".join(lines[node.lineno - 1 : node.end_lineno])
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256

    db_calls = set()
    sqls = []
    makedirs_count = 0
    open_count = 0
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            chain = call_chain(item.func)
            full = ".".join(chain)
            suffix = chain[-1].lower() if chain else ""
            if full.startswith("self.db."):
                db_calls.add(full)
            assert suffix not in FORBIDDEN_CALL_SUFFIXES, full
            if suffix == "execute":
                assert item.args and isinstance(item.args[0], ast.Constant) and isinstance(item.args[0].value, str)
                sql = " ".join(item.args[0].value.split())
                assert sql.upper().startswith(("SELECT ", "WITH ")), sql
                assert "CLIENTS" in sql.upper(), sql
                sqls.append(sql)
            if full == "os.makedirs":
                makedirs_count += 1
                assert any(kw.arg == "exist_ok" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in item.keywords)
            if suffix == "open":
                open_count += 1
                mode = "r"
                if len(item.args) >= 2 and isinstance(item.args[1], ast.Constant):
                    mode = str(item.args[1].value)
                for kw in item.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = str(kw.value.value)
                assert not any(flag in mode for flag in ("w", "a", "x", "+")), mode

    assert db_calls == set(EXPECTED_DB_CALLS), db_calls
    assert sqls == EXPECTED_SQL, sqls
    assert makedirs_count == EXPECTED_MAKEDIRS_COUNT
    assert open_count == 1

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    dtree = ast.parse(desktop_text)
    app = next(n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == TARGET_CLASS)
    originals = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
    assert not originals
    assert "_configure_wave39_collector_refresh(globals())" in desktop_text
    assert "App.refresh_collectors = _wave39_refresh_collectors" in desktop_text
    assert desktop_text.count("self.refresh_collectors") >= 5
    print("Wave 39 collector-refresh regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
