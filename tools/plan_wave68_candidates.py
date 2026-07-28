from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT_PATH = ROOT / "docs" / "wave68-candidates.json"

WRITE_TERMS = (
    "add", "insert", "update", "delete", "save", "commit", "rollback",
    "set_", "write", "remove", "rename", "move", "archive", "restore",
    "renew", "close_", "reopen", "create", "drop", "alter", "truncate",
)
FS_WRITE_SUFFIXES = (
    "write_text", "write_bytes", "unlink", "rename", "replace", "mkdir",
    "rmdir", "touch", "copy", "copy2", "move", "dump", "dumps",
)
SQL_WRITE_TOKENS = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE TABLE",
)
UI_PREFIXES = ("tk.", "ttk.", "messagebox.", "filedialog.", "simpledialog.")


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


def normalized_source(lines: list[str], node: ast.AST) -> str:
    text = "".join(lines[node.lineno - 1:node.end_lineno])
    return text.replace("\r\n", "\n")


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")

    candidates: list[dict[str, object]] = []
    for node in app.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        line_count = node.end_lineno - node.lineno + 1
        if line_count < 90:
            continue

        calls = sorted({
            dotted(item.func)
            for item in ast.walk(node)
            if isinstance(item, ast.Call) and dotted(item.func)
        })
        db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
        direct_sql_calls = sorted(c for c in calls if c.endswith(".execute") or c.endswith(".executemany"))
        write_calls = sorted({
            c for c in calls
            if any(term in c.lower().split(".")[-1] for term in WRITE_TERMS)
        })
        fs_write_calls = sorted({
            c for c in calls if c.lower().split(".")[-1] in FS_WRITE_SUFFIXES
        })
        ui_calls = sorted(c for c in calls if c.startswith(UI_PREFIXES))
        nested = [
            item.name for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        sql_write_literals: list[str] = []
        for item in ast.walk(node):
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                upper = " ".join(item.value.upper().split())
                for token in SQL_WRITE_TOKENS:
                    if token in upper:
                        sql_write_literals.append(token)

        db_write_calls = sorted({
            c for c in db_calls
            if any(term in c.lower().split(".")[-1] for term in WRITE_TERMS)
        })
        source = normalized_source(lines, node)
        signature = ast.unparse(node.args)
        presentation_like = bool(ui_calls) and not db_write_calls and not sql_write_literals
        read_only_db = bool(db_calls) and not db_write_calls and not direct_sql_calls and not sql_write_literals
        no_db = not db_calls and not direct_sql_calls and not sql_write_literals

        risk_penalty = (
            len(db_write_calls) * 140
            + len(sql_write_literals) * 160
            + len(direct_sql_calls) * 80
            + len(fs_write_calls) * 35
            + max(0, len(write_calls) - len(db_write_calls)) * 6
        )
        score = line_count + len(ui_calls) * 2 + len(nested) * 3 - risk_penalty

        candidates.append({
            "name": node.name,
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "lines": line_count,
            "signature": signature,
            "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "nested_callbacks": nested,
            "db_calls": db_calls,
            "db_write_calls": db_write_calls,
            "direct_sql_calls": direct_sql_calls,
            "sql_write_literals": sorted(set(sql_write_literals)),
            "filesystem_write_calls": fs_write_calls,
            "write_like_calls": write_calls,
            "ui_call_count": len(ui_calls),
            "presentation_like": presentation_like,
            "read_only_db": read_only_db,
            "no_db": no_db,
            "score": score,
        })

    candidates.sort(key=lambda item: (int(item["score"]), int(item["lines"])), reverse=True)
    payload = {
        "source_file": APP_PATH.name,
        "app_method_count_over_90_lines": len(candidates),
        "candidates": candidates,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(candidates)} Wave 68 candidates to {OUT_PATH}")
    for item in candidates[:20]:
        print(
            f"{item['name']}: {item['lines']} lines, score={item['score']}, "
            f"presentation={item['presentation_like']}, read_only_db={item['read_only_db']}, "
            f"db_writes={len(item['db_write_calls'])}, sql_writes={len(item['sql_write_literals'])}"
        )


if __name__ == "__main__":
    main()
