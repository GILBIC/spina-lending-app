#!/usr/bin/env python3
"""Plan a narrow cleanup for modern UI chrome pass-only exception handlers.

This tool is intentionally read-only. It finds pass-only exception handlers in
modern sidebar/header/theme UI chrome code and produces a JSON plan. It does not
modify the SPINA app.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

# Keep this narrow. These scopes are UI chrome only, not payment/report/database logic.
MODERN_UI_SCOPES = {
    "App.set_theme",
    "App._select_side_tab",
    "App._rebuild_side_nav",
    "App._refresh_side_nav_selection",
    "App._refresh_modern_shell_theme",
    "App._tk_button_hover",
    "App._set_mode",
    "App._refresh_mode_toggle",
    "App._refresh_header_theme",
}

# A second guard: keep the selected plan inside the modern UI chrome block seen
# in the pass-only exception audit. This avoids runtime role/access patches and
# other distant app logic even if names look similar.
MODERN_UI_LINE_MIN = 14900
MODERN_UI_LINE_MAX = 16350

PROTECTED_WORDS = {
    "payment",
    "balance",
    "7x7",
    "7×7",
    "renew",
    "collector",
    "route",
    "ledger",
    "report",
    "pdf",
    "backup",
    "restore",
    "postgres",
    "pg_",
    "database",
    "migration",
    "cash control",
    "interest",
    "principal",
    "transaction",
    "payroll",
    "receipt",
    "statement",
    "role_access",
    "apply_role_access",
}


def _is_pass_only(handler: ast.ExceptHandler) -> bool:
    return bool(handler.body) and all(isinstance(stmt, ast.Pass) for stmt in handler.body)


def _handler_name(handler: ast.ExceptHandler) -> str:
    t = handler.type
    if t is None:
        return "bare"
    if isinstance(t, ast.Name):
        return t.id
    if isinstance(t, ast.Attribute):
        parts = []
        cur: Any = t
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return type(t).__name__


def _context(lines: list[str], line: int, radius: int) -> list[dict[str, Any]]:
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return [{"line": i, "text": lines[i - 1].rstrip("\n")} for i in range(start, end + 1)]


def _protected_context(ctx: list[dict[str, Any]]) -> bool:
    text = "\n".join(str(row.get("text", "")) for row in ctx).lower()
    return any(word in text for word in PROTECTED_WORDS)


class PassOnlyVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], radius: int) -> None:
        self.lines = lines
        self.radius = radius
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self.sites: list[dict[str, Any]] = []

    def _scope(self) -> str:
        if self.class_stack and self.function_stack:
            return f"{self.class_stack[-1]}.{self.function_stack[-1]}"
        if self.function_stack:
            return self.function_stack[-1]
        return "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:  # noqa: N802
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: N802
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:  # noqa: N802
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_Try(self, node: ast.Try) -> Any:  # noqa: N802
        scope = self._scope()
        for handler in node.handlers:
            if not _is_pass_only(handler):
                continue
            line = int(getattr(handler, "lineno", 0) or 0)
            end_line = int(getattr(handler, "end_lineno", line) or line)
            ctx = _context(self.lines, line, self.radius)
            protected = _protected_context(ctx)
            in_scope = scope in MODERN_UI_SCOPES
            in_line_window = MODERN_UI_LINE_MIN <= line <= MODERN_UI_LINE_MAX
            selected = bool(in_scope and in_line_window and not protected)
            self.sites.append(
                {
                    "line": line,
                    "end_line": end_line,
                    "scope": scope,
                    "handler": _handler_name(handler),
                    "protected_context": protected,
                    "modern_ui_scope": in_scope,
                    "modern_ui_line_window": in_line_window,
                    "selected_for_cleanup_plan": selected,
                    "recommended_action": (
                        "replace pass-only handler with logged UI-chrome suppressed exception"
                        if selected
                        else "review only / do not change from this plan"
                    ),
                    "context": ctx,
                }
            )
        self.generic_visit(node)


def build_plan(app_path: Path, radius: int) -> dict[str, Any]:
    text = app_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(app_path))
    visitor = PassOnlyVisitor(lines, radius)
    visitor.visit(tree)

    selected = [s for s in visitor.sites if s["selected_for_cleanup_plan"]]
    modern_ui_review = [
        s for s in visitor.sites if s["modern_ui_scope"] and not s["selected_for_cleanup_plan"]
    ]

    return {
        "file": str(app_path),
        "line_count": len(lines),
        "context_radius": radius,
        "pass_only_exception_count": len(visitor.sites),
        "modern_ui_pass_only_count": len(selected) + len(modern_ui_review),
        "selected_cleanup_candidate_count": len(selected),
        "modern_ui_review_only_count": len(modern_ui_review),
        "selected_scopes": sorted({s["scope"] for s in selected}),
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "line_window": [MODERN_UI_LINE_MIN, MODERN_UI_LINE_MAX],
            "protected_words_excluded": sorted(PROTECTED_WORDS),
            "excluded_note": "runtime role/access patches and protected business logic are outside this narrow plan",
        },
        "selected_sites": selected,
        "review_only_modern_ui_sites": modern_ui_review[:40],
        "recommendations": [
            "Read-only plan only; no app source changes are made.",
            "Review selected_sites before creating any cleanup tool.",
            "Only modern sidebar/header/theme UI chrome handlers should be considered.",
            "Do not touch reports, PDFs, payments, balances, 7x7, renewals, collectors, backups, database migrations, cash-control, or report math.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", default=DEFAULT_APP)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--context", type=int, default=8)
    args = parser.parse_args()

    plan = build_plan(Path(args.app), args.context)
    output = json.dumps(plan, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
