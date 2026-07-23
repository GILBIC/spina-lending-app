from __future__ import annotations

import ast
import json
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("tools/fixtures/hierarchical_area_implementation.json")

EXACT_NAMES = {
    "get_all_areas",
    "ensure_area_exists",
    "add_area",
    "count_clients_in_area",
    "rename_area",
    "delete_area",
    "open_areas_manager",
    "set_area_for_selected_clients",
    "_refresh_area_dropdowns",
}


def owner_name(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.ClassDef):
            return parent.name
        parent = parents.get(parent)
    return ""


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP))
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    functions: list[dict[str, object]] = []
    schema_owners: set[ast.AST] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lower = node.value.lower()
            if (
                "create table" in lower and ("areas" in lower or "clients" in lower)
            ) or (
                "alter table clients" in lower and "area" in lower
            ):
                parent = parents.get(node)
                while parent is not None and not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    parent = parents.get(parent)
                if parent is not None:
                    schema_owners.add(parent)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        segment = ast.get_source_segment(source, node) or ""
        lower = segment.lower()
        include = node.name in EXACT_NAMES or node in schema_owners
        if not include:
            has_area_control = (
                ("area_var" in segment or "self.area_var" in segment)
                and ("combobox" in lower or "area / route" in lower or "add area" in lower)
            )
            has_area_manager = "areas manager" in lower or "manage areas" in lower
            include = has_area_control or has_area_manager
        if not include:
            continue
        functions.append({
            "owner": owner_name(node, parents),
            "name": node.name,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "signature": ast.unparse(node.args),
            "source": segment,
        })

    functions.sort(key=lambda item: (item["line"], item["name"]))

    sql: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        lower = node.value.lower()
        if "area" not in lower:
            continue
        if not any(token in lower for token in (
            "create table", "alter table", "insert into areas", "update clients set area",
            "delete from areas", "select name from areas", "select distinct trim(area)",
        )):
            continue
        sql.append({
            "line": getattr(node, "lineno", None),
            "text": " ".join(node.value.split()),
        })
    sql.sort(key=lambda item: (item["line"] or 0, item["text"]))

    result = {
        "app": str(APP),
        "function_count": len(functions),
        "sql_count": len(sql),
        "functions": functions,
        "sql": sql,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Implementation report: functions={len(functions)}, sql={len(sql)}")


if __name__ == "__main__":
    main()
