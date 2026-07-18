#!/usr/bin/env python3
"""Read-only planner for UI-compatibility pass-only exception handlers.

This script inspects the SPINA app source and groups pass-only exception
handlers that look like best-effort UI compatibility fallbacks. It never edits
source code and it does not approve cleanup by itself.
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

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

UI_COMPAT_HINTS = {
    "toplevel",
    "geometry",
    "transient",
    "grab_set",
    "resizable",
    "style.layout",
    "tag_configure",
    "bind(",
    "configure(",
    "tk.",
    "ttk.",
    "window",
    "dialog",
    "widget",
    "notebook",
    "treeview",
    "button",
    "label",
    "frame",
    "theme",
    "style",
}

UI_SCOPE_HINTS = {
    "open_",
    "dialog",
    "window",
    "_setup_style",
    "_apply_ui_theme",
    "_show_import_log_window",
    "_app_open_client_history_dialog",
    "_app_install_clients_picture_ui",
    "_app__client_form",
    "picture_ui",
    "history_dialog",
}

SENSITIVE_UI_REVIEW_HINTS = {
    "client",
    "history",
    "import",
    "databank",
    "daily close",
    "close_dialog",
    "auto close",
    "auto_close",
    "settings",
    "role",
    "mode",
    "7x7",
    "7×7",
}

LOW_RISK_UI_HINTS = {
    "geometry(",
    "transient(",
    "grab_set(",
    "resizable(",
    "style.layout",
    "tag_configure",
    "bind(",
}


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def handler_name(node: ast.ExceptHandler) -> str:
    if node.type is None:
        return "bare"
    if isinstance(node.type, ast.Name):
        return node.type.id
    if isinstance(node.type, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST | None = node.type
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts)) or ast.dump(node.type)
    return ast.unparse(node.type) if hasattr(ast, "unparse") else ast.dump(node.type)


def is_pass_only(node: ast.ExceptHandler) -> bool:
    return len(node.body) == 1 and isinstance(node.body[0], ast.Pass)


class PassOnlyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.handlers: list[tuple[ast.ExceptHandler, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:
        if is_pass_only(node):
            self.handlers.append((node, ".".join(self.stack) if self.stack else "<module>"))
        self.generic_visit(node)


def line_window(lines: list[str], start: int, end: int, radius: int) -> list[dict[str, Any]]:
    lo = max(1, start - radius)
    hi = min(len(lines), end + radius)
    return [{"line": i, "text": lines[i - 1]} for i in range(lo, hi + 1)]


def text_window(lines: list[str], start: int, end: int, radius: int) -> str:
    lo = max(1, start - radius)
    hi = min(len(lines), end + radius)
    return "\n".join(lines[lo - 1 : hi]).lower()


def contains_any(text: str, words: set[str]) -> bool:
    return any(word.lower() in text for word in words)


def classify_ui_site(scope: str, window: str) -> str | None:
    scope_l = scope.lower()
    combined = f"{scope_l}\n{window}"

    if not (contains_any(combined, UI_COMPAT_HINTS) or contains_any(scope_l, UI_SCOPE_HINTS)):
        return None

    if "dashboard" in combined:
        return "dashboard_ui_review"
    if contains_any(combined, SENSITIVE_UI_REVIEW_HINTS):
        return "sensitive_ui_review"
    if contains_any(combined, LOW_RISK_UI_HINTS):
        return "ui_chrome_compatibility_review"
    return "general_ui_compatibility_review"


def build_report(app_path: Path, context_radius: int, limit_per_group: int) -> dict[str, Any]:
    lines = read_lines(app_path)
    tree = ast.parse("\n".join(lines), filename=str(app_path))
    visitor = PassOnlyVisitor()
    visitor.visit(tree)

    group_counts: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_ui_compat = 0
    protected_ui_compat = 0
    non_protected_ui_compat = 0

    for handler, scope in visitor.handlers:
        start = int(getattr(handler, "lineno", 0) or 0)
        end = int(getattr(handler, "end_lineno", start) or start)
        window = text_window(lines, start, end, context_radius)
        protected = contains_any(f"{scope.lower()}\n{window}", PROTECTED_WORDS)
        group = classify_ui_site(scope, window)
        if group is None:
            continue

        total_ui_compat += 1
        if protected:
            protected_ui_compat += 1
            group = "protected_ui_compatibility_review"
        else:
            non_protected_ui_compat += 1
        group_counts[group] += 1

        if len(samples[group]) < limit_per_group:
            samples[group].append(
                {
                    "line": start,
                    "end_line": end,
                    "scope": scope,
                    "handler": handler_name(handler),
                    "protected_context": protected,
                    "group": group,
                    "selected_for_cleanup_plan": False,
                    "recommended_action": "Review only. This planner does not approve cleanup.",
                    "context": line_window(lines, start, end, context_radius),
                }
            )

    return {
        "file": str(app_path),
        "line_count": len(lines),
        "context_radius": context_radius,
        "pass_only_exception_count": len(visitor.handlers),
        "ui_compatibility_pass_only_count": total_ui_compat,
        "protected_ui_compatibility_count": protected_ui_compat,
        "non_protected_ui_compatibility_count": non_protected_ui_compat,
        "selected_cleanup_candidate_count": 0,
        "group_counts": dict(sorted(group_counts.items())),
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "cleanup_approved": False,
            "protected_words_used": sorted(PROTECTED_WORDS),
            "note": "This report groups UI compatibility pass-only handlers only. It does not approve cleanup.",
        },
        "group_samples": dict(sorted(samples.items())),
        "recommendations": [
            "Do not apply cleanup from this report alone.",
            "Leave protected UI compatibility sites as review-only.",
            "Leave dashboard and sensitive client/data UI sites for separate review.",
            "Only create a cleanup tool later for a very small reviewed subgroup, if any.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan UI compatibility pass-only exception review.")
    parser.add_argument("app", nargs="?", default=DEFAULT_APP)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--context-radius", type=int, default=8)
    parser.add_argument("--limit-per-group", type=int, default=25)
    args = parser.parse_args()

    report = build_report(Path(args.app), args.context_radius, args.limit_per_group)
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
