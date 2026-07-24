"""Focused regression checks for Dashboard presentation Wave 28."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from spina_app.tabs import dashboard

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "tabs" / "dashboard.py"
EXPECTED_HASHES = {'_spina_dashboard_summary_text': 'a3e3a98b08bb55760d26bd26e7007a24fc1e42a0806fbbd5f6cbbafc563d8fcc', '_spina_configure_dashboard_tree_theme': '763b1115268385a391bdf8570d0b807a5bd15d4a23ed3087c6abace5643e8950', '_spina_build_dashboard_tab': '8e3d70fed368facfb1cdfbb62442ea88eedfad0efbfc0b67d94df78ba7789207', '_spina_populate_dashboard_tree': '9a26abe818e6cfe37c8ffe1dec47176268cf057c8dcb4042ba02c6e226dbc985', '_spina_refresh_dashboard': 'b40c5dd7f2a081f322b2b04b6910dc408ac1fd903b234a29f2613c22ee851edb', '_spina_apply_dashboard_role': '37bc51146533cb798a7531f5ff01406f4611b8e1167e8ac4f59d5f10327a1a5b', '_spina_v18_patch_dashboard_chart_cards': '1cbd667d330a0230795ad2d8e9b279e28c5f276f0f1a9e37718de78562f0bebc', '_spina_v18_populate_dashboard_tree': 'fb838546b5ff7ef96b4ec7c00c64bda644bd959cf7358f73e2562751826259c5', '_spina_v18_refresh_dashboard': '2a667318c3cd97c93ce2ee82b7daba04cf97db16b0fba281a9a8cb537e3f89b3', '_spina_v19_populate_dashboard_tree': '3ab56f70a231c1813ea3a1040a46dcd6dc58d2aa5a8b6604a2d45b79cac62070', '_spina_v19_refresh_dashboard': '8a5a0ac327e8558bbf196b7586b17793d4c5f0a8f82f2214580d4eee950cf6cd', '_spina_v20_populate_dashboard_tree': '6d87d7b52220eb90964d2dceda98c2e0218a05875e903a90dbfaab94e2b07170', '_spina_v20_refresh_dashboard': '54f6e2e53214ab0062574e37ca7ff839f20ea6afb196eb09f246ccd049098912'}
EXPECTED_LINES = 449
SUMMARY_CASES = [[], [{'name': 'A', 'status': 'Finishing Now', 'remaining': 1000.0, 'loan_type': 'Regular'}, {'name': 'B', 'status': 'Overdue', 'remaining': 250.5, 'loan_type': '7x7'}, {'name': 'C', 'status': 'Active', 'remaining': 0.0, 'loan_type': 'Regular'}]]
SUMMARY_EXPECTED = ['Active: 0    Finishing Now: 0    Near: 0    Due Soon: 0    Overdue: 0    Complete: 0    Principal: PHP 0.00    Remaining: PHP 0.00', 'Active: 3    Finishing Now: 1    Near: 0    Due Soon: 0    Overdue: 1    Complete: 0    Principal: PHP 0.00    Remaining: PHP 1,250.50']


def functions(path: Path):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    lines = text.splitlines()
    result = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            source = "\n".join(lines[node.lineno - 1 : node.end_lineno])
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
    rows = [{"name": "Bridge"}]
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
