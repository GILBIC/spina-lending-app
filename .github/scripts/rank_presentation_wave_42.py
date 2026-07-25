from __future__ import annotations

import ast
import builtins
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT = ROOT / "wave-42-candidates.md"
TARGET_CLASS = "App"
TARGET_METHOD = "_run_long_task"

UI_NAMES = {
    "tk", "ttk", "messagebox", "Toplevel", "Treeview", "Canvas", "Label",
    "Button", "Entry", "Combobox", "Notebook", "PanedWindow", "Listbox",
    "Text", "StringVar", "BooleanVar", "IntVar", "DoubleVar", "Frame",
    "Scrollbar", "Checkbutton", "Radiobutton", "Spinbox", "Progressbar",
    "pack", "grid", "place", "bind", "geometry", "title", "transient",
    "grab_set", "protocol", "winfo_rootx", "winfo_rooty",
}
MUTATION_SUFFIXES = {
    "commit", "rollback", "execute", "executemany", "run_write", "add_client",
    "update_client", "delete_client", "archive_client", "restore_client",
    "renew_client", "add_transaction", "update_transaction", "delete_transaction",
    "set_transaction", "set_client_note", "save_settings", "_save_client_notes",
    "close_databank_day", "reopen_databank_day", "write", "write_text",
    "write_bytes", "unlink", "remove", "rmtree", "rename",
}
READ_SUFFIXES = {"fetchone", "fetchall", "fetchmany", "get_all_areas", "get_client", "get_clients"}
FINANCE_WORDS = {
    "payment", "principal", "interest", "balance", "renew", "offset", "advance",
    "adv", "pass", "7x7", "loan", "collection", "collector", "payroll",
}
SQL_WRITE = ("INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE", "DROP TABLE")


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


def summarize(name: str, node: ast.AST, kind: str) -> dict[str, object]:
    names: set[str] = set()
    strings: list[str] = []
    ui_hits: set[str] = set()
    db_calls: set[str] = set()
    mutation_calls: set[str] = set()
    read_calls: set[str] = set()
    finance_hits: set[str] = set()
    sql_writes: set[str] = set()

    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            names.add(item.id)
            if item.id in UI_NAMES:
                ui_hits.add(item.id)
        elif isinstance(item, ast.Attribute):
            parts = chain(item)
            if parts:
                names.update(parts)
                ui_hits.update(set(parts) & UI_NAMES)
        elif isinstance(item, ast.Call):
            parts = chain(item.func)
            call = ".".join(parts)
            if call:
                suffix = parts[-1].lower()
                if "self.db" in call or suffix in {"cursor", "execute", "executemany"}:
                    db_calls.add(call)
                if suffix in MUTATION_SUFFIXES:
                    mutation_calls.add(call)
                if suffix in READ_SUFFIXES:
                    read_calls.add(call)
        elif isinstance(item, ast.Constant) and isinstance(item.value, str):
            value = item.value
            strings.append(value)
            upper = " ".join(value.upper().split())
            for token in SQL_WRITE:
                if token in upper:
                    sql_writes.add(token)

    lower_blob = " ".join([name.lower(), *[x.lower() for x in names], *[s.lower() for s in strings]])
    for word in FINANCE_WORDS:
        if word in lower_blob:
            finance_hits.add(word)

    lines = node.end_lineno - node.lineno + 1
    safety_penalty = (
        len(mutation_calls) * 30
        + len(sql_writes) * 50
        + len(db_calls) * 8
        + len(finance_hits) * 2
    )
    ui_score = len(ui_hits) * 5
    rank = lines + ui_score - safety_penalty
    return {
        "name": name,
        "kind": kind,
        "start": node.lineno,
        "end": node.end_lineno,
        "lines": lines,
        "rank": rank,
        "ui_hits": sorted(ui_hits),
        "db_calls": sorted(db_calls),
        "mutation_calls": sorted(mutation_calls),
        "read_calls": sorted(read_calls),
        "finance_hits": sorted(finance_hits),
        "sql_writes": sorted(sql_writes),
    }


