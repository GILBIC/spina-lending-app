from __future__ import annotations

import ast
import hashlib
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "collector_refresh_presentation.py"
TEST = ROOT / "tools" / "test_collector_refresh_presentation_wave_39.py"
BOOT = ROOT / ".github" / "workflows" / "collector-refresh-presentation-wave-39-bootstrap.yml"
PERM = ROOT / ".github" / "workflows" / "collector-refresh-presentation-wave-39.yml"
SELF = ROOT / "tools" / "apply_collector_refresh_presentation_wave_39.py"

EXPECTED_BASE = "973ddff4002dd86a4b7f1fe5b7936b025e36d7b4"
TARGET_CLASS = "App"
TARGET = "refresh_collectors"
EXPECTED_LINES = 608
EXPECTED_DB_CALLS = {"self.db.conn.cursor", "self.db.get_all_areas"}
EXPECTED_SQL_COUNT = 3
EXPECTED_MAKEDIRS_COUNT = 1
ALLOWED_INITIAL = {
    ".github/workflows/collector-refresh-presentation-wave-39-bootstrap.yml",
    "tools/apply_collector_refresh_presentation_wave_39.py",
}
FORBIDDEN_SQL = (
    "INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP ",
    "TRUNCATE ", "REPLACE ", "UPSERT ", "MERGE ", "ON CONFLICT",
)
FORBIDDEN_CALL_SUFFIXES = {
    "commit", "rollback", "write", "write_text", "write_bytes", "unlink",
    "remove", "rename", "copy", "copy2", "move", "rmdir", "touch",
    "dump", "dumps", "save_settings", "_write_json_atomic",
    "_spina_pg_write_json", "add_client", "update_client", "delete_client",
    "add_transaction", "update_transaction", "delete_transaction",
    "set_client_note", "save_collectors", "save_collector_routes",
}


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def normalized_source(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized_source(source).encode("utf-8")).hexdigest()


def call_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def literal_sql(call: ast.Call) -> str:
    if not call.args or not isinstance(call.args[0], ast.Constant) or not isinstance(call.args[0].value, str):
        raise SystemExit(f"Every execute() in {TARGET} must use constant SQL")
    return " ".join(call.args[0].value.split())


def validate_read_refresh(node: ast.AST, source: str) -> list[str]:
    upper = source.upper()
    for token in FORBIDDEN_SQL:
        if token in upper:
            raise SystemExit(f"Forbidden SQL mutation token in {TARGET}: {token}")
    if "COLLECTORS.JSON" not in upper:
        raise SystemExit("Expected collectors.json read path is missing")

    db_calls: set[str] = set()
    sql_statements: list[str] = []
    makedirs_count = 0
    open_count = 0

    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            chain = call_chain(item)
            if len(chain) >= 2 and chain[:2] == ["self", "db"]:
                full = ".".join(chain)
                if not any(full == allowed or full.startswith(allowed + ".") for allowed in EXPECTED_DB_CALLS):
                    raise SystemExit(f"Unexpected database attribute in {TARGET}: {full}")

        if not isinstance(item, ast.Call):
            continue
        chain = call_chain(item.func)
        full = ".".join(chain)
        suffix = chain[-1].lower() if chain else ""

        if full.startswith("self.db."):
            db_calls.add(full)
        if suffix in FORBIDDEN_CALL_SUFFIXES:
            raise SystemExit(f"Forbidden mutating call in {TARGET}: {full}")

        if suffix == "execute":
            sql = literal_sql(item)
            sql_upper = sql.upper()
            if not (sql_upper.startswith("SELECT ") or sql_upper.startswith("WITH ")):
                raise SystemExit(f"Non-read-only SQL in {TARGET}: {sql}")
            if "CLIENTS" not in sql_upper:
                raise SystemExit(f"Unexpected SQL table boundary in {TARGET}: {sql}")
            sql_statements.append(sql)

        if full == "os.makedirs":
            makedirs_count += 1
            exist_ok = next(
                (kw.value.value for kw in item.keywords if kw.arg == "exist_ok" and isinstance(kw.value, ast.Constant)),
                None,
            )
            if exist_ok is not True:
                raise SystemExit("The existing directory check must retain exist_ok=True")

        if suffix == "open":
            open_count += 1
            mode = "r"
            if len(item.args) >= 2 and isinstance(item.args[1], ast.Constant):
                mode = str(item.args[1].value)
            for kw in item.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                raise SystemExit(f"File-writing open() is not allowed in {TARGET}: mode={mode!r}")

    if db_calls != EXPECTED_DB_CALLS:
        raise SystemExit(f"Unexpected database call set: {sorted(db_calls)}")
    if len(sql_statements) != EXPECTED_SQL_COUNT:
        raise SystemExit(f"Unexpected read-only SQL count: {len(sql_statements)}")
    if makedirs_count != EXPECTED_MAKEDIRS_COUNT:
        raise SystemExit(f"Unexpected os.makedirs count: {makedirs_count}")
    if open_count != 1:
        raise SystemExit(f"Unexpected collectors.json open() count: {open_count}")
    return sql_statements


