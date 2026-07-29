from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
ARCHITECTURE = Path("architecture-map.json")
JSON_REPORT = Path("wave72_databank_feature_plan.json")
MARKDOWN_REPORT = Path("wave72_databank_feature_plan.md")
DESKTOP = SOURCE.name

# Some legacy names are classified under a generic feature even though they are
# direct Data Bank tab callbacks. Include them explicitly in the inventory.
KNOWN_DATABANK_ROOTS = {
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
    "_build_data_tab",
    "on_day_double",
    "_start_edit",
    "_import_from_excel_entry",
    "_import_from_excel_entry_worker",
    "_import_encoder_batch",
    "_import_from_excel_core",
    "import_from_excel_with_reasons",
    "_spina_perf_refresh_data_grid",
}


def _is_databank_symbol(symbol: dict) -> bool:
    text = " ".join(
        str(symbol.get(key) or "")
        for key in ("feature", "name", "qualified_name", "purpose", "docstring")
    ).lower()
    return (
        symbol.get("feature") == "data bank"
        or "data bank" in text
        or "databank" in text
        or symbol.get("name") in KNOWN_DATABANK_ROOTS
    )


def _binding_value(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _app_bindings(tree: ast.AST) -> dict[str, list[dict]]:
    bindings: dict[str, list[dict]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
            ):
                bindings[target.attr].append({
                    "line": node.lineno,
                    "value": _binding_value(value),
                })
    for values in bindings.values():
        values.sort(key=lambda item: item["line"])
    return dict(bindings)


def _source_roots(tree: ast.Module) -> dict[tuple[str | None, str], ast.AST]:
    roots: dict[tuple[str | None, str], ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            roots[(None, node.name)] = node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    roots[(node.name, child.name)] = child
    return roots


def main() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    source_tree = ast.parse(source_text)
    architecture = json.loads(ARCHITECTURE.read_text(encoding="utf-8"))
    symbols = architecture.get("symbols") or []

    databank_symbols = [symbol for symbol in symbols if _is_databank_symbol(symbol)]
    application_symbols = [
        symbol for symbol in databank_symbols
        if symbol.get("file") == DESKTOP or str(symbol.get("file") or "").startswith("spina_app/")
    ]
    existing_module_symbols = [
        symbol for symbol in application_symbols
        if str(symbol.get("file") or "").startswith("spina_app/")
    ]
    desktop_symbols = [symbol for symbol in application_symbols if symbol.get("file") == DESKTOP]
    desktop_roots = [
        symbol for symbol in desktop_symbols
        if symbol.get("kind") in {"function", "method"}
        and not str(symbol.get("qualified_name") or "").endswith(".__init__")
        and symbol.get("class_name") != "LoanDB"
    ]
    database_layer = [
        symbol for symbol in desktop_symbols
        if symbol.get("class_name") == "LoanDB"
    ]

    roots = _source_roots(source_tree)
    bindings = _app_bindings(source_tree)
    candidates: list[dict] = []
    missing_roots: list[str] = []

    for symbol in sorted(desktop_roots, key=lambda item: (item.get("line") or 0, item.get("name") or "")):
        class_name = symbol.get("class_name")
        name = symbol.get("name")
        node = roots.get((class_name, name))
        if node is None:
            missing_roots.append(str(symbol.get("qualified_name") or name))
            continue
        start = int(getattr(node, "lineno", symbol.get("line") or 0))
        end = int(getattr(node, "end_lineno", symbol.get("end_line") or start) or start)
        later = [item for item in bindings.get(name, []) if item["line"] > end]
        latest = later[-1] if later else None
        candidates.append({
            "name": name,
            "class_name": class_name,
            "qualified_name": symbol.get("qualified_name"),
            "start_line": start,
            "end_line": end,
            "line_count": end - start + 1,
            "risk": symbol.get("risk"),
            "risk_flags": symbol.get("risk_flags") or [],
            "calls": symbol.get("calls_raw") or [],
            "callers": symbol.get("callers") or [],
            "nested_function_count": sum(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not node
                for child in ast.walk(node)
            ),
            "later_app_binding": latest,
            "status": "already_replaced" if latest else "desktop_active",
        })

    existing_modules = sorted({str(symbol.get("file")) for symbol in existing_module_symbols})
    lines_by_file = Counter()
    symbols_by_file = Counter()
    risks = Counter()
    for symbol in application_symbols:
        file_name = str(symbol.get("file") or "")
        lines_by_file[file_name] += int(symbol.get("lines") or 0)
        symbols_by_file[file_name] += 1
        risks[str(symbol.get("risk") or "unknown")] += 1

    active_candidates = [item for item in candidates if item["status"] == "desktop_active"]
    replaced_candidates = [item for item in candidates if item["status"] == "already_replaced"]

    report = {
        "scope": "Data Bank feature layer; LoanDB database engine remains in database layer",
        "architecture_generated_from": architecture.get("generated_from_commit"),
        "application_symbol_count": len(application_symbols),
        "application_function_lines": sum(int(symbol.get("lines") or 0) for symbol in application_symbols),
        "desktop_symbol_count": len(desktop_symbols),
        "existing_module_symbol_count": len(existing_module_symbols),
        "existing_modules": existing_modules,
        "existing_lines_by_file": dict(sorted(lines_by_file.items())),
        "symbols_by_file": dict(sorted(symbols_by_file.items())),
        "risk_counts": dict(sorted(risks.items())),
        "desktop_root_candidates": candidates,
        "desktop_active_candidates": active_candidates,
        "desktop_replaced_candidates": replaced_candidates,
        "database_layer_symbols_excluded": [
            {
                "name": symbol.get("name"),
                "line": symbol.get("line"),
                "lines": symbol.get("lines"),
                "risk": symbol.get("risk"),
            }
            for symbol in sorted(database_layer, key=lambda item: item.get("line") or 0)
        ],
        "missing_root_nodes": missing_roots,
        "totals": {
            "active_root_functions": len(active_candidates),
            "active_root_lines": sum(item["line_count"] for item in active_candidates),
            "already_replaced_root_functions": len(replaced_candidates),
            "already_replaced_root_lines": sum(item["line_count"] for item in replaced_candidates),
            "database_layer_symbols_excluded": len(database_layer),
        },
    }

    assert report["application_symbol_count"] >= 100, report["application_symbol_count"]
    assert report["application_function_lines"] >= 4500, report["application_function_lines"]
    assert len(existing_modules) >= 7, existing_modules
    assert len(candidates) >= 10, len(candidates)
    assert not missing_roots, missing_roots

    JSON_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    md = [
        "# Wave 72 Data Bank Feature Plan",
        "",
        f"- Application symbols: **{report['application_symbol_count']}**",
        f"- Application function lines: **{report['application_function_lines']:,}**",
        f"- Existing Data Bank modules: **{len(existing_modules)}**",
        f"- Active desktop root functions: **{report['totals']['active_root_functions']}** "
        f"(**{report['totals']['active_root_lines']:,} lines**)",
        f"- Already-replaced desktop roots: **{report['totals']['already_replaced_root_functions']}** "
        f"(**{report['totals']['already_replaced_root_lines']:,} lines**)",
        f"- LoanDB symbols retained in database layer: **{report['totals']['database_layer_symbols_excluded']}**",
        "",
        "## Existing modules",
        "",
    ]
    md.extend(f"- `{name}`" for name in existing_modules)
    md.extend(["", "## Active desktop functions to move", ""])
    for item in active_candidates:
        md.append(
            f"- `{item['qualified_name']}` — {item['line_count']} lines — risk `{item['risk']}`"
        )
    md.extend(["", "## Legacy roots already replaced by modules", ""])
    for item in replaced_candidates:
        binding = item.get("later_app_binding") or {}
        md.append(
            f"- `{item['qualified_name']}` — {item['line_count']} lines — "
            f"bound later to `{binding.get('value')}` at line {binding.get('line')}"
        )
    MARKDOWN_REPORT.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps(report["totals"], indent=2))
    print(f"Existing modules: {len(existing_modules)}")
    print(f"Data Bank feature lines: {report['application_function_lines']:,}")


if __name__ == "__main__":
    main()
