from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUT_PATH = Path("docs/wave-61-plan.md")
TARGETS = ["_save_cell_edit", "delete_selected_cell", "_mark_missed_for_selected"]
EXPECTED_LINES = {
    "_save_cell_edit": 84,
    "delete_selected_cell": 88,
    "_mark_missed_for_selected": 71,
}
WRITE_MARKERS = {
    "execute", "executemany", "commit", "rollback", "set_transaction",
    "delete_transaction", "save_transaction", "add_transaction", "run_write",
}
PROTECTED = {"open_delete_day_dialog"}


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def signature(node: ast.FunctionDef) -> str:
    return ast.unparse(node.args)


def normalized_sha(source: str) -> str:
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    app = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    methods = {
        node.name: node for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    missing = [name for name in TARGETS + sorted(PROTECTED) if name not in methods]
    if missing:
        raise SystemExit(f"Missing expected App methods: {missing}")

    report: dict[str, object] = {
        "base": "Wave 60 merge 7f074da81499cc67f05a61517d9a5d87cd0b2a8b",
        "targets": {},
        "protected": sorted(PROTECTED),
    }
    total = 0

    for name in TARGETS:
        node = methods[name]
        assert isinstance(node, ast.FunctionDef)
        source = "".join(lines[node.lineno - 1: node.end_lineno])
        dedented = textwrap.dedent(source)
        calls = sorted({
            value for child in ast.walk(node)
            if isinstance(child, ast.Call)
            for value in [dotted(child.func)]
            if value
        })
        db_calls = sorted(call for call in calls if call.startswith("self.db."))
        write_hits = sorted({
            call for call in calls
            if call.rsplit(".", 1)[-1] in WRITE_MARKERS
            or any(marker in call.lower() for marker in ("delete", "save", "transaction", "write"))
        })
        span = node.end_lineno - node.lineno + 1
        total += span
        if span != EXPECTED_LINES[name]:
            raise SystemExit(f"{name}: expected {EXPECTED_LINES[name]} lines, found {span}")
        report["targets"][name] = {
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "lines": span,
            "signature": signature(node),
            "source_sha256": normalized_sha(source),
            "dedented_sha256": normalized_sha(dedented),
            "calls": calls,
            "db_calls": db_calls,
            "write_hits": write_hits,
        }

    if total != 243:
        raise SystemExit(f"Expected 243 total lines, found {total}")

    protected_node = methods["open_delete_day_dialog"]
    protected_source = "".join(lines[protected_node.lineno - 1: protected_node.end_lineno])
    report["protected_hashes"] = {
        "open_delete_day_dialog": normalized_sha(protected_source),
    }

    out = [
        "# Wave 61 Data Bank write-boundary plan",
        "",
        "This planner analyzes the three adjacent Data Bank cell-write methods before extraction.",
        "Delete Day remains protected and outside the boundary.",
        "",
        f"- Base merge: `{report['base']}`",
        f"- Target methods: {len(TARGETS)}",
        f"- Total active source lines: **{total}**",
        "- Risk class: **database write / payment mutation**",
        "",
    ]
    for name in TARGETS:
        data = report["targets"][name]
        assert isinstance(data, dict)
        out.extend([
            f"## `App.{name}`",
            "",
            f"- Lines: {data['start_line']}–{data['end_line']} ({data['lines']})",
            f"- Signature: `{data['signature']}`",
            f"- Source SHA-256: `{data['source_sha256']}`",
            f"- Dedented SHA-256: `{data['dedented_sha256']}`",
            f"- Database calls: `{json.dumps(data['db_calls'])}`",
            f"- Write-sensitive calls: `{json.dumps(data['write_hits'])}`",
            f"- Full calls: `{json.dumps(data['calls'])}`",
            "",
        ])
    out.extend([
        "## Protected boundary",
        "",
        "- `App.open_delete_day_dialog` remains in the main application.",
        f"- Protected source SHA-256: `{report['protected_hashes']['open_delete_day_dialog']}`",
        "- Daily Close, import, authentication, balances, interest, ADV/PASS, 7x7, reports, backups, and Collector Route remain outside this extraction.",
        "",
        "## Planned validation",
        "",
        "- Exact source, dedented source, signature, call-set, and database-call preservation",
        "- Real save/update/zero-payment/missed-reason/delete behavior with fake database objects",
        "- Existing Tkinter editor and Data Bank grid regression suites",
        "- Protected Delete Day source hash",
        "- Permanent architecture map and repository audits",
        "- Desktop testing before merge",
        "",
    ])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
