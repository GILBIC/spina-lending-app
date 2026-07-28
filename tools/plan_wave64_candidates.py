from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave64-candidates.json"

PROTECTED_GROUPS = {
    "financial": ("payment", "balance", "principal", "interest", "renew", "offset", "advance", "7x7", "x7", "amort"),
    "authentication": ("password", "login", "authenticate", "permission", "role_access", "session", "users_db", "account"),
    "reporting": ("report", "pdf", "receipt", "statement", "ledger", "print"),
    "backup": ("backup", "restore", "pg_dump", "archive"),
    "import_export": ("import", "export", "excel", "encoder"),
    "payroll": ("payroll", "employee", "salary", "payslip", "sss", "pagibig", "philhealth"),
    "filesystem": ("open", "read_text", "read_bytes", "write_text", "write_bytes", "unlink", "rename", "replace", "mkdir", "copy", "move"),
}

WRITE_CALL_TERMS = (
    "add", "insert", "update", "delete", "remove", "save", "set_", "create",
    "commit", "rollback", "close_day", "reopen", "write", "store", "upload",
)

PRESENTATION_TERMS = (
    "build", "tab", "dialog", "window", "presentation", "refresh", "show",
    "view", "toolbar", "grid", "tree", "form", "history", "summary", "details",
)

UI_ROOTS = ("tk.", "ttk.", "messagebox.", "simpledialog.", "filedialog.")


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
        source = "".join(lines[node.lineno - 1:node.end_lineno])
        line_count = node.end_lineno - node.lineno + 1
        if line_count < 80 or line_count > 600:
            continue

        name_lower = node.name.lower()
        calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
        attrs = sorted({dotted(a) for a in ast.walk(node) if isinstance(a, ast.Attribute) and dotted(a)})
        strings = sorted({c.value for c in ast.walk(node) if isinstance(c, ast.Constant) and isinstance(c.value, str)})
        joined = " ".join([name_lower, source.lower(), *[c.lower() for c in calls], *[a.lower() for a in attrs]])

        db_calls = sorted({c for c in calls if c.startswith("self.db") or ".db." in c})
        db_writes = sorted({c for c in db_calls if any(term in c.lower().rsplit(".", 1)[-1] for term in WRITE_CALL_TERMS)})
        sql_write = any(token in source.upper() for token in ("INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE", "ALTER TABLE", "DROP TABLE"))
        protected = {
            group: sorted({term for term in terms if term in joined})
            for group, terms in PROTECTED_GROUPS.items()
        }
        protected = {group: hits for group, hits in protected.items() if hits}
        ui_calls = sorted({c for c in calls if c.startswith(UI_ROOTS)})
        presentation_hits = sorted({term for term in PRESENTATION_TERMS if term in name_lower})

        risk = []
        if db_writes or sql_write:
            risk.append("database_write")
        if protected.get("authentication"):
            risk.append("authentication")
        if protected.get("financial"):
            risk.append("financial")
        if protected.get("backup"):
            risk.append("backup")
        if protected.get("filesystem"):
            risk.append("filesystem")
        if protected.get("import_export"):
            risk.append("import_export")
        if protected.get("payroll"):
            risk.append("payroll")
        if protected.get("reporting") and not presentation_hits:
            risk.append("reporting")

        score = line_count
        score += 100 * len(presentation_hits)
        score += min(80, len(ui_calls) * 4)
        score += 80 if not db_writes and not sql_write else -500
        score += 60 if not risk else -100 * len(risk)
        score += 30 if db_calls and not db_writes else 0

        candidates.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": line_count,
            "signature": ast.unparse(node.args),
            "score": score,
            "source_sha256": sha(source),
            "presentation_hits": presentation_hits,
            "risk": risk,
            "db_calls": db_calls,
            "db_writes": db_writes,
            "ui_calls": ui_calls,
            "protected_hits": protected,
            "calls": calls,
            "attributes": attrs,
            "strings": strings,
            "source": source,
        })

    candidates.sort(key=lambda item: (-item["score"], -item["lines"], item["name"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "app_sha256": sha(text),
        "candidate_count": len(candidates),
        "candidates": candidates[:100],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wave 64 high-volume planner wrote {min(len(candidates), 100)} candidates to {OUT}")
    for item in candidates[:20]:
        print(f"{item['name']}: {item['lines']} lines, score={item['score']}, risk={item['risk']}")


if __name__ == "__main__":
    main()
