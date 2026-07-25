from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_queries.py"
TEST = ROOT / "tools" / "test_client_read_queries_wave_31.py"
BOOTSTRAP_WORKFLOW = ROOT / ".github" / "workflows" / "client-read-queries-wave-31-bootstrap.yml"
PERMANENT_WORKFLOW = ROOT / ".github" / "workflows" / "client-read-queries-wave-31.yml"

EXPECTED_BASE = "6ab46ec582f11f3dfdb901f3be2d09e5d26ac003"
TARGET_METHODS = (
    "get_all_clients",
    "get_client_info",
    "get_client_link_meta",
    "find_clients_by_person_uid",
    "get_client_uid",
    "get_client_by_uid",
    "get_client_history",
    "get_person_uid_for_client_uid",
)
ALLOWED_BOOTSTRAP_FILES = {
    ".github/workflows/client-read-queries-wave-31-bootstrap.yml",
    "tools/apply_client_read_queries_wave_31.py",
}


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def normalized_source(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_loandb(tree: ast.Module) -> ast.ClassDef:
    matches = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "LoanDB"
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one LoanDB class, found {len(matches)}")
    return matches[0]


def find_target_methods(loandb: ast.ClassDef) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    found: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in loandb.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGET_METHODS:
            if node.name in found:
                raise SystemExit(f"Duplicate LoanDB method: {node.name}")
            found[node.name] = node
    missing = [name for name in TARGET_METHODS if name not in found]
    if missing:
        raise SystemExit(f"Missing target LoanDB methods: {missing}")
    return found


def verify_branch_scope() -> None:
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], cwd=ROOT, check=True)
    base = run("git", "merge-base", "HEAD", "origin/main")
    if base != EXPECTED_BASE:
        raise SystemExit(f"Unexpected main base {base}; expected {EXPECTED_BASE}")
    changed = {
        line.strip()
        for line in run("git", "diff", "--name-only", f"{EXPECTED_BASE}..HEAD").splitlines()
        if line.strip()
    }
    unexpected = changed - ALLOWED_BOOTSTRAP_FILES
    if unexpected:
        raise SystemExit(f"Unexpected pre-extraction files: {sorted(unexpected)}")


def build_module(method_sources: dict[str, str], source_hashes: dict[str, str]) -> str:
    header = '''"""Read-only client query methods extracted from the SPINA desktop application.

Wave 31 keeps these functions byte-for-byte equivalent after dedenting and wires
them back onto ``LoanDB`` immediately after the class definition. Application
globals are supplied explicitly so the extracted methods retain the same helper,
compatibility, logging, and PostgreSQL references as before.
"""

from __future__ import annotations

_CLIENT_QUERY_DEPENDENCIES: dict[str, object] = {}
_PROTECTED_GLOBALS = {
    "__builtins__",
    "__cached__",
    "__doc__",
    "__file__",
    "__loader__",
    "__name__",
    "__package__",
    "__spec__",
    "_CLIENT_QUERY_DEPENDENCIES",
    "_PROTECTED_GLOBALS",
    "configure_client_queries_dependencies",
}


def configure_client_queries_dependencies(namespace: dict[str, object]) -> None:
    """Bind application-owned globals required by the extracted LoanDB methods."""
    _CLIENT_QUERY_DEPENDENCIES.clear()
    _CLIENT_QUERY_DEPENDENCIES.update(namespace)
    module_globals = globals()
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            module_globals[name] = value


'''
    manifest = (
        "# Original dedented source SHA-256 values from the guarded Wave 31 base.\n"
        f"CLIENT_QUERY_SOURCE_SHA256 = {json.dumps(source_hashes, indent=4, sort_keys=True)}\n\n"
    )
    bodies = "\n\n".join(method_sources[name].rstrip() for name in TARGET_METHODS) + "\n"
    return header + manifest + bodies


def build_wiring() -> str:
    imports = ",\n    ".join(
        f"{name} as _client_query_{name}" for name in TARGET_METHODS
    )
    assigns = "\n".join(
        f"LoanDB.{name} = _client_query_{name}" for name in TARGET_METHODS
    )
    return f'''\n# Wave 31: read-only client database queries.
from spina_app.client_queries import (
    configure_client_queries_dependencies as _configure_client_queries_wave31_dependencies,
    {imports},
)
_configure_client_queries_wave31_dependencies(globals())
{assigns}

'''


def rewrite_desktop(text: str, loandb: ast.ClassDef, methods: dict[str, ast.AST]) -> str:
    lines = text.splitlines(keepends=True)
    spans = {
        int(node.lineno): int(node.end_lineno or node.lineno)
        for node in methods.values()
    }
    start_to_end = dict(sorted(spans.items()))
    output: list[str] = []
    line_no = 1
    class_end = int(loandb.end_lineno or loandb.lineno)
    inserted = False

    while line_no <= len(lines):
        if line_no in start_to_end:
            end_line = start_to_end[line_no]
            output.append("\n")
            line_no = end_line + 1
            continue
        if line_no == class_end + 1 and not inserted:
            output.append(build_wiring())
            inserted = True
        output.append(lines[line_no - 1])
        line_no += 1

    if not inserted:
        output.append(build_wiring())
    return "".join(output)


