#!/usr/bin/env python3
"""Run Wave 51 chart coverage through the Wave 76 feature installer."""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

from tools import test_dashboard_chart_presentation_wave_51 as wave51

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
FEATURE = ROOT / "spina_app" / "features" / "dashboard.py"


def main() -> None:
    module = importlib.import_module("spina_app.dashboard_chart_presentation")
    assert module.DASHBOARD_CHART_TARGETS == wave51.TARGETS
    assert module.DASHBOARD_CHART_SOURCE_LINES == wave51.EXPECTED_LINES
    assert module.DASHBOARD_CHART_SOURCE_SHA256 == wave51.EXPECTED_HASHES
    assert module.DASHBOARD_CHART_SIGNATURES == wave51.EXPECTED_SIGNATURES
    assert module.DASHBOARD_CHART_CALLS == wave51.EXPECTED_CALLS

    module_text = wave51.MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    total_lines = 0
    for name in wave51.TARGETS:
        matches = wave51.top_functions(module_tree, name)
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = wave51.source_for(module_text, node)
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        assert line_count == wave51.EXPECTED_LINES[name], (name, line_count)
        assert wave51.source_hash(source) == wave51.EXPECTED_HASHES[name], name
        assert ast.unparse(node.args) == wave51.EXPECTED_SIGNATURES[name], name
        assert wave51.calls_for(node) == wave51.EXPECTED_CALLS[name], name
        lower = source.lower()
        for token in wave51.FORBIDDEN:
            assert token.lower() not in lower, (name, token)
        total_lines += line_count
    assert total_lines == 274, total_lines

    sentinels = {
        name: object() for name in module.DASHBOARD_CHART_REQUIRED_DEPENDENCIES
    }
    module.configure_dashboard_chart_dependencies(sentinels)
    assert module._DASHBOARD_CHART_DEPENDENCIES == sentinels
    for name, value in sentinels.items():
        assert getattr(module, name) is value

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    for name in wave51.TARGETS:
        assert not wave51.top_functions(desktop_tree, name), f"{name} remains in desktop"
    assert "spina_app.dashboard_chart_presentation" not in desktop_text
    assert desktop_text.count("_wave76_install_dashboard_feature(") == 1

    feature_text = FEATURE.read_text(encoding="utf-8")
    feature_tree = ast.parse(feature_text)
    imports = [
        node
        for node in feature_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.dashboard_chart_presentation"
    ]
    assert len(imports) == 1, len(imports)
    imported_names = {alias.name for alias in imports[0].names}
    assert imported_names == {
        "configure_dashboard_chart_dependencies",
        "_spina_v18_draw_dashboard_charts",
        "_spina_v20_draw_dashboard_charts",
    }, imported_names

    install_nodes = wave51.top_functions(feature_tree, "install_dashboard_feature")
    assert len(install_nodes) == 1
    install_source = wave51.source_for(feature_text, install_nodes[0])
    for token in (
        "configure_dashboard_chart_dependencies(",
        "configure_legacy_dashboard_feature(",
        "draw_v18_charts=_spina_v18_draw_dashboard_charts",
        "draw_v20_charts=_spina_v20_draw_dashboard_charts",
    ):
        assert token in install_source, token

    wave51.verify_bridge_sources()
    print("Wave 51 dashboard-chart compatibility under Wave 76 passed.")


if __name__ == "__main__":
    main()
