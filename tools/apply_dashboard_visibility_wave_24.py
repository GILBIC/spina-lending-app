"""Apply SPINA modularization Wave 24 for Dashboard visibility filters."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/dashboard.py")
TEST = Path("tools/test_dashboard_visibility_wave_24.py")
PERMANENT_WORKFLOW = Path(".github/workflows/dashboard-visibility-wave-24.yml")
TEMP_WORKFLOW = Path(".github/workflows/apply-dashboard-visibility-wave-24.yml")
SELF = Path("tools/apply_dashboard_visibility_wave_24.py")

TARGETS = {
    "_spina_dashboard_visible_rows": "4c8d9a40a9119ee422f66de37bdcacf222953ee7e7c606180a52996814b88457",
    "_spina_v19_visible_dashboard_rows": "6ff49ee1c41c7b340ca62f58ed09bbe05a16118f791626b5d85946e7db6515ae",
    "_spina_v20_visible_rows": "b4f184c6ae909b0cb1a1d4053306e4bc19a08aa52fac8d2cb45dea3b965a1a6a",
}
EXPECTED_SOURCE_SHA = "391191cb55aa5e9cc681cfc231465e6b7d6a99b181334b223c009c9be7220c30"
EXPECTED_MODULE_GIT_BLOB = "9e9706a430b42c7781118d6f87ff8c191870acb2"
MARKER = "\n# Dashboard visibility filters extracted in Wave 24.\n\n"
IMPORT_BLOCK = [
    "from spina_app.tabs.dashboard import (",
    "    _spina_dashboard_visible_rows,",
    "    _spina_v19_visible_dashboard_rows,",
    "    _spina_v20_visible_rows,",
    ")",
]


def function_source(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def function_hashes(text: str) -> dict[str, str]:
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))
    return {
        node.name: hashlib.sha256(function_source(lines, node).encode("utf-8")).hexdigest()
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def git_blob_sha(path: Path) -> str:
    result = subprocess.run(
        ["git", "hash-object", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_test_content(original_module_sha256: str) -> str:
    return f'''"""Regression checks for Dashboard visibility Wave 24."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/dashboard.py")
TARGETS = {TARGETS!r}
MARKER = {MARKER!r}
ORIGINAL_MODULE_SHA256 = {original_module_sha256!r}


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\\n".join(lines[node.lineno - 1 : node.end_lineno])


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Dummy:
    pass


def sample_rows():
    return [
        {{"name": "Ana Cruz", "area": "East", "loan_type": "Regular", "status": "Finishing Now"}},
        {{"name": "Ben Santos", "area": "West", "loan_type": "7x7", "status": "Active"}},
        {{"name": "Cara Reyes", "area": "North", "loan_type": "Regular", "status": "Overdue"}},
    ]


def make_dummy(*, loan="All", status="All Active", search=""):
    obj = Dummy()
    obj._dashboard_rows = sample_rows()
    obj.dashboard_loan_filter_var = Var(loan)
    obj.dashboard_status_filter_var = Var(status)
    obj.dashboard_search_var = Var(search)
    return obj


def main() -> None:
    app_text = SOURCE.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text, filename=str(SOURCE))
    remaining = {{
        node.name
        for node in app_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS
    }}
    assert not remaining, f"Definitions still remain in desktop source: {{sorted(remaining)}}"

    imported = set()
    for node in app_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard":
            imported.update(alias.name for alias in node.names)
    assert set(TARGETS).issubset(imported), f"Dashboard imports missing: {{sorted(set(TARGETS) - imported)}}"

    module_text = MODULE.read_text(encoding="utf-8")
    assert module_text.count(MARKER) == 1, "Wave 24 marker missing or duplicated"
    base_text, _extracted_text = module_text.split(MARKER, 1)
    base_sha = hashlib.sha256(base_text.encode("utf-8")).hexdigest()
    assert base_sha == ORIGINAL_MODULE_SHA256, f"Pre-existing Dashboard module changed: {{base_sha}}"

    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text, filename=str(MODULE))
    module_nodes = {{
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS
    }}
    assert set(module_nodes) == set(TARGETS), f"Module definitions differ: {{sorted(module_nodes)}}"

    for name, expected_hash in TARGETS.items():
        source = source_for(module_lines, module_nodes[name])
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        assert digest == expected_hash, f"Source changed for {{name}}: {{digest}}"

    module = importlib.import_module("spina_app.tabs.dashboard")
    for name in TARGETS:
        assert callable(getattr(module, name, None)), f"{{name}} is not callable after import"

    rows = module._spina_v19_visible_dashboard_rows(make_dummy())
    assert len(rows) == 3, "All Active should keep every loaded row"

    priority = module._spina_v19_visible_dashboard_rows(make_dummy(status="Priority"))
    assert [row["name"] for row in priority] == ["Ana Cruz", "Cara Reyes"]

    seven = module._spina_v19_visible_dashboard_rows(make_dummy(loan="7x7"))
    assert [row["name"] for row in seven] == ["Ben Santos"]

    searched = module._spina_v19_visible_dashboard_rows(make_dummy(search="overdue"))
    assert [row["name"] for row in searched] == ["Cara Reyes"]

    old_priority = module._spina_dashboard_visible_rows(make_dummy(status="Finishing Priority"))
    assert [row["name"] for row in old_priority] == ["Ana Cruz", "Cara Reyes"]

    wrapped = module._spina_v20_visible_rows(make_dummy(status="Priority"))
    assert wrapped == priority, "v20 wrapper must preserve v19 behavior"

    print("Dashboard visibility Wave 24 regression passed.")


