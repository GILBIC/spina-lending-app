from __future__ import annotations

import ast
import builtins
import hashlib
import json
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("tools/fixtures/pure_display_helper_batch_04_candidates.json")
RISK_TERMS = [
    "sql", "db", "postgres", "sqlite", "cursor", "conn", "commit", "rollback",
    "payment", "balance", "principal", "interest", "7x7", "renew", "loan",
    "report", "pdf", "canvas", "widget", "tk", "messagebox", "dialog",
    "file", "path", "folder", "os.", "open(", "auth", "login", "role",
    "thread", "queue", "after(", "bind(", "configure(", "destroy(",
]


def _external_names(node: ast.FunctionDef) -> list[str]:
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


def _calls(node: ast.FunctionDef) -> list[str]:
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
    tree = ast.parse(source)
    references: dict[str, int] = {}
    for child in ast.walk(tree):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            references[child.id] = references.get(child.id, 0) + 1

    candidates: list[dict[str, object]] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        if line_count > 24:
            continue
        if any(
            isinstance(item, (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom, ast.Await))
            for item in ast.walk(node)
        ):
            continue
        exact = ast.get_source_segment(source, node) or ""
        lower = exact.lower()
        risks = sorted({term for term in RISK_TERMS if term in lower})
        candidates.append(
            {
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno,
                "lines": line_count,
                "signature": ast.unparse(node.args),
                "external_names": _external_names(node),
                "calls": _calls(node),
                "risk_terms": risks,
                "reference_count": max(0, references.get(node.name, 0) - 1),
                "source_sha256": hashlib.sha256(exact.encode("utf-8")).hexdigest(),
                "source": exact,
            }
        )

    candidates.sort(
        key=lambda item: (
            len(item["risk_terms"]),
            len(item["external_names"]),
            0 if item["reference_count"] > 0 else 1,
            item["lines"],
            item["name"],
        )
    )
    OUTPUT.write_text(
        json.dumps(candidates[:120], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {min(len(candidates), 120)} candidates")


if __name__ == "__main__":
    main()
