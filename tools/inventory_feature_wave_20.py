from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUT = Path("artifacts/feature-inventory-wave-20.json")

GROUPS = {
    "client_information_log": {
        "prefixes": ("_spina_v24_cilog_",),
        "explicit": (
            "_spina_v24_build_client_info_logs_tab",
            "_spina_v24_render_client_info_logs",
            "_spina_v24_refresh_client_info_logs",
        ),
    },
    "cash_control_modern": {
        "prefixes": ("_spina_v21_cash_",),
        "explicit": (),
    },
    "collector_route_modern": {
        "prefixes": ("_spina_v27_",),
        "explicit": (),
    },
}

PROTECTED_MARKERS = (
    "execute",
    "executemany",
    "commit",
    "rollback",
    "insert",
    "update",
    "delete",
    "save",
    "write",
    "pdf",
    "balance",
    "interest",
    "principal",
    "payment",
    "renew",
    "offset",
    "backup",
    "restore",
    "picture",
    "auth",
    "role",
)


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def call_name(call: ast.Call) -> str:
    cur = call.func
    parts: list[str] = []
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts)) if parts else "<dynamic>"


def main() -> None:
    text = MAIN.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    payload: dict[str, object] = {
        "source": str(MAIN),
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_line_count": len(lines),
        "groups": {},
    }

    for group_name, spec in GROUPS.items():
        selected = []
        for name, node in functions.items():
            if name in spec["explicit"] or any(name.startswith(p) for p in spec["prefixes"]):
                src = source_for(lines, node)
                calls = sorted({call_name(x) for x in ast.walk(node) if isinstance(x, ast.Call)})
                loads = sorted(
                    {
                        x.id
                        for x in ast.walk(node)
                        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)
                    }
                )
                risk_hits = sorted(
                    marker
                    for marker in PROTECTED_MARKERS
                    if any(marker in item.lower() for item in calls)
                    or marker in name.lower()
                )
                selected.append(
                    {
                        "name": name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno,
                        "source_lines": node.end_lineno - node.lineno + 1,
                        "sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
                        "calls": calls,
                        "loaded_spina_names": [x for x in loads if x.startswith("_spina") or x == "_log_exc"],
                        "risk_markers": risk_hits,
                    }
                )
        selected.sort(key=lambda item: item["start_line"])
        payload["groups"][group_name] = {
            "function_count": len(selected),
            "source_lines": sum(item["source_lines"] for item in selected),
            "functions": selected,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        name: {
            "function_count": data["function_count"],
            "source_lines": data["source_lines"],
        }
        for name, data in payload["groups"].items()
    }, indent=2))


if __name__ == "__main__":
    main()
