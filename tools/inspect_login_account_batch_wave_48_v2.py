from __future__ import annotations

import ast
import hashlib
import json
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-48-login-account-batch-inspection.json"

LINE_START = 37400
LINE_END = 38200
PROTECTED_TERMS = (
    "password", "verify_login", "force_change_password", "must_change_password",
    "hash_password", "save_users", "write_users", "psycopg", "sqlite3",
    ".execute(", ".commit(", "payment", "balance", "principal", "interest",
    "renew", "offset", "advance", "7x7", "report", "pdf", "backup",
    "open(", "write_text", "write_bytes", "unlink", "mkdir",
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


def build_report() -> dict[str, object]:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    candidates: list[dict[str, object]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("_spina_v32_"):
            continue
        if not (LINE_START <= node.lineno <= LINE_END):
            continue
        source = ast.get_source_segment(text, node)
        if source is None:
            continue
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
                term for term in PROTECTED_TERMS if term.lower() in source.lower()
            }),
            "source": source,
        })

    candidates.sort(key=lambda item: int(item["lineno"]))
    candidate_names = {str(item["name"]) for item in candidates}
    bindings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        names = {part.id for part in ast.walk(node) if isinstance(part, ast.Name)}
        if names & candidate_names:
            bindings.append({
                "lineno": getattr(node, "lineno", None),
                "source": ast.get_source_segment(text, node) or "",
            })

    return {
        "desktop": DESKTOP.name,
        "line_range": [LINE_START, LINE_END],
        "candidate_count": len(candidates),
        "total_candidate_lines": sum(int(item["lines"]) for item in candidates),
        "candidates": candidates,
        "bindings": sorted(bindings, key=lambda item: int(item["lineno"] or 0)),
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
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
