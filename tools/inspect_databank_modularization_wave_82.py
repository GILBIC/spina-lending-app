#!/usr/bin/env python3
"""Inventory the active Data Bank runtime before Wave 82 extraction."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

NAME_TOKENS = (
    "databank", "data_bank", "data_grid", "transaction", "day_close", "dayclose",
    "audit", "advance", "adv_", "pass_", "close_day", "reopen_day", "delete_day",
    "import", "export", "daily_collection", "cell_edit", "selected_cell", "month",
)
SOURCE_TOKENS = (
    "Data Bank", "databank_day_close", "transaction_history", "ADV", "PASS",
    "auto_close_after_days", "delete_transactions_for_day", "close_databank_day",
    "reopen_databank_day", "refresh_data_grid", "days_tree", "name_tree",
)


def line_span(node: ast.AST) -> tuple[int, int]:
    return int(getattr(node, "lineno", 0)), int(getattr(node, "end_lineno", 0))


def relevant(name: str, source: str) -> bool:
    low = name.lower()
    if any(token in low for token in NAME_TOKENS):
        return True
    return any(token.lower() in source.lower() for token in SOURCE_TOKENS)


def assignment_target(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return ""


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(APP_PATH))

    classes: dict[str, list[dict[str, object]]] = {"LoanDB": [], "App": []}
    top_level: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in classes:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start, end = line_span(child)
                    segment = "\n".join(lines[start - 1 : end])
                    if relevant(child.name, segment):
                        classes[node.name].append({"name": child.name, "start": start, "end": end})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start, end = line_span(node)
            name = getattr(node, "name", "")
            segment = "\n".join(lines[start - 1 : end])
            if relevant(name, segment):
                top_level.append({"kind": type(node).__name__, "name": name, "start": start, "end": end})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                name = assignment_target(target)
                if name.startswith(("App.", "LoanDB.")) and relevant(name, lines[node.lineno - 1]):
                    bindings.append({"target": name, "line": node.lineno, "source": lines[node.lineno - 1].strip()})

    markers = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        if any(token.lower() in stripped.lower() for token in SOURCE_TOKENS + ("daily close", "cell edit", "audit tab")):
            markers.append({"line": number, "text": stripped})

    payload = {
        "app_path": str(APP_PATH.relative_to(ROOT)),
        "line_count": len(lines),
        "classes": classes,
        "top_level": top_level,
        "bindings": bindings,
        "markers": markers,
    }
    print("DATABANK_WAVE82_INVENTORY_BEGIN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("DATABANK_WAVE82_INVENTORY_END")

    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "databank-wave-82-inventory.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
