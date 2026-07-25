from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "area_picker_presentation.py"
TEST = ROOT / "tools" / "test_area_picker_presentation_wave_37.py"
BOOT = ROOT / ".github" / "workflows" / "area-picker-presentation-wave-37-bootstrap.yml"
PERM = ROOT / ".github" / "workflows" / "area-picker-presentation-wave-37.yml"
SELF = ROOT / "tools" / "apply_area_picker_presentation_wave_37.py"

EXPECTED_BASE = "f9ce15a100982512f108491f447fd5e850bbf9da"
TARGET = "_area_picker_dialog"
EXPECTED_LINES = 511
ALLOWED_INITIAL = {
    ".github/workflows/area-picker-presentation-wave-37-bootstrap.yml",
    "tools/apply_area_picker_presentation_wave_37.py",
}
ALLOWED_DB_CALLS = {"get_all_areas", "conn.cursor"}
FORBIDDEN_TEXT = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE ", "ON CONFLICT", ".COMMIT(", ".ROLLBACK(",
    "WRITE_TEXT(", "WRITE_BYTES(", ".UNLINK(", "SAVE_SETTINGS(",
    "_WRITE_JSON_ATOMIC(", "ADD_TRANSACTION(", "UPDATE_TRANSACTION(",
    "DELETE_TRANSACTION(", "SET_CLIENT_NOTE(", "ADD_CLIENT(", "UPDATE_CLIENT(",
    "DELETE_CLIENT(", "ADD_AREA(", "UPDATE_AREA(", "DELETE_AREA(",
)
FORBIDDEN_APPLICATION_CALLS = {
    "_write_json_atomic", "add_area", "add_client", "add_transaction", "commit",
    "delete_area", "delete_client", "delete_transaction", "load_settings",
    "rollback", "save_settings", "set_client_note", "update_area",
    "update_client", "update_transaction",
}
FORBIDDEN_FS_CALLS = {
    "copy", "copy2", "makedirs", "mkdir", "move", "remove", "rename", "rmdir",
    "touch", "unlink", "write", "write_bytes", "write_text",
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


def validate_read_only(node: ast.AST, source: str) -> list[str]:
    upper = source.upper()
    for token in FORBIDDEN_TEXT:
        if token in upper:
            raise SystemExit(f"Forbidden mutation token in {TARGET}: {token}")

    db_calls: set[str] = set()
    select_sql: list[str] = []

    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        chain = call_chain(item.func)
        dotted = ".".join(chain)

        if len(chain) >= 3 and chain[:2] == ["self", "db"]:
            suffix = ".".join(chain[2:])
            db_calls.add(suffix)
            if suffix not in ALLOWED_DB_CALLS:
                raise SystemExit(f"Unexpected self.db call in {TARGET}: {dotted}")

        if chain and chain[-1] == "execute":
            if not item.args:
                raise SystemExit("SQL execute call without SQL text")
            sql_node = item.args[0]
            if not isinstance(sql_node, ast.Constant) or not isinstance(sql_node.value, str):
                raise SystemExit("Dynamic SQL is not allowed in Wave 37")
            compact = " ".join(sql_node.value.split())
            if not compact.upper().startswith("SELECT "):
                raise SystemExit(f"Non-SELECT SQL found: {compact[:100]}")
            select_sql.append(compact)

        if chain and chain[-1] in FORBIDDEN_APPLICATION_CALLS:
            raise SystemExit(f"Forbidden application mutation in {TARGET}: {dotted}")

        if chain and chain[-1] in FORBIDDEN_FS_CALLS:
            root = chain[0] if chain else ""
            if root in {"os", "shutil", "pathlib", "Path"}:
                raise SystemExit(f"Forbidden filesystem mutation in {TARGET}: {dotted}")

        if isinstance(item.func, ast.Name) and item.func.id == "open":
            raise SystemExit("File open() is not allowed in Wave 37")

    if db_calls != ALLOWED_DB_CALLS:
        raise SystemExit(
            f"Unexpected database call set: {sorted(db_calls)}; "
            f"expected {sorted(ALLOWED_DB_CALLS)}"
        )
    if len(select_sql) != 1:
        raise SystemExit(f"Expected exactly one SELECT query, found {len(select_sql)}")
    if " FROM CLIENTS" not in select_sql[0].upper():
        raise SystemExit(f"Unexpected SELECT table: {select_sql[0]}")
    return select_sql


def find_app_method(tree: ast.Module) -> tuple[ast.ClassDef, ast.FunctionDef]:
    app = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"),
        None,
    )
    if app is None:
        raise SystemExit("App class not found")
    matches = [
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == TARGET
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one App.{TARGET}, found {len(matches)}")
    return app, matches[0]


def make_module(source: str, digest: str, select_sql: list[str]) -> str:
    body = normalized_source(source)
    prefix = (
        '"""Read-only route area-picker presentation extracted in Wave 37."""\n'
        "from __future__ import annotations\n\n"
        "_AREA_PICKER_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        '    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",\n'
        '    "__name__", "__package__", "__spec__", "_AREA_PICKER_DEPENDENCIES",\n'
        '    "_PROTECTED_GLOBALS", "configure_area_picker_dependencies",\n'
        '    "AREA_PICKER_SOURCE_SHA256", "AREA_PICKER_TARGET",\n'
        '    "AREA_PICKER_SELECT_SQL",\n'
        "}\n\n\n"
        "def configure_area_picker_dependencies(namespace):\n"
        "    _AREA_PICKER_DEPENDENCIES.clear()\n"
        "    _AREA_PICKER_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n\n"
        f"AREA_PICKER_TARGET = {TARGET!r}\n"
        f"AREA_PICKER_SOURCE_SHA256 = {digest!r}\n"
        f"AREA_PICKER_SELECT_SQL = {select_sql!r}\n\n"
    )
    return prefix + body


def make_test(digest: str) -> str:
    return f"""from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "area_picker_presentation.py"
TARGET = {TARGET!r}
EXPECTED_LINES = {EXPECTED_LINES}
EXPECTED_SHA256 = {digest!r}
ALLOWED_DB_CALLS = {ALLOWED_DB_CALLS!r}
FORBIDDEN_TEXT = {FORBIDDEN_TEXT!r}


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\\n"


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
    funcs = {{
        node.name: node for node in module_tree.body
        if isinstance(node, ast.FunctionDef)
    }}
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
"""


def permanent_workflow() -> str:
    return """name: Area picker presentation Wave 37
on: [pull_request]
permissions:
  contents: read
jobs:
  validate:
    if: github.head_ref == 'agent/area-picker-presentation-wave-37'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 40
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
          python -m py_compile spina_app/area_picker_presentation.py
          python -m py_compile tools/test_area_picker_presentation_wave_37.py
          python -m compileall -q spina_app
      - name: Run exact area-picker regression
        shell: cmd
        run: python tools/test_area_picker_presentation_wave_37.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-37-redundancy.json
          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-37-quality.json
      - name: Upload Wave 37 reports
        uses: actions/upload-artifact@v4
        with:
          name: area-picker-presentation-wave-37-reports
          path: |
            artifacts/wave-37-redundancy.json
            artifacts/wave-37-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
"""


def main() -> None:
    base = run("git", "merge-base", "HEAD", "origin/main")
    if base != EXPECTED_BASE:
        raise SystemExit(f"Unexpected merge base: {base}; expected {EXPECTED_BASE}")
    current_main = run("git", "rev-parse", "origin/main")
    if current_main != EXPECTED_BASE:
        raise SystemExit(f"origin/main moved: {current_main}; expected {EXPECTED_BASE}")

    changed = {
        line.strip()
        for line in run("git", "diff", "--name-only", EXPECTED_BASE, "HEAD").splitlines()
        if line.strip()
    }
    if changed != ALLOWED_INITIAL:
        raise SystemExit(f"Unexpected initial branch files: {sorted(changed)}")

    desktop_source = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(desktop_source, filename=str(DESKTOP))
    app, method = find_app_method(tree)
    actual_lines = (method.end_lineno or method.lineno) - method.lineno + 1
    if actual_lines != EXPECTED_LINES:
        raise SystemExit(f"Unexpected {TARGET} size: {actual_lines}; expected {EXPECTED_LINES}")

    source = ast.get_source_segment(desktop_source, method)
    if not source:
        raise SystemExit("Could not extract target source")
    select_sql = validate_read_only(method, source)
    digest = source_hash(source)

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(make_module(source, digest, select_sql), encoding="utf-8")
    TEST.write_text(make_test(digest), encoding="utf-8")
    PERM.parent.mkdir(parents=True, exist_ok=True)
    PERM.write_text(permanent_workflow(), encoding="utf-8")

    lines = desktop_source.splitlines(keepends=True)
    del lines[method.lineno - 1:(method.end_lineno or method.lineno)]
    removed_source = "".join(lines)

    reparsed = ast.parse(removed_source, filename=str(DESKTOP))
    app_after = next(
        node for node in reparsed.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    insert_line = app_after.end_lineno or app_after.lineno
    block = (
        "\n\n# Wave 37: read-only route area-picker presentation.\n"
        "from spina_app.area_picker_presentation import (\n"
        "    configure_area_picker_dependencies as _configure_wave37_area_picker,\n"
        "    _area_picker_dialog as _wave37_area_picker_dialog,\n"
        ")\n"
        "_configure_wave37_area_picker(globals())\n"
        "App._area_picker_dialog = _wave37_area_picker_dialog\n\n"
    )
    updated_lines = removed_source.splitlines(keepends=True)
    updated_lines.insert(insert_line, block)
    DESKTOP.write_text("".join(updated_lines), encoding="utf-8")

    if BOOT.exists():
        BOOT.unlink()
    if SELF.exists():
        SELF.unlink()

    print(json.dumps({
        "target": TARGET,
        "lines": actual_lines,
        "sha256": digest,
        "db_calls": sorted(ALLOWED_DB_CALLS),
        "select_sql": select_sql,
    }, indent=2))


if __name__ == "__main__":
    main()
