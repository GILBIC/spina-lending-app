from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUT = Path("artifacts/cash-control-feature-wave-21.json")
TARGETS = (
    "_spina_v21_cash_build_tab",
    "_spina_v21_cash_draw_charts",
)
PROTECTED = (
    "_spina_v21_cash_refresh",
    "_spina_cashctl_get_average_collection",
    "_spina_cashctl_get_collection_totals",
    "_spina_cashctl_reserve_rows",
)


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def call_name(call: ast.Call) -> str:
    cur = call.func
    parts: list[str] = []
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts)) if parts else "<dynamic>"


def main() -> None:
    text = MAIN.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = [name for name in TARGETS + PROTECTED if name not in functions]
    if missing:
        raise RuntimeError(f"Missing expected functions: {missing}")

    selected = []
    for name in TARGETS:
        node = functions[name]
        src = source_for(lines, node)
        loads = sorted({
            item.id for item in ast.walk(node)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
        })
        calls = sorted({call_name(item) for item in ast.walk(node) if isinstance(item, ast.Call)})
        selected.append({
            "name": name,
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "source_lines": node.end_lineno - node.lineno + 1,
            "sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
            "loaded_spina_names": [item for item in loads if item.startswith("_spina") or item == "_log_exc"],
            "calls": calls,
        })

    payload = {
        "wave": 21,
        "feature": "cash_control_presentation_shell",
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "function_count": len(selected),
        "source_lines": sum(item["source_lines"] for item in selected),
        "functions": selected,
        "protected_functions_kept_in_desktop": list(PROTECTED),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
