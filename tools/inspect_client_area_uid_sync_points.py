from __future__ import annotations

import ast
import json
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("tools/fixtures/client_area_uid_sync_points.json")
TARGETS = {"add_client", "update_client"}


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(APP))
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in TARGETS:
            continue
        commits = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            try:
                call = ast.unparse(child.func)
            except Exception:
                continue
            if call not in {"self.conn.commit", "conn.commit"}:
                continue
            lineno = child.lineno
            start = max(node.lineno, lineno - 12)
            end = min(node.end_lineno, lineno + 18)
            commits.append({
                "line": lineno,
                "start_line": start,
                "end_line": end,
                "text": "\n".join(f"{n}: {lines[n-1]}" for n in range(start, end + 1)),
            })
        results.append({
            "name": node.name,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "signature": ast.unparse(node.args),
            "commit_contexts": commits,
        })
    results.sort(key=lambda item: int(item["line"]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Recorded {len(results)} client Area UID sync targets")


if __name__ == "__main__":
    main()
