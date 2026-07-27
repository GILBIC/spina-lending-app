from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave64-candidates.json"

HARD_EXCLUDES = {
    "payment", "transaction", "balance", "principal", "interest", "renew",
    "offset", "advance", "adv", "pass", "7x7", "x7", "loan", "collector",
    "report", "pdf", "ledger", "receipt", "print", "backup", "restore",
    "postgres", "database", "sql", "cursor", "account", "login", "password",
    "auth", "role", "permission", "client", "delete", "remove", "close_day",
    "daily_close", "import", "export", "payroll", "employee", "cash_control",
}

SIDE_EFFECT_CALL_TERMS = {
    "open", "write", "unlink", "remove", "rename", "replace", "mkdir", "copy",
    "move", "subprocess", "system", "popen", "urlopen", "request", "connect",
    "execute", "executemany", "commit", "rollback", "insert", "update", "delete",
    "save", "create", "destroy", "after", "bind", "protocol",
}

PREFERRED_NAME_TERMS = {
    "format", "display", "label", "text", "tooltip", "palette", "style",
    "color", "width", "column", "scroll", "sync", "resize", "toolbar",
    "selection", "focus", "month", "date", "status", "summary", "normalize",
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
    rejected = []
    for node in app.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        source = "".join(lines[node.lineno - 1:node.end_lineno])
        line_count = node.end_lineno - node.lineno + 1
        name_lower = node.name.lower()
        calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
        attrs = sorted({dotted(a) for a in ast.walk(node) if isinstance(a, ast.Attribute) and dotted(a)})
        strings = sorted({c.value for c in ast.walk(node) if isinstance(c, ast.Constant) and isinstance(c.value, str)})
        joined = " ".join([name_lower, *[c.lower() for c in calls], *[a.lower() for a in attrs], *[s.lower() for s in strings]])

        reasons = []
        if line_count < 4 or line_count > 140:
            reasons.append("line_count")
        if any(term in joined for term in HARD_EXCLUDES):
            reasons.append("protected_domain")
        if any(c.startswith("self.db") or ".db." in c for c in calls + attrs):
            reasons.append("database")
        if any(term in c.lower() for c in calls for term in SIDE_EFFECT_CALL_TERMS):
            reasons.append("side_effect_call")
        if any(token in source for token in ("INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE", "ALTER TABLE", "DROP TABLE")):
            reasons.append("sql")
        if node.decorator_list:
            reasons.append("decorated")

        score = 0
        score += sum(8 for term in PREFERRED_NAME_TERMS if term in name_lower)
        score += max(0, 100 - line_count) // 10
        if name_lower.startswith("_"):
            score += 2
        if not reasons:
            candidates.append({
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": node.end_lineno,
                "lines": line_count,
                "signature": ast.unparse(node.args),
                "score": score,
                "source_sha256": sha(source),
                "calls": calls,
                "attributes": attrs,
                "strings": strings,
                "source": source,
            })
        else:
            rejected.append({"name": node.name, "lines": line_count, "reasons": sorted(set(reasons))})

    candidates.sort(key=lambda item: (-item["score"], item["lines"], item["name"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "app_sha256": sha(text),
        "candidate_count": len(candidates),
        "candidates": candidates[:80],
        "rejected_count": len(rejected),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wave 64 planner wrote {min(len(candidates), 80)} candidates to {OUT}")


if __name__ == "__main__":
    main()
