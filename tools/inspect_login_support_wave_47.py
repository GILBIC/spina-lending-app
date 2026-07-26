from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-47-login-support-inspection.json"

TARGETS = (
    "_spina_v32_login_colors",
    "_spina_v32_account_permission_text",
    "_spina_v32_account_choices",
    "_spina_v32_selected_label_for_user",
    "_spina_v32_account_display_name",
    "_spina_v32_login_button",
)

PROTECTED_TERMS = (
    "password",
    "verify_login",
    "force_change_password",
    "psycopg",
    "sqlite3",
    "commit",
    "execute",
    "payment",
    "balance",
    "principal",
    "interest",
    "renew",
    "advance",
    "pass",
    "7x7",
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


def referenced_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for part in ast.walk(node):
        if isinstance(part, ast.Name):
            names.add(part.id)
        elif isinstance(part, ast.Attribute):
            value = dotted(part)
            if value:
                names.add(value)
                names.add(part.attr)
    return names


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    all_nodes = list(ast.walk(tree))
    report: dict[str, object] = {
        "desktop": DESKTOP.name,
        "targets": {},
        "assignments": [],
    }

    function_nodes = [
        node
        for node in all_nodes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    for name in TARGETS:
        matches = [node for node in function_nodes if node.name == name]
        if not matches:
            report["targets"][name] = {"found": False}
            continue
        entries = []
        for node in matches:
            source = ast.get_source_segment(text, node)
            assert source is not None
            calls = sorted(
                {
                    dotted(call.func)
                    for call in ast.walk(node)
                    if isinstance(call, ast.Call) and dotted(call.func)
                }
            )
            loads = sorted(
                {
                    part.id
                    for part in ast.walk(node)
                    if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)
                }
            )
            stores = sorted(
                {
                    part.id
                    for part in ast.walk(node)
                    if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)
                }
            )
            protected_hits = sorted(
                {
                    term
                    for term in PROTECTED_TERMS
                    if term.lower() in source.lower()
                }
            )
            entries.append(
                {
                    "lineno": node.lineno,
                    "end_lineno": node.end_lineno,
                    "lines": node.end_lineno - node.lineno + 1,
                    "signature": ast.unparse(node.args),
                    "sha256": normalized_hash(source),
                    "calls": calls,
                    "loads": loads,
                    "stores": stores,
                    "protected_hits": protected_hits,
                    "source": source,
                }
            )
        report["targets"][name] = {"found": True, "definitions": entries}

    for node in all_nodes:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        names = referenced_names(node)
        if not any(name in names for name in TARGETS):
            continue
        rendered = ast.get_source_segment(text, node) or ""
        report["assignments"].append(
            {
                "lineno": getattr(node, "lineno", None),
                "source": rendered,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
