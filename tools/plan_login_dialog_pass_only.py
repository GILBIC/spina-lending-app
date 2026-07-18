#!/usr/bin/env python3
"""Read-only planner for login/auth dialog pass-only exception handlers.

This tool never edits the SPINA app.  It scans for exception handlers whose
body is exactly ``pass`` and groups only login/auth/dialog related handlers for
review.  Cleanup approval is intentionally always zero; this report is used to
pick a very small future cleanup subgroup, if any.
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

APP_PATH = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

PROTECTED_WORDS = [
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
]

LOGIN_WORDS = [
    "login",
    "log in",
    "signin",
    "sign in",
    "auth",
    "authenticate",
    "password",
    "username",
    "user_name",
    "user role",
    "user_role",
    "account login",
    "staff login",
]

LOGIN_DIALOG_WORDS = [
    "login",
    "log in",
    "sign in",
    "password",
    "username",
    "dialog",
    "toplevel",
    "messagebox",
    "entry",
    "button",
    "grab_set",
    "transient",
    "geometry",
    "focus",
]

SENSITIVE_LOGIN_WORDS = [
    "password",
    "hash",
    "token",
    "credential",
    "authenticate",
    "auth",
    "permission",
    "role",
    "role_access",
    "admin",
]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _handler_name(handler: ast.ExceptHandler) -> str:
    if handler.type is None:
        return "bare"
    try:
        return ast.unparse(handler.type)
    except Exception:
        return handler.type.__class__.__name__


def _is_pass_only(handler: ast.ExceptHandler) -> bool:
    return len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)


def _line_window(lines: list[str], lineno: int, end_lineno: int, radius: int) -> list[dict[str, Any]]:
    start = max(1, lineno - radius)
    end = min(len(lines), end_lineno + radius)
    return [
        {"line": i, "text": lines[i - 1].rstrip("\n")}
        for i in range(start, end + 1)
    ]


def _context_text(context: list[dict[str, Any]]) -> str:
    return "\n".join(str(item.get("text", "")) for item in context).lower()


def _has_any(text: str, words: list[str]) -> bool:
    low = text.lower()
    return any(word.lower() in low for word in words)


class PassOnlyVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], radius: int) -> None:
        self.lines = lines
        self.radius = radius
        self.scope_stack: list[str] = []
        self.sites: list[dict[str, Any]] = []

    def _scope(self) -> str:
        return ".".join(self.scope_stack) if self.scope_stack else "<module>"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:
        if _is_pass_only(node):
            lineno = int(getattr(node, "lineno", 0) or 0)
            end_lineno = int(getattr(node, "end_lineno", lineno) or lineno)
            context = _line_window(self.lines, lineno, end_lineno, self.radius)
            scope = self._scope()
            haystack = f"{scope}\n{_context_text(context)}"
            is_login_related = _has_any(haystack, LOGIN_WORDS)
            protected = _has_any(haystack, PROTECTED_WORDS)
            sensitive_login = _has_any(haystack, SENSITIVE_LOGIN_WORDS)
            dialog_like = _has_any(haystack, LOGIN_DIALOG_WORDS)
            group = "outside_login_scope"
            if is_login_related:
                if protected:
                    group = "protected_login_review"
                elif sensitive_login:
                    group = "login_sensitive_auth_review"
                elif dialog_like:
                    group = "login_dialog_ui_review"
                else:
                    group = "login_related_review"
            self.sites.append(
                {
                    "line": lineno,
                    "end_line": end_lineno,
                    "scope": scope,
                    "handler": _handler_name(node),
                    "login_related": is_login_related,
                    "protected_context": protected,
                    "sensitive_login_context": sensitive_login,
                    "dialog_like_context": dialog_like,
                    "group": group,
                    "selected_for_cleanup_plan": False,
                    "recommended_action": "Review only. This planner does not approve cleanup.",
                    "context": context,
                }
            )
        self.generic_visit(node)


def build_report(app_path: Path, context_radius: int, limit_per_group: int) -> dict[str, Any]:
    source = _read_text(app_path)
    lines = source.splitlines()
    tree = ast.parse(source)
    visitor = PassOnlyVisitor(lines, context_radius)
    visitor.visit(tree)

    all_sites = visitor.sites
    login_sites = [s for s in all_sites if s["login_related"]]
    non_protected_login = [s for s in login_sites if not s["protected_context"]]
    group_counts = Counter(str(s["group"]) for s in login_sites)
    non_protected_group_counts = Counter(str(s["group"]) for s in non_protected_login)

    samples: dict[str, list[dict[str, Any]]] = {}
    for site in login_sites:
        group = str(site["group"])
        bucket = samples.setdefault(group, [])
        if len(bucket) < limit_per_group:
            bucket.append(site)

    return {
        "file": str(app_path),
        "line_count": len(lines),
        "context_radius": context_radius,
        "pass_only_exception_count": len(all_sites),
        "login_pass_only_count": len(login_sites),
        "protected_login_count": sum(1 for s in login_sites if s["protected_context"]),
        "non_protected_login_count": len(non_protected_login),
        "selected_cleanup_candidate_count": 0,
        "group_counts": dict(sorted(group_counts.items())),
        "non_protected_group_counts": dict(sorted(non_protected_group_counts.items())),
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "cleanup_approved": False,
            "protected_words_used": PROTECTED_WORDS,
            "note": "This report only groups login/auth/dialog pass-only handlers. It does not approve cleanup.",
        },
        "group_samples": dict(sorted(samples.items())),
        "recommendations": [
            "Do not apply cleanup from this report alone.",
            "Leave password/auth/role-sensitive login handlers as review-only.",
            "Only consider a future cleanup tool for a very small login dialog UI-only subgroup, if one exists.",
            "Smoke-test staff login after any future login UI cleanup.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan login-dialog pass-only exception review groups.")
    parser.add_argument("app", nargs="?", default=APP_PATH)
    parser.add_argument("--json", dest="json_path", default="login-dialog-pass-only-plan.json")
    parser.add_argument("--context-radius", type=int, default=8)
    parser.add_argument("--limit-per-group", type=int, default=25)
    args = parser.parse_args()

    app_path = Path(args.app)
    if not app_path.exists():
        raise SystemExit(f"App file not found: {app_path}")

    report = build_report(app_path, args.context_radius, args.limit_per_group)
    Path(args.json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "file": report["file"],
        "login_pass_only_count": report["login_pass_only_count"],
        "selected_cleanup_candidate_count": report["selected_cleanup_candidate_count"],
        "json": args.json_path,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
