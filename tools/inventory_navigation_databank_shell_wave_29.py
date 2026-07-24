"""Inventory the high-volume Navigation + Data Bank shell Wave 29 target."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MAP = ROOT / "architecture-map.json"
OUT = ROOT / "artifacts" / "navigation-databank-shell-wave-29-inventory.json"

GROUPS = {
    "navigation": (
        "_update_data_toolbar",
        "_side_nav_items",
        "_rebuild_side_nav",
        "_refresh_side_nav_selection",
        "_header_palette",
        "_make_header_button",
        "_refresh_mode_toggle",
        "_vscroll",
        "_month_label",
        "_on_mousewheel_sync",
        "_update_toolbar_states",
    ),
    "data_bank_shell": (
        "_looks_like_data_grid",
        "_locate_data_tree",
        "_ensure_databank_edit_bindings",
        "_show_audit_tab",
        "_hide_audit_tab",
        "_resize_databank_columns",
    ),
}
TARGETS = tuple(name for names in GROUPS.values() for name in names)
PROTECTED_TERMS = (
    "principal", "interest", "allocation", "renew", "offset", "7x7",
    "password", "authenticate", "pg_dump", "backup_postgres",
    "insert into", "update clients", "delete from", "commit(",
)


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], cwd=ROOT, text=True
    ).strip()


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def segment(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def local_names(node: ast.FunctionDef) -> set[str]:
    names = {arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
            names.add(item.id)
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and item is not node:
            names.add(item.name)
    return names


def runtime_references(tree: ast.Module) -> dict[str, list[dict[str, object]]]:
    refs: dict[str, list[dict[str, object]]] = defaultdict(list)
    target_set = set(TARGETS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in target_set:
            refs[node.attr].append(
                {
                    "line": node.lineno,
                    "kind": "attribute_load" if isinstance(node.ctx, ast.Load) else "attribute_store",
                    "owner": dotted(node.value),
                }
            )
        elif isinstance(node, ast.Name) and node.id in target_set and isinstance(node.ctx, ast.Load):
            refs[node.id].append({"line": node.lineno, "kind": "name_load", "owner": ""})
    return refs


def app_assignments(tree: ast.Module) -> dict[str, list[int]]:
    result: dict[str, list[int]] = defaultdict(list)
    target_set = set(TARGETS)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "App"
                    and target.attr in target_set
                ):
                    result[target.attr].append(node.lineno)
    return result


def architecture_records() -> dict[str, dict[str, object]]:
    data = json.loads(MAP.read_text(encoding="utf-8"))
    records = {}
    for symbol in data.get("symbols", []):
        name = str(symbol.get("name") or "")
        leaf = name.rsplit(".", 1)[-1]
        if leaf in TARGETS and ".App." in name:
            records[leaf] = symbol
    return records


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))
    app_nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"]
    assert len(app_nodes) == 1, f"Expected one App class, found {len(app_nodes)}"
    app = app_nodes[0]

    methods: dict[str, list[ast.FunctionDef]] = defaultdict(list)
    for node in app.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods[node.name].append(node)

    missing = [name for name in TARGETS if name not in methods]
    duplicates = {name: len(methods[name]) for name in TARGETS if len(methods[name]) != 1}
    assert not missing, f"Missing Wave 29 targets: {missing}"
    assert not duplicates, f"Duplicate Wave 29 App methods: {duplicates}"

    refs = runtime_references(tree)
    assignments = app_assignments(tree)
    map_records = architecture_records()
    report: dict[str, object] = {
        "source": SOURCE.name,
        "source_blob": git_blob(SOURCE),
        "base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "destinations": {
            "navigation": "spina_app/navigation.py",
            "data_bank_shell": "spina_app/tabs/data_bank_shell.py",
        },
        "destination_exists": {
            "navigation": (ROOT / "spina_app" / "navigation.py").exists(),
            "data_bank_shell": (ROOT / "spina_app" / "tabs" / "data_bank_shell.py").exists(),
        },
        "groups": {},
        "total_methods": len(TARGETS),
        "total_lines": 0,
        "protected_term_hits": [],
    }

    total_lines = 0
    protected_hits: list[dict[str, object]] = []
    for group, names in GROUPS.items():
        rows = []
        for name in names:
            node = methods[name][0]
            source = segment(lines, node)
            lower = source.lower()
            hits = [term for term in PROTECTED_TERMS if term in lower]
            if hits:
                protected_hits.append({"name": name, "terms": hits})

            locals_ = local_names(node)
            globals_ = sorted(
                {
                    child.id
                    for child in ast.walk(node)
                    if isinstance(child, ast.Name)
                    and isinstance(child.ctx, ast.Load)
                    and child.id not in locals_
                    and child.id not in {"True", "False", "None"}
                }
            )
            calls = sorted(
                {
                    dotted(child.func)
                    for child in ast.walk(node)
                    if isinstance(child, ast.Call) and dotted(child.func)
                }
            )
            line_count = (node.end_lineno or node.lineno) - node.lineno + 1
            total_lines += line_count
            record = map_records.get(name, {})
            rows.append(
                {
                    "name": name,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "line_count": line_count,
                    "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "decorators": [ast.unparse(item) for item in node.decorator_list],
                    "nested_definitions": sorted(
                        item.name
                        for item in ast.walk(node)
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        and item is not node
                    ),
                    "calls": calls,
                    "global_dependencies": globals_,
                    "runtime_references": refs.get(name, []),
                    "app_assignment_lines": assignments.get(name, []),
                    "map_risk": record.get("risk"),
                    "map_feature": record.get("feature"),
                    "protected_term_hits": hits,
                }
            )
        report["groups"][group] = {
            "method_count": len(rows),
            "line_count": sum(int(row["line_count"]) for row in rows),
            "methods": rows,
        }

    report["total_lines"] = total_lines
    report["protected_term_hits"] = protected_hits
    assert total_lines >= 500, f"Wave 29 volume too small: {total_lines} lines"
    assert total_lines <= 800, f"Wave 29 volume too large: {total_lines} lines"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "Wave 29 inventory passed:",
        len(TARGETS),
        "methods,",
        total_lines,
        "lines,",
        len(protected_hits),
        "protected-term review items",
    )


if __name__ == "__main__":
    main()
