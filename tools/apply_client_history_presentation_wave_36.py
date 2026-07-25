from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_history_presentation.py"
TEST = ROOT / "tools" / "test_client_history_presentation_wave_36.py"
BOOT = ROOT / ".github" / "workflows" / "client-history-presentation-wave-36-bootstrap.yml"
PERM = ROOT / ".github" / "workflows" / "client-history-presentation-wave-36.yml"
SELF = ROOT / "tools" / "apply_client_history_presentation_wave_36.py"

EXPECTED_BASE = "b5aad49922bc31ea8166031c04fb4a336c904525"
TARGET = "_app_open_client_history_dialog"
EXPECTED_LINES = 514
EXPECTED_SHA256 = "570a2e0946cd702bfcdcbc1d3433b72ab9aed73fd61fba56be70e1ebb53555b8"
ALLOWED_INITIAL = {
    ".github/workflows/client-history-presentation-wave-36-bootstrap.yml",
    "tools/apply_client_history_presentation_wave_36.py",
}
ALLOWED_DB_READS = {
    "get_client_history",
    "get_client_uid",
    "get_linked_client_uids",
    "get_transaction_history_for_client_uids",
    "get_transactions_for_client_uids",
}
FORBIDDEN_TEXT = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE ", "ON CONFLICT", ".COMMIT(", ".ROLLBACK(",
    "WRITE_TEXT(", "WRITE_BYTES(", ".UNLINK(", "SAVE_SETTINGS(",
    "_WRITE_JSON_ATOMIC(", "ADD_TRANSACTION(", "UPDATE_TRANSACTION(",
    "DELETE_TRANSACTION(", "SET_CLIENT_NOTE(", "ADD_CLIENT(", "UPDATE_CLIENT(",
)
FORBIDDEN_MUTATING_ATTRS = {
    "commit", "rollback", "write", "write_text", "write_bytes", "unlink",
    "mkdir", "makedirs", "rename", "copy", "copy2", "move",
    "rmdir", "touch",
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


def validate_read_only(node: ast.AST, source: str) -> None:
    upper = source.upper()
    for token in FORBIDDEN_TEXT:
        if token in upper:
            raise SystemExit(f"Forbidden mutation token in {TARGET}: {token}")

    db_calls: set[str] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        chain = call_chain(item.func)
        if len(chain) >= 3 and chain[:2] == ["self", "db"]:
            db_calls.add(chain[2])
            if chain[2] not in ALLOWED_DB_READS:
                raise SystemExit(f"Unexpected self.db call in {TARGET}: {'.'.join(chain)}")
        if isinstance(item.func, ast.Attribute):
            attr = item.func.attr.lower()
            if attr in FORBIDDEN_MUTATING_ATTRS:
                raise SystemExit(f"Forbidden mutation call in {TARGET}: {attr}")
        elif isinstance(item.func, ast.Name):
            name = item.func.id.lower()
            if name in FORBIDDEN_MUTATING_ATTRS or name == "open":
                raise SystemExit(f"Forbidden file mutation call in {TARGET}: {name}")

    if db_calls != ALLOWED_DB_READS:
        raise SystemExit(f"Client-history DB read set changed: {sorted(db_calls)}")


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
    matches = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one top-level {TARGET}, found {len(matches)}")
    node = matches[0]
    segment = ast.get_source_segment(desktop_text, node)
    if not segment:
        raise SystemExit(f"Unable to read source for {TARGET}")
    line_count = (node.end_lineno or node.lineno) - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise SystemExit(f"Unexpected {TARGET} line count: {line_count}")
    digest = source_hash(segment)
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"Unexpected {TARGET} source hash: {digest}")
    validate_read_only(node, segment)

    module_text = (
        '"""Read-only client-history dialog presentation extracted in Wave 36."""\n'
        "from __future__ import annotations\n\n"
        "_CLIENT_HISTORY_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        '    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",\n'
        '    "__name__", "__package__", "__spec__", "_CLIENT_HISTORY_DEPENDENCIES",\n'
        '    "_PROTECTED_GLOBALS", "configure_client_history_dependencies",\n'
        '    "CLIENT_HISTORY_SOURCE_SHA256", "CLIENT_HISTORY_TARGET",\n'
        "}\n\n\n"
        "def configure_client_history_dependencies(namespace):\n"
        "    _CLIENT_HISTORY_DEPENDENCIES.clear()\n"
        "    _CLIENT_HISTORY_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n\n"
        f"CLIENT_HISTORY_TARGET = {TARGET!r}\n"
        f"CLIENT_HISTORY_SOURCE_SHA256 = {digest!r}\n\n"
        + normalized_source(segment)
    )
    MODULE.write_text(module_text, encoding="utf-8")

    wiring = f'''# Wave 36: read-only client-history dialog presentation.
from spina_app.client_history_presentation import (
    configure_client_history_dependencies as _configure_wave36_client_history,
    {TARGET} as _wave36_client_history_dialog,
)
_configure_wave36_client_history(globals())
{TARGET} = _wave36_client_history_dialog

'''

    lines = desktop_text.splitlines(keepends=True)
    start = node.lineno
    end = node.end_lineno or node.lineno
    rewritten = "".join(lines[: start - 1] + [wiring] + lines[end:])
    ast.parse(rewritten, filename=str(DESKTOP))
    DESKTOP.write_text(rewritten, encoding="utf-8")

    test_text = f'''from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_history_presentation.py"
TARGET = {TARGET!r}
EXPECTED_SHA256 = {digest!r}
EXPECTED_LINES = {line_count}
ALLOWED_DB_READS = {sorted(ALLOWED_DB_READS)!r}
FORBIDDEN_TEXT = {FORBIDDEN_TEXT!r}
FORBIDDEN_MUTATING_ATTRS = {sorted(FORBIDDEN_MUTATING_ATTRS)!r}


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\\n"


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
    funcs = {{
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}
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
    top_defs = {{
        node.name
        for node in desktop_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}
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
    print(f"Wave 36 client-history regression passed: {{TARGET}} / {{actual_lines}} lines.")


if __name__ == "__main__":
    main()
'''
    TEST.write_text(test_text, encoding="utf-8")

    permanent = '''name: Client history presentation Wave 36
on: [pull_request]
permissions:
  contents: read
jobs:
  validate:
    if: github.head_ref == 'agent/client-history-presentation-wave-36'
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
          python -m py_compile spina_app/client_history_presentation.py
          python -m py_compile tools/test_client_history_presentation_wave_36.py
          python -m compileall -q spina_app
      - name: Run exact client-history regression
        shell: cmd
        run: python tools/test_client_history_presentation_wave_36.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-36-redundancy.json
          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-36-quality.json
      - name: Upload Wave 36 reports
        uses: actions/upload-artifact@v4
        with:
          name: client-history-presentation-wave-36-reports
          path: |
            artifacts/wave-36-redundancy.json
            artifacts/wave-36-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''
    PERM.write_text(permanent, encoding="utf-8")

    BOOT.unlink(missing_ok=True)
    SELF.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