if __name__ == "__main__":
    main()
'''


PERMANENT_WORKFLOW_CONTENT = r'''name: Dashboard visibility Wave 24

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    if: github.head_ref == 'agent/dashboard-visibility-wave-24'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 30
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Verify local Python
        shell: cmd
        run: |
          where python
          python --version

      - name: Compile application, module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app\tabs\dashboard.py
          python -m py_compile tools\test_dashboard_visibility_wave_24.py

      - name: Run Dashboard visibility regression
        shell: cmd
        run: python -m tools.test_dashboard_visibility_wave_24

      - name: Run redundancy audit
        shell: cmd
        run: python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json redundancy-report.json

      - name: Run SPINA quality audit
        shell: cmd
        run: python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json quality-report.json

      - name: Upload audit reports
        uses: actions/upload-artifact@v4
        with:
          name: dashboard-visibility-wave-24-audits
          path: |
            redundancy-report.json
            quality-report.json
'''


def main() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    source_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"Unexpected current-main source SHA: {source_sha}")

    module_blob = git_blob_sha(MODULE)
    if module_blob != EXPECTED_MODULE_GIT_BLOB:
        raise SystemExit(f"Unexpected Dashboard module blob: {module_blob}")

    source_lines = source_text.splitlines()
    source_tree = ast.parse(source_text, filename=str(SOURCE))
    all_nodes = {
        node.name: node
        for node in source_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(TARGETS) - set(all_nodes))
    if missing:
        raise SystemExit(f"Missing target functions: {missing}")

    before_hashes = function_hashes(source_text)
    sources: dict[str, str] = {}
    ranges: list[tuple[int, int, str]] = []
    for name, expected_hash in TARGETS.items():
        node = all_nodes[name]
        source = function_source(source_lines, node)
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if digest != expected_hash:
            raise SystemExit(f"Source hash mismatch for {name}: {digest}")
        sources[name] = source
        ranges.append((node.lineno, node.end_lineno, name))

    ranges.sort()
    output: list[str] = []
    cursor = 0
    inserted = False
    for start, end, _name in ranges:
        output.extend(source_lines[cursor : start - 1])
        if not inserted:
            output.extend(IMPORT_BLOCK)
            inserted = True
        cursor = end
    output.extend(source_lines[cursor:])
    new_source_text = "\n".join(output) + "\n"

    after_hashes = function_hashes(new_source_text)
    expected_after_names = set(before_hashes) - set(TARGETS)
    if set(after_hashes) != expected_after_names:
        missing_after = sorted(expected_after_names - set(after_hashes))
        extra_after = sorted(set(after_hashes) - expected_after_names)
        raise SystemExit(f"Non-target function set changed; missing={missing_after}, extra={extra_after}")
    for name in expected_after_names:
        if before_hashes[name] != after_hashes[name]:
            raise SystemExit(f"Non-target function changed: {name}")

    module_base_text = MODULE.read_text(encoding="utf-8")
    if MARKER in module_base_text:
        raise SystemExit("Wave 24 marker already exists in Dashboard module")
    original_module_sha256 = hashlib.sha256(module_base_text.encode("utf-8")).hexdigest()
    extracted_text = "\n\n\n".join(sources[name] for name in TARGETS)

    SOURCE.write_text(new_source_text, encoding="utf-8")
    MODULE.write_text(module_base_text + MARKER + extracted_text + "\n", encoding="utf-8")
    TEST.write_text(build_test_content(original_module_sha256), encoding="utf-8")
    PERMANENT_WORKFLOW.write_text(PERMANENT_WORKFLOW_CONTENT, encoding="utf-8")

    TEMP_WORKFLOW.unlink(missing_ok=True)
    SELF.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
