#!/usr/bin/env python3
"""Read-only audit for silent UI/startup exception handlers in the SPINA source.

This tool does not modify the app. It finds broad/silent exception handlers and
prioritizes ones near UI refresh, startup, login, and tab-building code so they
can be reviewed before any logging or cleanup change is made.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

EXCEPT_RE = re.compile(r"^(?P<indent>[ \t]*)except(?:\s+[^:]+)?:\s*(?P<trailing>.*)$")
DEF_RE = re.compile(r"^(?P<indent>[ \t]*)def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
CLASS_RE = re.compile(r"^(?P<indent>[ \t]*)class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)")

FOCUS_TERMS = (
    "__init__",
    "startup",
    "login",
    "refresh",
    "dashboard",
    "client",
    "data bank",
    "databank",
    "collector",
    "route",
    "tab",
    "build",
    "populate",
    "load",
    "search",
)

PROTECTED_TERMS = (
    "balance",
    "7x7",
    "principal",
    "interest",
    "payment allocation",
    "advance",
    "pass",
    "note",
    "statement",
    "client_pdf",
    "ledger total",
    "collector route",
    "report math",
)

VISIBLE_ERROR_TERMS = (
    "_log_exc",
    "logging.",
    "logger.",
    "traceback",
    "print(",
    "messagebox.showerror",
    "messagebox.showwarning",
    "raise",
)

SILENT_ONLY_TOKENS = {"pass", "return", "continue", "break", "..."}


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _line_context(lines: list[str], line_no: int, radius: int = 3) -> str:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _body_range(lines: list[str], except_index: int) -> tuple[int, int]:
    """Return 0-based [start, end) body range for an except block."""
    except_indent = _indent_width(lines[except_index])
    start = except_index + 1
    end = start
    for idx in range(start, len(lines)):
        line = lines[idx]
        if not line.strip():
            end = idx + 1
            continue
        indent = _indent_width(line)
        if indent <= except_indent:
            break
        end = idx + 1
    return start, end


def _body_is_silent(body_lines: list[str], trailing: str) -> bool:
    combined = "\n".join([trailing.strip(), *[line.strip() for line in body_lines if line.strip()]]).lower()
    if any(term in combined for term in VISIBLE_ERROR_TERMS):
        return False
    meaningful: list[str] = []
    if trailing.strip():
        meaningful.append(trailing.strip())
    for line in body_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        meaningful.append(stripped)
    if not meaningful:
        return True
    if all(item in SILENT_ONLY_TOKENS or item.startswith("return ") for item in meaningful):
        return True
    return False


def _scan_def_context(lines: list[str]) -> list[dict[str, Any]]:
    """Build a simple per-line function/class context map."""
    stack: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    current_class = ""
    current_function = ""
    for line_no, line in enumerate(lines, start=1):
        indent = _indent_width(line)
        if line.strip():
            stack = [item for item in stack if item["indent"] < indent or item["line"] == line_no]
        class_match = CLASS_RE.match(line)
        if class_match:
            current_class = class_match.group("name")
            stack.append({"kind": "class", "name": current_class, "indent": indent, "line": line_no})
        def_match = DEF_RE.match(line)
        if def_match:
            current_function = def_match.group("name")
            stack.append({"kind": "def", "name": current_function, "indent": indent, "line": line_no})
        active_class = ""
        active_func = ""
        for item in stack:
            if item["kind"] == "class":
                active_class = item["name"]
            elif item["kind"] == "def":
                active_func = item["name"]
        contexts.append({"class": active_class, "function": active_func})
    return contexts


def audit(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    contexts = _scan_def_context(lines)
    hits: list[dict[str, Any]] = []

    for idx, line in enumerate(lines):
        match = EXCEPT_RE.match(line)
        if not match:
            continue
        body_start, body_end = _body_range(lines, idx)
        body_lines = lines[body_start:body_end]
        trailing = match.group("trailing")
        if not _body_is_silent(body_lines, trailing):
            continue
        line_no = idx + 1
        context_text = _line_context(lines, line_no, radius=5)
        ctx = contexts[idx] if idx < len(contexts) else {"class": "", "function": ""}
        combined_context = "\n".join([context_text, ctx.get("class", ""), ctx.get("function", "")])
        focus = _has_any(combined_context, FOCUS_TERMS)
        protected = _has_any(combined_context, PROTECTED_TERMS)
        hits.append(
            {
                "line": line_no,
                "class": ctx.get("class", ""),
                "function": ctx.get("function", ""),
                "except_text": line.strip(),
                "body_line_count": max(0, body_end - body_start),
                "focus_context": focus,
                "protected_context": protected,
                "context_preview": context_text,
            }
        )

    focus_hits = [hit for hit in hits if hit["focus_context"]]
    protected_hits = [hit for hit in hits if hit["protected_context"]]
    safe_review_hits = [hit for hit in focus_hits if not hit["protected_context"]]

    recommendations = [
        f"Silent exception handlers found: {len(hits)}.",
        f"UI/startup-focused silent handlers: {len(focus_hits)}.",
        f"Protected-context silent handlers: {len(protected_hits)}; do not edit these first.",
        f"Review non-protected UI/startup handlers first: {len(safe_review_hits)} candidates.",
        "This audit is read-only. Add logging in small PRs only after manual review.",
    ]

    return {
        "file": str(path),
        "line_count": len(lines),
        "silent_exception_count": len(hits),
        "focus_silent_exception_count": len(focus_hits),
        "protected_silent_exception_count": len(protected_hits),
        "safe_review_candidate_count": len(safe_review_hits),
        "hits": hits,
        "recommendations": recommendations,
    }


def print_summary(report: dict[str, Any]) -> None:
    print("SPINA silent UI/startup error audit")
    print(f"File: {report['file']}")
    print(f"Lines scanned: {report['line_count']}")
    print(f"Silent exception handlers: {report['silent_exception_count']}")
    print(f"UI/startup-focused silent handlers: {report['focus_silent_exception_count']}")
    print(f"Protected-context silent handlers: {report['protected_silent_exception_count']}")
    print(f"Non-protected UI/startup review candidates: {report['safe_review_candidate_count']}")
    print()
    shown = 0
    for hit in report["hits"]:
        if not hit.get("focus_context") or hit.get("protected_context"):
            continue
        owner = ".".join(part for part in (hit.get("class"), hit.get("function")) if part)
        print(f"L{hit['line']} REVIEW {owner}: {hit['except_text']}")
        shown += 1
        if shown >= 20:
            break
    if report["safe_review_candidate_count"] > shown:
        print(f"... {report['safe_review_candidate_count'] - shown} more non-protected UI/startup candidates")
    print()
    print("Recommendations:")
    for item in report["recommendations"]:
        print(f"  - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit silent UI/startup exception handlers in SPINA source.")
    parser.add_argument("source", nargs="?", default=DEFAULT_APP_FILE, help="SPINA app source file")
    parser.add_argument("--json", dest="json_path", help="Optional JSON output path")
    args = parser.parse_args()

    path = Path(args.source)
    if not path.exists():
        raise SystemExit(f"Source file not found: {path}")

    report = audit(path)
    print_summary(report)
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote JSON report: {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
