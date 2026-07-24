"""Read-only inventory for SPINA modularization Wave 22.

This tool parses the current large desktop source and records cohesive remaining
feature groups without changing production code. It is intentionally limited to
source inspection and JSON output.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("wave-22-inventory.json")

PREFIXES = (
    "_spina_v25_",
    "_spina_v26_",
    "_spina_v27_",
    "_spina_v28_",
    "_spina_collector",
    "_spina_route",
    "_spina_payroll",
    "_spina_databank",
)

RISK_PATTERNS = {
    "database": re.compile(r"\b(execute|executemany|commit|rollback|cursor|connect|SELECT|INSERT|UPDATE|DELETE)\b", re.I),
    "payments": re.compile(r"\b(payment|principal|balance|interest|7x7|renewal|renew|offset)\b", re.I),
    "reports_pdf": re.compile(r"\b(pdf|reportlab|canvas|statement|report total)\b", re.I),
    "filesystem": re.compile(r"\b(open\s*\(|os\.|pathlib|shutil|remove\s*\(|unlink\s*\()", re.I),
    "authentication": re.compile(r"\b(login|password|permission|role|account recovery|authenticate)\b", re.I),
    "ui": re.compile(r"\b(tk\.|ttk\.|Treeview|Canvas|Label|Button|Frame|StringVar|BooleanVar)\b"),
}


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
    calls: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            calls.append(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            calls.append(child.func.attr)
    return sorted(set(calls))


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))

    top_functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    class_methods: list[dict[str, object]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start, end, span = _line_span(child)
                    class_methods.append(
                        {
                            "class": node.name,
                            "name": child.name,
                            "start_line": start,
                            "end_line": end,
                            "lines": span,
                        }
                    )

    direct_callers: dict[str, set[str]] = defaultdict(set)
    for caller_name, node in top_functions.items():
        for called in _called_names(node):
            if called in top_functions and called != caller_name:
                direct_callers[called].add(caller_name)

    entries: list[dict[str, object]] = []
    group_counts: Counter[str] = Counter()
    for name, node in top_functions.items():
        if not (name.startswith(PREFIXES) or "collector" in name.lower() or "route" in name.lower()):
            continue
        source = _function_source(lines, node)
        start, end, span = _line_span(node)
        risks = [label for label, pattern in RISK_PATTERNS.items() if pattern.search(source)]
        group_match = re.match(r"(_spina_v\d+)", name)
        group = group_match.group(1) if group_match else "collector_or_route_other"
        group_counts[group] += 1
        entries.append(
            {
                "name": name,
                "group": group,
                "start_line": start,
                "end_line": end,
                "lines": span,
                "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                "direct_callers": sorted(direct_callers.get(name, set())),
                "called_names": _called_names(node),
                "global_dependencies": _loaded_globals(node),
                "risk_tags": risks,
                "presentation_only_candidate": risks == ["ui"] or ("ui" in risks and not any(r in risks for r in ("database", "payments", "reports_pdf", "filesystem", "authentication"))),
            }
        )

    entries.sort(key=lambda item: (int(item["start_line"]), str(item["name"])))

    safe_groups: dict[str, dict[str, object]] = {}
    for group in sorted(group_counts):
        members = [item for item in entries if item["group"] == group]
        safe = [item for item in members if item["presentation_only_candidate"]]
        protected = [item for item in members if not item["presentation_only_candidate"]]
        safe_groups[group] = {
            "function_count": len(members),
            "source_lines": sum(int(item["lines"]) for item in members),
            "presentation_candidates": [item["name"] for item in safe],
            "protected_or_mixed": [item["name"] for item in protected],
        }

    payload = {
        "source": str(SOURCE),
        "source_lines": len(lines),
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "top_level_function_count": len(top_functions),
        "class_method_count": len(class_methods),
        "candidate_prefixes": list(PREFIXES),
        "group_summary": safe_groups,
        "functions": entries,
        "large_class_methods": sorted(
            [item for item in class_methods if int(item["lines"]) >= 80],
            key=lambda item: (-int(item["lines"]), str(item["class"]), str(item["name"])),
        )[:80],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(payload["group_summary"], indent=2, sort_keys=True))
    print(f"Wrote {OUTPUT} with {len(entries)} candidate functions.")


if __name__ == "__main__":
    main()
