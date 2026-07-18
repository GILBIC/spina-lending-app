#!/usr/bin/env python3
"""Dry-run/apply cleanup for exact pure login dialog UI pass-only handlers.

This tool targets only a tiny reviewed subgroup from
plan_pure_login_dialog_ui_pass_only.py. By default it is dry-run only.
It refuses to write unless every exact target is either still safely patchable
or already patched by this same tool.
"""
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


@dataclass(frozen=True)
class Target:
    key: str
    expected_line: int
    scope: str
    guard_text: str
    log_context: str
    note: str


TARGETS: tuple[Target, ...] = (
    Target(
        key="login_dialog_transient",
        expected_line=48175,
        scope="_spina_v32_prompt_login",
        guard_text="dlg.transient(self.root)",
        log_context="pure_login_dialog_ui.transient",
        note="Login dialog transient window relation only.",
    ),
    Target(
        key="login_dialog_account_trace",
        expected_line=48332,
        scope="_spina_v32_prompt_login",
        guard_text='account_var.trace_add("write", _refresh_account_info)',
        log_context="pure_login_dialog_ui.account_trace",
        note="Login dialog account info trace callback only.",
    ),
    Target(
        key="login_dialog_return_bind",
        expected_line=48342,
        scope="_spina_v32_prompt_login",
        guard_text='account_cb.bind("<Return>", _enter)',
        log_context="pure_login_dialog_ui.return_bind",
        note="Login dialog Return-key binding only.",
    ),
    Target(
        key="login_dialog_grab_set",
        expected_line=48347,
        scope="_spina_v32_prompt_login",
        guard_text="dlg.grab_set()",
        log_context="pure_login_dialog_ui.grab_set",
        note="Login dialog modal grab only.",
    ),
    Target(
        key="login_dialog_position",
        expected_line=48365,
        scope="_spina_v32_prompt_login",
        guard_text='dlg.geometry(f"{w}x{h}+{x}+{y}")',
        log_context="pure_login_dialog_ui.position",
        note="Login dialog geometry/positioning only.",
    ),
)

# Extra fail-closed guards. These are intentionally narrow so the reviewed
# Return-key binding can still be selected even though it mentions pw_entry.
EXCLUDED_TARGET_GUARDS = (
    "_verify_login",
    "verify_login(",
    "_must_change_password",
    "_force_change_password_dialog",
    "_save_users_db",
    "_load_users_db",
    "switch_account",
    "_refresh_user_header",
    "_build_header",
    "access_profile",
    "permission",
    "users[",
)


class ParentSetter(ast.NodeVisitor):
    def visit(self, node: ast.AST) -> Any:  # noqa: ANN401
        for child in ast.iter_child_nodes(node):
            setattr(child, "parent", node)
        return super().visit(node)


def node_name(node: ast.AST | None) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    return None


def scope_for(node: ast.AST) -> str:
    names: list[str] = []
    cur: ast.AST | None = getattr(node, "parent", None)
    while cur is not None:
        name = node_name(cur)
        if name:
            names.append(name)
        cur = getattr(cur, "parent", None)
    names.reverse()
    return ".".join(names) if names else "<module>"


def is_exception_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return False
    if isinstance(handler.type, ast.Name):
        return handler.type.id == "Exception"
    if isinstance(handler.type, ast.Attribute):
        return handler.type.attr == "Exception"
    return False


def is_pass_only_handler(handler: ast.ExceptHandler) -> bool:
    return (
        is_exception_handler(handler)
        and len(handler.body) == 1
        and isinstance(handler.body[0], ast.Pass)
    )


def get_context(lines: list[str], start_line: int, radius: int = 8) -> str:
    lo = max(1, start_line - radius)
    hi = min(len(lines), start_line + radius)
    return "".join(lines[lo - 1 : hi])


def find_handlers(source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source)
    ParentSetter().visit(tree)
    lines = source.splitlines(keepends=True)
    handlers: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and is_pass_only_handler(node):
            pass_node = node.body[0]
            handlers.append(
                {
                    "line": int(node.lineno),
                    "end_line": int(pass_node.lineno),
                    "scope": scope_for(node),
                    "context": get_context(lines, int(node.lineno), 8),
                    "handler": node,
                }
            )
    return handlers


def replacement_lines(lines: list[str], handler: ast.ExceptHandler, target: Target) -> list[str]:
    except_line = lines[handler.lineno - 1]
    pass_line = lines[handler.body[0].lineno - 1]
    except_indent = except_line[: len(except_line) - len(except_line.lstrip())]
    body_indent = pass_line[: len(pass_line) - len(pass_line.lstrip())]
    return [
        f"{except_indent}except Exception as __spina_exc:\n",
        f"{body_indent}_log_suppressed_once('{target.log_context}', 'suppressed pure login dialog UI exception: {target.key}', __spina_exc)\n",
        f"{body_indent}pass\n",
    ]


