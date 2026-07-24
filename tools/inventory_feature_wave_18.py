from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
PREFIXES = {
    "cash_control": ("_spina_v21_", "_spina_cashctl_"),
    "client_information_log": ("_spina_v24_cilog_", "_spina_cilog_"),
    "clients": ("_spina_v23_",),
    "reports": ("_spina_v22_",),
    "collector": ("_spina_v25_",),
    "collector_route": ("_spina_v27_",),
    "dashboard_modern": ("_spina_v18_", "_spina_v20_"),
}


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        group = next(
            (name for name, prefixes in PREFIXES.items() if node.name.startswith(prefixes)),
            None,
        )
        if group is None:
            continue
        end = getattr(node, "end_lineno", node.lineno)
        segment = "\n".join(lines[node.lineno - 1 : end])
        names = sorted(
            {
                child.id
                for child in ast.walk(node)
                if isinstance(child, ast.Name)
                and isinstance(child.ctx, ast.Load)
            }
        )
        calls = sorted(
            {
                child.func.id
                for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
            }
        )
        groups[group].append(
            {
                "name": node.name,
                "start": node.lineno,
                "end": end,
                "lines": end - node.lineno + 1,
                "calls": calls,
                "loaded_names": names,
                "source": segment,
            }
        )

    summary = []
    for group, functions in groups.items():
        functions.sort(key=lambda item: int(item["start"]))
        summary.append(
            {
                "group": group,
                "function_count": len(functions),
                "source_lines": sum(int(item["lines"]) for item in functions),
                "functions": functions,
            }
        )
    summary.sort(key=lambda item: int(item["source_lines"]), reverse=True)

    out = Path("artifacts/wave-18-feature-inventory.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Wave 18 feature inventory")
    for item in summary:
        print(f"{item['group']}: {item['function_count']} functions, {item['source_lines']} lines")
        for fn in item["functions"]:
            print(f"  {fn['name']}: L{fn['start']}-L{fn['end']} ({fn['lines']} lines)")


if __name__ == "__main__":
    main()
