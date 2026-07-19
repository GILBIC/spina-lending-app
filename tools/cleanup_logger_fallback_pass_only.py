#!/usr/bin/env python3
"""Dry-run/apply cleanup for exactly two logger fallback pass-only handlers.

This tool is intentionally narrow. It only replaces the final last-resort
logger fallback `pass` statements with explicit `return` statements so the
behavior stays the same and no recursive logging is introduced.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")

TARGETS = [
    {
        "key": "log_exc_stderr_fallback",
        "scope": "_log_exc",
        "guard_text": 'print(f"[SPINA][ERROR] {context}: {exc}", file=sys.stderr)',
        "note": "Final stderr fallback inside _log_exc only; do not call logger again.",
    },
    {
        "key": "log_suppressed_once_stderr_fallback",
        "scope": "_log_suppressed_once",
        "guard_text": 'print(f"[SPINA][SUPPRESSED] {context}: {exc}", file=sys.stderr)',
        "note": "Final stderr fallback inside _log_suppressed_once only; do not call logger again.",
    },
]


def _line_text(lines: list[str], index_1based: int) -> str:
    if index_1based < 1 or index_1based > len(lines):
        return ""
    return lines[index_1based - 1].rstrip("\n\r")


def _find_top_level_function(lines: list[str], name: str) -> tuple[int, int] | None:
    start = None
    prefix = f"def {name}("
    for idx, line in enumerate(lines, start=1):
        if line.startswith(prefix):
            start = idx
            break
    if start is None:
        return None
    end = len(lines)
    for idx in range(start + 1, len(lines) + 1):
        line = _line_text(lines, idx)
        if idx > start and (line.startswith("def ") or line.startswith("class ")):
            end = idx - 1
            break
    return start, end


def _locate_target(lines: list[str], target: dict[str, str]) -> dict[str, Any]:
    scope_range = _find_top_level_function(lines, target["scope"])
    if scope_range is None:
        return {
            "key": target["key"],
            "scope": target["scope"],
            "status": "unsafe",
            "reason": "scope not found",
        }

    start, end = scope_range
    guard_line = None
    for idx in range(start, end + 1):
        if _line_text(lines, idx).strip() == target["guard_text"]:
            guard_line = idx
            break

    if guard_line is None:
        # Already-clean detection can still rely on the same guard; without it we fail closed.
        return {
            "key": target["key"],
            "scope": target["scope"],
            "status": "unsafe",
            "reason": "exact guard line not found",
        }

    except_line = guard_line + 1
    body_line = guard_line + 2
    except_text = _line_text(lines, except_line)
    body_text = _line_text(lines, body_line)

    if except_text != "        except Exception:":
        return {
            "key": target["key"],
            "scope": target["scope"],
            "guard_line": guard_line,
            "status": "unsafe",
            "reason": "unexpected except line after guard",
            "except_text": except_text,
        }

    common = {
        "key": target["key"],
        "scope": target["scope"],
        "guard_line": guard_line,
        "line": except_line,
        "end_line": body_line,
        "handler": "Exception",
        "guard_text": target["guard_text"],
        "note": target["note"],
        "recursive_logging_safe": True,
        "replacement_behavior": "return from logger fallback path; no logging call is added",
    }

    if body_text == "            return":
        return {**common, "status": "already_clean"}

    if body_text != "            pass":
        return {
            **common,
            "status": "unsafe",
            "reason": "expected pass body not found",
            "body_text": body_text,
        }

    return {
        **common,
        "status": "safe_candidate",
        "original": [
            {"line": except_line, "text": except_text},
            {"line": body_line, "text": body_text},
        ],
        "replacement_preview": [
            "        except Exception:",
            "            return",
        ],
    }


def build_report(app_file: Path, apply: bool) -> dict[str, Any]:
    text = app_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    located = [_locate_target(lines, target) for target in TARGETS]
    safe_candidates = [item for item in located if item.get("status") == "safe_candidate"]
    already_clean = [item for item in located if item.get("status") == "already_clean"]
    unsafe = [item for item in located if item.get("status") == "unsafe"]

    safe = not unsafe
    patched = False
    app_source_modified = False

    if apply and safe and safe_candidates:
        # Replace from bottom to top so line numbers remain valid.
        for item in sorted(safe_candidates, key=lambda x: int(x["end_line"]), reverse=True):
            body_index = int(item["end_line"]) - 1
            if lines[body_index].rstrip("\n\r") != "            pass":
                raise RuntimeError(f"Target changed while patching: {item['key']}")
            newline = "\n" if lines[body_index].endswith("\n") else ""
            lines[body_index] = "            return" + newline
        app_file.write_text("".join(lines), encoding="utf-8")
        patched = True
        app_source_modified = True

    return {
        "file": str(app_file),
        "apply": apply,
        "target_count": len(TARGETS),
        "safe_candidate_count": len(safe_candidates),
        "already_clean_count": len(already_clean),
        "unsafe_count": len(unsafe),
        "safe": safe,
        "patched": patched,
        "app_source_modified": app_source_modified,
        "selected_scope": "2 exact logger fallback pass-only handlers only; no recursive logging; no business logic",
        "safe_candidates": safe_candidates,
        "already_clean": already_clean,
        "unsafe": unsafe,
        "recommendations": [
            "Review dry-run JSON before applying.",
            "Apply only if safe is true and unsafe_count is 0.",
            "After apply, rerun this tool, the logger fallback planner, and the pass-only exception audit.",
            "Smoke-test app startup and confirm logging still writes to data/spina_app.log during normal suppressed exceptions.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean exact logger fallback pass-only handlers.")
    parser.add_argument("--app", default=str(APP_FILE), help="SPINA app source file")
    parser.add_argument("--apply", action="store_true", help="Modify the app source file")
    parser.add_argument("--json", default="logger-fallback-cleanup-report.json", help="JSON report path")
    args = parser.parse_args()

    app_file = Path(args.app)
    report = build_report(app_file, args.apply)
    Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["safe"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
