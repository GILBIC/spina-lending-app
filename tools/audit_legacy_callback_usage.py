#!/usr/bin/env python3
"""Read-only usage audit for remaining legacy callback-name matches.

This tool helps decide whether old callback-looking functions are actually unused
or are shared app functions that must stay. It does not modify the app.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

TARGETS = (
    "import_missing_clients_from_transactions",
    "print_full_daily_ledger",
    "import_clients_from_excel",
    "export_clients_template",
    "export_range_template",
    "_app_export_clients_template",
    "_app_import_clients_from_excel",
)

PROTECTED_KEYWORDS = (
    "balance",
    "7x7",
    "principal",
    "interest",
    "payment allocation",
    "advance",
    "pass",
    "collector route",
    "note",
    "statement",
    "client_pdf",
    "ledger total",
)

ASSIGN_OR_DEF_RE = re.compile(r"^\s*(?:def|class)\s+|^\s*[A-Za-z_][A-Za-z0-9_\.]*\s*=")


def line_context(lines: list[str], line_no: int, radius: int = 2) -> str:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def has_protected_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in PROTECTED_KEYWORDS)


def function_ranges(lines: list[str]) -> dict[tuple[str, str], tuple[int, int]]:
    """Return {(class_name, function_name): (start_line, end_line)}."""
    tree = ast.parse("\n".join(lines))
    ranges: dict[tuple[str, str], tuple[int, int]] = {}

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            ranges[("", node.name)] = (node.lineno, getattr(node, "end_lineno", node.lineno))
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    ranges[(node.name, child.name)] = (child.lineno, getattr(child, "end_lineno", child.lineno))
    return ranges


def collect_definitions(ranges: dict[tuple[str, str], tuple[int, int]]) -> list[dict[str, Any]]:
    defs: list[dict[str, Any]] = []
    for (class_name, func_name), (start, end) in ranges.items():
        if func_name in TARGETS:
            defs.append(
                {
                    "class": class_name,
                    "function": func_name,
                    "start_line": start,
                    "end_line": end,
                    "line_count": end - start + 1,
                }
            )
    defs.sort(key=lambda item: (item["start_line"], item["class"], item["function"]))
    return defs


def line_inside_any_definition(line_no: int, definitions: list[dict[str, Any]]) -> bool:
    for item in definitions:
        if int(item["start_line"]) <= line_no <= int(item["end_line"]):
            return True
    return False


def collect_references(lines: list[str], definitions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    results: dict[str, list[dict[str, Any]]] = {target: [] for target in TARGETS}
    patterns = {target: re.compile(r"\b" + re.escape(target) + r"\b") for target in TARGETS}

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for target, pattern in patterns.items():
            if not pattern.search(line):
                continue
            is_definition_line = bool(re.match(rf"^\s*def\s+{re.escape(target)}\s*\(", line))
            if is_definition_line:
                kind = "definition"
            elif "command" in line.lower():
                kind = "command_reference"
            elif re.search(rf"\.\s*{re.escape(target)}\b", line):
                kind = "attribute_reference"
            elif re.search(rf"\b{re.escape(target)}\s*\(", line):
                kind = "direct_call"
            elif ASSIGN_OR_DEF_RE.search(line):
                kind = "assignment_or_patch"
            else:
                kind = "name_reference"

            context = line_context(lines, line_no)
            results[target].append(
                {
                    "line": line_no,
                    "kind": kind,
                    "inside_target_definition": line_inside_any_definition(line_no, definitions),
                    "protected_context": has_protected_keyword(context),
                    "text": stripped[:220],
                }
            )
    return results


def build_recommendations(definitions: list[dict[str, Any]], refs: dict[str, list[dict[str, Any]]]) -> list[str]:
    recommendations: list[str] = []
    definitions_by_name: dict[str, list[dict[str, Any]]] = {}
    for item in definitions:
        definitions_by_name.setdefault(str(item["function"]), []).append(item)

    for target in TARGETS:
        target_defs = definitions_by_name.get(target, [])
        target_refs = refs.get(target, [])
        external_refs = [r for r in target_refs if not r.get("inside_target_definition") and r.get("kind") != "definition"]
        command_refs = [r for r in external_refs if r.get("kind") == "command_reference"]
        protected_refs = [r for r in external_refs if r.get("protected_context")]
        if not target_defs:
            recommendations.append(f"{target}: no definition found; nothing to remove for this name.")
        elif command_refs:
            recommendations.append(f"{target}: KEEP for now; command references still exist.")
        elif protected_refs:
            recommendations.append(f"{target}: KEEP for now; external references touch protected context.")
        elif external_refs:
            recommendations.append(f"{target}: REVIEW; definitions exist with non-command external references.")
        else:
            recommendations.append(f"{target}: possible REMOVE candidate only after manual review; no external references found.")

    recommendations.append(
        "Do not delete protected report/payment/collector functions unless a separate manual review proves they are unused."
    )
    return recommendations


def audit(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    ranges = function_ranges(lines)
    definitions = collect_definitions(ranges)
    refs = collect_references(lines, definitions)
    return {
        "file": str(path),
        "line_count": len(lines),
        "target_names": list(TARGETS),
        "definitions": definitions,
        "references": refs,
        "recommendations": build_recommendations(definitions, refs),
    }


def print_summary(report: dict[str, Any]) -> None:
    print("SPINA legacy callback usage audit")
    print(f"File: {report['file']}")
    print(f"Lines scanned: {report['line_count']}")
    print()

    definitions_by_name: dict[str, list[dict[str, Any]]] = {}
    for item in report["definitions"]:
        definitions_by_name.setdefault(str(item["function"]), []).append(item)

    for target in report["target_names"]:
        defs = definitions_by_name.get(target, [])
        refs = report["references"].get(target, [])
        external = [r for r in refs if not r.get("inside_target_definition") and r.get("kind") != "definition"]
        commands = [r for r in external if r.get("kind") == "command_reference"]
        protected = [r for r in external if r.get("protected_context")]
        print(f"{target}:")
        print(f"  definitions: {len(defs)}")
        for item in defs[:8]:
            owner = f"{item['class']}." if item.get("class") else ""
            print(f"    L{item['start_line']}-L{item['end_line']}: {owner}{item['function']} ({item['line_count']} lines)")
        print(f"  external references: {len(external)}")
        print(f"  command references: {len(commands)}")
        print(f"  protected external references: {len(protected)}")
        for ref in external[:8]:
            mark = " protected" if ref.get("protected_context") else ""
            print(f"    L{ref['line']} [{ref['kind']}{mark}]: {ref['text']}")
        if len(external) > 8:
            print(f"    ... {len(external) - 8} more external references")
        print()

    print("Recommendations:")
    for item in report["recommendations"]:
        print(f"  - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only audit for remaining legacy callback-name matches.")
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
