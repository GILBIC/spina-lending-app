from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "postgres_read_storage.py"
TEST = ROOT / "tools" / "test_postgres_read_storage_wave_35.py"
BOOT = ROOT / ".github" / "workflows" / "postgres-read-storage-wave-35-bootstrap.yml"
PERM = ROOT / ".github" / "workflows" / "postgres-read-storage-wave-35.yml"

EXPECTED_BASE = "fbef746fe88c7f584e04345fa9bc1ffc2923ce9f"
ALLOWED_INITIAL = {
    ".github/workflows/postgres-read-storage-wave-35-bootstrap.yml",
    "tools/apply_postgres_read_storage_wave_35.py",
}
ALREADY_EXTRACTED = {
    "_spina_pg_sha256",
    "_spina_pg_guess_file_type",
    "_spina_pg_guess_report_date",
    "_spina_pg_guess_collector",
    "_spina_pg_normalize_value",
    "_spina_pg_replace_qmarks",
    "_spina_pg_escape_literal_percents",
}
EXACT_SAFE = {
    "_spina_pg_storage_enabled",
    "_spina_pg_app_dir",
    "_spina_pg_relpath",
    "_spina_pg_json_table_for_path",
    "_spina_pg_read_json",
}
READ_NAME_PARTS = (
    "read", "load", "fetch", "find", "lookup", "list", "get", "exists",
    "enabled", "relpath", "app_dir", "json_table",
)
EXCLUDED_NAME_PARTS = (
    "write", "store", "save", "ensure", "sync", "import", "backup", "restore",
    "delete", "remove", "update", "insert", "upsert", "migrate", "schema",
    "commit", "rollback", "connect", "_conn", "_log",
)
SQL_WRITE_MARKERS = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE ", "REPLACE INTO", "ON CONFLICT",
)
MUTATING_ATTRS = {
    "commit", "rollback", "write", "write_text", "write_bytes", "unlink",
    "remove", "rename", "mkdir", "makedirs", "rmdir", "touch",
    "copy", "copy2", "move",
}


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def normalized_source(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized_source(source).encode("utf-8")).hexdigest()


def opens_for_write(node: ast.AST) -> bool:
    for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
        fn = call.func
        name = ""
        if isinstance(fn, ast.Name):
            name = fn.id
        elif isinstance(fn, ast.Attribute):
            name = fn.attr
        if name == "open":
            mode = None
            if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                mode = call.args[1].value
            for kw in call.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if isinstance(mode, str) and any(ch in mode for ch in "wax+"):
                return True
    return False


def is_safe_read_helper(name: str, node: ast.AST, source: str) -> bool:
    lname = name.lower()
    if not name.startswith("_spina_pg_") or name in ALREADY_EXTRACTED:
        return False
    if name not in EXACT_SAFE:
        if not any(part in lname for part in READ_NAME_PARTS):
            return False
        if any(part in lname for part in EXCLUDED_NAME_PARTS):
            return False
    upper = source.upper()
    if any(marker in upper for marker in SQL_WRITE_MARKERS):
        return False
    if opens_for_write(node):
        return False
    for item in ast.walk(node):
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
            if item.func.attr.lower() in MUTATING_ATTRS:
                return False
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
            if item.func.id.lower() in MUTATING_ATTRS:
                return False
    return True