def build_report(app_path: Path, apply: bool) -> dict[str, Any]:
    source = app_path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    handlers = find_handlers(source)

    safe_candidates: list[dict[str, Any]] = []
    already_clean: list[dict[str, Any]] = []
    unsafe: list[dict[str, Any]] = []

    for target in TARGETS:
        log_marker = f"_log_suppressed_once('{target.log_context}'"
        if log_marker in source:
            already_clean.append(
                {
                    "key": target.key,
                    "expected_line": target.expected_line,
                    "status": "already_clean",
                    "note": target.note,
                }
            )
            continue

        matches = []
        for item in handlers:
            context = str(item["context"])
            if item["scope"] != target.scope:
                continue
            if abs(int(item["line"]) - target.expected_line) > 3:
                continue
            if target.guard_text not in context:
                continue
            bad_hits = [word for word in EXCLUDED_TARGET_GUARDS if word in context]
            if bad_hits:
                item = dict(item)
                item["excluded_guard_hits"] = bad_hits
                matches.append(item)
                continue
            matches.append(item)

        valid_matches = [m for m in matches if not m.get("excluded_guard_hits")]
        if len(valid_matches) == 1:
            m = valid_matches[0]
            handler = m["handler"]
            safe_candidates.append(
                {
                    "key": target.key,
                    "line": m["line"],
                    "end_line": m["end_line"],
                    "scope": m["scope"],
                    "guard_text": target.guard_text,
                    "status": "safe_candidate",
                    "note": target.note,
                    "original": [
                        {"line": i + 1, "text": lines[i].rstrip("\n")}
                        for i in range(handler.lineno - 1, handler.body[0].lineno)
                    ],
                    "replacement_preview": [s.rstrip("\n") for s in replacement_lines(lines, handler, target)],
                }
            )
        else:
            unsafe.append(
                {
                    "key": target.key,
                    "expected_line": target.expected_line,
                    "guard_text": target.guard_text,
                    "match_count": len(valid_matches),
                    "raw_match_count": len(matches),
                    "excluded_guard_hits": sorted(
                        {
                            hit
                            for m in matches
                            for hit in m.get("excluded_guard_hits", [])
                        }
                    ),
                    "status": "unsafe_or_missing",
                    "note": target.note,
                }
            )

    safe = (not unsafe) and (len(safe_candidates) + len(already_clean) == len(TARGETS))
    patched = False
    app_source_modified = False

    if apply and safe and safe_candidates:
        # Rebuild the candidate list with AST handler objects for patching.
        patch_items: list[tuple[int, int, Target, ast.ExceptHandler]] = []
        for target in TARGETS:
            if any(item["key"] == target.key for item in already_clean):
                continue
            for item in handlers:
                context = str(item["context"])
                if (
                    item["scope"] == target.scope
                    and abs(int(item["line"]) - target.expected_line) <= 3
                    and target.guard_text in context
                    and not any(word in context for word in EXCLUDED_TARGET_GUARDS)
                ):
                    handler = item["handler"]
                    patch_items.append((handler.lineno, handler.body[0].lineno, target, handler))
                    break

        for start, end, target, handler in sorted(patch_items, reverse=True):
            lines[start - 1 : end] = replacement_lines(lines, handler, target)
        app_path.write_text("".join(lines), encoding="utf-8")
        patched = True
        app_source_modified = True

    return {
        "file": str(app_path),
        "apply": apply,
        "target_count": len(TARGETS),
        "safe_candidate_count": len(safe_candidates),
        "already_clean_count": len(already_clean),
        "unsafe_count": len(unsafe),
        "safe": safe,
        "patched": patched,
        "app_source_modified": app_source_modified,
        "selected_scope": "5 exact pure login dialog UI pass-only handlers only; excludes auth/password/role/account database/header/focus handlers",
        "excluded_focus_handler": "line 48370 pw_entry.focus_set() is intentionally not targeted",
        "safe_candidates": safe_candidates,
        "already_clean": already_clean,
        "unsafe": unsafe,
        "recommendations": [
            "Review dry-run JSON before applying.",
            "Apply only if safe is true and unsafe_count is 0.",
            "After apply, rerun this tool, the pure login dialog planner, and the pass-only exception audit.",
            "Smoke-test staff login, account switching, password-change-required flow, Cancel, and Return-key login.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", default=APP_FILE, help="Path to SPINA app source")
    parser.add_argument("--json", dest="json_path", help="Write report JSON to this path")
    parser.add_argument("--apply", action="store_true", help="Apply the cleanup if every exact target is safe")
    args = parser.parse_args()

    report = build_report(Path(args.app), bool(args.apply))
    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    if args.apply and not report["safe"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