def main() -> None:
    current = run("git", "rev-parse", "HEAD")
    merge_base = run("git", "merge-base", "HEAD", "origin/main")
    if merge_base != EXPECTED_BASE:
        raise SystemExit(f"Unexpected main base: {merge_base}; expected {EXPECTED_BASE}")

    changed = {
        line.strip()
        for line in run("git", "diff", "--name-only", EXPECTED_BASE, "HEAD").splitlines()
        if line.strip()
    }
    if changed != ALLOWED_INITIAL:
        raise SystemExit(f"Unexpected initial branch files: {sorted(changed)}")

    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    app_classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == TARGET_CLASS]
    if len(app_classes) != 1:
        raise SystemExit(f"Expected exactly one {TARGET_CLASS} class, found {len(app_classes)}")
    app = app_classes[0]
    targets = [n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == TARGET]
    if len(targets) != 1:
        raise SystemExit(f"Expected exactly one {TARGET_CLASS}.{TARGET}, found {len(targets)}")
    node = targets[0]
    line_count = node.end_lineno - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise SystemExit(f"Unexpected {TARGET_CLASS}.{TARGET} line count: {line_count}")

    lines = text.splitlines(keepends=True)
    raw_source = "".join(lines[node.lineno - 1 : node.end_lineno])
    exact_source = normalized_source(raw_source)
    sql_statements = validate_read_refresh(node, exact_source)
    digest = source_hash(exact_source)

    module_header = f'''"""Read-only collector-list refresh presentation extracted in Wave 39."""\nfrom __future__ import annotations\n\n_COLLECTOR_REFRESH_DEPENDENCIES = {{}}\n_PROTECTED_GLOBALS = {{\n    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",\n    "__name__", "__package__", "__spec__", "_COLLECTOR_REFRESH_DEPENDENCIES",\n    "_PROTECTED_GLOBALS", "configure_collector_refresh_dependencies",\n    "COLLECTOR_REFRESH_SOURCE_SHA256", "COLLECTOR_REFRESH_TARGET",\n    "COLLECTOR_REFRESH_SQL",\n}}\n\n\ndef configure_collector_refresh_dependencies(namespace):\n    _COLLECTOR_REFRESH_DEPENDENCIES.clear()\n    _COLLECTOR_REFRESH_DEPENDENCIES.update(namespace)\n    for name, value in namespace.items():\n        if name not in _PROTECTED_GLOBALS:\n            globals()[name] = value\n\n\nCOLLECTOR_REFRESH_TARGET = {TARGET!r}\nCOLLECTOR_REFRESH_SOURCE_SHA256 = {digest!r}\nCOLLECTOR_REFRESH_SQL = {sql_statements!r}\n\n'''
    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(module_header + exact_source, encoding="utf-8")

    binding = '''\n# Wave 39: read-only collector-list refresh presentation.\nfrom spina_app.collector_refresh_presentation import (\n    configure_collector_refresh_dependencies as _configure_wave39_collector_refresh,\n    refresh_collectors as _wave39_refresh_collectors,\n)\n_configure_wave39_collector_refresh(globals())\nApp.refresh_collectors = _wave39_refresh_collectors\n\n'''
    new_lines = (
        lines[: node.lineno - 1]
        + lines[node.end_lineno : app.end_lineno]
        + [binding]
        + lines[app.end_lineno :]
    )
    DESKTOP.write_text("".join(new_lines), encoding="utf-8")

    test_source = f'''from __future__ import annotations\n\nimport ast\nimport hashlib\nimport textwrap\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\nDESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"\nMODULE = ROOT / "spina_app" / "collector_refresh_presentation.py"\nTARGET_CLASS = {TARGET_CLASS!r}\nTARGET = {TARGET!r}\nEXPECTED_LINES = {EXPECTED_LINES}\nEXPECTED_SHA256 = {digest!r}\nEXPECTED_DB_CALLS = {sorted(EXPECTED_DB_CALLS)!r}\nEXPECTED_SQL = {sql_statements!r}\nEXPECTED_MAKEDIRS_COUNT = {EXPECTED_MAKEDIRS_COUNT}\nFORBIDDEN_CALL_SUFFIXES = {sorted(FORBIDDEN_CALL_SUFFIXES)!r}\n\n\ndef normalized(source):\n    return textwrap.dedent(source).strip() + "\\n"\n\n\ndef call_chain(node):\n    parts = []\n    while isinstance(node, ast.Attribute):\n        parts.append(node.attr)\n        node = node.value\n    if isinstance(node, ast.Name):\n        parts.append(node.id)\n    return list(reversed(parts))\n\n\ndef main():\n    module_text = MODULE.read_text(encoding="utf-8")\n    mtree = ast.parse(module_text)\n    funcs = [n for n in mtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]\n    assert len(funcs) == 1, len(funcs)\n    node = funcs[0]\n    lines = module_text.splitlines(keepends=True)\n    source = "".join(lines[node.lineno - 1 : node.end_lineno])\n    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES\n    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256\n\n    db_calls = set()\n    sqls = []\n    makedirs_count = 0\n    open_count = 0\n    for item in ast.walk(node):\n        if isinstance(item, ast.Call):\n            chain = call_chain(item.func)\n            full = ".".join(chain)\n            suffix = chain[-1].lower() if chain else ""\n            if full.startswith("self.db."):\n                db_calls.add(full)\n            assert suffix not in FORBIDDEN_CALL_SUFFIXES, full\n            if suffix == "execute":\n                assert item.args and isinstance(item.args[0], ast.Constant) and isinstance(item.args[0].value, str)\n                sql = " ".join(item.args[0].value.split())\n                assert sql.upper().startswith(("SELECT ", "WITH ")), sql\n                assert "CLIENTS" in sql.upper(), sql\n                sqls.append(sql)\n            if full == "os.makedirs":\n                makedirs_count += 1\n                assert any(kw.arg == "exist_ok" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in item.keywords)\n            if suffix == "open":\n                open_count += 1\n                mode = "r"\n                if len(item.args) >= 2 and isinstance(item.args[1], ast.Constant):\n                    mode = str(item.args[1].value)\n                for kw in item.keywords:\n                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):\n                        mode = str(kw.value.value)\n                assert not any(flag in mode for flag in ("w", "a", "x", "+")), mode\n\n    assert db_calls == set(EXPECTED_DB_CALLS), db_calls\n    assert sqls == EXPECTED_SQL, sqls\n    assert makedirs_count == EXPECTED_MAKEDIRS_COUNT\n    assert open_count == 1\n\n    desktop_text = DESKTOP.read_text(encoding="utf-8")\n    dtree = ast.parse(desktop_text)\n    app = next(n for n in dtree.body if isinstance(n, ast.ClassDef) and n.name == TARGET_CLASS)\n    originals = [n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]\n    assert not originals\n    assert "_configure_wave39_collector_refresh(globals())" in desktop_text\n    assert "App.refresh_collectors = _wave39_refresh_collectors" in desktop_text\n    assert desktop_text.count("self.refresh_collectors") >= 5\n    print("Wave 39 collector-refresh regression passed:", EXPECTED_LINES, EXPECTED_SHA256)\n\n\nif __name__ == "__main__":\n    main()\n'''
    TEST.write_text(test_source, encoding="utf-8")

    workflow = '''name: Collector refresh presentation Wave 39\non: [pull_request]\npermissions:\n  contents: read\njobs:\n  validate:\n    if: github.head_ref == 'agent/collector-refresh-presentation-wave-39'\n    runs-on: [self-hosted, Windows, X64]\n    timeout-minutes: 45\n    steps:\n      - name: Check out exact PR head\n        uses: actions/checkout@v4\n        with:\n          ref: ${{ github.event.pull_request.head.sha }}\n          fetch-depth: 0\n      - name: Compile application, module, and test\n        shell: cmd\n        run: |\n          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py\n          python -m py_compile spina_app/collector_refresh_presentation.py\n          python -m py_compile tools/test_collector_refresh_presentation_wave_39.py\n          python -m compileall -q spina_app\n      - name: Run exact collector-refresh regression\n        shell: cmd\n        run: python tools/test_collector_refresh_presentation_wave_39.py\n      - name: Validate permanent architecture map\n        uses: ./.github/actions/architecture-map-check\n      - name: Run repository audits\n        shell: cmd\n        run: |\n          if not exist artifacts mkdir artifacts\n          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-39-redundancy.json\n          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-39-quality.json\n      - name: Upload Wave 39 reports\n        uses: actions/upload-artifact@v4\n        with:\n          name: collector-refresh-presentation-wave-39-reports\n          path: |\n            artifacts/wave-39-redundancy.json\n            artifacts/wave-39-quality.json\n            architecture-map.json\n            docs/architecture\n          if-no-files-found: error\n'''
    PERM.write_text(workflow, encoding="utf-8")

    if BOOT.exists():
        BOOT.unlink()
    if SELF.exists():
        SELF.unlink()

    print(
        f"Extracted {TARGET_CLASS}.{TARGET}: {EXPECTED_LINES} lines, "
        f"sha256={digest}, sql_count={len(sql_statements)}, branch_head={current}"
    )


if __name__ == "__main__":
    main()
