from __future__ import annotations

import ast
import json
import re
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("tools/fixtures/hierarchical_area_system_inspection.json")

IDENTIFIER_PATTERNS = (
    "area", "areas", "main_area", "sub_area", "client_area",
    "area_var", "area_entry", "area_combo", "area_order",
)
TEXT_PATTERNS = (
    "CREATE TABLE", "ALTER TABLE", "clients", "collectors", "Area",
    "area_order", "ledger_prefs", "Data Bank", "Collector Route",
)


def _source_segment(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ""


def _node_has_area_reference(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            name = child.id.lower()
            if any(pattern in name for pattern in IDENTIFIER_PATTERNS):
                return True
        elif isinstance(child, ast.Attribute):
            name = child.attr.lower()
            if any(pattern in name for pattern in IDENTIFIER_PATTERNS):
                return True
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            text = child.value.lower()
            if "area" in text:
                return True
    return False


def _calls(node: ast.AST) -> list[str]:
    result: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            try:
                result.append(ast.unparse(child.func))
            except Exception:
                result.append("?")
    return sorted(set(result))


def _line_context(lines: list[str], line_number: int, radius: int = 4) -> dict[str, object]:
    start = max(1, line_number - radius)
    end = min(len(lines), line_number + radius)
    return {
        "line": line_number,
        "start_line": start,
        "end_line": end,
        "text": "".join(lines[start - 1:end]),
    }


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source, filename=str(APP))

    functions: list[dict[str, object]] = []
    classes: list[dict[str, object]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _node_has_area_reference(node):
            exact = _source_segment(source, node)
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno,
                "line_count": (node.end_lineno or node.lineno) - node.lineno + 1,
                "calls": _calls(node),
                "source": exact if len(exact) <= 12000 else exact[:12000] + "\n...[truncated]",
            })
        elif isinstance(node, ast.ClassDef) and _node_has_area_reference(node):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and _node_has_area_reference(item):
                    methods.append({
                        "name": item.name,
                        "line": item.lineno,
                        "end_line": item.end_lineno,
                        "line_count": (item.end_lineno or item.lineno) - item.lineno + 1,
                        "calls": _calls(item),
                    })
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno,
                "area_methods": methods,
            })

    contexts: list[dict[str, object]] = []
    context_seen: set[int] = set()
    regexes = [
        re.compile(r"\barea\b", re.I),
        re.compile(r"main_area|sub_area|client_area|area_var|area_entry|area_combo", re.I),
        re.compile(r"CREATE\s+TABLE.*clients|ALTER\s+TABLE.*clients", re.I),
        re.compile(r"collectors\.json|ledger_prefs\.json|area_order", re.I),
    ]
    for index, line in enumerate(lines, start=1):
        if any(regex.search(line) for regex in regexes):
            if index not in context_seen:
                contexts.append(_line_context(lines, index))
                context_seen.add(index)

    sql_strings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            lowered = text.lower()
            if ("clients" in lowered and ("create table" in lowered or "alter table" in lowered or "update clients" in lowered or "insert into clients" in lowered)) or (
                "area" in lowered and any(token in lowered for token in ("select", "insert", "update", "alter table", "create table"))
            ):
                sql_strings.append({
                    "line": getattr(node, "lineno", None),
                    "text": text if len(text) <= 6000 else text[:6000] + "\n...[truncated]",
                })

    result = {
        "app": str(APP),
        "function_count": len(functions),
        "class_count": len(classes),
        "context_count": len(contexts),
        "sql_string_count": len(sql_strings),
        "functions": functions,
        "classes": classes,
        "contexts": contexts[:350],
        "sql_strings": sql_strings[:150],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Recorded {len(functions)} functions, {len(classes)} classes, "
        f"{len(contexts)} contexts, and {len(sql_strings)} SQL strings"
    )


if __name__ == "__main__":
    main()