def build_test(source_hashes: dict[str, str], total_lines: int) -> str:
    return f'''from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_queries.py"
TARGETS = {TARGET_METHODS!r}
EXPECTED_SHA256 = {source_hashes!r}
EXPECTED_TOTAL_LINES = {total_lines}


def normalized_source(text: str) -> str:
    return textwrap.dedent(text).strip() + "\\n"


def source_hash(text: str) -> str:
    return hashlib.sha256(normalized_source(text).encode("utf-8")).hexdigest()


def direct_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {{
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text, filename=str(MODULE))
    functions = direct_functions(module_tree)

    missing = [name for name in TARGETS if name not in functions]
    assert not missing, f"Missing extracted functions: {{missing}}"

    actual_total = 0
    for name in TARGETS:
        node = functions[name]
        segment = ast.get_source_segment(module_text, node)
        assert segment is not None
        actual = source_hash(segment)
        assert actual == EXPECTED_SHA256[name], (name, actual, EXPECTED_SHA256[name])
        actual_total += (node.end_lineno or node.lineno) - node.lineno + 1
    assert actual_total == EXPECTED_TOTAL_LINES, (actual_total, EXPECTED_TOTAL_LINES)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text, filename=str(DESKTOP))
    loandb = next(
        node for node in desktop_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "LoanDB"
    )
    remaining = {{
        node.name for node in loandb.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}
    assert not (set(TARGETS) & remaining), set(TARGETS) & remaining

    class_end = loandb.end_lineno or loandb.lineno
    wiring_positions = []
    for node in ast.walk(desktop_tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "LoanDB"
            and target.attr in TARGETS
        ):
            wiring_positions.append((target.attr, node.lineno))
    assert {{name for name, _ in wiring_positions}} == set(TARGETS)
    assert all(line > class_end for _, line in wiring_positions)

    forbidden_sql = (
        "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE",
        "ALTER TABLE", "DROP TABLE",
    )
    forbidden_calls = (
        ".commit(", ".rollback(", "write_text(", "write_bytes(",
        ".unlink(", ".replace(",
    )
    for name in TARGETS:
        segment = ast.get_source_segment(module_text, functions[name]) or ""
        upper = segment.upper()
        for token in forbidden_sql:
            assert token not in upper, (name, token)
        for token in forbidden_calls:
            assert token not in segment, (name, token)

    print(
        f"Wave 31 client read-query regression passed: "
        f"{{len(TARGETS)}} methods / {{EXPECTED_TOTAL_LINES}} lines."
    )


if __name__ == "__main__":
    main()
'''


def build_permanent_workflow() -> str:
    return '''name: Client read queries Wave 31

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    if: github.head_ref == 'agent/client-read-queries-wave-31'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 35

    steps:
      - name: Check out exact PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0

      - name: Verify local Python
        shell: cmd
        run: |
          where python
          python --version

      - name: Compile application, module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app/client_queries.py
          python -m py_compile tools/test_client_read_queries_wave_31.py
          python -m compileall -q spina_app

      - name: Run client read-query regression
        shell: cmd
        run: python -m tools.test_client_read_queries_wave_31

      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check

      - name: Run redundancy audit
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-31-redundancy.json

      - name: Run SPINA quality audit
        shell: cmd
        run: python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-31-quality.json

      - name: Upload Wave 31 reports
        uses: actions/upload-artifact@v4
        with:
          name: client-read-queries-wave-31-reports
          path: |
            artifacts/wave-31-redundancy.json
            artifacts/wave-31-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''


def main() -> None:
    verify_branch_scope()
    if MODULE.exists():
        raise SystemExit(f"Target module already exists: {MODULE.relative_to(ROOT)}")

    desktop_text = DESKTOP.read_text(encoding="utf-8-sig")
    tree = ast.parse(desktop_text, filename=str(DESKTOP))
    loandb = find_loandb(tree)
    methods = find_target_methods(loandb)

    method_sources: dict[str, str] = {}
    source_hashes: dict[str, str] = {}
    total_lines = 0
    for name in TARGET_METHODS:
        node = methods[name]
        segment = ast.get_source_segment(desktop_text, node)
        if not segment:
            raise SystemExit(f"Could not extract source for {name}")
        normalized = normalized_source(segment)
        method_sources[name] = normalized
        source_hashes[name] = sha256_text(normalized)
        total_lines += (node.end_lineno or node.lineno) - node.lineno + 1

    if not 250 <= total_lines <= 800:
        raise SystemExit(f"Unexpected Wave 31 source size: {total_lines} lines")

    rewritten = rewrite_desktop(desktop_text, loandb, methods)
    ast.parse(rewritten, filename=str(DESKTOP))

    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(build_module(method_sources, source_hashes), encoding="utf-8")
    TEST.write_text(build_test(source_hashes, total_lines), encoding="utf-8")
    DESKTOP.write_text(rewritten, encoding="utf-8")

    PERMANENT_WORKFLOW.write_text(build_permanent_workflow(), encoding="utf-8")
    if BOOTSTRAP_WORKFLOW.exists():
        BOOTSTRAP_WORKFLOW.unlink()
    Path(__file__).unlink()

    print(
        f"Wave 31 extracted {len(TARGET_METHODS)} read-only LoanDB methods "
        f"({total_lines} original lines)."
    )


if __name__ == "__main__":
    main()
