#!/usr/bin/env python3
"""Inventory active Clients-owned symbols and runtime bindings for Wave 81."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

TERMS = (
    "client", "archive", "restore", "renew", "link", "picture",
    "flex_due", "due_meta", "payment_mode", "import_missing",
)


def relevant(name: str) -> bool:
    value = str(name or "").lower()
    return any(term in value for term in TERMS)


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()

    report: dict[str, object] = {
        "app_path": str(APP.relative_to(ROOT)),
        "line_count": len(lines),
        "top_level": [],
        "app_methods": [],
        "classes": [],
        "runtime_bindings": [],
        "imports": [],
        "markers": [],
    }

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and relevant(node.name):
            report["top_level"].append({
                "name": node.name,
                "start": node.lineno,
                "end": node.end_lineno,
            })
        elif isinstance(node, ast.ClassDef):
            if relevant(node.name):
                report["classes"].append({
                    "name": node.name,
                    "start": node.lineno,
                    "end": node.end_lineno,
                })
            if node.name == "App":
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and relevant(child.name):
                        report["app_methods"].append({
                            "name": child.name,
                            "start": child.lineno,
                            "end": child.end_lineno,
                        })
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            text = ast.get_source_segment(source, node) or ""
            if relevant(text) or "spina_app.tabs.clients" in text:
                report["imports"].append({
                    "start": node.lineno,
                    "end": node.end_lineno,
                    "source": text,
                })

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [dotted(t) for t in node.targets]
            target_text = " | ".join(t for t in targets if t)
            value_text = ast.get_source_segment(source, node.value) or ""
            if any((t.startswith("App.") or t.startswith("LoanDB.")) and relevant(t) for t in targets):
                report["runtime_bindings"].append({
                    "start": node.lineno,
                    "end": node.end_lineno,
                    "target": target_text,
                    "value": value_text[:240],
                })
        elif isinstance(node, ast.Call):
            fn = dotted(node.func)
            if fn == "setattr" and len(node.args) >= 2:
                owner = ast.get_source_segment(source, node.args[0]) or ""
                attr = ast.get_source_segment(source, node.args[1]) or ""
                if owner in {"App", "LoanDB"} and relevant(attr):
                    report["runtime_bindings"].append({
                        "start": node.lineno,
                        "end": node.end_lineno,
                        "target": f"setattr({owner}, {attr})",
                        "value": ast.get_source_segment(source, node.args[2])[:240] if len(node.args) >= 3 and ast.get_source_segment(source, node.args[2]) else "",
                    })

    for lineno, text in enumerate(lines, 1):
        stripped = text.strip()
        if stripped.startswith("# --- BEGIN:") or stripped.startswith("# --- END:"):
            if relevant(stripped):
                report["markers"].append({"line": lineno, "text": stripped})

    for key in ("top_level", "app_methods", "classes", "runtime_bindings", "imports", "markers"):
        report[key] = sorted(report[key], key=lambda item: (item.get("start", item.get("line", 0)), item.get("name", "")))

    out = ROOT / "clients-wave81-inventory.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("CLIENTS_WAVE81_INVENTORY_BEGIN")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("CLIENTS_WAVE81_INVENTORY_END")


if __name__ == "__main__":
    main()
