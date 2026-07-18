#!/usr/bin/env python3
"""Safely add log-once calls to selected silent UI/startup exception handlers.

This tool is conservative and dry-run by default. It scans the large SPINA source
for small ``except Exception:`` handlers in UI/startup/loading context, skips any
protected loan/report/math areas, and can insert a lightweight call to
``_log_suppressed_once`` before the existing fallback behavior.

It does not change behavior except for logging, and only edits the source when
``--apply`` is provided.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

# Business/report/storage contexts must not be part of the first logging batch.
# The uploaded dry-run plan showed that broad words like "path", "cache",
# "picture", and "load" can select PostgreSQL storage, report/PDF, and notes
# helpers. Keep this list intentionally broad; it is safer to skip too much and
# add a narrower tool later than to touch loan/report behavior accidentally.
PROTECTED_TERMS = (
    "balance",
    "7x7",
    "principal",
    "interest",
    "payment allocation",
    "payment logic",
    "payment",
    "collector route",
    "collector",
    "daily collection ledger",
    "ledger",
    "client statement",
    "statement pdf",
    "statement",
    "report math",
    "report",
    "reports",
    "pdf",
    "client_pdf",
    "ledger total",
    "advance pass",
    "advance",
    "pass",
    "note",
    "notes",
    "postgresql",
    "_spina_pg",
    "pg_",
    "storage",
    "store_file",
    "file_to_db",
    "restore_client_picture",
    "client_picture",
    "reportlab",
    "canvas",
    "transaction",
    "transactions",
    "loan",
)

# Keep focus terms strictly UI/startup chrome. Avoid broad words such as
# "load", "path", "cache", "picture", "image", and "font" because they matched
# storage/report/notes helpers in the first uploaded dry run.
FOCUS_TERMS = (
    "startup",
    "login",
    "refresh_",
    "reload_",
    "build_",
    "_build",
    "tab",
    "ui",
    "widget",
    "button",
    "dialog",
    "frame",
    "window",
    "root",
    "after(",
    "theme",
)

# Function/name denylist for contexts that may not contain obvious protected words
# in the small radius but still should not be touched by this general UI tool.
PROTECTED_NAME_TERMS = (
    "spina_pg",
    "pg_",
    "storage",
    "store_file",
    "restore_client_picture",
    "delete_client_picture",
    "open_path",
    "report",
    "pdf",
    "note",
    "collector",
    "ledger",
    "statement",
    "transaction",
    "client_uid",
    "loan",
    "advance",
    "pass",
    "balance",
    "principal",
    "interest",
    "json",  # settings/json storage can affect persistence; review separately.
    "writable_dir",
    "reports_root",
    "logger",  # do not instrument the logging fallback itself.
)

SILENT_FALLBACK_PATTERNS = (
    re.compile(r"^\s*pass\s*(?:#.*)?$"),
    re.compile(r"^\s*continue\s*(?:#.*)?$"),
    re.compile(r"^\s*return\s*(?:None|False|True|0|0\.0|''|\"\"|\[\]|\{\}|str\(|date\.today\(\)|datetime\.now\(\)|os\.getcwd\(\))"),
)

EXCEPT_RE = re.compile(r"^(?P<indent>\s*)except\s+Exception\s*:\s*(?:#.*)?$")
DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)")


def _lower(text: str) -> str:
    return str(text or "").lower()


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = _lower(text)
    return any(term in lowered for term in terms)


def _line_indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _context(lines: list[str], line_no: int, radius: int = 10) -> str:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def _function_map(lines: list[str]) -> dict[int, tuple[str, str]]:
    current_class = ""
    current_function = ""
    out: dict[int, tuple[str, str]] = {}
    for index, line in enumerate(lines, start=1):
        class_match = CLASS_RE.match(line)
        if class_match and not line.startswith("    "):
            current_class = class_match.group(1)
            current_function = ""
        def_match = DEF_RE.match(line)
        if def_match:
            current_function = def_match.group(1)
        out[index] = (current_class, current_function)
    return out


def _body_after_except(lines: list[str], except_index: int, except_indent: int, max_body_lines: int = 8) -> list[str]:
    body: list[str] = []
    for line in lines[except_index: min(len(lines), except_index + 1 + max_body_lines)]:
        if not line.strip():
            body.append(line)
            continue
        indent = _line_indent_width(line)
        if indent <= except_indent:
            break
        body.append(line)
    return body


def _is_silent_fallback_body(body: list[str]) -> bool:
    body_text = "\n".join(body)
    lowered = _lower(body_text)
    if any(term in lowered for term in ("_log_exc", "_log_suppressed_once", "raise ", "traceback", "messagebox")):
        return False
    meaningful = [line for line in body if line.strip() and not line.lstrip().startswith("#")]
    if not meaningful:
        return False
    if len(meaningful) > 3:
        return False
    return any(pattern.match(line) for line in meaningful for pattern in SILENT_FALLBACK_PATTERNS)


def _skip_reason(context: str, cls: str, fn: str, body: list[str]) -> str:
    owner = f"{cls}.{fn}" if cls else fn
    joined = "\n".join([context, owner, "\n".join(body)])
    if _has_any(joined, PROTECTED_TERMS):
        return "protected_context"
    if _has_any(owner, PROTECTED_NAME_TERMS):
        return "protected_name"
    if not _has_any(joined, FOCUS_TERMS):
        return "not_ui_startup_chrome"
    return ""


def find_candidates(lines: list[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    funcs = _function_map(lines)
    candidates: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    for index, line in enumerate(lines, start=1):
        match = EXCEPT_RE.match(line)
        if not match:
            continue
        except_indent = len(match.group("indent"))
        body = _body_after_except(lines, index, except_indent)
        context = _context(lines, index)
        if not _is_silent_fallback_body(body):
            continue
        cls, fn = funcs.get(index, ("", ""))
        reason = _skip_reason(context, cls, fn, body)
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        candidates.append(
            {
                "line": index,
                "class": cls,
                "function": fn,
                "except_text": line.rstrip(),
                "body_preview": "\n".join(item.rstrip() for item in body[:4]),
            }
        )
    return candidates, skipped


def _insert_logging(lines: list[str], selected: list[dict[str, Any]]) -> list[str]:
    selected_by_line = {int(item["line"]): item for item in selected}
    output: list[str] = []
    for index, line in enumerate(lines, start=1):
        item = selected_by_line.get(index)
        if not item:
            output.append(line)
            continue
        match = EXCEPT_RE.match(line)
        if not match:
            output.append(line)
            continue
        indent = match.group("indent")
        body_indent = indent + "    "
        context_name = f"silent_ui_{index}_{item.get('function') or 'module'}"
        message = f"suppressed UI/startup exception at line {index}"
        output.append(f"{indent}except Exception as __spina_exc:")
        output.append(f"{body_indent}__spina_logger = globals().get('_log_suppressed_once')")
        output.append(f"{body_indent}if callable(__spina_logger):")
        output.append(f"{body_indent}    __spina_logger({context_name!r}, {message!r}, __spina_exc)")
    return output


def run(path: Path, *, apply: bool, limit: int, json_path: str | None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    candidates, skipped = find_candidates(lines)
    selected = candidates[: max(0, int(limit))]
    report = {
        "file": str(path),
        "line_count": len(lines),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "apply": bool(apply),
        "selected": selected,
        "skipped_summary": dict(sorted(skipped.items())),
        "recommendations": [
            "Dry-run first and review selected lines.",
            "This tightened version skips PostgreSQL storage, files, reports/PDFs, notes, collectors, transactions, and loan/payment contexts.",
            "Use a small limit first, then compile and smoke-test SPINA.",
            "Do not use this for balances, 7x7, interest, notes, collector route, statements, reports, PDFs, or storage helpers.",
        ],
    }
    if json_path:
        Path(json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if apply and selected:
        backup = path.with_suffix(path.suffix + ".bak_silent_ui_logging")
        shutil.copy2(path, backup)
        new_lines = _insert_logging(lines, selected)
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        report["backup"] = str(backup)
    return report


def print_report(report: dict[str, Any]) -> None:
    print("[SPINA] Silent UI logging injector")
    print(f"[SPINA] File: {report['file']}")
    print(f"[SPINA] Candidates found: {report['candidate_count']}")
    print(f"[SPINA] Selected this run: {report['selected_count']}")
    if report.get("skipped_summary"):
        print(f"[SPINA] Skipped summary: {report['skipped_summary']}")
    for item in report["selected"][:50]:
        owner = ((item.get("class") or "") + "." if item.get("class") else "") + (item.get("function") or "<module>")
        print(f"  L{item['line']}: {owner} | {item['except_text']}")
    if report.get("apply"):
        if report.get("selected_count"):
            print(f"[SPINA] Applied. Backup: {report.get('backup')}")
        else:
            print("[SPINA] Nothing selected; no file changes made.")
    else:
        print("[SPINA] Dry run only. To apply selected lines, add --apply.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add log-once calls to safe silent UI/startup exception handlers.")
    parser.add_argument("source", nargs="?", default=DEFAULT_APP_FILE, help="SPINA app source file")
    parser.add_argument("--limit", type=int, default=25, help="Maximum handlers to change per apply run")
    parser.add_argument("--apply", action="store_true", help="Edit the source file; default is dry run")
    parser.add_argument("--json", dest="json_path", help="Optional JSON report path")
    args = parser.parse_args()
    path = Path(args.source)
    if not path.exists():
        raise SystemExit(f"Source file not found: {path}")
    report = run(path, apply=args.apply, limit=args.limit, json_path=args.json_path)
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
