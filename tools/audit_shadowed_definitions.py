#!/usr/bin/env python3
"""Read-only review of duplicate and shadowed definitions in the SPINA app.

The main source has accumulated compatibility patches and replacement functions.
This tool does not edit the app. It identifies duplicate top-level functions,
duplicate class methods, and repeated monkey-patch assignments so each group can
be reviewed before any removal is attempted.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

CLASS_RE = re.compile(r"^(?P<indent>\s*)class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
DEF_RE = re.compile(r"^(?P<indent>\s*)def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
PATCH_RE = re.compile(r"^\s*(?P<class>[A-Z][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=")
SETATTR_RE = re.compile(r"setattr\s*\(\s*(?P<class>[A-Z][A-Za-z0-9_]*)\s*,\s*['\"](?P<name>[A-Za-z_][A-Za-z0-9_]*)['\"]")

PROTECTED_TERMS = (
    "balance",
    "7x7",
    "principal",
    "interest",
    "payment allocation",
    "payment logic",
    "collector route",
    "daily collection ledger",
    "client statement",
    "statement pdf",
    "report math",
    "client_pdf",
    "ledger total",
    "advance",
    "pass",
    "note",
    "transaction",
    "loan",
    "renew",
    "cash control",
    "pdf",
    "report",
    "collector",
)


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _context(lines: list[str], line_no: int, radius: int = 8) -> str:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def _has_protected_context(lines: list[str], line_no: int) -> bool:
    text = _context(lines, line_no).lower()
    return any(term in text for term in PROTECTED_TERMS)


def _entry(lines: list[str], line_no: int) -> dict[str, Any]:
    return {
        "line": line_no,
        "protected_context": _has_protected_context(lines, line_no),
        "text": lines[line_no - 1].strip(),
    }


def collect(lines: list[str]) -> dict[str, Any]:
    top_level: dict[str, list[dict[str, Any]]] = {}
    class_methods: dict[str, dict[str, list[dict[str, Any]]]] = {}
    patch_targets: dict[str, list[dict[str, Any]]] = {}
    class_stack: list[tuple[int, str]] = []

    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        indent = _indent_width(line)

        if stripped and not stripped.startswith("#"):
            while class_stack and indent <= class_stack[-1][0]:
                class_stack.pop()

        class_match = CLASS_RE.match(line)
        if class_match:
            class_stack.append((len(class_match.group("indent")), class_match.group("name")))
            continue

        def_match = DEF_RE.match(line)
        if def_match:
            name = def_match.group("name")
            def_indent = len(def_match.group("indent"))
            if class_stack and def_indent == class_stack[-1][0] + 4:
                cls = class_stack[-1][1]
                class_methods.setdefault(cls, {}).setdefault(name, []).append(_entry(lines, index))
            elif def_indent == 0:
                top_level.setdefault(name, []).append(_entry(lines, index))

        patch_match = PATCH_RE.match(line) or SETATTR_RE.search(line)
        if patch_match:
            key = f"{patch_match.group('class')}.{patch_match.group('name')}"
            patch_targets.setdefault(key, []).append(_entry(lines, index))

    duplicate_top = {name: entries for name, entries in top_level.items() if len(entries) > 1}
    duplicate_methods = {
        cls: {name: entries for name, entries in methods.items() if len(entries) > 1}
        for cls, methods in class_methods.items()
    }
    duplicate_methods = {cls: methods for cls, methods in duplicate_methods.items() if methods}
    repeated_patches = {name: entries for name, entries in patch_targets.items() if len(entries) > 1}

    review_candidates: list[dict[str, Any]] = []
    for name, entries in duplicate_top.items():
        shadowed = entries[:-1]
        if shadowed and not any(item["protected_context"] for item in shadowed):
            review_candidates.append({"kind": "top_level", "name": name, "shadowed_lines": [item["line"] for item in shadowed], "active_line": entries[-1]["line"]})
    for cls, methods in duplicate_methods.items():
        for name, entries in methods.items():
            shadowed = entries[:-1]
            if shadowed and not any(item["protected_context"] for item in shadowed):
                review_candidates.append({"kind": "class_method", "name": f"{cls}.{name}", "shadowed_lines": [item["line"] for item in shadowed], "active_line": entries[-1]["line"]})

    return {
        "top_level_duplicate_count": len(duplicate_top),
        "class_method_duplicate_count": sum(len(methods) for methods in duplicate_methods.values()),
        "repeated_patch_target_count": len(repeated_patches),
        "top_level_duplicates": duplicate_top,
        "class_method_duplicates": duplicate_methods,
        "repeated_patch_targets": repeated_patches,
        "review_candidates": review_candidates[:100],
        "recommendations": [
            "Read-only audit only; no app source changes are made.",
            "Review one duplicate family at a time before deleting any code.",
            "Treat protected-context duplicates as keep/review, not automatic removal.",
            "Repeated App monkey-patches should be consolidated only after a manual behavior check.",
            "Do not touch balances, 7x7, interest, payment allocation, notes, collector route, statements, PDFs, renewals, or report math from this report alone.",
        ],
    }


def run(path: Path, json_path: str | None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    report = {"file": str(path), "line_count": len(lines)}
    report.update(collect(lines))
    if json_path:
        Path(json_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def print_report(report: dict[str, Any]) -> None:
    print("[SPINA] Shadowed definition audit")
    print(f"[SPINA] File: {report['file']}")
    print(f"[SPINA] Top-level duplicate names: {report['top_level_duplicate_count']}")
    print(f"[SPINA] Class-method duplicate names: {report['class_method_duplicate_count']}")
    print(f"[SPINA] Repeated patch targets: {report['repeated_patch_target_count']}")
    print(f"[SPINA] First review candidates: {len(report['review_candidates'])}")
    for item in report["review_candidates"][:25]:
        print(f"  {item['kind']}: {item['name']} shadowed={item['shadowed_lines']} active={item['active_line']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit of duplicate and shadowed SPINA definitions.")
    parser.add_argument("source", nargs="?", default=DEFAULT_APP_FILE, help="SPINA app source file")
    parser.add_argument("--json", dest="json_path", help="Optional JSON report path")
    args = parser.parse_args()
    path = Path(args.source)
    if not path.exists():
        raise SystemExit(f"Source file not found: {path}")
    report = run(path, args.json_path)
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
