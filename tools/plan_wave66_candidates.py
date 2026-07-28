from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave66-candidates.json"

WRITE_TERMS = (
    "add", "insert", "update", "delete", "remove", "save", "set_", "create",
    "commit", "rollback", "close_day", "reopen", "write", "store", "upload",
    "archive", "restore", "renew", "offset", "import", "export",
)
PRESENTATION_TERMS = (
    "build", "refresh", "show", "open", "dialog", "window", "tab", "view",
    "history", "summary", "grid", "tree", "toolbar", "form", "details",
    "preview", "panel", "page", "screen",
)
HIGH_RISK_GROUPS = {
    "authentication": ("password", "login", "authenticate", "permission", "role", "account", "session"),
    "financial": ("payment", "balance", "principal", "interest", "renew", "offset", "advance", "7x7", "x7"),
    "backup": ("backup", "restore", "pg_dump", "archive"),
    "import_export": ("import", "export", "excel", "encoder"),
    "payroll": ("payroll", "employee", "salary", "payslip", "sss", "pagibig", "philhealth"),
    "filesystem": ("read_text", "read_bytes", "write_text", "write_bytes", "unlink", "rename", "replace", "mkdir", "copy", "move"),
}


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


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")

    candidates = []
    for node in app.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        count = node.end_lineno - node.lineno + 1
        if count < 150 or count > 800:
            continue

        source = "".join(lines[node.lineno - 1:node.end_lineno])
        calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
        attrs = sorted({dotted(a) for a in ast.walk(node) if isinstance(a, ast.Attribute) and dotted(a)})
        lower_name = node.name.lower()
        joined = " ".join([lower_name, *[c.lower() for c in calls], *[a.lower() for a in attrs]])

        db_calls = sorted({c for c in calls if c.startswith("self.db") or ".db." in c})
        db_writes = sorted({
            c for c in db_calls
            if any(term in c.lower().rsplit(".", 1)[-1] for term in WRITE_TERMS)
        })
        sql_write = any(
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and any(token in value.value.upper() for token in ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP "))
            for value in ast.walk(node)
        )
        risk_hits = {
            group: sorted({term for term in terms if term in joined})
            for group, terms in HIGH_RISK_GROUPS.items()
        }
        risk_hits = {group: hits for group, hits in risk_hits.items() if hits}
        presentation_hits = sorted({term for term in PRESENTATION_TERMS if term in lower_name})

        blockers = []
        if db_writes or sql_write:
            blockers.append("database_write")
        for group in ("authentication", "backup", "payroll", "import_export"):
            if group in risk_hits:
                blockers.append(group)

        score = count
        score += 140 * len(presentation_hits)
        score += 120 if not db_calls else 30
        score -= 800 if db_writes or sql_write else 0
        score -= 180 * len(blockers)
        score -= 40 * len(risk_hits)

        candidates.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": count,
            "signature": ast.unparse(node.args),
            "score": score,
            "source_sha256": sha(source),
            "presentation_hits": presentation_hits,
            "blockers": sorted(set(blockers)),
            "risk_hits": risk_hits,
            "db_calls": db_calls,
            "db_writes": db_writes,
            "sql_write": sql_write,
            "calls": calls,
            "attributes": attrs,
            "source": source,
        })

    candidates.sort(key=lambda item: (bool(item["blockers"]), -item["score"], -item["lines"], item["name"]))
    safe = [item for item in candidates if not item["blockers"] and not item["db_writes"] and not item["sql_write"]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "app_sha256": sha(text),
        "candidate_count": len(candidates),
        "safe_candidate_count": len(safe),
        "safe_candidates": safe[:50],
        "all_candidates": candidates[:100],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wave 66 planner found {len(safe)} safe high-volume candidates")
    for item in safe[:25]:
        print(
            f"{item['name']}: {item['lines']} lines score={item['score']} "
            f"db_calls={item['db_calls']} risk={sorted(item['risk_hits'])}"
        )


if __name__ == "__main__":
    main()
