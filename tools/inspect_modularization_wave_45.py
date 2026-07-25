from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT = ROOT / "artifacts" / "wave-45-candidates.json"

UI_TOKENS = {
    "tk", "ttk", "Toplevel", "Frame", "Label", "Button", "Entry", "Text",
    "Treeview", "Combobox", "Scrollbar", "Menu", "messagebox", "geometry",
    "pack", "grid", "place", "bind", "title", "transient", "grab_set",
}
DB_TOKENS = {
    "execute", "executemany", "cursor", "commit", "rollback", "run_write",
    "fetchone", "fetchall", "self.db", "LoanDB",
}
FILESYSTEM_MUTATORS = {
    "write", "write_text", "write_bytes", "unlink", "remove", "rmtree",
    "rename", "replace", "mkdir", "makedirs", "dump", "dumps", "open",
}
FINANCIAL_TOKENS = {
    "principal", "interest", "balance", "payment", "renew", "loan",
    "total_to_pay", "remaining", "payoff", "7x7", "advance", "pass",
}
SQL_WRITES = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "REPLACE INTO", "ALTER TABLE",
    "DROP TABLE", "CREATE TABLE", "TRUNCATE TABLE",
)


def chain(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def source_for(node: ast.AST, lines: list[str]) -> str:
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def direct_nested_callbacks(node: ast.FunctionDef) -> list[str]:
    return [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def summarize(owner: str, node: ast.FunctionDef, lines: list[str]) -> dict[str, object]:
    source = source_for(node, lines)
    calls: set[str] = set()
    strings: list[str] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            name = chain(item.func)
            if name:
                calls.add(name)
        elif isinstance(item, ast.Constant) and isinstance(item.value, str):
            strings.append(item.value)

    call_lower = {name.lower() for name in calls}
    text_lower = source.lower()
    ui_hits = sorted({token for token in UI_TOKENS if token.lower() in text_lower})
    db_hits = sorted({
        token for token in DB_TOKENS
        if any(token.lower() in call for call in call_lower) or token.lower() in text_lower
    })
    fs_hits = sorted({
        token for token in FILESYSTEM_MUTATORS
        if any(call.split(".")[-1] == token.lower() for call in call_lower)
    })
    sql_hits = sorted({
        token for value in strings for token in SQL_WRITES
        if token in " ".join(value.upper().split())
    })
    financial_hits = sorted({token for token in FINANCIAL_TOKENS if token in text_lower})

    line_count = node.end_lineno - node.lineno + 1
    unsafe = bool(db_hits or fs_hits or sql_hits)
    presentation_score = len(ui_hits) * 10 + min(line_count, 350) / 10
    presentation_score -= len(financial_hits) * 2
    presentation_score -= 100 if unsafe else 0

    return {
        "symbol": f"{owner}.{node.name}" if owner else node.name,
        "owner": owner,
        "name": node.name,
        "start": node.lineno,
        "end": node.end_lineno,
        "lines": line_count,
        "signature": ast.unparse(node.args),
        "sha256": hashlib.sha256(normalized(source).encode("utf-8")).hexdigest(),
        "nested_callbacks": direct_nested_callbacks(node),
        "ui_hits": ui_hits,
        "db_hits": db_hits,
        "filesystem_hits": fs_hits,
        "sql_hits": sql_hits,
        "financial_hits": financial_hits,
        "calls": sorted(calls),
        "unsafe": unsafe,
        "presentation_score": round(presentation_score, 1),
    }


def runtime_bindings(tree: ast.AST) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = chain(node.targets[0])
        value = chain(node.value)
        if target.startswith("App.") and value:
            found.append({"line": node.lineno, "target": target, "value": value})
    return sorted(found, key=lambda item: int(item["line"]))


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)

    candidates: list[dict[str, object]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            candidates.append(summarize("", node, lines))
        elif isinstance(node, ast.ClassDef) and node.name == "App":
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    candidates.append(summarize("App", member, lines))

    eligible = [
        item for item in candidates
        if 60 <= int(item["lines"]) <= 360
        and len(item["ui_hits"]) >= 3
        and not item["unsafe"]
        and len(item["financial_hits"]) <= 2
    ]
    eligible.sort(key=lambda item: (-float(item["presentation_score"]), -int(item["lines"]), str(item["symbol"])))

    report = {
        "desktop_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "desktop_lines": len(lines),
        "eligible_count": len(eligible),
        "top_candidates": eligible[:30],
        "runtime_bindings": runtime_bindings(tree),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"DESKTOP lines={report['desktop_lines']} sha256={report['desktop_sha256']}")
    print(f"ELIGIBLE candidates={report['eligible_count']}")
    for index, item in enumerate(report["top_candidates"], start=1):
        print(
            f"CANDIDATE {index:02d} | {item['symbol']} | lines={item['lines']} "
            f"range={item['start']}-{item['end']} score={item['presentation_score']} "
            f"hash={item['sha256']} callbacks={item['nested_callbacks']} "
            f"ui={item['ui_hits']} financial={item['financial_hits']}"
        )
    print("RUNTIME BINDINGS")
    for item in report["runtime_bindings"]:
        print(f"BINDING line={item['line']} {item['target']}={item['value']}")


if __name__ == "__main__":
    main()
