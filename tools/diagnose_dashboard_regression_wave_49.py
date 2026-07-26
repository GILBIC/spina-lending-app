from __future__ import annotations

import importlib.util
import json
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_PATH = ROOT / "tools" / "test_dashboard_presentation_wave_28.py"
OUT = ROOT / "artifacts" / "wave-49-dashboard-diagnostic.json"


def load_test_module():
    spec = importlib.util.spec_from_file_location("wave28_dashboard_test", TEST_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_check(name, callback, results):
    try:
        value = callback()
        results.append({"name": name, "status": "passed", "value": repr(value)})
    except BaseException as exc:
        results.append({
            "name": name,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc().splitlines()[-12:],
        })


def main() -> None:
    test = load_test_module()
    results = []

    def source_and_module_shape():
        source_functions = test.functions(test.SOURCE)
        module_functions = test.functions(test.MODULE)
        assert not (set(test.EXPECTED_HASHES) & set(source_functions)), (
            "desktop leftovers",
            sorted(set(test.EXPECTED_HASHES) & set(source_functions)),
        )
        assert set(test.EXPECTED_HASHES).issubset(module_functions), (
            "module missing",
            sorted(set(test.EXPECTED_HASHES) - set(module_functions)),
        )
        return len(source_functions), len(module_functions)

    def exact_hashes_and_lines():
        module_functions = test.functions(test.MODULE)
        total_lines = 0
        import hashlib
        for name, expected in test.EXPECTED_HASHES.items():
            node, text = module_functions[name]
            actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
            assert actual == expected, (name, actual, expected)
            total_lines += (node.end_lineno or node.lineno) - node.lineno + 1
        assert total_lines == test.EXPECTED_LINES, total_lines
        return total_lines

    def chart_bridges():
        calls = []
        marker = object()
        test.dashboard.configure_legacy_dashboard_feature(
            draw_v18_charts=lambda self, rows: calls.append(("v18", self, rows)) or marker,
            draw_v20_charts=lambda self, rows: calls.append(("v20", self, rows)) or marker,
        )
        owner = object()
        rows = [{"name": "Bridge"}]
        assert test.dashboard._spina_v18_draw_dashboard_charts(owner, rows) is marker
        assert test.dashboard._spina_v20_draw_dashboard_charts(owner, rows) is marker
        assert [entry[0] for entry in calls] == ["v18", "v20"]
        return calls

    def summaries():
        actual = [test.dashboard._spina_dashboard_summary_text(rows) for rows in test.SUMMARY_CASES]
        assert actual == test.SUMMARY_EXPECTED, (actual, test.SUMMARY_EXPECTED)
        return actual

    def defensive_helpers():
        class EmptyApp:
            pass
        test.dashboard._spina_configure_dashboard_tree_theme(EmptyApp())
        test.dashboard._spina_apply_dashboard_role(EmptyApp())
        return True

    run_check("source_and_module_shape", source_and_module_shape, results)
    run_check("exact_hashes_and_lines", exact_hashes_and_lines, results)
    run_check("chart_bridges", chart_bridges, results)
    run_check("summaries", summaries, results)
    run_check("defensive_helpers", defensive_helpers, results)
    run_check("startup_wiring", test.assert_dashboard_startup_wiring, results)
    run_check("role_visibility", test.assert_dashboard_role_visibility, results)

    report = {
        "failed_count": sum(item["status"] == "failed" for item in results),
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
