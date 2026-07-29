from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
REPORT = Path("wave72_whole_function_report.json")
EXPORT = Path("wave72_set_theme_source.py")
TARGET_CLASS = "App"
TARGET_METHOD = "set_theme"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts: list[str] = []
    positional = list(node.args.posonlyargs) + list(node.args.args)
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if default is not None:
            text += "=" + ast.unparse(default)
        parts.append(text)
    if node.args.vararg:
        parts.append("*" + node.args.vararg.arg)
    elif node.args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if default is not None:
            text += "=" + ast.unparse(default)
        parts.append(text)
    if node.args.kwarg:
        parts.append("**" + node.args.kwarg.arg)
    return ", ".join(parts)


def _qualified_call_name(node: ast.Call) -> str:
    cur: ast.AST = node.func
    names: list[str] = []
    while isinstance(cur, ast.Attribute):
        names.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        names.append(cur.id)
    return ".".join(reversed(names))


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)

    app = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS
    )
    method = next(
        node for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == TARGET_METHOD
    )

    start = method.lineno
    end = method.end_lineno or method.lineno
    raw = "".join(lines[start - 1:end])
    normalized = ast.dump(method, include_attributes=False)

    calls = sorted({
        _qualified_call_name(node)
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
    })

    callers: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == TARGET_METHOD:
            callers.append({
                "line": node.lineno,
                "expression": ast.unparse(func),
            })

    later_bindings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == TARGET_CLASS
                and target.attr == TARGET_METHOD
            ):
                later_bindings.append({
                    "line": node.lineno,
                    "statement": ast.unparse(node),
                })

    risky_call_terms = (
        "execute", "executemany", "commit", "rollback", "run_write",
        "connect_db", "payment", "balance", "interest", "day_close",
        "close_day", "password", "login", "backup", "restore",
    )
    risky_calls = [
        call for call in calls
        if any(term in call.lower() for term in risky_call_terms)
    ]
    sql_literals = sorted({
        node.value.strip()
        for node in ast.walk(method)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and any(
            token in node.value.lower()
            for token in ("insert into", "update ", "delete from", "drop table", "alter table")
        )
    })

    report = {
        "target": f"{TARGET_CLASS}.{TARGET_METHOD}",
        "start_line": start,
        "end_line": end,
        "line_count": end - start + 1,
        "signature": _signature(method),
        "raw_sha256": _sha256(raw),
        "ast_sha256": _sha256(normalized),
        "calls": calls,
        "callers": callers,
        "later_bindings": later_bindings,
        "risky_calls": risky_calls,
        "sql_literals": sql_literals,
        "nested_function_count": sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not method
            for node in ast.walk(method)
        ),
    }

    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    EXPORT.write_text(raw, encoding="utf-8")

    assert 30 <= report["line_count"] <= 100, report
    assert report["signature"].startswith("self"), report
    assert not later_bindings, report
    assert not risky_calls, report
    assert not sql_literals, report
    assert report["nested_function_count"] == 0, report
    assert callers, report

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
