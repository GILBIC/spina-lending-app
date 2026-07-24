"""Guarded high-volume Dashboard presentation extraction for Wave 28."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "tabs" / "dashboard.py"
TEST = ROOT / "tools" / "test_dashboard_presentation_wave_28.py"
WORKFLOW = ROOT / ".github" / "workflows" / "dashboard-presentation-wave-28.yml"

EXPECTED_SOURCE_SHA256 = "afcf60afc4e058ee65e9915157837f6b0a911dadae8195d7abbc42eda68879f7"
EXPECTED_SOURCE_BLOB = "35a04d2928cc757129c65d2ebab1ec4932eae327"
EXPECTED_MODULE_SHA256 = "d534818fc18b0ec7b06a1a909fa7e0a27252f598071b1e4233650756d5a9ac70"
EXPECTED_MODULE_BLOB = "3ae71f94c774a4b7428e14fc29457e152ccf04f3"

TARGET_HASHES = {
    "_spina_dashboard_summary_text": "a3e3a98b08bb55760d26bd26e7007a24fc1e42a0806fbbd5f6cbbafc563d8fcc",
    "_spina_configure_dashboard_tree_theme": "763b1115268385a391bdf8570d0b807a5bd15d4a23ed3087c6abace5643e8950",
    "_spina_build_dashboard_tab": "8e3d70fed368facfb1cdfbb62442ea88eedfad0efbfc0b67d94df78ba7789207",
    "_spina_populate_dashboard_tree": "9a26abe818e6cfe37c8ffe1dec47176268cf057c8dcb4042ba02c6e226dbc985",
    "_spina_refresh_dashboard": "b40c5dd7f2a081f322b2b04b6910dc408ac1fd903b234a29f2613c22ee851edb",
    "_spina_apply_dashboard_role": "37bc51146533cb798a7531f5ff01406f4611b8e1167e8ac4f59d5f10327a1a5b",
    "_spina_v18_patch_dashboard_chart_cards": "1cbd667d330a0230795ad2d8e9b279e28c5f276f0f1a9e37718de78562f0bebc",
    "_spina_v18_populate_dashboard_tree": "fb838546b5ff7ef96b4ec7c00c64bda644bd959cf7358f73e2562751826259c5",
    "_spina_v18_refresh_dashboard": "2a667318c3cd97c93ce2ee82b7daba04cf97db16b0fba281a9a8cb537e3f89b3",
    "_spina_v19_populate_dashboard_tree": "3ab56f70a231c1813ea3a1040a46dcd6dc58d2aa5a8b6604a2d45b79cac62070",
    "_spina_v19_refresh_dashboard": "8a5a0ac327e8558bbf196b7586b17793d4c5f0a8f82f2214580d4eee950cf6cd",
    "_spina_v20_populate_dashboard_tree": "6d87d7b52220eb90964d2dceda98c2e0218a05875e903a90dbfaab94e2b07170",
    "_spina_v20_refresh_dashboard": "54f6e2e53214ab0062574e37ca7ff839f20ea6afb196eb09f246ccd049098912",
}
TARGET_ORDER = list(TARGET_HASHES)
EXPECTED_TARGET_LINES = 449


def raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], cwd=ROOT, text=True).strip()


def top_level_functions(text: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(text)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def segment(text: str, node: ast.AST) -> str:
    lines = text.splitlines()
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def source_hashes(text: str) -> dict[str, str]:
    return {
        name: hashlib.sha256(segment(text, node).encode("utf-8")).hexdigest()
        for name, node in top_level_functions(text).items()
    }


def replacement_lines(value: str) -> list[str]:
    if value and not value.endswith("\n"):
        value += "\n"
    return value.splitlines(keepends=True)


def apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    lines = text.splitlines(keepends=True)
    for start, end, value in sorted(edits, key=lambda item: item[0], reverse=True):
        lines[start:end] = replacement_lines(value)
    return "".join(lines)


def import_block(node: ast.ImportFrom, extra_names: list[str]) -> str:
    items: list[tuple[str, str | None]] = [(alias.name, alias.asname) for alias in node.names]
    existing = {name for name, _ in items}
    items.extend((name, None) for name in extra_names if name not in existing)
    rendered = []
    for name, alias in items:
        rendered.append(f"    {name} as {alias}," if alias else f"    {name},")
    return f"from {node.module} import (\n" + "\n".join(rendered) + "\n)\n"


def build_test(summary_cases: list[list[dict[str, object]]], summary_expected: list[str]) -> str:
    return f'''"""Focused regression checks for Dashboard presentation Wave 28."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from spina_app.tabs import dashboard

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "tabs" / "dashboard.py"
EXPECTED_HASHES = {TARGET_HASHES!r}
EXPECTED_LINES = {EXPECTED_TARGET_LINES}
SUMMARY_CASES = {summary_cases!r}
SUMMARY_EXPECTED = {summary_expected!r}


