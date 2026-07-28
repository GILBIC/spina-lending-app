from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
META_PATH = ROOT / "docs" / "wave70-client-new-meta.json"
SOURCE_PATH = ROOT / "docs" / "wave70-client-new-source.txt"
TARGET = "_is_client_new"
EXPECTED_LINES = 124
SQL_WRITE_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|REPLACE)\b", re.I)
WRITE_PREFIXES = (
    "add", "archive", "clear", "commit", "create", "delete", "drop", "import",
    "insert", "merge", "remove", "rename", "replace", "restore", "save", "set",
    "update", "upsert", "write",
)
FS_WRITE_NAMES = {
    "copy", "copy2", "copyfile", "makedirs", "mkdir", "move", "remove", "rename",
    "replace", "rmdir", "rmtree", "save", "unlink", "write_bytes", "write_text",
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def signature(node: ast.FunctionDef) -> str:
    parts: list[str] = []
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if default is not None:
            text += f"={ast.unparse(default)}"
        parts.append(text)
    if node.args.vararg:
        parts.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if default is not None:
            text += f"={ast.unparse(default)}"
        parts.append(text)
    if node.args.kwarg:
        parts.append(f"**{node.args.kwarg.arg}")
    return ", ".join(parts)


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP_PATH))
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    matches = [node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == TARGET]
    assert len(matches) == 1, f"Expected one App.{TARGET}, found {len(matches)}"
    node = matches[0]
    start = node.lineno
    end = node.end_lineno or start
    count = end - start + 1
    assert count == EXPECTED_LINES, f"Expected {EXPECTED_LINES} lines, found {count}"
    sig = signature(node)
    assert sig == "self, name, ledger_date, days=None", sig

    source = "".join(lines[start - 1:end])
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    calls: list[str] = []
    db_calls: list[str] = []
    db_write_calls: list[str] = []
    filesystem_write_calls: list[str] = []
    sql_write_literals: list[str] = []
    select_literals: list[str] = []

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = dotted(child.func)
            if name:
                calls.append(name)
                leaf = name.rsplit(".", 1)[-1].lower()
                if name.startswith("self.db.") or name.startswith("self.conn.") or name in {"conn.cursor", "cur.execute"}:
                    db_calls.append(name)
                if name.startswith("self.db.") and any(leaf == p or leaf.startswith(p + "_") for p in WRITE_PREFIXES):
                    db_write_calls.append(name)
                if leaf in FS_WRITE_NAMES:
                    filesystem_write_calls.append(name)
                if name == "open" or name.endswith(".open"):
                    for arg in child.args[1:2]:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            if any(mode in arg.value for mode in ("w", "a", "x", "+")):
                                filesystem_write_calls.append(name)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            value = child.value
            if SQL_WRITE_RE.search(value):
                sql_write_literals.append(value)
            if re.search(r"\bSELECT\b", value, re.I):
                select_literals.append(value)

    assert not db_write_calls, db_write_calls
    assert not filesystem_write_calls, filesystem_write_calls
    assert not sql_write_literals, sql_write_literals
    assert len(select_literals) == 1, select_literals

    caller_lines: list[int] = []
    for other in ast.walk(tree):
        if isinstance(other, ast.Call) and isinstance(other.func, ast.Attribute):
            if other.func.attr == TARGET:
                caller_lines.append(other.lineno)

    binding_lines: list[int] = []
    for other in ast.walk(tree):
        if not isinstance(other, ast.Assign):
            continue
        for target in other.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                if target.value.id == "App" and target.attr == TARGET:
                    binding_lines.append(other.lineno)

    meta = {
        "target": f"App.{TARGET}",
        "start_line": start,
        "end_line": end,
        "lines": count,
        "signature": sig,
        "raw_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "ast_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "calls": sorted(set(calls)),
        "db_calls": sorted(set(db_calls)),
        "db_write_calls": sorted(set(db_write_calls)),
        "filesystem_write_calls": sorted(set(filesystem_write_calls)),
        "sql_write_literals": sql_write_literals,
        "select_literals": select_literals,
        "caller_lines": sorted(caller_lines),
        "binding_lines": sorted(binding_lines),
        "read_only_boundary": True,
    }
    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    SOURCE_PATH.write_text(source, encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
