#!/usr/bin/env python3
"""Remove the neutral AppClass.__init__ patch/restore pair after review.

The patch-chain audit identified exactly one non-protected repeated patch target:
AppClass.__init__. It assigns a temporary patched_init and then immediately restores
orig_App_init. This tool is intentionally narrow and dry-run by default.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

START_MARKER = "AppClass.__init__ = patched_init"
END_MARKER = "AppClass.__init__ = orig_App_init"
DEF_RE = re.compile(r"^(?P<indent>\s*)def\s+patched_init\s*\(")

PROTECTED_TERMS = (
    "balance",
    "7x7",
    "principal",
    "interest",
    "payment",
    "collector",
    "ledger",
    "statement",
    "report",
    "pdf",
    "note",
    "renew",
    "cash",
    "transaction",
    "loan",
    "database",
    "postgres",
)


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _find_neutral_block(lines: list[str]) -> dict[str, Any]:
    patched_lines = [i for i, line in enumerate(lines, start=1) if START_MARKER in line]
    restore_lines = [i for i, line in enumerate(lines, start=1) if END_MARKER in line]
    if len(patched_lines) != 1 or len(restore_lines) != 1:
        return {
            "safe": False,
            "reason": "expected exactly one patch assignment and one restore assignment",
            "patched_lines": patched_lines,
            "restore_lines": restore_lines,
        }

    patch_line = patched_lines[0]
    restore_line = restore_lines[0]
    if restore_line <= patch_line or restore_line - patch_line > 20:
        return {
            "safe": False,
            "reason": "patch/restore assignments are not an immediate neutral pair",
            "patched_lines": patched_lines,
            "restore_lines": restore_lines,
        }

    # Include the patched_init function immediately above the temporary assignment.
    def_line = None
    for i in range(patch_line - 1, max(0, patch_line - 30), -1):
        if DEF_RE.match(lines[i - 1]):
            def_line = i
            break
    if not def_line:
        return {
            "safe": False,
            "reason": "could not find nearby def patched_init before temporary assignment",
            "patched_lines": patched_lines,
            "restore_lines": restore_lines,
        }

    # Start at a nearby orig_App_init assignment if present; otherwise start at def patched_init.
    start_line = def_line
    for i in range(def_line - 1, max(0, def_line - 12), -1):
        text = lines[i - 1]
        if "orig_App_init" in text and "AppClass.__init__" in text:
            start_line = i
            break
        if text.strip() and not text.lstrip().startswith("#") and "AppClass" not in text:
            break

    end_line = restore_line
    block = lines[start_line - 1 : end_line]
    block_text = "\n".join(block).lower()
    protected_hits = sorted({term for term in PROTECTED_TERMS if term in block_text})
    if protected_hits:
        return {
            "safe": False,
            "reason": f"protected terms found in candidate block: {', '.join(protected_hits)}",
            "start_line": start_line,
            "end_line": end_line,
            "patched_lines": patched_lines,
            "restore_lines": restore_lines,
        }

    if not any("orig_App_init" in line and "AppClass.__init__" in line for line in block):
        return {
            "safe": False,
            "reason": "candidate block does not contain orig_App_init/AppClass.__init__ capture or restore",
            "start_line": start_line,
            "end_line": end_line,
            "patched_lines": patched_lines,
            "restore_lines": restore_lines,
        }

    return {
        "safe": True,
        "reason": "neutral AppClass.__init__ patch/restore pair found",
        "start_line": start_line,
        "end_line": end_line,
        "line_count": end_line - start_line + 1,
        "patched_lines": patched_lines,
        "restore_lines": restore_lines,
        "preview": [f"{start_line + idx}: {line}" for idx, line in enumerate(block[:30])],
    }


def run(path: Path, *, apply: bool, json_path: str | None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    candidate = _find_neutral_block(lines)
    report: dict[str, Any] = {
        "file": str(path),
        "line_count": len(lines),
        "apply": bool(apply),
        "candidate": candidate,
        "recommendations": [
            "Dry run first and review the exact candidate block.",
            "This tool only targets the non-protected AppClass.__init__ patch/restore pair from the patch-chain report.",
            "Do not use this for App.__init__, client refresh, collectors, dashboards, reports, PDFs, notes, payments, balances, 7x7, renewals, or cash-control patch chains.",
            "After apply, run py_compile and smoke-test SPINA before committing only the app file.",
        ],
    }
    if json_path:
        Path(json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")

    if apply:
        if not candidate.get("safe"):
            raise SystemExit(f"Unsafe candidate: {candidate.get('reason')}")
        start = int(candidate["start_line"])
        end = int(candidate["end_line"])
        backup = path.with_suffix(path.suffix + ".bak_neutral_appclass_init")
        shutil.copy2(path, backup)
        new_lines = lines[: start - 1] + lines[end:]
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        report["backup"] = str(backup)
        report["removed_lines"] = end - start + 1

    return report


def print_report(report: dict[str, Any]) -> None:
    candidate = report["candidate"]
    print("[SPINA] Neutral AppClass.__init__ patch cleanup")
    print(f"[SPINA] File: {report['file']}")
    print(f"[SPINA] Safe candidate: {candidate.get('safe')}")
    print(f"[SPINA] Reason: {candidate.get('reason')}")
    if candidate.get("safe"):
        print(f"[SPINA] Candidate lines: {candidate.get('start_line')}-{candidate.get('end_line')} ({candidate.get('line_count')} lines)")
        for line in candidate.get("preview", [])[:20]:
            print("  " + line)
    if report.get("apply"):
        print(f"[SPINA] Applied. Backup: {report.get('backup')}")
    else:
        print("[SPINA] Dry run only. To remove the candidate block, rerun with --apply.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove the neutral AppClass.__init__ patch/restore pair after review.")
    parser.add_argument("source", nargs="?", default=DEFAULT_APP_FILE, help="SPINA app source file")
    parser.add_argument("--apply", action="store_true", help="Edit the source file; default is dry run")
    parser.add_argument("--json", dest="json_path", help="Optional JSON report path")
    args = parser.parse_args()
    report = run(Path(args.source), apply=args.apply, json_path=args.json_path)
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
