from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT_PATH = ROOT / "docs" / "wave69-candidates.json"

SQL_WRITE_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|REPLACE)\b", re.I)
WRITE_NAMES = {
    "add", "archive", "clear", "close", "commit", "create", "delete", "drop",
    "import", "insert", "merge", "remove", "rename", "replace", "restore",
    "save", "set", "update", "upsert", "write",
}
FILESYSTEM_WRITE_NAMES = {
    "copy", "copy2", "copyfile", "makedirs", "mkdir", "move", "remove",
    "rename", "replace", "rmdir", "rmtree", "save", "unlink", "write_bytes",
    "write_text",
}
UI_PREFIXES = ("tk.", "ttk.", "messagebox.", "simpledialog.", "filedialog.")
PROTECTED_TERMS = (
    "backup", "restore", "password", "login", "auth", "permission", "payroll",
    "interest", "balance", "payment", "transaction", "close_day", "delete_day",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = []
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f"={ast.unparse(default)}"
        args.append(text)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        args.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f"={ast.unparse(default)}"
        args.append(text)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    return ", ".join(args)


def source_hash(lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno") - 1
    end = getattr(node, "end_lineno")
    return hashlib.sha256("".join(lines[start:end]).encode("utf-8")).hexdigest()


def analyze_method(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    calls: list[str] = []
    db_calls: list[str] = []
    db_write_calls: list[str] = []
    filesystem_write_calls: list[str] = []
    sql_write_literals: list[str] = []
    ui_calls: list[str] = []

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = dotted(child.func)
            if name:
                calls.append(name)
                if name.startswith("self.db."):
                    db_calls.append(name)
                    leaf = name.rsplit(".", 1)[-1].lower()
                    if any(leaf == prefix or leaf.startswith(prefix + "_") for prefix in WRITE_NAMES):
                        db_write_calls.append(name)
                leaf = name.rsplit(".", 1)[-1].lower()
                if leaf in FILESYSTEM_WRITE_NAMES:
                    filesystem_write_calls.append(name)
                if name == "open" or name.endswith(".open"):
                    for arg in child.args[1:2]:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            if any(mode in arg.value for mode in ("w", "a", "x", "+")):
                                filesystem_write_calls.append(name)
                if name.startswith(UI_PREFIXES) or any(part in name for part in (".pack", ".grid", ".place", ".bind", ".column", ".heading")):
                    ui_calls.append(name)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            if SQL_WRITE_RE.search(child.value):
                sql_write_literals.append(child.value[:160])

    start = node.lineno
    end = node.end_lineno or start
    count = end - start + 1
    lowered_name = node.name.lower()
    protected_terms = [term for term in PROTECTED_TERMS if term in lowered_name]
    presentation_like = len(set(ui_calls)) >= 5
    no_db = not db_calls
    read_only_db = bool(db_calls) and not db_write_calls and not sql_write_literals

    score = count
    score += min(len(set(ui_calls)), 20) * 5
    score += 45 if presentation_like else 0
    score += 35 if no_db else 0
    score += 20 if read_only_db else 0
    score -= len(set(db_write_calls)) * 120
    score -= len(sql_write_literals) * 160
    score -= len(set(filesystem_write_calls)) * 90
    score -= len(protected_terms) * 80

    return {
        "name": node.name,
        "start_line": start,
        "end_line": end,
        "lines": count,
        "signature": signature(node),
        "source_sha256": source_hash(lines, node),
        "calls": sorted(set(calls)),
        "db_calls": sorted(set(db_calls)),
        "db_write_calls": sorted(set(db_write_calls)),
        "filesystem_write_calls": sorted(set(filesystem_write_calls)),
        "sql_write_literals": sorted(set(sql_write_literals)),
        "ui_call_count": len(set(ui_calls)),
        "presentation_like": presentation_like,
        "no_db": no_db,
        "read_only_db": read_only_db,
        "protected_terms": protected_terms,
        "score": score,
    }


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP_PATH))
    app_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )

    candidates = []
    for node in app_class.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (node.end_lineno or node.lineno) - node.lineno + 1 < 90:
            continue
        candidates.append(analyze_method(lines, node))

    candidates.sort(key=lambda item: (item["score"], item["lines"]), reverse=True)
    report = {
        "source_file": APP_PATH.name,
        "source_commit_note": "Generated from the Wave 69 branch rooted at the Wave 68 squash merge.",
        "app_method_count_over_90_lines": len(candidates),
        "safe_priority": [
            item for item in candidates
            if not item["db_write_calls"]
            and not item["sql_write_literals"]
            and not item["filesystem_write_calls"]
            and not item["protected_terms"]
        ][:15],
        "all_candidates": candidates[:30],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wave 69 candidates: {len(candidates)} methods >= 90 lines")
    for item in report["safe_priority"][:10]:
        print(
            f"{item['name']}: {item['lines']} lines, score={item['score']}, "
            f"db={len(item['db_calls'])}, ui={item['ui_call_count']}"
        )


if __name__ == "__main__":
    main()