def main() -> None:
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], cwd=ROOT, check=True)
    merge_base = run("git", "merge-base", "HEAD", "origin/main")
    if merge_base != EXPECTED_BASE:
        raise SystemExit(f"Unexpected main base: {merge_base}")

    changed = {
        line.strip()
        for line in run("git", "diff", "--name-only", f"{EXPECTED_BASE}..HEAD").splitlines()
        if line.strip()
    }
    unexpected = changed - ALLOWED_INITIAL
    if unexpected:
        raise SystemExit(f"Unexpected initial files: {sorted(unexpected)}")

    desktop_text = DESKTOP.read_text(encoding="utf-8-sig")
    tree = ast.parse(desktop_text, filename=str(DESKTOP))
    top_functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    candidates = []
    for node in top_functions:
        segment = ast.get_source_segment(desktop_text, node)
        if not segment:
            continue
        if is_safe_read_helper(node.name, node, segment):
            line_count = (node.end_lineno or node.lineno) - node.lineno + 1
            candidates.append((node, segment, line_count))

    exact_missing = sorted(EXACT_SAFE - {node.name for node, _, _ in candidates})
    if exact_missing:
        raise SystemExit(f"Missing required safe helpers: {exact_missing}")

    selected = []
    total_lines = 0
    for item in candidates:
        node, segment, line_count = item
        if total_lines + line_count > 800 and total_lines >= 300:
            continue
        selected.append(item)
        total_lines += line_count

    if total_lines < 300:
        detail = [(n.name, lines) for n, _, lines in candidates]
        raise SystemExit(
            f"Safe PostgreSQL read/path batch too small ({total_lines} lines): {detail}"
        )
    if total_lines > 900:
        raise SystemExit(f"Selected batch unexpectedly large: {total_lines}")
    if not (8 <= len(selected) <= 30):
        raise SystemExit(f"Unexpected selected function count: {len(selected)}")

    targets = tuple(node.name for node, _, _ in selected)
    sources = {node.name: normalized_source(segment) for node, segment, _ in selected}
    hashes = {name: source_hash(source) for name, source in sources.items()}

    header = (
        '"""PostgreSQL read-only storage/path helpers extracted in Wave 35."""\n'
        "from __future__ import annotations\n\n"
        "_POSTGRES_READ_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        '    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",\n'
        '    "__name__", "__package__", "__spec__", "_POSTGRES_READ_DEPENDENCIES",\n'
        '    "_PROTECTED_GLOBALS", "configure_postgres_read_dependencies",\n'
        '    "POSTGRES_READ_SOURCE_SHA256", "POSTGRES_READ_TARGETS",\n'
        "}\n\n\n"
        "def configure_postgres_read_dependencies(namespace):\n"
        "    _POSTGRES_READ_DEPENDENCIES.clear()\n"
        "    _POSTGRES_READ_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n\n"
    )
    module_text = (
        header
        + "POSTGRES_READ_TARGETS = " + repr(targets) + "\n"
        + "POSTGRES_READ_SOURCE_SHA256 = " + json.dumps(hashes, indent=4, sort_keys=True) + "\n\n"
        + "\n\n".join(sources[name].rstrip() for name in targets)
        + "\n"
    )
    MODULE.write_text(module_text, encoding="utf-8")

    import_lines = ",\n    ".join(targets)
    wiring = f"""# Wave 35: high-volume PostgreSQL read-only storage/path helpers.
from spina_app.postgres_read_storage import (
    configure_postgres_read_dependencies as _configure_postgres_read_wave35_dependencies,
    {import_lines},
)
_configure_postgres_read_wave35_dependencies(globals())

"""

    spans = {
        node.lineno: (node.end_lineno or node.lineno)
        for node, _, _ in selected
    }
    first_line = min(spans)
    lines = desktop_text.splitlines(keepends=True)
    output = []
    line_no = 1
    inserted = False
    while line_no <= len(lines):
        if line_no == first_line and not inserted:
            output.append(wiring)
            inserted = True
        if line_no in spans:
            output.append("\n")
            line_no = spans[line_no] + 1
            continue
        output.append(lines[line_no - 1])
        line_no += 1
    if not inserted:
        raise SystemExit("Failed to insert Wave 35 wiring")

    rewritten = "".join(output)
    ast.parse(rewritten, filename=str(DESKTOP))
    DESKTOP.write_text(rewritten, encoding="utf-8")

    test_text = f"""from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "postgres_read_storage.py"
TARGETS = {targets!r}
EXPECTED = {hashes!r}
EXPECTED_TOTAL_LINES = {total_lines}
SQL_WRITE_MARKERS = {SQL_WRITE_MARKERS!r}
MUTATING_ATTRS = {tuple(sorted(MUTATING_ATTRS))!r}


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\\n"


def digest(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text, filename=str(MODULE))
    funcs = {{
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}
    assert set(TARGETS) <= set(funcs), sorted(set(TARGETS) - set(funcs))
    actual_lines = 0
    for name in TARGETS:
        node = funcs[name]
        segment = ast.get_source_segment(module_text, node)
        assert segment
        assert digest(segment) == EXPECTED[name], name
        actual_lines += (node.end_lineno or node.lineno) - node.lineno + 1
        upper = segment.upper()
        assert not any(marker in upper for marker in SQL_WRITE_MARKERS), name
        for item in ast.walk(node):
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
                assert item.func.attr.lower() not in MUTATING_ATTRS, (name, item.func.attr)
    assert actual_lines == EXPECTED_TOTAL_LINES, (actual_lines, EXPECTED_TOTAL_LINES)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text, filename=str(DESKTOP))
    desktop_defs = {{
        node.name
        for node in desktop_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}
    assert not (set(TARGETS) & desktop_defs), sorted(set(TARGETS) & desktop_defs)
    imported = set()
    for node in desktop_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.postgres_read_storage":
            imported.update(alias.name for alias in node.names)
    assert set(TARGETS) <= imported, sorted(set(TARGETS) - imported)
    print(f"Wave 35 PostgreSQL read/storage regression passed: {{len(TARGETS)}} functions / {{actual_lines}} lines.")


if __name__ == "__main__":
    main()
"""
    TEST.write_text(test_text, encoding="utf-8")

    permanent = """name: PostgreSQL read storage Wave 35
on: [pull_request]
permissions:
  contents: read
jobs:
  validate:
    if: github.head_ref == 'agent/postgres-read-storage-wave-35'
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
          python -m py_compile spina_app\\postgres_read_storage.py
          python -m py_compile tools\\test_postgres_read_storage_wave_35.py
          python -m compileall -q spina_app
      - name: Run high-volume PostgreSQL read/storage regression
        shell: cmd
        run: python tools\\test_postgres_read_storage_wave_35.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools\\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-35-redundancy.json
          python tools\\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-35-quality.json
      - name: Upload Wave 35 reports
        uses: actions/upload-artifact@v4
        with:
          name: postgres-read-storage-wave-35-reports
          path: |
            artifacts/wave-35-redundancy.json
            artifacts/wave-35-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
"""
    PERM.write_text(permanent, encoding="utf-8")

    if BOOT.exists():
        BOOT.unlink()
    Path(__file__).unlink()
    print(
        f"Wave 35 extracted {len(targets)} PostgreSQL read/path helpers "
        f"({total_lines} lines): {', '.join(targets)}"
    )


if __name__ == "__main__":
    main()