def target_details(node: ast.FunctionDef, text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1 : node.end_lineno])
    calls: set[str] = set()
    strings: set[str] = set()
    locals_bound: set[str] = set()
    loads: set[str] = set()
    nested: list[str] = []

    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg:
        args.append(node.args.vararg)
    if node.args.kwarg:
        args.append(node.args.kwarg)
    locals_bound.update(arg.arg for arg in args)

    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            full = ".".join(chain(item.func))
            if full:
                calls.add(full)
        elif isinstance(item, ast.Name):
            if isinstance(item.ctx, ast.Store):
                locals_bound.add(item.id)
            elif isinstance(item.ctx, ast.Load):
                loads.add(item.id)
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item is not node:
            nested.append(item.name)
            locals_bound.add(item.name)
        elif isinstance(item, ast.Constant) and isinstance(item.value, str):
            cleaned = " ".join(item.value.split())
            if cleaned and len(cleaned) <= 140:
                strings.add(cleaned)

    global_reads = sorted(loads - locals_bound - set(dir(builtins)))
    signature = ast.unparse(node.args)
    return [
        "# Detailed inspection: `App._run_long_task`",
        "",
        f"- Signature: `{TARGET_METHOD}({signature})`",
        f"- Source: lines {node.lineno}–{node.end_lineno} ({node.end_lineno - node.lineno + 1} lines)",
        f"- Normalized SHA-256: `{hashlib.sha256(normalized(source).encode('utf-8')).hexdigest()}`",
        f"- Nested callbacks: {', '.join(nested) or 'none'}",
        f"- Global reads: {', '.join(global_reads) or 'none'}",
        f"- Calls: {', '.join(sorted(calls)) or 'none'}",
        "- Short UI/status strings:",
        *[f"  - `{value}`" for value in sorted(strings)],
        "",
    ]


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    candidates: list[dict[str, object]] = []
    target_node: ast.FunctionDef | None = None

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            item = summarize(node.name, node, "top-level function")
            if item["lines"] >= 180:
                candidates.append(item)
        elif isinstance(node, ast.ClassDef):
            if node.name != TARGET_CLASS:
                item = summarize(node.name, node, "top-level class")
                if item["lines"] >= 180:
                    candidates.append(item)
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    item = summarize(f"{node.name}.{member.name}", member, "method")
                    if item["lines"] >= 180:
                        candidates.append(item)
                    if node.name == TARGET_CLASS and member.name == TARGET_METHOD:
                        target_node = member

    if target_node is None:
        raise RuntimeError(f"Missing {TARGET_CLASS}.{TARGET_METHOD}")

    candidates.sort(
        key=lambda item: (
            bool(item["mutation_calls"] or item["sql_writes"]),
            bool(item["db_calls"]),
            -int(item["rank"]),
            -int(item["lines"]),
            str(item["name"]),
        )
    )

    rows = [
        "# Wave 42 Presentation Candidate Ranking",
        "",
        "Generated by AST analysis of the current desktop monolith.",
        "Candidates are ordered by low mutation risk, low database coupling, UI density, and size.",
        "",
    ]
    for index, item in enumerate(candidates[:60], start=1):
        rows.extend([
            f"## {index}. `{item['name']}`",
            "",
            f"- Kind: {item['kind']}",
            f"- Source: lines {item['start']}–{item['end']} ({item['lines']} lines)",
            f"- Rank: {item['rank']}",
            f"- UI hits: {', '.join(item['ui_hits']) or 'none'}",
            f"- Database calls: {', '.join(item['db_calls']) or 'none'}",
            f"- Mutation/file calls: {', '.join(item['mutation_calls']) or 'none'}",
            f"- Read helpers: {', '.join(item['read_calls']) or 'none'}",
            f"- Financial/business words: {', '.join(item['finance_hits']) or 'none'}",
            f"- SQL writes: {', '.join(item['sql_writes']) or 'none'}",
            "",
        ])

    rows.extend(target_details(target_node, text))
    REPORT.write_text("\n".join(rows), encoding="utf-8")
    print(f"Wrote {REPORT.name} with {min(len(candidates), 60)} ranked candidates and target detail.")


if __name__ == "__main__":
    main()