def functions(path: Path):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    lines = text.splitlines()
    result = {{}}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            source = "\\n".join(lines[node.lineno - 1 : node.end_lineno])
            result[node.name] = (node, source)
    return result


def main() -> None:
    source_functions = functions(SOURCE)
    module_functions = functions(MODULE)
    assert not (set(EXPECTED_HASHES) & set(source_functions)), "Wave 28 functions remain in desktop source"
    assert set(EXPECTED_HASHES).issubset(module_functions), "Wave 28 functions missing from Dashboard module"

    total_lines = 0
    for name, expected in EXPECTED_HASHES.items():
        node, text = module_functions[name]
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert actual == expected, (name, actual, expected)
        total_lines += (node.end_lineno or node.lineno) - node.lineno + 1
    assert total_lines == EXPECTED_LINES, total_lines

    calls = []
    marker = object()
    dashboard.configure_legacy_dashboard_feature(
        draw_v18_charts=lambda self, rows: calls.append(("v18", self, rows)) or marker,
        draw_v20_charts=lambda self, rows: calls.append(("v20", self, rows)) or marker,
    )
    owner = object()
    rows = [{{"name": "Bridge"}}]
    assert dashboard._spina_v18_draw_dashboard_charts(owner, rows) is marker
    assert dashboard._spina_v20_draw_dashboard_charts(owner, rows) is marker
    assert [entry[0] for entry in calls] == ["v18", "v20"]

    actual_summary = [dashboard._spina_dashboard_summary_text(rows) for rows in SUMMARY_CASES]
    assert actual_summary == SUMMARY_EXPECTED, (actual_summary, SUMMARY_EXPECTED)

    class EmptyApp:
        pass

    # Defensive UI helpers must stay no-throw when optional widgets are absent.
    dashboard._spina_configure_dashboard_tree_theme(EmptyApp())
    dashboard._spina_apply_dashboard_role(EmptyApp())

    print("Dashboard presentation Wave 28 regression passed:", len(EXPECTED_HASHES), "functions,", total_lines, "lines")


if __name__ == "__main__":
    main()
'''


def build_workflow() -> str:
    return '''name: Dashboard presentation Wave 28

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    if: github.head_ref == 'agent/dashboard-presentation-wave-28'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 35

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Verify local Python
        shell: cmd
        run: |
          where python
          python --version

      - name: Compile application, Dashboard module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app\tabs\dashboard.py
          python -m py_compile tools\test_dashboard_presentation_wave_28.py
          python -m compileall -q spina_app

      - name: Run Dashboard presentation regression
        shell: cmd
        run: python -m tools.test_dashboard_presentation_wave_28

      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check

      - name: Run redundancy audit
        shell: cmd
        run: python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json redundancy-report.json

      - name: Run SPINA quality audit
        shell: cmd
        run: python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json quality-report.json

      - name: Upload Wave 28 reports
        uses: actions/upload-artifact@v4
        with:
          name: dashboard-presentation-wave-28-reports
          path: |
            redundancy-report.json
            quality-report.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''


