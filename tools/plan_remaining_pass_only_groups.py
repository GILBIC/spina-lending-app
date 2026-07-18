#!/usr/bin/env python3
"""Group remaining pass-only exception handlers in the SPINA app.

This is a read-only planning tool. It does not edit source files. The purpose is
not to declare all non-protected pass-only handlers safe, but to separate the
remaining handlers into review buckets so any future cleanup can be scoped to one
small family at a time.
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
CONTEXT_RADIUS = 8

PROTECTED_WORDS = {
    "7x7",
    "7×7",
    "apply_role_access",
    "backup",
    "balance",
    "cash control",
    "collector",
    "database",
    "interest",
    "ledger",
    "migration",
    "payment",
    "payroll",
    "pdf",
    "pg_",
    "postgres",
    "principal",
    "receipt",
    "renew",
    "report",
    "restore",
    "role_access",
    "route",
    "statement",
    "transaction",
}


def handler_name(node: ast.ExceptHandler) -> str:
    typ = node.type
    if typ is None:
        return "bare"
    if isinstance(typ, ast.Name):
        return typ.id
    if isinstance(typ, ast.Attribute):
        parts = []
        cur: ast.AST | None = typ
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    try:
        return ast.unparse(typ)
    except Exception:
        return type(typ).__name__


def is_pass_only(node: ast.ExceptHandler) -> bool:
    return len(node.body) == 1 and isinstance(node.body[0], ast.Pass)


def context_for(lines: list[str], line: int, radius: int = CONTEXT_RADIUS) -> list[dict[str, Any]]:
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return [{"line": i, "text": lines[i - 1].rstrip("\n")} for i in range(start, end + 1)]


def has_protected_context(scope: str, ctx: list[dict[str, Any]]) -> bool:
    blob = (scope + "\n" + "\n".join(item["text"] for item in ctx)).lower()
    return any(word.lower() in blob for word in PROTECTED_WORDS)


def classify(scope: str, handler: str, ctx: list[dict[str, Any]], protected: bool) -> tuple[str, str]:
    blob = (scope + "\n" + "\n".join(item["text"] for item in ctx)).lower()

    if protected:
        return "protected_review", "Leave protected business/runtime context alone."
    if scope == "_log_exc" or "[spina][error]" in blob or "file=sys.stderr" in blob:
        return "logger_fallback_leave", "Logger fallback must not raise while reporting another exception."
    if handler == "queue.Empty" or "nothing pending" in blob:
        return "queue_empty_control_flow_leave", "Empty queue is normal control flow."
    if "root is likely closing" in blob or "winfo_exists" in blob or "root.after" in blob:
        return "app_lifecycle_leave", "Tk root may be closing; avoid noisy failures during shutdown."
    if "apply_role_access" in blob or "role_access" in blob or "user_role" in blob:
        return "role_access_runtime_patch_review", "Role/access patching affects visible permissions; keep review-only."
    if "_spina_perf_ensure_indexes" in blob or "pragma" in blob or "create index" in blob or "perf_index" in blob:
        return "performance_index_maintenance_review", "Performance index maintenance should be reviewed separately."
    if "dashboard" in blob:
        return "dashboard_ui_review", "Dashboard UI and summary behavior should be reviewed separately."
    if "theme" in blob or "sidebar" in blob or "header" in blob or "tk." in blob or "ttk." in blob:
        return "ui_compatibility_review", "General UI compatibility fallback; review before cleanup."
    return "other_review", "No narrow cleanup family selected yet."


class PassOnlyVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.scope_stack: list[str] = []
        self.sites: list[dict[str, Any]] = []

    def current_scope(self) -> str:
        return ".".join(self.scope_stack) if self.scope_stack else "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:
        if is_pass_only(node):
            scope = self.current_scope()
            ctx = context_for(self.lines, int(node.lineno))
            handler = handler_name(node)
            protected = has_protected_context(scope, ctx)
            group, recommendation = classify(scope, handler, ctx, protected)
            self.sites.append(
                {
                    "line": int(node.lineno),
                    "end_line": int(getattr(node, "end_lineno", node.lineno) or node.lineno),
                    "scope": scope,
                    "handler": handler,
                    "protected_context": protected,
                    "group": group,
                    "recommended_action": recommendation,
                    "context": ctx,
                }
            )
        self.generic_visit(node)


def build_report(path: Path, max_sites_per_group: int) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    visitor = PassOnlyVisitor(lines)
    visitor.visit(tree)

    sites = sorted(visitor.sites, key=lambda item: item["line"])
    counts = Counter(item["group"] for item in sites)
    non_protected = [item for item in sites if not item["protected_context"]]
    protected = [item for item in sites if item["protected_context"]]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for site in non_protected:
        group = str(site["group"])
        if len(grouped[group]) < max_sites_per_group:
            grouped[group].append(site)

    return {
        "file": str(path),
        "line_count": len(lines),
        "context_radius": CONTEXT_RADIUS,
        "pass_only_exception_count": len(sites),
        "protected_context_count": len(protected),
        "non_protected_pass_only_count": len(non_protected),
        "group_counts": dict(sorted(counts.items())),
        "non_protected_group_counts": dict(sorted(Counter(item["group"] for item in non_protected).items())),
        "selected_cleanup_candidate_count": 0,
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "protected_words_used": sorted(PROTECTED_WORDS),
            "note": "This report only groups remaining handlers. It does not approve cleanup.",
        },
        "non_protected_group_samples": grouped,
        "recommendations": [
            "Do not clean all remaining handlers together.",
            "Leave logger fallback, queue.Empty, and shutdown/lifecycle handlers alone unless there is a clear bug.",
            "Treat role/access, dashboard, performance-index, and protected business contexts as review-only.",
            "Choose at most one narrow family for a future cleanup plan after reviewing this report.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Group remaining pass-only exception handlers.")
    parser.add_argument("source", nargs="?", default=DEFAULT_APP)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--max-sites-per-group", type=int, default=12)
    args = parser.parse_args()

    report = build_report(Path(args.source), max(1, args.max_sites_per_group))
    data = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(data + "\n", encoding="utf-8")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
