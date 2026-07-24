"""Read-only inventory for Collector Route modularization Wave 23."""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
from collections import defaultdict
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("wave-23-inventory.json")
TARGETS = (
    "_spina_v27_update_route_cards",
    "_spina_v27_hidden_collector_widgets",
)


def _source_for(lines: list[str], node: ast.AST) -> str:
    start = int(getattr(node, "lineno"))
    end = int(getattr(node, "end_lineno"))
    return "\n".join(lines[start - 1 : end])


def _called_names(node: ast.AST) -> set[str]:
    result: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            result.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            result.add(child.func.attr)
    return result


def _global_dependencies(node: ast.FunctionDef) -> list[str]:
    local = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        local.add(node.args.vararg.arg)
    if node.args.kwarg:
        local.add(node.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Param)):
            local.add(child.id)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
            local.add(child.name)
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    return sorted(loaded - local - set(dir(builtins)))


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    missing = [name for name in TARGETS if name not in functions]
    if missing:
        raise RuntimeError(f"Missing Wave 23 targets: {missing}")

    callers: dict[str, set[str]] = defaultdict(set)
    for caller_name, caller_node in functions.items():
        for called in _called_names(caller_node):
            if called in functions and called != caller_name:
                callers[called].add(caller_name)

    entries = []
    for name in TARGETS:
        node = functions[name]
        source = _source_for(lines, node)
        start = int(node.lineno)
        end = int(node.end_lineno)
        entries.append(
            {
                "name": name,
                "start_line": start,
                "end_line": end,
                "lines": end - start + 1,
                "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                "direct_callers": sorted(callers.get(name, set())),
                "called_names": sorted(_called_names(node)),
                "global_dependencies": _global_dependencies(node),
                "source": source,
            }
        )

    payload = {
        "source": str(SOURCE),
        "source_lines": len(lines),
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "base_commit": "0c48274fc40efb928b6f5466d077dffed7f0c513",
        "target_count": len(entries),
        "moved_source_lines": sum(item["lines"] for item in entries),
        "functions": entries,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "functions"}, indent=2))
    for entry in entries:
        print(json.dumps({key: value for key, value in entry.items() if key != "source"}, indent=2))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
