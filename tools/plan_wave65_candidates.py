from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave65-candidates.json"

WRITE_TERMS = (
    "add", "insert", "update", "delete", "remove", "save", "set_", "create",
    "commit", "rollback", "close_day", "reopen", "write", "store", "upload",
)
PRESENTATION_TERMS = (
    "build", "refresh", "show", "open", "dialog", "window", "tab", "view",
    "history", "summary", "grid", "tree", "toolbar", "form", "details",
)
PROTECTED_TERMS = {
    "authentication": ("password", "login", "authenticate", "permission", "role", "account", "session"),
    "financial": ("payment", "balance", "principal", "interest", "renew", "offset", "advance", "7x7", "x7"),
    "backup": ("backup", "restore", "pg_dump"),
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

    methods = []
    for node in app.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        source = "".join(lines[node.lineno - 1:node.end_lineno])
        count = node.end_lineno - node.lineno + 1
        if count < 120 or count > 700:
            continue
        name = node.name
        calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
        attrs = sorted({dotted(a) for a in ast.walk(node) if isinstance(a, ast.Attribute) and dotted(a)})
        joined = " ".join([name.lower(), source.lower(), *[c.lower() for c in calls], *[a.lower() for a in attrs]])
        db_calls = sorted({c for c in calls if c.startswith("self.db") or ".db." in c})
        db_writes = sorted({
            c for c in db_calls
            if any(term in c.lower().rsplit(".", 1)[-1] for term in WRITE_TERMS)
        })
        protected = {
            group: sorted({term for term in terms if term in joined})
            for group, terms in PROTECTED_TERMS.items()
        }
        protected = {group: hits for group, hits in protected.items() if hits}
        presentation_hits = sorted({term for term in PRESENTATION_TERMS if term in name.lower()})
        risk = []
        if db_writes:
            risk.append("database_write")
        if "authentication" in protected:
            risk.append("authentication")
        if "backup" in protected:
            risk.append("backup")
        if "payroll" in protected:
            risk.append("payroll")
        if "filesystem" in protected:
            risk.append("filesystem")
        if "import_export" in protected:
            risk.append("import_export")

        score = count + 120 * len(presentation_hits)
        score += 100 if not db_writes else -600
        score += 50 if db_calls and not db_writes else 0
        score -= 120 * len(risk)

        methods.append({
            "name": name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": count,
            "signature": ast.unparse(node.args),
            "score": score,
            "source_sha256": sha(source),
            "presentation_hits": presentation_hits,
            "risk": risk,
            "db_calls": db_calls,
            "db_writes": db_writes,
            "protected_hits": protected,
            "calls": calls,
            "attributes": attrs,
            "source": source,
        })

    methods.sort(key=lambda item: (-item["score"], -item["lines"], item["name"]))

    # Also surface adjacent same-feature groups to enable multi-method high-volume waves.
    groups = []
    for index, first in enumerate(methods):
        for second in methods[index + 1:index + 8]:
            if abs(first["lineno"] - second["lineno"]) > 1200:
                continue
            combined_risk = sorted(set(first["risk"] + second["risk"]))
            groups.append({
                "methods": [first["name"], second["name"]],
                "lines": first["lines"] + second["lines"],
                "distance": abs(first["lineno"] - second["lineno"]),
                "risk": combined_risk,
                "score": first["score"] + second["score"] - abs(first["lineno"] - second["lineno"]) // 10,
            })
    groups.sort(key=lambda item: (-item["score"], -item["lines"], item["methods"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "app_sha256": sha(text),
        "candidate_count": len(methods),
        "candidates": methods[:100],
        "adjacent_groups": groups[:100],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wave 65 planner wrote {len(methods)} high-volume candidates")
    for item in methods[:25]:
        print(f"{item['name']}: {item['lines']} lines score={item['score']} risk={item['risk']} db_writes={item['db_writes']}")


if __name__ == "__main__":
    main()
