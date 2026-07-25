from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "postgres_compat.py"
TARGETS = ('_spina_pg_sha256', '_spina_pg_guess_file_type', '_spina_pg_guess_report_date', '_spina_pg_guess_collector', '_spina_pg_normalize_value', '_spina_pg_replace_qmarks', '_spina_pg_escape_literal_percents')
EXPECTED_SHA256 = {'_spina_pg_sha256': 'cb67c3f2ff0ca8599ff47ef9cd24f4184061c97c1ddb6418016ea218bb0b2c8f', '_spina_pg_guess_file_type': '4c5ae58cc1c8958be489de35470a4dde256c158fc3f007b364bbffa874b45a04', '_spina_pg_guess_report_date': 'bcfdf7e9c2366e7d376ee55a8757f78cd3b75c3e867e87f7c3ff76bdef86c291', '_spina_pg_guess_collector': 'f27b107fc5529bba73e68c249be14d9f03757114d2ff94af47dd3b56555fa5da', '_spina_pg_normalize_value': 'a3d32820748ce7d3b8f8cc40563d75e759b005cdcbff6311a5e8c907efbb4ad0', '_spina_pg_replace_qmarks': '444266c36ffc8188f5fe242e25ca37a3d0a09730d76fc25eae07d71030245859', '_spina_pg_escape_literal_percents': 'e6c3cf7667cefad7b7c301189c5513f6d8b7f6fb232be23a9ee9314aa43a7a11'}
EXPECTED_TOTAL_LINES = 106


def normalized_source(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized_source(source).encode("utf-8")).hexdigest()


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text, filename=str(MODULE))
    functions = {
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = [name for name in TARGETS if name not in functions]
    assert not missing, f"Missing extracted functions: {missing}"

    actual_total = 0
    for name in TARGETS:
        segment = ast.get_source_segment(module_text, functions[name])
        assert segment, name
        assert source_hash(segment) == EXPECTED_SHA256[name], name
        actual_total += len(normalized_source(segment).splitlines())
    assert actual_total == EXPECTED_TOTAL_LINES, (actual_total, EXPECTED_TOTAL_LINES)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text, filename=str(DESKTOP))
    remaining = {
        node.name
        for node in desktop_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in TARGETS
    }
    assert not remaining, f"Functions still defined in desktop file: {sorted(remaining)}"

    rebound = set()
    for node in desktop_tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in TARGETS:
                    rebound.add(target.id)
    assert rebound == set(TARGETS), (rebound, set(TARGETS))

    forbidden_calls = {
        "execute", "executemany", "commit", "rollback",
        "write_text", "write_bytes", "unlink", "remove", "rename",
    }
    for name in TARGETS:
        node = functions[name]
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                call_name = ""
                if isinstance(func, ast.Name):
                    call_name = func.id
                elif isinstance(func, ast.Attribute):
                    call_name = func.attr
                assert call_name not in forbidden_calls, (name, call_name)

    print(
        f"Wave 34 PostgreSQL compatibility regression passed: "
        f"{len(TARGETS)} functions / {EXPECTED_TOTAL_LINES} lines."
    )


if __name__ == "__main__":
    main()
