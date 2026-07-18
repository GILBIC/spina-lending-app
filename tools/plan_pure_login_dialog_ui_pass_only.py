#!/usr/bin/env python3
"""Read-only planner for pure login dialog UI pass-only handlers.

This tool deliberately does not edit the SPINA app. It narrows the prior
login-dialog report to the outer login dialog UI shell only, excluding account
storage, password verification, role/access, header/account switch, and other
auth-sensitive behavior.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

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

SENSITIVE_LOGIN_WORDS = [
    "_verify_login",
    "verify_login",
    "_must_change_password",
    "_force_change_password_dialog",
    "password",
    "pw_var",
    "show password",
    "role",
    "user_role",
    "access_profile",
    "permission",
    "_save_users_db",
    "_load_users_db",
    "users[",
    "switch_account",
    "_refresh_user_header",
    "_build_header",
]

PURE_OUTER_SCOPE = "_spina_v32_prompt_login"


class HandlerVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], context_radius: int) -> None:
        self.lines = lines
        self.context_radius = context_radius
        self.scope_stack: list[str] = []
        self.sites: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:  # noqa: ANN401
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: ANN401
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:  # noqa: ANN401
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:  # noqa: ANN401
        if self._is_exception_pass_only(node):
            self.sites.append(self._site(node))
        self.generic_visit(node)

    def _is_exception_pass_only(self, node: ast.ExceptHandler) -> bool:
        if len(node.body) != 1 or not isinstance(node.body[0], ast.Pass):
            return False
        if isinstance(node.type, ast.Name) and node.type.id == "Exception":
            return True
        return False

    def _scope(self) -> str:
        return ".".join(self.scope_stack) if self.scope_stack else "<module>"

    def _context(self, start: int, end: int) -> list[dict[str, Any]]:
        first = max(1, start - self.context_radius)
        last = min(len(self.lines), end + self.context_radius)
        return [
            {"line": line_no, "text": self.lines[line_no - 1].rstrip("\n")}
            for line_no in range(first, last + 1)
        ]

    def _site(self, node: ast.ExceptHandler) -> dict[str, Any]:
        end_line = getattr(node, "end_lineno", node.lineno)
        context = self._context(node.lineno, end_line)
        local_start = max(1, node.lineno - 6)
        local_end = min(len(self.lines), end_line + 4)
        local_text = "\n".join(self.lines[local_start - 1 : local_end]).lower()
        full_context_text = "\n".join(item["text"] for item in context).lower()
        scope = self._scope()
        pure_group = _classify_pure_login_dialog_ui(scope, local_text)
        protected = any(word.lower() in full_context_text for word in PROTECTED_WORDS)
        sensitive = any(word.lower() in local_text for word in SENSITIVE_LOGIN_WORDS)
        return {
            "line": node.lineno,
            "end_line": end_line,
            "scope": scope,
            "handler": "Exception",
            "protected_context": protected,
            "sensitive_login_context": sensitive,
            "pure_login_dialog_ui": pure_group is not None,
            "group": pure_group or _fallback_login_group(scope, protected, sensitive, full_context_text),
            "selected_for_cleanup_plan": False,
            "recommended_action": "Review only. This planner does not approve cleanup.",
            "context": context,
        }


def _classify_pure_login_dialog_ui(scope: str, local_text: str) -> str | None:
    if scope != PURE_OUTER_SCOPE:
        return None
    if "dlg.transient" in local_text:
        return "pure_dialog_transient_review"
    if "account_var.trace_add" in local_text:
        return "pure_dialog_account_trace_review"
    if "<return>" in local_text and ".bind" in local_text:
        return "pure_dialog_return_bind_review"
    if "dlg.grab_set" in local_text:
        return "pure_dialog_grab_review"
    if "dlg.geometry" in local_text:
        return "pure_dialog_position_review"
    if "pw_entry.focus_set" in local_text:
        return "pure_dialog_initial_focus_review"
    return None


def _fallback_login_group(scope: str, protected: bool, sensitive: bool, context_text: str) -> str:
    if protected:
        return "protected_login_review"
    if scope.startswith("_spina_v32_prompt_login") or "login" in scope.lower():
        if sensitive:
            return "excluded_login_auth_sensitive_review"
        return "excluded_login_dialog_non_pure_review"
    if "account" in context_text or "user_role" in context_text or "password" in context_text:
        return "excluded_account_or_role_review"
    return "other_pass_only_review"


def build_report(app_path: Path, context_radius: int) -> dict[str, Any]:
    text = app_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(app_path))
    visitor = HandlerVisitor(lines, context_radius)
    visitor.visit(tree)

    all_sites = visitor.sites
    pure_sites = [site for site in all_sites if site["pure_login_dialog_ui"]]
    login_related = [
        site
        for site in all_sites
        if site["scope"].startswith("_spina_v32_prompt_login")
        or "login" in site["scope"].lower()
        or "account" in "\n".join(item["text"] for item in site["context"]).lower()
    ]

    group_counts: dict[str, int] = {}
    for site in pure_sites:
        group_counts[site["group"]] = group_counts.get(site["group"], 0) + 1

    excluded_counts: dict[str, int] = {}
    for site in login_related:
        if site["pure_login_dialog_ui"]:
            continue
        excluded_counts[site["group"]] = excluded_counts.get(site["group"], 0) + 1

    return {
        "file": str(app_path),
        "line_count": len(lines),
        "context_radius": context_radius,
        "pass_only_exception_count": len(all_sites),
        "login_related_pass_only_count": len(login_related),
        "pure_login_dialog_ui_review_count": len(pure_sites),
        "selected_cleanup_candidate_count": 0,
        "group_counts": dict(sorted(group_counts.items())),
        "excluded_login_group_counts": dict(sorted(excluded_counts.items())),
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "cleanup_approved": False,
            "protected_words_used": PROTECTED_WORDS,
            "excluded_sensitive_words": SENSITIVE_LOGIN_WORDS,
            "note": "This report narrows to pure login dialog UI only. It does not approve cleanup.",
        },
        "pure_login_dialog_ui_sites": pure_sites,
        "recommendations": [
            "Do not apply cleanup from this report alone.",
            "Leave password/auth/role/account database/header-switch handlers as review-only.",
            "A future cleanup tool, if created, should target only exact reviewed pure dialog UI handlers.",
            "Smoke-test staff login, account switching, password-change-required flow, Cancel, and Return-key login after any future login UI cleanup.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", default=APP_FILE, help="Path to the SPINA app source file")
    parser.add_argument("--json", dest="json_path", default=None, help="Optional JSON output path")
    parser.add_argument("--context-radius", type=int, default=8, help="Lines of context before/after each handler")
    args = parser.parse_args()

    app_path = Path(args.app)
    report = build_report(app_path, args.context_radius)
    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
