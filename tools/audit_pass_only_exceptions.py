#!/usr/bin/env python3
"""Read-only audit for pass-only exception handlers in the SPINA desktop app."""
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path

DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

PROTECTED_WORDS = {
    "payment", "payments", "balance", "balances", "7x7", "7×7", "renew", "renewal",
    "collector", "route", "report", "reports", "pdf", "payroll", "cash", "ledger",
    "databank", "data bank", "transaction", "transactions", "client", "clients",
    "postgres", "postgresql", "pg_", "backup", "restore", "migration", "schema",
    "login", "account", "audit", "history", "image", "picture", "excel", "import",
    "grid", "tree", "day", "close", "settings", "json",
}


def _segment(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[max(0, start - 1): min(len(lines), end)])


def _scope_name(parents: list[ast.AST]) -> str:
    names: list[str] = []
    for node in parents:
        if isinstance(node, ast.ClassDef):
            names.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
    return ".".join(names) or "<module>"


def _handler_name(node: ast.ExceptHandler) -> str:
    if node.type is None:
        return "bare"
    try:
        return ast.unparse(node.type)
    except Exception:
        return type(node.type).__name__


def _is_pass_only(node: ast.ExceptHandler) -> bool:
    return len(node.body) == 1 and isinstance(node.body[0], ast.Pass)


def _protected(text: str, scope: str) -> bool:
    hay = (scope + "\n" + text).lower()
    return any(word in hay for word in PROTECTED_WORDS)


def audit(path: Path, *, limit: int = 80, context: int = 8) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)

    results: list[dict] = []
    counter = Counter()

    parents: list[ast.AST] = []

    def walk(node: ast.AST) -> None:
        is_scope = isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        if is_scope:
            parents.append(node)
        try:
            if isinstance(node, ast.ExceptHandler) and _is_pass_only(node):
                start = int(getattr(node, "lineno", 0) or 0)
                end = int(getattr(node, "end_lineno", start) or start)
                scope = _scope_name(parents)
                lo = max(1, start - context)
                hi = min(len(lines), end + context)
                ctx = _segment(lines, lo, hi)
                protected = _protected(ctx, scope)
                hname = _handler_name(node)
                severity = "protected_review" if protected else "review_candidate"
                counter[severity] += 1
                counter[f"handler:{hname}"] += 1
                item = {
                    "line": start,
                    "end_line": end,
                    "scope": scope,
                    "handler": hname,
                    "protected_context": protected,
                    "severity": severity,
                    "context": [
                        {"line": i, "text": lines[i - 1]}
                        for i in range(lo, hi + 1)
                    ],
                }
                results.append(item)
            for child in ast.iter_child_nodes(node):
                walk(child)
        finally:
            if is_scope:
                parents.pop()

    walk(tree)

    non_protected = [r for r in results if not r["protected_context"]]
    protected_items = [r for r in results if r["protected_context"]]
    shown = non_protected[:limit]
    if len(shown) < limit:
        shown.extend(protected_items[: max(0, limit - len(shown))])

    return {
        "file": str(path),
        "line_count": len(lines),
        "context_radius": context,
        "pass_only_exception_count": len(results),
        "protected_context_count": len(protected_items),
        "non_protected_pass_only_count": len(non_protected),
        "shown_site_count": len(shown),
        "by_severity": dict(counter),
        "sites": shown,
        "recommendations": [
            "Read-only audit only; no app source changes are made.",
            "Review non-protected candidates first; do not edit protected areas from this audit alone.",
            "Prefer logging or narrowing only one small confirmed-safe area at a time.",
            "Do not touch payments, balances, 7x7, renewals, collectors, reports, backups, migrations, or report math from this audit alone.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", default=DEFAULT_APP)
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--context", type=int, default=8)
    args = parser.parse_args()

    report = audit(Path(args.app), limit=max(1, args.limit), context=max(2, args.context))
    out = json.dumps(report, indent=2)
    if args.json_path:
        Path(args.json_path).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
