#!/usr/bin/env python3
"""Inventory legacy UI/action code in the SPINA desktop source.

This tool is intentionally read-only. It scans the large SPINA source file with
fast line-based rules and reports likely old UI controls, callback names, and
protected business-logic areas. It does not modify the app.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

UI_GROUPS: dict[str, tuple[str, ...]] = {
    "clients_legacy_actions": (
        "From Transactions",
        "Full Ledger",
        "Export Template",
        "Import Excel",
    ),
    "databank_export_controls": (
        "Exports",
        "Date Range Template",
        "JSONL Month",
        "Daily Excel Template",
    ),
}

CALLBACK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "clients_legacy_actions": (
        "from_transactions",
        "full_ledger",
        "full_daily_ledger",
        "export_template",
        "export_range_template",
        "export_clients_template",
        "import_excel",
        "import_clients_excel",
        "import_clients_from_excel",
    ),
    "databank_export_controls": (
        "date_range_template",
        "jsonl_month",
        "daily_excel_template",
        "export_template",
        "export_date_range",
        "export_jsonl",
        "daily_collection_template",
        "create_daily_collection_template",
    ),
}

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

UI_TERMS = (
    "button",
    "ctkbutton",
    "ttk.button",
    "tk.button",
    "command=",
    ".pack(",
    ".grid(",
    ".place(",
    "menu.add_command",
    "add_command",
)

DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)")
COMMAND_RE = re.compile(r"command\s*=\s*(?:self\.)?([A-Za-z_][A-Za-z0-9_]*)")


def normalize(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def line_context(lines: list[str], line_no: int, radius: int = 2) -> str:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def looks_like_ui_context(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in UI_TERMS)


def has_protected_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in PROTECTED_KEYWORDS)


def collect_label_hits(lines: list[str]) -> dict[str, list[dict[str, Any]]]:
    results: dict[str, list[dict[str, Any]]] = {}
    for group, labels in UI_GROUPS.items():
        hits: list[dict[str, Any]] = []
        for index, line in enumerate(lines, start=1):
            for label in labels:
                if normalize(label) in normalize(line):
                    context = line_context(lines, index)
                    hits.append(
                        {
                            "line": index,
                            "label": label,
                            "text": line.strip(),
                            "ui_like_context": looks_like_ui_context(context),
                            "protected_context": has_protected_keyword(context),
                        }
                    )
        results[group] = hits
    return results


def collect_callback_candidates(lines: list[str]) -> dict[str, list[dict[str, Any]]]:
    results: dict[str, list[dict[str, Any]]] = {group: [] for group in CALLBACK_KEYWORDS}
    current_class = ""
    for index, line in enumerate(lines, start=1):
        class_match = CLASS_RE.match(line)
        if class_match:
            current_class = class_match.group(1)
        def_match = DEF_RE.match(line)
        if not def_match:
            continue
        name = def_match.group(1)
        normalized_name = name.lower()
        for group, keywords in CALLBACK_KEYWORDS.items():
            if any(keyword in normalized_name for keyword in keywords):
                context = line_context(lines, index, radius=3)
                results[group].append(
                    {
                        "line": index,
                        "function": name,
                        "class": current_class if line.startswith("    ") else "",
                        "protected_context": has_protected_keyword(context),
                    }
                )
    return results


def collect_command_references(lines: list[str]) -> dict[str, list[dict[str, Any]]]:
    results: dict[str, list[dict[str, Any]]] = {group: [] for group in CALLBACK_KEYWORDS}
    for index, line in enumerate(lines, start=1):
        if "command" not in line.lower():
            continue
        commands = COMMAND_RE.findall(line)
        if not commands:
            continue
        lowered_line = line.lower()
        for group, keywords in CALLBACK_KEYWORDS.items():
            if any(keyword in lowered_line for keyword in keywords):
                for command in commands:
                    results[group].append(
                        {
                            "line": index,
                            "command": command,
                            "text": line.strip(),
                            "protected_context": has_protected_keyword(line_context(lines, index)),
                        }
                    )
    return results


def build_recommendations(label_hits: dict[str, list[dict[str, Any]]], callbacks: dict[str, list[dict[str, Any]]]) -> list[str]:
    recommendations: list[str] = []
    for group in UI_GROUPS:
        ui_like = sum(1 for hit in label_hits[group] if hit.get("ui_like_context"))
        callback_count = len(callbacks[group])
        protected = sum(1 for hit in label_hits[group] if hit.get("protected_context"))
        if ui_like or callback_count:
            recommendations.append(
                f"{group}: review {ui_like} UI-like label hits and {callback_count} callback candidates. "
                f"Avoid deleting {protected} protected-context hits without manual review."
            )
    recommendations.append(
        "Delete only confirmed UI/action glue first. Do not touch balances, 7x7, interest, payment allocation, notes, or report math."
    )
    return recommendations


def audit(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    label_hits = collect_label_hits(lines)
    callbacks = collect_callback_candidates(lines)
    command_refs = collect_command_references(lines)
    return {
        "file": str(path),
        "line_count": len(lines),
        "ui_groups": list(UI_GROUPS.keys()),
        "label_hits": label_hits,
        "callback_candidates": callbacks,
        "command_references": command_refs,
        "protected_keywords": list(PROTECTED_KEYWORDS),
        "recommendations": build_recommendations(label_hits, callbacks),
    }


def print_summary(report: dict[str, Any]) -> None:
    print("SPINA UI/action inventory")
    print(f"File: {report['file']}")
    print(f"Lines scanned: {report['line_count']}")
    print()
    for group in report["ui_groups"]:
        labels = report["label_hits"].get(group, [])
        callbacks = report["callback_candidates"].get(group, [])
        commands = report["command_references"].get(group, [])
        ui_like = sum(1 for hit in labels if hit.get("ui_like_context"))
        print(f"{group}:")
        print(f"  label hits: {len(labels)} ({ui_like} UI-like)")
        print(f"  callback candidates: {len(callbacks)}")
        print(f"  command references: {len(commands)}")
        for hit in labels[:10]:
            mark = "UI" if hit.get("ui_like_context") else "text"
            protected = " protected" if hit.get("protected_context") else ""
            print(f"    L{hit['line']} [{mark}{protected}] {hit['label']}: {hit['text'][:140]}")
        if len(labels) > 10:
            print(f"    ... {len(labels) - 10} more label hits")
        for item in callbacks[:10]:
            owner = f"{item['class']}." if item.get("class") else ""
            protected = " protected" if item.get("protected_context") else ""
            print(f"    callback L{item['line']}{protected}: {owner}{item['function']}")
        if len(callbacks) > 10:
            print(f"    ... {len(callbacks) - 10} more callback candidates")
        print()
    print("Recommendations:")
    for item in report["recommendations"]:
        print(f"  - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory legacy UI/action code in the SPINA source.")
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
