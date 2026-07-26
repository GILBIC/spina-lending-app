from __future__ import annotations

import ast
import hashlib
import json
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-49-databank-dashboard-inspection.json"
PREFIXES = ("_spina_v15_", "_spina_v16_", "_spina_v17_")

PROTECTED_TERMS = (
    "password", "verify_login", "role_access", "save_users", "hash_password",
    "psycopg", "sqlite3", "connect_db", "run_write", ".execute(",
    ".executemany(", ".commit(", ".rollback(", "insert into", "update ",
    "delete from", "alter table", "create table", "drop table", "payment",
    "balance", "principal", "interest", "renew", "offset", "advance",
    "7x7", "import", "export", "report", "pdf", "backup", "restore",
    "open(", "write_text", "write_bytes", "unlink", "mkdir", "copy",
    "move", "rename",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def source_for(lines: list[str], node: ast.AST) -> str:
    end = getattr(node, "end_lineno", None) or node.lineno
    return "\n".join(lines[node.lineno - 1:end])


def build_report() -> dict[str, object]:
    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    candidates: list[dict[str, object]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith(PREFIXES):
            continue
        source = source_for(lines, node)
        calls = sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        })
        loads = sorted({
            part.id
            for part in ast.walk(node)
            if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)
        })
        stores = sorted({
            dotted(part) if isinstance(part, ast.Attribute) else part.id
            for part in ast.walk(node)
            if (
                isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)
            ) or (
                isinstance(part, ast.Attribute) and isinstance(part.ctx, ast.Store)
            )
        })
        lower = source.lower()
        candidates.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
            "signature": ast.unparse(node.args),
            "sha256": normalized_hash(source),
            "calls": calls,
            "loads": loads,
            "stores": stores,
            "protected_hits": sorted({
                term for term in PROTECTED_TERMS if term.lower() in lower
            }),
            "source": source,
        })

    candidates.sort(key=lambda item: int(item["lineno"]))
    names = {str(item["name"]) for item in candidates}
    assignments: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        mentioned = {
            part.id for part in ast.walk(node)
            if isinstance(part, ast.Name) and part.id in names
        }
        if not mentioned:
            continue
        assignments.append({
            "lineno": getattr(node, "lineno", None),
            "mentioned": sorted(mentioned),
            "source": source_for(lines, node),
        })

    return {
        "desktop": DESKTOP.name,
        "prefixes": list(PREFIXES),
        "candidate_count": len(candidates),
        "total_candidate_lines": sum(int(item["lines"]) for item in candidates),
        "candidates": candidates,
        "assignments": sorted(assignments, key=lambda item: int(item["lineno"] or 0)),
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = build_report()
    except BaseException as exc:
        frames = traceback.extract_tb(exc.__traceback__)
        last = frames[-1] if frames else None
        report = {
            "error_type": type(exc).__name__,
            "error_message": repr(exc),
            "error_location": (
                f"{last.filename}:{last.lineno} in {last.name}" if last else "unknown"
            ),
        }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {
        key: report.get(key)
        for key in (
            "candidate_count", "total_candidate_lines", "error_type",
            "error_message", "error_location",
        )
        if key in report
    }
    if "candidates" in report:
        summary["names"] = [item["name"] for item in report["candidates"]]
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
