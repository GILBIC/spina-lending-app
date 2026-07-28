from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT_PATH = ROOT / "docs" / "wave70-candidates.json"

SQL_WRITE_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|REPLACE)\b", re.I)
DB_WRITE_PREFIXES = (
    "add", "archive", "clear", "close", "commit", "create", "delete", "drop",
    "import", "insert", "merge", "remove", "rename", "replace", "restore",
    "save", "set", "update", "upsert", "write",
)
FS_WRITE_NAMES = {
    "copy", "copy2", "copyfile", "makedirs", "mkdir", "move", "remove",
    "rename", "replace", "rmdir", "rmtree", "save", "unlink", "write_bytes",
    "write_text",
}
PROTECTED_TERMS = (
    "auth", "backup", "balance", "close_day", "delete_day", "interest", "login",
    "password", "payment", "payroll", "permission", "restore", "transaction",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    return ast.unparse(node.args)


def node_source(lines: list[str], node: ast.AST) -> str:
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def source_hash(lines: list[str], node: ast.AST) -> str:
    return hashlib.sha256(node_source(lines, node).encode("utf-8")).hexdigest()


def top_level_app_bindings(tree: ast.Module) -> dict[str, list[dict[str, object]]]:
    bindings: dict[str, list[dict[str, object]]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if not (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
            ):
                continue
            bindings.setdefault(target.attr, []).append(
                {
                    "line": node.lineno,
                    "value": ast.unparse(value) if value is not None else None,
                }
            )
    return bindings


def analyze_method(
    lines: list[str],
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    bindings: dict[str, list[dict[str, object]]],
    full_text: str,
) -> dict[str, object]:
    calls: set[str] = set()
    db_calls: set[str] = set()
    db_write_calls: set[str] = set()
    fs_write_calls: set[str] = set()
    sql_write_literals: set[str] = set()
    ui_calls: set[str] = set()

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = dotted(child.func)
            if not name:
                continue
            calls.add(name)
            if name.startswith("self.db."):
                db_calls.add(name)
                leaf = name.rsplit(".", 1)[-1].lower()
                if any(leaf == prefix or leaf.startswith(prefix + "_") for prefix in DB_WRITE_PREFIXES):
                    db_write_calls.add(name)
            leaf = name.rsplit(".", 1)[-1].lower()
            if leaf in FS_WRITE_NAMES:
                fs_write_calls.add(name)
            if name in {"open", "Path.open"} or name.endswith(".open"):
                for arg in child.args[1:2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if any(mode in arg.value for mode in ("w", "a", "x", "+")):
                            fs_write_calls.add(name)
            if (
                name.startswith(("tk.", "ttk.", "messagebox.", "simpledialog.", "filedialog."))
                or any(token in name for token in (".pack", ".grid", ".place", ".bind", ".column", ".heading"))
            ):
                ui_calls.add(name)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            if SQL_WRITE_RE.search(child.value):
                sql_write_literals.add(child.value[:160])

    count = (node.end_lineno or node.lineno) - node.lineno + 1
    protected_terms = [term for term in PROTECTED_TERMS if term in node.name.lower()]
    method_bindings = bindings.get(node.name, [])
    later_bindings = [item for item in method_bindings if int(item["line"]) > (node.end_lineno or node.lineno)]
    call_pattern = re.compile(rf"(?<!def )\b(?:self\.|App\.)?{re.escape(node.name)}\s*\(")
    call_count = len(call_pattern.findall(full_text))

    presentation_like = len(ui_calls) >= 5
    no_db = not db_calls
    read_only_db = bool(db_calls) and not db_write_calls and not sql_write_literals
    overridden_fallback = bool(later_bindings)

    score = count
    score += min(len(ui_calls), 20) * 5
    score += 45 if presentation_like else 0
    score += 35 if no_db else 0
    score += 20 if read_only_db else 0
    score += 120 if overridden_fallback else 0
    score -= len(db_write_calls) * 130
    score -= len(sql_write_literals) * 180
    score -= len(fs_write_calls) * 100
    score -= len(protected_terms) * 90

    return {
        "name": node.name,
        "start_line": node.lineno,
        "end_line": node.end_lineno,
        "lines": count,
        "signature": signature(node),
        "source_sha256": source_hash(lines, node),
        "calls": sorted(calls),
        "call_count_in_source": call_count,
        "db_calls": sorted(db_calls),
        "db_write_calls": sorted(db_write_calls),
        "filesystem_write_calls": sorted(fs_write_calls),
        "sql_write_literals": sorted(sql_write_literals),
        "ui_call_count": len(ui_calls),
        "presentation_like": presentation_like,
        "no_db": no_db,
        "read_only_db": read_only_db,
        "protected_terms": protected_terms,
        "later_app_bindings": later_bindings,
        "overridden_fallback": overridden_fallback,
        "score": score,
    }


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP_PATH))
    app_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    bindings = top_level_app_bindings(tree)

    candidates = [
        analyze_method(lines, node, bindings, text)
        for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (node.end_lineno or node.lineno) - node.lineno + 1 >= 80
    ]
    candidates.sort(key=lambda item: (int(item["score"]), int(item["lines"])), reverse=True)

    safe = [
        item
        for item in candidates
        if not item["db_write_calls"]
        and not item["sql_write_literals"]
        and not item["filesystem_write_calls"]
        and not item["protected_terms"]
    ]
    report = {
        "source_file": APP_PATH.name,
        "source_commit": "63d1328967663482b78c83cd317b984b74279728",
        "branch": "agent/high-volume-wave-70",
        "app_methods_over_80_lines": len(candidates),
        "safe_priority": safe[:20],
        "overridden_fallbacks": [item for item in candidates if item["overridden_fallback"]],
        "all_candidates": candidates[:35],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wave 70: {len(candidates)} App methods >= 80 lines")
    for item in safe[:12]:
        print(
            f"{item['name']}: {item['lines']} lines, score={item['score']}, "
            f"db={len(item['db_calls'])}, ui={item['ui_call_count']}, "
            f"overridden={item['overridden_fallback']}"
        )


if __name__ == "__main__":
    main()
