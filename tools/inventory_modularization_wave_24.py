"""Read-only broad inventory for SPINA modularization Wave 24.

This tool scans the current desktop entry source for remaining low-risk presentation helpers.
It also includes two levels of low-risk direct callers so wrapper chains can be reviewed.
It does not modify application code.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("wave-24-inventory.json")
EXPECTED_BASE = "1ca6ebaa8276db6611e5cc26f6afc9b65f6e1780"

PROTECTED_PATTERNS = {
    "database": re.compile(r"\b(execute|executemany|commit|rollback|cursor|connect|SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|ALTER TABLE)\b", re.I),
    "payments": re.compile(r"\b(payment|principal|balance|interest|7x7|renewal|renew|offset|advance|ADV|PASS|amortization)\b", re.I),
    "reports_pdf": re.compile(r"\b(pdf|reportlab|canvas\.|statement|ledger|receipt|payslip|print_)\b", re.I),
    "filesystem": re.compile(r"\b(open\s*\(|os\.|pathlib|shutil|remove\s*\(|unlink\s*\(|mkdir\s*\(|write_text|read_text|asksaveasfilename|askopenfilename)\b", re.I),
    "authentication": re.compile(r"\b(login|password|permission|role|account|authenticate|session|token)\b", re.I),
    "network": re.compile(r"\b(requests\.|httpx\.|urllib|socket|FastAPI|uvicorn)\b", re.I),
}

UI_PATTERN = re.compile(
    r"\b(tk\.|ttk\.|Treeview|Canvas|Label|Button|Frame|Entry|Combobox|Listbox|Text|Scrollbar|Panedwindow|Notebook|StringVar|BooleanVar|IntVar|DoubleVar|Style)\b"
)
UI_NAME_HINT = re.compile(
    r"(card|style|color|palette|button|widget|layout|display|render|view|visible|tab|panel|header|footer|status|summary|filter|toggle|theme|tree|chart|label|dialog|form|toolbar)",
    re.I,
)


def _line_span(node: ast.AST) -> tuple[int, int, int]:
    start = int(getattr(node, "lineno", 0) or 0)
    end = int(getattr(node, "end_lineno", start) or start)
    return start, end, max(0, end - start + 1)


def _function_source(lines: list[str], node: ast.AST) -> str:
    start, end, _ = _line_span(node)
    return "\n".join(lines[start - 1 : end])


def _local_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
            names.add(child.name)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Param)):
            names.add(child.id)
        elif isinstance(child, ast.alias):
            names.add(child.asname or child.name.split(".")[0])
    return names


def _loaded_globals(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    local = _local_names(node)
    builtin_names = set(dir(builtins))
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    return sorted(name for name in loaded if name not in local and name not in builtin_names)


def _called_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            calls.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            calls.add(child.func.attr)
    return sorted(calls)


def _group_name(name: str) -> str:
    m = re.match(r"(_spina_v\d+_[a-z0-9]+)", name, re.I)
    if m:
        return m.group(1)
    m = re.match(r"(_spina_[a-z0-9]+)", name, re.I)
    if m:
        return m.group(1)
    parts = [part for part in name.strip("_").split("_") if part]
    return "_" + "_".join(parts[:2]) if parts else name


def _base_commit() -> str:
    result = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    base_commit = _base_commit()
    if base_commit != EXPECTED_BASE:
        raise SystemExit(f"Unexpected main base: {base_commit}")

    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))

    top_functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    direct_callers: dict[str, set[str]] = defaultdict(set)
    for caller_name, node in top_functions.items():
        for called in _called_names(node):
            if called in top_functions and called != caller_name:
                direct_callers[called].add(caller_name)

    facts: dict[str, dict[str, object]] = {}
    initial_names: set[str] = set()
    for name, node in top_functions.items():
        source = _function_source(lines, node)
        start, end, span = _line_span(node)
        protected = [label for label, pattern in PROTECTED_PATTERNS.items() if pattern.search(source)]
        has_ui = bool(UI_PATTERN.search(source))
        hinted = bool(UI_NAME_HINT.search(name))
        presentation_only = has_ui and not protected
        support_candidate = hinted and not protected and span <= 220
        facts[name] = {
            "source": source,
            "start": start,
            "end": end,
            "span": span,
            "protected": protected,
            "has_ui": has_ui,
            "hinted": hinted,
            "presentation_only": presentation_only,
            "support_candidate": support_candidate,
        }
        if span <= 500 and (presentation_only or support_candidate):
            initial_names.add(name)

    selected_names = set(initial_names)
    frontier = set(initial_names)
    for _depth in range(2):
        next_frontier: set[str] = set()
        for name in frontier:
            for caller in direct_callers.get(name, set()):
                fact = facts[caller]
                if fact["protected"] or int(fact["span"]) > 220:
                    continue
                if caller not in selected_names:
                    selected_names.add(caller)
                    next_frontier.add(caller)
        frontier = next_frontier

    entries: list[dict[str, object]] = []
    group_counts: Counter[str] = Counter()
    for name in selected_names:
        node = top_functions[name]
        fact = facts[name]
        source = str(fact["source"])
        group = _group_name(name)
        group_counts[group] += 1
        entries.append(
            {
                "name": name,
                "group": group,
                "start_line": int(fact["start"]),
                "end_line": int(fact["end"]),
                "lines": int(fact["span"]),
                "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                "direct_callers": sorted(direct_callers.get(name, set())),
                "called_names": _called_names(node),
                "global_dependencies": _loaded_globals(node),
                "protected_tags": list(fact["protected"]),
                "has_ui": bool(fact["has_ui"]),
                "name_hint": bool(fact["hinted"]),
                "presentation_only_candidate": bool(fact["presentation_only"]),
                "support_candidate": bool(fact["support_candidate"]),
                "included_as_caller": name not in initial_names,
                "source": source,
            }
        )

    entries.sort(key=lambda item: (int(item["start_line"]), str(item["name"])))

    groups: dict[str, dict[str, object]] = {}
    for group in sorted(group_counts):
        members = [item for item in entries if item["group"] == group]
        groups[group] = {
            "function_count": len(members),
            "source_lines": sum(int(item["lines"]) for item in members),
            "presentation_candidates": [item["name"] for item in members if item["presentation_only_candidate"]],
            "support_candidates": [item["name"] for item in members if item["support_candidate"]],
            "caller_chain": [item["name"] for item in members if item["included_as_caller"]],
        }

    payload = {
        "base_commit": base_commit,
        "source": str(SOURCE),
        "source_lines": len(lines),
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "top_level_function_count": len(top_functions),
        "candidate_count": len(entries),
        "group_summary": groups,
        "functions": entries,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    ranked = sorted(
        groups.items(),
        key=lambda item: (
            -len(item[1]["presentation_candidates"]),
            -len(item[1]["support_candidates"]),
            -len(item[1]["caller_chain"]),
            int(item[1]["source_lines"]),
            item[0],
        ),
    )
    print(json.dumps(dict(ranked[:25]), indent=2, sort_keys=True))
    print(f"Wrote {OUTPUT} with {len(entries)} candidates across {len(groups)} groups.")


if __name__ == "__main__":
    main()
