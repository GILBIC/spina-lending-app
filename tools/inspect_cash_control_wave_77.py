#!/usr/bin/env python3
"""Read-only structural inspection for Cash Control modularization Wave 77."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT_PATH = ROOT / "artifacts" / "cash_control_wave_77_inspection.json"

START_MARKER = (
    "# --- BEGIN: Cash Control tab - percent buffer + net renewal cash forecast + "
    "separated current/forecast safe amounts ---"
)
END_MARKER = (
    "# --- END: Cash Control tab - percent buffer + net renewal cash forecast + "
    "separated current/forecast safe amounts ---"
)

EXPECTED_TOP_LEVEL_FUNCTIONS = (
    "_spina_cashctl__fmt_money",
    "_spina_cashctl__parse_percent",
    "_spina_cashctl_get_collection_totals",
    "_spina_cashctl_get_average_collection",
    "_spina_cashctl__ceil_thousand_units",
    "_spina_cashctl__x7_daily_interest",
    "_spina_cashctl_estimated_payoff_with_interest",
    "_spina_cashctl_reserve_rows",
    "_spina_cashctl_build_tab",
    "_spina_cashctl_refresh",
    "_spina_cashctl_apply_role",
)

EXPECTED_APP_BINDINGS = (
    "_build_cash_control_tab",
    "refresh_cash_control",
    "_cash_control_get_collection_totals",
    "_cash_control_get_average_collection",
    "_cash_control_reserve_rows",
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _find_block(source: str) -> tuple[str, int, int]:
    start = source.find(START_MARKER)
    end = source.find(END_MARKER)
    if start < 0 or end < 0:
        raise AssertionError("Cash Control boundary marker missing")
    if source.find(START_MARKER, start + 1) >= 0:
        raise AssertionError("Cash Control start marker is duplicated")
    if source.find(END_MARKER, end + 1) >= 0:
        raise AssertionError("Cash Control end marker is duplicated")
    if end <= start:
        raise AssertionError("Cash Control end marker precedes start marker")
    end += len(END_MARKER)
    block = source[start:end]
    start_line = source.count("\n", 0, start) + 1
    end_line = start_line + block.count("\n")
    return block, start_line, end_line


def _call_name(node: ast.Call) -> str:
    target: ast.AST = node.func
    parts: list[str] = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return ".".join(reversed(parts))


def inspect() -> dict[str, Any]:
    source = APP_PATH.read_text(encoding="utf-8")
    block, start_line, end_line = _find_block(source)
    tree = ast.parse(block)

    top_level_functions = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    missing_functions = sorted(set(EXPECTED_TOP_LEVEL_FUNCTIONS) - set(top_level_functions))
    unexpected_functions = sorted(set(top_level_functions) - set(EXPECTED_TOP_LEVEL_FUNCTIONS))
    if missing_functions:
        raise AssertionError(f"Missing Cash Control functions: {missing_functions}")
    if unexpected_functions:
        raise AssertionError(f"Unexpected Cash Control functions: {unexpected_functions}")

    calls = sorted(
        {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for name in [_call_name(node)]
            if name
        }
    )
    direct_db_calls = sorted(
        name
        for name in calls
        if name.startswith("self.db.") or name.startswith("conn.") or name.startswith("cur.")
    )

    app_bindings = sorted(
        {
            node.args[1].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _call_name(node) == "setattr"
            and len(node.args) >= 3
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "App"
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        }
    )
    missing_bindings = sorted(set(EXPECTED_APP_BINDINGS) - set(app_bindings))
    if missing_bindings:
        raise AssertionError(f"Missing Cash Control App bindings: {missing_bindings}")

    lowered = block.lower()
    destructive_sql_tokens = [
        token
        for token in ("insert into", "update ", "delete from", "drop table", "alter table")
        if token in lowered
    ]
    if destructive_sql_tokens:
        raise AssertionError(
            "Cash Control inspection expected read-only SQL, found: "
            + ", ".join(destructive_sql_tokens)
        )

    required_dependencies = {
        "dashboard_rows": "_spina_dashboard_fetch_rows" in block,
        "loan_type_normalizer": "_spina_dash__norm_lt" in block,
        "x7_allocator": "_wave74_allocate_x7_payments" in block,
        "x7_interest": "_wave74_x7_daily_interest" in block,
        "date_formatter": "_spina_dash__date_text" in block,
        "role_hook": "apply_role_access" in block,
        "mode_hook": "_on_mode_change" in block,
    }
    missing_dependencies = sorted(name for name, present in required_dependencies.items() if not present)
    if missing_dependencies:
        raise AssertionError(f"Missing expected Cash Control dependencies: {missing_dependencies}")

    report: dict[str, Any] = {
        "wave": 77,
        "source_path": str(APP_PATH.relative_to(ROOT)).replace("\\", "/"),
        "start_line": start_line,
        "end_line": end_line,
        "line_count": block.count("\n") + 1,
        "sha256": _sha256(block),
        "top_level_functions": top_level_functions,
        "app_bindings": app_bindings,
        "direct_db_calls": direct_db_calls,
        "destructive_sql_tokens": destructive_sql_tokens,
        "required_dependencies": required_dependencies,
        "recommended_modules": {
            "spina_app/repositories/cash_control.py": [
                "daily collection totals",
                "average active-day collection",
                "current-cycle 7x7 payment reads",
            ],
            "spina_app/services/cash_control.py": [
                "input normalization",
                "renewal payoff estimation",
                "reserve prioritization",
                "safe-now and forecast-safe calculations",
            ],
            "spina_app/tabs/cash_control.py": [
                "Tkinter tab construction",
                "summary and reserve-table refresh",
                "role visibility",
            ],
            "spina_app/features/cash_control.py": [
                "one idempotent App installer",
                "init, role, and mode hooks",
            ],
        },
    }
    return report


def main() -> None:
    report = inspect()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Cash Control Wave 77 inspection passed.")


if __name__ == "__main__":
    main()
