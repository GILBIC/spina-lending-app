from __future__ import annotations

import ast
import builtins
import hashlib
import json
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("tools/fixtures/area_text_helper_batch_05_inspection.json")
TARGETS = ["split_area_main_sub", "join_area_main_sub", "_spina_crc_split_area"]


def external_names(node: ast.FunctionDef) -> list[str]:
    local = {a.arg for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
    if node.args.vararg:
        local.add(node.args.vararg.arg)
    if node.args.kwarg:
        local.add(node.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            local.add(child.id)
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    return sorted(loaded - local - set(dir(builtins)) - {node.name})


def calls(node: ast.FunctionDef) -> list[str]:
    result: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            try:
                result.append(ast.unparse(child.func))
            except Exception:
                result.append("?")
    return sorted(set(result))


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP))
    nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TARGETS
    }
    missing = [name for name in TARGETS if name not in nodes]
    if missing:
        raise SystemExit(f"Missing target helpers: {missing}")

    refs: dict[str, int] = {}
    for child in ast.walk(tree):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            refs[child.id] = refs.get(child.id, 0) + 1

    result = []
    for name in TARGETS:
        node = nodes[name]
        exact = ast.get_source_segment(source, node)
        if exact is None:
            raise SystemExit(f"Could not recover source for {name}")
        result.append({
            "name": name,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "signature": ast.unparse(node.args),
            "source_sha256": hashlib.sha256(exact.encode("utf-8")).hexdigest(),
            "external_names": external_names(node),
            "calls": calls(node),
            "reference_count": max(0, refs.get(name, 0) - 1),
            "source": exact,
        })

    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Recorded {len(result)} area helpers")


if __name__ == "__main__":
    main()
