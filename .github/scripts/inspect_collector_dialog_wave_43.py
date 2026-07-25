from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT = ROOT / "wave-43-collector-dialog-inspection.md"
JSON_REPORT = ROOT / "wave-43-collector-dialog-inspection.json"

CANDIDATES = [
    "_spina_v27_collector_editor_dialog",
    "_spina_v25_build_collectors_tab",
    "_build_collectors_tab",
    "_spina_v27_build_collectors_tab",
]
BINDING_ATTRS = {
    "_collector_editor_dialog",
    "_build_collectors_tab",
    "build_collectors_tab",
}
MUTATION_SUFFIXES = {
    "commit", "rollback", "execute", "executemany", "run_write",
    "add_client", "update_client", "delete_client", "archive_client",
    "restore_client", "renew_client", "add_transaction", "update_transaction",
    "delete_transaction", "set_transaction", "set_client_note", "save_settings",
    "_save_client_notes", "close_databank_day", "reopen_databank_day",
    "write", "write_text", "write_bytes", "unlink", "remove", "rmtree",
    "rename", "replace", "dump", "dumps",
}
SQL_WRITE = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE TABLE",
)


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def source_for(node: ast.AST, lines: list[str]) -> str:
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def target_name(node: ast.AST) -> str:
    parts = chain(node)
    return ".".join(parts)


def summarize(node: ast.FunctionDef, lines: list[str]) -> dict[str, object]:
    source = source_for(node, lines)
    nested = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    calls: set[str] = set()
    db_calls: set[str] = set()
    mutation_calls: set[str] = set()
    sql_writes: set[str] = set()
    global_reads: set[str] = set()
    local_names = {arg.arg for arg in node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        local_names.add(node.args.vararg.arg)
    if node.args.kwarg:
        local_names.add(node.args.kwarg.arg)
    for item in ast.walk(node):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if item is not node and hasattr(item, "args"):
                for arg in item.args.args + item.args.kwonlyargs:
                    local_names.add(arg.arg)
                if item.args.vararg:
                    local_names.add(item.args.vararg.arg)
                if item.args.kwarg:
                    local_names.add(item.args.kwarg.arg)
        if isinstance(item, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        local_names.add(sub.id)
        if isinstance(item, ast.Call):
            full = target_name(item.func)
            if full:
                calls.add(full)
                suffix = full.split(".")[-1].lower()
                if full.startswith("self.db") or suffix in {"cursor", "execute", "executemany"}:
                    db_calls.add(full)
                if suffix in MUTATION_SUFFIXES:
                    mutation_calls.add(full)
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            upper = " ".join(item.value.upper().split())
            for token in SQL_WRITE:
                if token in upper:
                    sql_writes.add(token)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load):
            global_reads.add(item.id)

    builtin_names = set(dir(__builtins__))
    global_reads -= local_names
    global_reads -= builtin_names
    global_reads.discard(node.name)
    global_reads -= set(nested)

    signature = ast.unparse(node.args)
    return {
        "name": node.name,
        "start": node.lineno,
        "end": node.end_lineno,
        "lines": node.end_lineno - node.lineno + 1,
        "signature": signature,
        "sha256": hashlib.sha256(normalized(source).encode("utf-8")).hexdigest(),
        "nested_callbacks": nested,
        "global_reads": sorted(global_reads),
        "calls": sorted(calls),
        "db_calls": sorted(db_calls),
        "mutation_calls": sorted(mutation_calls),
        "sql_writes": sorted(sql_writes),
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)

    functions = {
        node.name: node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in CANDIDATES
    }
    missing = [name for name in CANDIDATES if name not in functions]
    if missing:
        raise RuntimeError(f"Missing Wave 43 candidates: {missing}")

    summaries = [summarize(functions[name], lines) for name in CANDIDATES]

    bindings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        value_name = target_name(value)
        for target in targets:
            target_full = target_name(target)
            if not target_full:
                continue
            attr = target_full.split(".")[-1]
            if attr in BINDING_ATTRS or value_name in CANDIDATES:
                bindings.append({
                    "line": node.lineno,
                    "target": target_full,
                    "value": value_name or ast.dump(value, include_attributes=False),
                    "source": source_for(node, lines).strip(),
                })
    bindings.sort(key=lambda item: int(item["line"]))

    references: dict[str, list[dict[str, object]]] = {name: [] for name in CANDIDATES}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in references:
            references[node.id].append({
                "line": getattr(node, "lineno", 0),
                "context": type(node.ctx).__name__,
            })
    for values in references.values():
        values.sort(key=lambda item: int(item["line"]))

    app_methods: dict[str, dict[str, object]] = {}
    app = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"), None)
    if app is not None:
        for member in app.body:
            if isinstance(member, ast.FunctionDef) and member.name in BINDING_ATTRS:
                app_methods[member.name] = {
                    "line": member.lineno,
                    "end": member.end_lineno,
                    "lines": member.end_lineno - member.lineno + 1,
                    "sha256": hashlib.sha256(
                        normalized(source_for(member, lines)).encode("utf-8")
                    ).hexdigest(),
                }

    result = {
        "desktop_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "candidates": summaries,
        "bindings": bindings,
        "references": references,
        "app_methods": app_methods,
    }
    JSON_REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")

    rows = [
        "# Wave 43 Collector Dialog Binding Inspection",
        "",
        "Generated from the exact pull-request head.",
        "",
        "## Candidate summaries",
        "",
    ]
    for item in summaries:
        rows.extend([
            f"### `{item['name']}`",
            "",
            f"- Source: lines {item['start']}–{item['end']} ({item['lines']} lines)",
            f"- Signature: `{item['signature']}`",
            f"- Normalized SHA-256: `{item['sha256']}`",
            f"- Nested callbacks: {', '.join(item['nested_callbacks']) or 'none'}",
            f"- Global reads: {', '.join(item['global_reads']) or 'none'}",
            f"- Database calls: {', '.join(item['db_calls']) or 'none'}",
            f"- Mutation/file calls: {', '.join(item['mutation_calls']) or 'none'}",
            f"- SQL writes: {', '.join(item['sql_writes']) or 'none'}",
            "",
        ])

    rows.extend(["## Runtime binding assignments", ""])
    for item in bindings:
        rows.append(
            f"- Line {item['line']}: `{item['source']}`"
        )
    if not bindings:
        rows.append("- none")

    rows.extend(["", "## Candidate reference counts", ""])
    for name in CANDIDATES:
        refs = references[name]
        load_count = sum(1 for item in refs if item["context"] == "Load")
        store_count = sum(1 for item in refs if item["context"] == "Store")
        rows.append(
            f"- `{name}`: {len(refs)} total references ({load_count} loads, {store_count} stores); "
            f"lines: {', '.join(str(item['line']) for item in refs)}"
        )

    rows.extend(["", "## Original App methods with matching names", ""])
    if app_methods:
        for name, item in sorted(app_methods.items()):
            rows.append(
                f"- `App.{name}`: lines {item['line']}–{item['end']} ({item['lines']} lines), "
                f"SHA `{item['sha256']}`"
            )
    else:
        rows.append("- none")

    REPORT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
