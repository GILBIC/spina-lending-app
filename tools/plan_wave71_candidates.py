from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUTPUT_PATH = ROOT / "docs" / "wave71-candidates.json"

SQL_WRITE_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|REPLACE)\b", re.I)
FILE_WRITE_NAMES = {
    "write_text", "write_bytes", "open", "unlink", "remove", "rename", "replace",
    "mkdir", "makedirs", "rmdir", "rmtree", "copy", "copy2", "move", "dump",
}
PROTECTED_TERMS = {
    "payment", "principal", "balance", "interest", "renew", "loan", "collector_payment",
    "auth", "login", "password", "permission", "role", "account", "user",
    "backup", "restore", "close_day", "day_close", "delete_day", "payroll",
    "sss", "philhealth", "pagibig", "overtime", "holiday", "night_diff",
    "gcash", "receipt", "proof", "transaction", "advance", "pass_count",
}
PRESENTATION_TERMS = {
    "dialog", "tab", "frame", "label", "button", "tree", "listbox", "canvas",
    "scroll", "window", "show", "render", "display", "refresh", "layout", "style",
    "preview", "viewer", "editor", "route", "report", "statement", "ledger",
}


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
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


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ast_hash(node: ast.AST) -> str:
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def top_level_app_bindings(tree: ast.Module) -> dict[str, list[str]]:
    bindings: dict[str, list[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
            ):
                bindings.setdefault(target.attr, []).append(ast.unparse(node.value))
    return bindings


def method_call_counts(tree: ast.Module) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            counts[node.func.attr] = counts.get(node.func.attr, 0) + 1
    return counts


def analyze_method(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source: str,
    bindings: dict[str, list[str]],
    call_counts: dict[str, int],
) -> dict[str, object]:
    segment = ast.get_source_segment(source, node) or ""
    lowered = segment.lower()
    string_literals = [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]
    dotted_calls = [
        dotted(child.func)
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
    ]
    sql_writes = [value for value in string_literals if SQL_WRITE_RE.search(value)]
    file_write_calls = sorted({
        name for name in dotted_calls
        if name.rsplit(".", 1)[-1] in FILE_WRITE_NAMES
    })
    db_commit_calls = sorted({name for name in dotted_calls if name.endswith(".commit")})
    db_rollback_calls = sorted({name for name in dotted_calls if name.endswith(".rollback")})
    protected_hits = sorted(term for term in PROTECTED_TERMS if term in lowered)
    presentation_hits = sorted(term for term in PRESENTATION_TERMS if term in lowered)
    line_count = (node.end_lineno or node.lineno) - node.lineno + 1
    overridden_by = bindings.get(node.name, [])

    has_db_write = bool(sql_writes or db_commit_calls)
    has_file_write = bool(file_write_calls)
    protected = bool(protected_hits)
    already_replaced = bool(overridden_by)
    read_only = not has_db_write and not has_file_write

    score = line_count
    score += min(len(presentation_hits) * 5, 35)
    score += 15 if read_only else -80
    score -= min(len(protected_hits) * 15, 120)
    score -= 150 if already_replaced else 0
    score += min(call_counts.get(node.name, 0) * 2, 20)

    classification = "candidate"
    if already_replaced:
        classification = "already-replaced"
    elif has_db_write or has_file_write:
        classification = "writes"
    elif protected:
        classification = "protected"
    elif line_count < 60:
        classification = "too-small"

    return {
        "method": f"App.{node.name}",
        "name": node.name,
        "start_line": node.lineno,
        "end_line": node.end_lineno,
        "line_count": line_count,
        "signature": signature(node),
        "raw_sha256": source_hash(segment),
        "ast_sha256": ast_hash(node),
        "call_count": call_counts.get(node.name, 0),
        "classification": classification,
        "score": score,
        "read_only": read_only,
        "sql_write_literals": sql_writes,
        "database_commit_calls": db_commit_calls,
        "database_rollback_calls": db_rollback_calls,
        "filesystem_write_calls": file_write_calls,
        "protected_hits": protected_hits,
        "presentation_hits": presentation_hits,
        "overridden_by": overridden_by,
    }


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP_PATH))
    app_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    bindings = top_level_app_bindings(tree)
    call_counts = method_call_counts(tree)
    methods = [
        analyze_method(node, source, bindings, call_counts)
        for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    ranked = sorted(
        (item for item in methods if item["classification"] == "candidate"),
        key=lambda item: (int(item["score"]), int(item["line_count"])),
        reverse=True,
    )
    rejected = sorted(
        (item for item in methods if item["classification"] != "candidate" and int(item["line_count"]) >= 60),
        key=lambda item: int(item["line_count"]),
        reverse=True,
    )
    report = {
        "source_file": APP_PATH.name,
        "source_sha256": source_hash(source),
        "candidate_count": len(ranked),
        "top_candidates": ranked[:25],
        "large_rejected_boundaries": rejected[:40],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wave 71 planner ranked {len(ranked)} candidates")
    for item in ranked[:10]:
        print(
            f"{item['method']}: {item['line_count']} lines, score={item['score']}, "
            f"calls={item['call_count']}"
        )


if __name__ == "__main__":
    main()