def main() -> None:
    assert raw_sha(SOURCE) == EXPECTED_SOURCE_SHA256, (raw_sha(SOURCE), EXPECTED_SOURCE_SHA256)
    assert git_blob(SOURCE) == EXPECTED_SOURCE_BLOB, (git_blob(SOURCE), EXPECTED_SOURCE_BLOB)
    assert raw_sha(MODULE) == EXPECTED_MODULE_SHA256, (raw_sha(MODULE), EXPECTED_MODULE_SHA256)
    assert git_blob(MODULE) == EXPECTED_MODULE_BLOB, (git_blob(MODULE), EXPECTED_MODULE_BLOB)

    source_text = SOURCE.read_text(encoding="utf-8")
    module_text = MODULE.read_text(encoding="utf-8")
    source_tree = ast.parse(source_text, filename=str(SOURCE))
    module_tree = ast.parse(module_text, filename=str(MODULE))
    source_nodes = top_level_functions(source_text)
    module_nodes = top_level_functions(module_text)

    assert not (set(TARGET_ORDER) & set(module_nodes)), "Target names already exist in Dashboard module"
    assert set(TARGET_ORDER).issubset(source_nodes), "Target functions missing from desktop source"
    assert sum((source_nodes[name].end_lineno or source_nodes[name].lineno) - source_nodes[name].lineno + 1 for name in TARGET_ORDER) == EXPECTED_TARGET_LINES

    target_sources: dict[str, str] = {}
    for name, expected in TARGET_HASHES.items():
        text = segment(source_text, source_nodes[name])
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert actual == expected, (name, actual, expected)
        target_sources[name] = text

    original_source_hashes = source_hashes(source_text)
    original_module_hashes = source_hashes(module_text)

    dashboard_imports = [
        node for node in ast.walk(source_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard"
    ]
    assert len(dashboard_imports) == 1, len(dashboard_imports)
    dashboard_import = dashboard_imports[0]
    configure_alias = next(
        (alias.asname or alias.name for alias in dashboard_import.names if alias.name == "configure_legacy_dashboard_feature"),
        None,
    )
    assert configure_alias, "Dashboard configure import is missing"

    main_node = source_nodes.get("main")
    assert main_node is not None, "Desktop main() function is missing"
    assert source_nodes["_spina_v18_draw_dashboard_charts"].lineno < main_node.lineno
    assert source_nodes["_spina_v20_draw_dashboard_charts"].lineno < main_node.lineno

    source_edits: list[tuple[int, int, str]] = [
        (
            dashboard_import.lineno - 1,
            dashboard_import.end_lineno,
            import_block(dashboard_import, TARGET_ORDER),
        ),
        (
            main_node.lineno - 1,
            main_node.lineno - 1,
            f"# Dashboard presentation callback bridge configured in Wave 28.\n{configure_alias}(\n    draw_v18_charts=_spina_v18_draw_dashboard_charts,\n    draw_v20_charts=_spina_v20_draw_dashboard_charts,\n)\n\n",
        ),
    ]
    earliest = min(source_nodes[name].lineno for name in TARGET_ORDER)
    for name in TARGET_ORDER:
        node = source_nodes[name]
        replacement = ""
        if node.lineno == earliest:
            replacement = "# Dashboard presentation helpers extracted to spina_app/tabs/dashboard.py in Wave 28.\n\n"
        source_edits.append((node.lineno - 1, node.end_lineno, replacement))
    new_source = apply_edits(source_text, source_edits)

    theme_imports = [
        node for node in ast.walk(module_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.theme_palettes"
    ]
    assert len(theme_imports) == 1
    theme_import = theme_imports[0]
    formatting_imports = [
        node for node in ast.walk(module_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.utilities.formatting"
    ]
    assert len(formatting_imports) == 1
    formatting_import = formatting_imports[0]

    log_assign = next(
        node for node in module_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_dashboard_log_exc" for target in node.targets)
    )
    configure_node = module_nodes["configure_legacy_dashboard_feature"]
    log_node = module_nodes["_log_exc"]

    configure_source = '''def configure_legacy_dashboard_feature(
    *, fetch_rows=None, log_exc=None, draw_v18_charts=None, draw_v20_charts=None
):
    """Attach main-module services without importing the large entry module."""
    global _dashboard_fetch_rows, _dashboard_log_exc
    global _dashboard_draw_v18_charts, _dashboard_draw_v20_charts
    if fetch_rows is not None:
        _dashboard_fetch_rows = fetch_rows
    if log_exc is not None:
        _dashboard_log_exc = log_exc
    if draw_v18_charts is not None:
        _dashboard_draw_v18_charts = draw_v18_charts
    if draw_v20_charts is not None:
        _dashboard_draw_v20_charts = draw_v20_charts
'''
    bridge_source = '''def _spina_v18_draw_dashboard_charts(self, rows):
    if callable(_dashboard_draw_v18_charts):
        return _dashboard_draw_v18_charts(self, rows)
    return None


def _spina_v20_draw_dashboard_charts(self, rows):
    if callable(_dashboard_draw_v20_charts):
        return _dashboard_draw_v20_charts(self, rows)
    return None


'''
    module_edits: list[tuple[int, int, str]] = [
        (
            theme_import.lineno - 1,
            theme_import.end_lineno,
            import_block(theme_import, ["_spina_v18_dashboard_palette"]),
        ),
        (
            formatting_import.lineno - 1,
            formatting_import.lineno - 1,
            "from spina_app.utilities.dates import _spina_dash__date_text\n",
        ),
        (
            log_assign.end_lineno,
            log_assign.end_lineno,
            "_dashboard_draw_v18_charts = None\n_dashboard_draw_v20_charts = None\n",
        ),
        (
            configure_node.lineno - 1,
            configure_node.end_lineno,
            configure_source,
        ),
        (
            log_node.end_lineno,
            log_node.end_lineno,
            "\n" + bridge_source,
        ),
    ]
    new_module = apply_edits(module_text, module_edits)
    if not new_module.endswith("\n"):
        new_module += "\n"
    new_module += "\n# Dashboard presentation helpers extracted in Wave 28.\n\n"
    new_module += "\n\n".join(target_sources[name] for name in TARGET_ORDER) + "\n"

    SOURCE.write_text(new_source, encoding="utf-8")
    MODULE.write_text(new_module, encoding="utf-8")

    final_source_text = SOURCE.read_text(encoding="utf-8")
    final_module_text = MODULE.read_text(encoding="utf-8")
    final_source_nodes = top_level_functions(final_source_text)
    final_module_nodes = top_level_functions(final_module_text)

    assert not (set(TARGET_ORDER) & set(final_source_nodes))
    assert set(TARGET_ORDER).issubset(final_module_nodes)
    for name, old_hash in original_source_hashes.items():
        if name not in TARGET_HASHES:
            assert source_hashes(final_source_text)[name] == old_hash, f"Non-target source function changed: {name}"
    for name, old_hash in original_module_hashes.items():
        if name != "configure_legacy_dashboard_feature":
            assert source_hashes(final_module_text)[name] == old_hash, f"Existing Dashboard function changed: {name}"
    for name, expected in TARGET_HASHES.items():
        actual = hashlib.sha256(segment(final_module_text, final_module_nodes[name]).encode("utf-8")).hexdigest()
        assert actual == expected, (name, actual, expected)

    final_tree = ast.parse(final_source_text)
    final_dashboard_import = next(
        node for node in ast.walk(final_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard"
    )
    imported = {alias.asname or alias.name for alias in final_dashboard_import.names}
    assert set(TARGET_ORDER).issubset(imported)
    bridge_calls = [
        node for node in ast.walk(final_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == configure_alias
        and {kw.arg for kw in node.keywords} >= {"draw_v18_charts", "draw_v20_charts"}
    ]
    assert bridge_calls, "Dashboard chart callback bridge call is missing"

    # Record exact expected summary behavior from the original function body.
    from spina_app.utilities.formatting import _spina_dash__fmt_money

    namespace = {"_spina_dash__fmt_money": _spina_dash__fmt_money}
    exec(compile(target_sources["_spina_dashboard_summary_text"], "<wave28-summary>", "exec"), namespace)
    original_summary = namespace["_spina_dashboard_summary_text"]
    summary_cases = [
        [],
        [
            {"name": "A", "status": "Finishing Now", "remaining": 1000.0, "loan_type": "Regular"},
            {"name": "B", "status": "Overdue", "remaining": 250.5, "loan_type": "7x7"},
            {"name": "C", "status": "Active", "remaining": 0.0, "loan_type": "Regular"},
        ],
    ]
    summary_expected = [original_summary(rows) for rows in summary_cases]

    TEST.write_text(build_test(summary_cases, summary_expected), encoding="utf-8")
    WORKFLOW.write_text(build_workflow(), encoding="utf-8")

    print("Dashboard presentation Wave 28 extraction applied:", len(TARGET_ORDER), "functions,", EXPECTED_TARGET_LINES, "lines")


if __name__ == "__main__":
    main()
