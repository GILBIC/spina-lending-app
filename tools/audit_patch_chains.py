#!/usr/bin/env python3
"""Read-only audit for SPINA monkey-patch assignment chains.

The main SPINA file contains several late ``App.method = wrapper`` and
``setattr(App, 'method', wrapper)`` layers. This tool does not edit the app.
It reports the chain order and the final effective assignment for repeated
patch targets so a human can review one family at a time before any cleanup.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

OWNERS = ("App", "LoanDB", "RenewDialog", "AppClass")

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
    "advance",
    "pass",
    "note",
    "notes",
    "transaction",
    "transactions",
    "loan",
    "renew",
    "cash control",
    "cashctl",
)

DIRECT_ASSIGN_RE = re.compile(
    r"^\s*(?P<owner>App|LoanDB|RenewDialog|AppClass)\.(?P<attr>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<rhs>[A-Za-z_][A-Za-z0-9_]*)\s*(?:#.*)?$"
)
SETATTR_RE = re.compile(
    r"^\s*setattr\(\s*(?P<owner>App|LoanDB|RenewDialog|AppClass)\s*,\s*['\"](?P<attr>[A-Za-z_][A-Za-z0-9_]*)['\"]\s*,\s*(?P<rhs>[A-Za-z_][A-Za-z0-9_]*)\s*\)"
)
DEF_RE = re.compile(r"^\s*def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _lower(text: str) -> str:
    return str(text or "").lower()


def _context(lines: list[str], line_no: int, radius: int = 8) -> str:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def _has_protected(text: str) -> bool:
    lowered = _lower(text)
    return any(term in lowered for term in PROTECTED_TERMS)


def _classify_rhs(rhs: str) -> str:
    lowered = _lower(rhs)
    if lowered.startswith("orig") or "orig_" in lowered or "original" in lowered:
        return "restore_original"
    if "perf" in lowered:
        return "performance_wrapper"
    if re.search(r"_v\d+", lowered):
        return "versioned_patch"
    if "fixed" in lowered or "guard" in lowered:
        return "fix_or_guard_patch"
    if "with_" in lowered:
        return "feature_wrapper"
    return "patch"


def _def_lines(lines: list[str]) -> dict[str, list[int]]:
    defs: dict[str, list[int]] = {}
    for index, line in enumerate(lines, start=1):
        match = DEF_RE.match(line)
        if match:
            defs.setdefault(match.group("name"), []).append(index)
    return defs


def _find_patch_assignments(lines: list[str]) -> list[dict[str, Any]]:
    defs = _def_lines(lines)
    assignments: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        match = DIRECT_ASSIGN_RE.match(line) or SETATTR_RE.match(line)
        if not match:
            continue
        owner = match.group("owner")
        attr = match.group("attr")
        rhs = match.group("rhs")
        target = f"{owner}.{attr}"
        context = _context(lines, index)
        protected = _has_protected("\n".join([target, rhs, line, context]))
        assignments.append(
            {
                "target": target,
                "line": index,
                "owner": owner,
                "attribute": attr,
                "rhs": rhs,
                "rhs_kind": _classify_rhs(rhs),
                "rhs_def_lines": defs.get(rhs, []),
                "protected_context": protected,
                "text": line.strip(),
            }
        )
    return assignments


def run(path: Path, json_path: str | None = None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    assignments = _find_patch_assignments(lines)
    by_target: dict[str, list[dict[str, Any]]] = {}
    for item in assignments:
        by_target.setdefault(str(item["target"]), []).append(item)

    repeated: dict[str, dict[str, Any]] = {}
    non_protected: dict[str, dict[str, Any]] = {}
    for target, chain in sorted(by_target.items()):
        if len(chain) < 2:
            continue
        final = chain[-1]
        protected = any(bool(item.get("protected_context")) for item in chain)
        data = {
            "assignment_count": len(chain),
            "protected_chain": protected,
            "final_assignment": final,
            "chain": chain,
        }
        repeated[target] = data
        if not protected:
            non_protected[target] = data

    report: dict[str, Any] = {
        "file": str(path),
        "line_count": len(lines),
        "patch_assignment_count": len(assignments),
        "repeated_patch_target_count": len(repeated),
        "non_protected_repeated_patch_target_count": len(non_protected),
        "repeated_patch_targets": repeated,
        "non_protected_repeated_patch_targets": non_protected,
        "recommendations": [
            "Read-only audit only; no app source changes are made.",
            "The final assignment is the currently effective patch for each repeated target.",
            "Do not remove earlier assignments until the wrapper chain and behavior are manually reviewed.",
            "Protected chains should be treated as keep/review, not automatic cleanup.",
            "Do not touch balances, 7x7, interest, payment allocation, notes, collector route, statements, PDFs, renewals, cash-control, or report math from this report alone.",
        ],
    }
    if json_path:
        Path(json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def print_report(report: dict[str, Any]) -> None:
    print("[SPINA] Patch chain resolution audit")
    print(f"[SPINA] File: {report['file']}")
    print(f"[SPINA] Patch assignments found: {report['patch_assignment_count']}")
    print(f"[SPINA] Repeated patch targets: {report['repeated_patch_target_count']}")
    print(f"[SPINA] Non-protected repeated targets: {report['non_protected_repeated_patch_target_count']}")
    for target, data in list(report["repeated_patch_targets"].items())[:40]:
        final = data["final_assignment"]
        status = "PROTECTED" if data["protected_chain"] else "review"
        print(f"  {target}: {data['assignment_count']} assignments, final L{final['line']} -> {final['rhs']} [{status}]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit for SPINA monkey-patch assignment chains.")
    parser.add_argument("source", nargs="?", default=DEFAULT_APP_FILE, help="SPINA app source file")
    parser.add_argument("--json", dest="json_path", help="Optional JSON report path")
    args = parser.parse_args()
    path = Path(args.source)
    if not path.exists():
        raise SystemExit(f"Source file not found: {path}")
    report = run(path, json_path=args.json_path)
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
