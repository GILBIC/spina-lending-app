from __future__ import annotations

import ast
import hashlib
import json
import shutil
import textwrap
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
REPORT = Path("wave72_databank_exact_inventory.json")
EXPORT_DIR = Path("wave72_databank_sources")

APP_METHODS = (
    "_clear_preview",
    "_get_databank_focus_date",
    "_show_system_data_tab",
    "_hide_system_data_tab",
    "_system_data_open_close",
    "_system_data_open_history",
    "_system_data_open_records",
    "_system_data_print_report",
    "_load_collectors_route_map",
    "_build_databank_collector_defaults_for_date",
    "print_databank_close_report",
    "open_databank_close_dialog",
    "on_day_double",
    "_start_edit",
    "_import_from_excel_entry",
    "_import_from_excel_entry_worker",
    "_import_encoder_batch",
    "_import_from_excel_core",
)

TOP_LEVEL_FUNCTIONS = (
    "import_from_excel_with_reasons",
    "_spina_perf_refresh_data_grid",
    "_spina_auto_close_one_day",
    "_spina_run_auto_daily_close",
    "_spina_save_closed_collector_route_copy",
)

LEGACY_REPLACED_METHODS = ("_build_data_tab",)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _root_nodes(tree: ast.Module) -> dict[tuple[str | None, str], ast.AST]:
    result: dict[tuple[str | None, str], ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[(None, node.name)] = node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[(node.name, child.name)] = child
    return result


def _app_bindings(tree: ast.AST) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
            ):
                result.setdefault(target.attr, []).append({
                    "line": node.lineno,
                    "value": ast.unparse(value) if value is not None else "",
                })
    for items in result.values():
        items.sort(key=lambda item: item["line"])
    return result


def _called_names(node: ast.AST) -> list[str]:
    names = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        try:
            names.add(ast.unparse(child.func))
        except Exception:
            pass
    return sorted(names)


def _default_expressions(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    result = []
    for default in list(node.args.defaults) + [item for item in node.args.kw_defaults if item is not None]:
        result.append(ast.unparse(default))
    return result


def _global_name_reads(node: ast.AST) -> list[str]:
    local = set()
    reads = set()
    for child in ast.walk(node):
        if isinstance(child, ast.arg):
            local.add(child.arg)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
            local.add(child.name)
        elif isinstance(child, ast.Name):
            if isinstance(child.ctx, (ast.Store, ast.Param)):
                local.add(child.id)
            elif isinstance(child.ctx, ast.Load):
                reads.add(child.id)
    return sorted(reads - local - {"self"})


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    roots = _root_nodes(tree)
    bindings = _app_bindings(tree)

    if EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)
    EXPORT_DIR.mkdir(parents=True)

    inventory = []
    total_lines = 0

    for class_name, names in (("App", APP_METHODS), (None, TOP_LEVEL_FUNCTIONS)):
        for name in names:
            node = roots.get((class_name, name))
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)), (class_name, name)
            start = node.lineno
            end = node.end_lineno or start
            raw = "".join(lines[start - 1:end])
            moved_source = textwrap.dedent(raw) if class_name else raw
            file_name = ("App__" if class_name else "global__") + name + ".py"
            (EXPORT_DIR / file_name).write_text(moved_source, encoding="utf-8")
            later_bindings = [item for item in bindings.get(name, []) if item["line"] > end]
            item = {
                "class_name": class_name,
                "name": name,
                "start_line": start,
                "end_line": end,
                "line_count": end - start + 1,
                "raw_sha256": _sha256(raw),
                "moved_source_sha256": _sha256(moved_source),
                "ast_sha256": _sha256(ast.dump(node, include_attributes=False)),
                "signature": ast.unparse(node.args),
                "default_expressions": _default_expressions(node),
                "global_name_reads": _global_name_reads(node),
                "calls": _called_names(node),
                "nested_function_count": sum(
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not node
                    for child in ast.walk(node)
                ),
                "later_app_bindings": later_bindings,
                "export_file": file_name,
            }
            inventory.append(item)
            total_lines += item["line_count"]

    replaced = []
    for name in LEGACY_REPLACED_METHODS:
        node = roots.get(("App", name))
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)), name
        start = node.lineno
        end = node.end_lineno or start
        later = [item for item in bindings.get(name, []) if item["line"] > end]
        assert later, name
        replaced.append({
            "name": name,
            "start_line": start,
            "end_line": end,
            "line_count": end - start + 1,
            "raw_sha256": _sha256("".join(lines[start - 1:end])),
            "ast_sha256": _sha256(ast.dump(node, include_attributes=False)),
            "latest_binding": later[-1],
        })

    report = {
        "scope": "Complete active Data Bank feature/controller roots; shared LoanDB engine excluded",
        "function_count": len(inventory),
        "total_lines": total_lines,
        "app_method_count": len(APP_METHODS),
        "top_level_function_count": len(TOP_LEVEL_FUNCTIONS),
        "inventory": inventory,
        "legacy_replaced": replaced,
        "union_global_name_reads": sorted({name for item in inventory for name in item["global_name_reads"]}),
        "union_calls": sorted({name for item in inventory for name in item["calls"]}),
    }

    assert len(inventory) == 23, len(inventory)
    assert total_lines == 2993, total_lines
    assert len(replaced) == 1 and replaced[0]["line_count"] == 67, replaced
    assert replaced[0]["latest_binding"]["value"] == "_spina_v15_build_data_tab", replaced

    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "function_count": report["function_count"],
        "total_lines": report["total_lines"],
        "legacy_replaced_lines": replaced[0]["line_count"],
        "global_dependency_count": len(report["union_global_name_reads"]),
    }, indent=2))


if __name__ == "__main__":
    main()
