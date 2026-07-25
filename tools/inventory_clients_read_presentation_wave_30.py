"""Inventory the high-volume Clients read/presentation Wave 30 candidates."""

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
OUT = ROOT / "artifacts" / "clients-read-presentation-wave-30-inventory.json"

TARGETS = (
    "_db_get_client_picture",
    "_app__selected_client_name_and_lt",
    "_app_set_selected_client_picture",
    "_app_clear_selected_client_picture",
    "_app_install_clients_picture_ui",
    "_spina_perf_clients_rows",
    "_spina_perf_refresh_clients",
    "_spina_build_client_info_logs_tab",
    "_spina_render_client_info_logs",
    "_spina_refresh_client_info_logs",
    "_spina__client_due_meta",
    "_spina_route_notice_for_client",
)

SQL_WRITE_WORDS = (
    "insert into", "update ", "delete from", "truncate ", "alter table",
    "drop table", "create table", "commit", "rollback",
)
FILE_WRITE_CALLS = {
    "write", "write_text", "write_bytes", "unlink", "remove", "rename",
    "replace", "mkdir", "rmdir", "copy", "copy2", "move", "save",
}
DB_WRITE_PREFIXES = (
    "set_", "clear_", "update_", "delete_", "add_", "insert_", "save_",
    "link_", "unlink_", "archive_", "restore_",
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


def source_segment(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def local_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names = {
        arg.arg
        for arg in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
    }
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


def string_literals(node: ast.AST) -> list[str]:
    return [
        item.value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    ]


def mutation_report(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, object]:
    sql_hits: set[str] = set()
    file_hits: set[str] = set()
    db_write_hits: set[str] = set()
    open_write_modes: set[str] = set()
    state_writes: set[str] = set()

    for literal in string_literals(node):
        lower = literal.lower()
        for word in SQL_WRITE_WORDS:
            if word in lower:
                sql_hits.add(word.strip())

    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            call = dotted(item.func)
            leaf = call.rsplit(".", 1)[-1]
            if leaf in FILE_WRITE_CALLS:
                file_hits.add(call)
            if call.startswith("self.db.") and leaf.startswith(DB_WRITE_PREFIXES):
                db_write_hits.add(call)
            if leaf == "open":
                mode = None
                if len(item.args) >= 2 and isinstance(item.args[1], ast.Constant):
                    mode = item.args[1].value
                for kw in item.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if isinstance(mode, str) and any(flag in mode for flag in "wax+"):
                    open_write_modes.add(mode)
        elif isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                if isinstance(target, ast.Attribute):
                    state_writes.add(ast.unparse(target))
                elif isinstance(target, ast.Subscript):
                    state_writes.add(ast.unparse(target))

    return {
        "sql_write_hits": sorted(sql_hits),
        "database_mutation_calls": sorted(db_write_hits),
        "file_mutation_calls": sorted(file_hits),
        "open_write_modes": sorted(open_write_modes),
        "attribute_or_subscript_writes": sorted(state_writes),
    }


def runtime_wiring(tree: ast.Module, lines: list[str]) -> dict[str, list[dict[str, object]]]:
    """Capture top-level assignments, setattr calls, and dynamic statements using targets."""
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    target_set = set(TARGETS)
    ignored = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)

    for statement in tree.body:
        if isinstance(statement, ignored):
            continue
        statement_source = source_segment(lines, statement)
        names = {
            item.id
            for item in ast.walk(statement)
            if isinstance(item, ast.Name) and item.id in target_set
        }
        for item in ast.walk(statement):
            if isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value in target_set:
                names.add(item.value)
        if not names:
            continue

        kind = type(statement).__name__
        for item in ast.walk(statement):
            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                kind = "assignment"
                break
            if isinstance(item, ast.Call) and dotted(item.func) == "setattr":
                kind = "setattr"
                break

        record = {
            "line": statement.lineno,
            "end_line": statement.end_lineno,
            "kind": kind,
            "source": statement_source,
        }
        for name in sorted(names):
            result[name].append(record)
    return result


def architecture_records() -> dict[str, list[dict[str, object]]]:
    data = json.loads(MAP.read_text(encoding="utf-8"))
    records: dict[str, list[dict[str, object]]] = defaultdict(list)
    for symbol in data.get("symbols", []):
        if symbol.get("file") != SOURCE.name:
            continue
        leaf = str(symbol.get("name") or "")
        if leaf in TARGETS:
            records[leaf].append(symbol)
    return records


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))

    definitions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = defaultdict(list)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS:
            definitions[node.name].append(node)

    missing = [name for name in TARGETS if name not in definitions]
    assert not missing, f"Missing Wave 30 candidates: {missing}"

    wiring = runtime_wiring(tree, lines)
    map_records = architecture_records()
    report: dict[str, object] = {
        "source": SOURCE.name,
        "source_blob": git_blob(SOURCE),
        "branch_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "target_count": len(TARGETS),
        "candidates": {},
        "total_effective_lines": 0,
        "write_review": [],
    }

    total_effective_lines = 0
    write_review: list[str] = []
    for name in TARGETS:
        nodes = definitions[name]
        rows = []
        for index, node in enumerate(nodes, start=1):
            source = source_segment(lines, node)
            locals_ = local_names(node)
            globals_ = sorted(
                {
                    item.id
                    for item in ast.walk(node)
                    if isinstance(item, ast.Name)
                    and isinstance(item.ctx, ast.Load)
                    and item.id not in locals_
                    and item.id not in {"True", "False", "None"}
                }
            )
            calls = sorted(
                {
                    dotted(item.func)
                    for item in ast.walk(node)
                    if isinstance(item, ast.Call) and dotted(item.func)
                }
            )
            mutations = mutation_report(node)
            is_effective = index == len(nodes)
            line_count = (node.end_lineno or node.lineno) - node.lineno + 1
            if is_effective:
                total_effective_lines += line_count
                if (
                    mutations["sql_write_hits"]
                    or mutations["database_mutation_calls"]
                    or mutations["file_mutation_calls"]
                    or mutations["open_write_modes"]
                ):
                    write_review.append(name)
            rows.append(
                {
                    "occurrence": index,
                    "effective": is_effective,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "line_count": line_count,
                    "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "source": source,
                    "calls": calls,
                    "global_dependencies": globals_,
                    "nested_definitions": sorted(
                        item.name
                        for item in ast.walk(node)
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        and item is not node
                    ),
                    "mutations": mutations,
                }
            )

        report["candidates"][name] = {
            "definition_count": len(nodes),
            "definitions": rows,
            "runtime_wiring": wiring.get(name, []),
            "map_records": [
                {
                    "id": record.get("id"),
                    "qualified_name": record.get("qualified_name"),
                    "feature": record.get("feature"),
                    "risk": record.get("risk"),
                    "callers": record.get("callers"),
                    "calls_resolved": record.get("calls_resolved"),
                }
                for record in map_records.get(name, [])
            ],
        }

    report["total_effective_lines"] = total_effective_lines
    report["write_review"] = sorted(set(write_review))
    assert 450 <= total_effective_lines <= 900, total_effective_lines

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "Wave 30 inventory passed:",
        len(TARGETS),
        "candidates,",
        total_effective_lines,
        "effective lines,",
        len(write_review),
        "write-review candidates",
    )


if __name__ == "__main__":
    main()
