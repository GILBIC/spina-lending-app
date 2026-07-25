from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-46-account-header-candidates.json"
TARGETS = [
    "_spina_v32_prompt_user_role",
    "_spina_v32_refresh_user_header",
    "_spina_v32_switch_account",
    "_spina_v32_build_header",
]
SQL_RE = re.compile(
    r"\b(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE)\b",
    re.I,
)


def normalized(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()) + "\n"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def signature_text(fn: ast.FunctionDef) -> str:
    parts: list[str] = []
    positional = list(fn.args.posonlyargs) + list(fn.args.args)
    defaults = [None] * (len(positional) - len(fn.args.defaults)) + list(fn.args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f"={ast.unparse(default)}"
        parts.append(text)
    if fn.args.vararg:
        parts.append(f"*{fn.args.vararg.arg}")
    elif fn.args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        text = arg.arg
        if arg.annotation is not None:
            text += f": {ast.unparse(arg.annotation)}"
        if default is not None:
            text += f"={ast.unparse(default)}"
        parts.append(text)
    if fn.args.kwarg:
        parts.append(f"**{fn.args.kwarg.arg}")
    return ", ".join(parts)


def runtime_bindings(tree: ast.Module) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        lhs = node.targets[0]
        rhs = dotted(node.value)
        if (
            isinstance(lhs, ast.Attribute)
            and isinstance(lhs.value, ast.Name)
            and lhs.value.id == "App"
            and lhs.attr in {"_prompt_user_role", "_refresh_user_header", "switch_account", "_build_header"}
        ):
            rows.append({"line": node.lineno, "target": f"App.{lhs.attr}", "value": rhs})
    return sorted(rows, key=lambda row: int(row["line"]))


def symbol_resolutions(tree: ast.Module, lines: list[str]) -> dict[str, list[dict[str, object]]]:
    rows: dict[str, list[dict[str, object]]] = {name: [] for name in TARGETS}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in rows:
            rows[node.name].append(
                {
                    "kind": "function",
                    "line": node.lineno,
                    "end": node.end_lineno,
                    "source": "\n".join(lines[node.lineno - 1 : node.end_lineno]),
                }
            )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in rows:
                    rows[target.id].append(
                        {
                            "kind": "assignment",
                            "line": node.lineno,
                            "value": ast.unparse(node.value),
                            "source": "\n".join(lines[node.lineno - 1 : node.end_lineno]),
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound = alias.asname or alias.name
                if bound in rows:
                    rows[bound].append(
                        {
                            "kind": "import",
                            "line": node.lineno,
                            "module": node.module,
                            "name": alias.name,
                            "asname": alias.asname,
                            "source": "\n".join(lines[node.lineno - 1 : node.end_lineno]),
                        }
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound in rows:
                    rows[bound].append(
                        {
                            "kind": "import",
                            "line": node.lineno,
                            "module": alias.name,
                            "name": alias.name,
                            "asname": alias.asname,
                            "source": "\n".join(lines[node.lineno - 1 : node.end_lineno]),
                        }
                    )
    return rows


def inspect_function(fn: ast.FunctionDef, lines: list[str]) -> dict[str, object]:
    source = "\n".join(lines[fn.lineno - 1 : fn.end_lineno])
    calls = sorted({dotted(node.func) for node in ast.walk(fn) if isinstance(node, ast.Call) and dotted(node.func)})
    attrs = sorted({dotted(node) for node in ast.walk(fn) if isinstance(node, ast.Attribute) and dotted(node)})
    names = sorted({node.id for node in ast.walk(fn) if isinstance(node, ast.Name)})
    constants = [node.value for node in ast.walk(fn) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    nested = [
        node.name
        for node in sorted(
            (
                node
                for node in ast.walk(fn)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not fn
            ),
            key=lambda node: node.lineno,
        )
    ]
    database_hits = sorted(
        item
        for item in set(calls + attrs + names)
        if item.startswith("self.db")
        or item in {"connect_db", "run_write"}
        or any(token in item.lower() for token in ("cursor", "execute", "commit", "rollback"))
    )
    filesystem_hits = sorted(
        item
        for item in set(calls + attrs + names)
        if item.startswith(("os.", "pathlib.", "shutil.", "subprocess."))
        or item in {"open", "Path", "data_path", "save_settings", "load_settings"}
    )
    sql_hits = sorted({value for value in constants if SQL_RE.search(value)})
    protected_calls = sorted(
        item
        for item in calls
        if any(
            token in item.lower()
            for token in (
                "verify_login",
                "password",
                "role_access",
                "payment",
                "balance",
                "interest",
                "principal",
                "renew",
                "advance",
                "close_day",
                "delete",
                "save",
                "write",
            )
        )
    )
    return {
        "name": fn.name,
        "start": fn.lineno,
        "end": fn.end_lineno,
        "lines": fn.end_lineno - fn.lineno + 1,
        "signature": signature_text(fn),
        "sha256": hashlib.sha256(normalized(source).encode("utf-8")).hexdigest(),
        "nested_callbacks": nested,
        "calls": calls,
        "database_hits": database_hits,
        "filesystem_hits": filesystem_hits,
        "sql_hits": sql_hits,
        "protected_calls": protected_calls,
        "source": source,
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    resolutions = symbol_resolutions(tree, lines)
    functions_by_name: dict[str, list[ast.FunctionDef]] = {name: [] for name in TARGETS}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in functions_by_name:
            functions_by_name[node.name].append(node)

    unresolved = [name for name, rows in resolutions.items() if not rows]
    if unresolved:
        raise AssertionError(f"Unresolved Wave 46 targets: {unresolved}")

    function_rows: list[dict[str, object]] = []
    for name in TARGETS:
        for fn in sorted(functions_by_name[name], key=lambda node: node.lineno):
            function_rows.append(inspect_function(fn, lines))

    report = {
        "desktop_lines": len(lines),
        "desktop_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "functions": function_rows,
        "symbol_resolutions": resolutions,
        "runtime_bindings": runtime_bindings(tree),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"DESKTOP lines={report['desktop_lines']} sha256={report['desktop_sha256']}")
    for name in TARGETS:
        print(f"RESOLVE {name}: {resolutions[name]}")
    for item in function_rows:
        print(
            f"TARGET {item['name']} lines={item['lines']} range={item['start']}-{item['end']} "
            f"hash={item['sha256']} callbacks={item['nested_callbacks']} "
            f"db={item['database_hits']} fs={item['filesystem_hits']} "
            f"sql={len(item['sql_hits'])} protected={item['protected_calls']}"
        )
    print("BINDINGS", report["runtime_bindings"])


if __name__ == "__main__":
    main()
