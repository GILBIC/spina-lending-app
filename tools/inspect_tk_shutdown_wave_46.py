from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT = ROOT / "artifacts" / "wave-46-tk-shutdown-inspection.json"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def source_line(lines: list[str], lineno: int) -> str:
    return lines[lineno - 1].rstrip() if 1 <= lineno <= len(lines) else ""


def parent_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
    return None


def numbered_range(lines: list[str], start: int, end: int) -> list[dict[str, object]]:
    return [
        {"line": line_no, "source": source_line(lines, line_no)}
        for line_no in range(start, min(end, len(lines)) + 1)
    ]


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    functions = []
    calls = []
    strings = []

    interesting_names = {
        "pump", "_pump", "destroy", "quit", "after", "after_idle", "after_cancel",
        "event_generate", "theme_use", "set_theme", "_refresh_header_theme",
        "_spina_v32_switch_account", "mainloop", "protocol",
    }

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            low = node.name.lower()
            if any(term in low for term in ("pump", "shutdown", "close", "destroy", "theme", "switch_account", "main")):
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "end": node.end_lineno,
                    "parent": parent_function(node, parents),
                    "source": "\n".join(lines[node.lineno - 1 : node.end_lineno]),
                })
        elif isinstance(node, ast.Call):
            name = dotted(node.func)
            low = name.lower()
            if any(term in low for term in interesting_names):
                calls.append({
                    "call": name,
                    "line": node.lineno,
                    "function": parent_function(node, parents),
                    "source": source_line(lines, node.lineno),
                    "args": [ast.unparse(arg) for arg in node.args],
                    "keywords": {kw.arg or "**": ast.unparse(kw.value) for kw in node.keywords},
                })
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if any(term.lower() in node.value.lower() for term in ("ThemeChanged", "_pump", "after script", "WM_DELETE_WINDOW")):
                strings.append({
                    "line": node.lineno,
                    "function": parent_function(node, parents),
                    "value": node.value,
                    "source": source_line(lines, node.lineno),
                })

    raw_matches = []
    pattern = re.compile(r"pump|after_cancel|after\s*\(|ThemeChanged|theme_use|destroy\s*\(|WM_DELETE_WINDOW|switch_account", re.I)
    for index, line in enumerate(lines, 1):
        if pattern.search(line):
            raw_matches.append({"line": index, "source": line.rstrip()})

    lifecycle_ranges = {
        "app_init_and_login_exit": numbered_range(lines, 11155, 11245),
        "ui_queue_pump": numbered_range(lines, 11330, 11382),
        "theme_setup": numbered_range(lines, 11505, 11562),
        "main_entry": numbered_range(lines, 26080, 26100),
        "account_switch": numbered_range(lines, 37810, 37880),
    }

    report = {
        "desktop_lines": len(lines),
        "functions": sorted(functions, key=lambda row: row["line"]),
        "calls": sorted(calls, key=lambda row: row["line"]),
        "strings": sorted(strings, key=lambda row: row["line"]),
        "raw_matches": raw_matches,
        "lifecycle_ranges": lifecycle_ranges,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"functions={len(functions)} calls={len(calls)} raw_matches={len(raw_matches)}")
    for name, rows in lifecycle_ranges.items():
        print(f"\n--- {name} ---")
        for row in rows:
            print(f"{row['line']}: {row['source']}")


if __name__ == "__main__":
    main()
