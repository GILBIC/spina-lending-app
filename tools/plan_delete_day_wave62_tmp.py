from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUT_PATH = Path("docs/wave-62-delete-day-plan.md")
TARGET = "open_delete_day_dialog"
EXPECTED_LINES = 141
REQUIRED_TEXT_MARKERS = (
    "Delete Day",
    "password",
    "backup",
    "delete",
    "refresh_data_grid",
)
SENSITIVE_CALL_TERMS = (
    "password", "backup", "delete", "transaction", "audit", "commit", "rollback",
    "execute", "executemany", "messagebox", "simpledialog", "refresh",
)


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    methods = {
        node.name: node
        for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if TARGET not in methods:
        raise SystemExit(f"Missing App.{TARGET}")

    node = methods[TARGET]
    assert isinstance(node, ast.FunctionDef)
    source = "".join(lines[node.lineno - 1 : node.end_lineno])
    dedented = textwrap.dedent(source)
    span = node.end_lineno - node.lineno + 1
    if span != EXPECTED_LINES:
        raise SystemExit(f"Expected {EXPECTED_LINES} lines, found {span}")

    lowered = source.lower()
    missing_markers = [marker for marker in REQUIRED_TEXT_MARKERS if marker.lower() not in lowered]
    if missing_markers:
        raise SystemExit(f"Missing required Delete Day markers: {missing_markers}")

    calls = sorted({
        value
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        for value in [dotted(child.func)]
        if value
    })
    db_calls = sorted(call for call in calls if call.startswith("self.db."))
    sensitive_calls = sorted({
        call for call in calls
        if any(term in call.lower() for term in SENSITIVE_CALL_TERMS)
    })
    nested = [
        {
            "name": child.name,
            "lines": child.end_lineno - child.lineno + 1,
            "signature": ast.unparse(child.args),
        }
        for child in node.body
        if isinstance(child, ast.FunctionDef)
    ]
    strings = sorted({
        child.value.strip()
        for child in ast.walk(node)
        if isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and child.value.strip()
    })

    wave61_binding_markers = (
        "App._save_cell_edit = _wave61_save_cell_edit",
        "App.delete_selected_cell = _wave61_delete_selected_cell",
        "App._mark_missed_for_selected = _wave61_mark_missed_for_selected",
    )
    missing_bindings = [marker for marker in wave61_binding_markers if marker not in text]
    if missing_bindings:
        raise SystemExit(f"Missing protected Wave 61 bindings: {missing_bindings}")

    report = {
        "base_merge": "45d781b2d23bb1e2772cf8d5cd3a35e4f8154d65",
        "target": TARGET,
        "start_line": node.lineno,
        "end_line": node.end_lineno,
        "lines": span,
        "signature": ast.unparse(node.args),
        "source_sha256": sha(source),
        "dedented_sha256": sha(dedented),
        "calls": calls,
        "db_calls": db_calls,
        "sensitive_calls": sensitive_calls,
        "nested_functions": nested,
        "strings": strings,
        "protected_wave61_bindings": list(wave61_binding_markers),
    }

    out = [
        "# Wave 62 Delete Day boundary plan",
        "",
        "Wave 62 analyzes the complete Data Bank Delete Day dialog before any extraction.",
        "",
        f"- Base merge: `{report['base_merge']}`",
        f"- Target: `App.{TARGET}`",
        f"- Lines: **{span}** ({node.lineno}–{node.end_lineno})",
        f"- Signature: `{report['signature']}`",
        f"- Source SHA-256: `{report['source_sha256']}`",
        f"- Dedented SHA-256: `{report['dedented_sha256']}`",
        "- Risk class: **authentication / backup / destructive database write**",
        "",
        "## Database and sensitive calls",
        "",
        f"- Database calls: `{json.dumps(db_calls)}`",
        f"- Sensitive calls: `{json.dumps(sensitive_calls)}`",
        "",
        "## Nested functions",
        "",
    ]
    if nested:
        out.extend(
            f"- `{item['name']}({item['signature']})` — {item['lines']} lines"
            for item in nested
        )
    else:
        out.append("- None")
    out.extend([
        "",
        "## Required extraction gates",
        "",
        "- Exact source, signature, call-set, database-call, and string preservation",
        "- Fake-database tests for successful deletion, cancellation, wrong password, backup failure, and DB failure",
        "- Real Tkinter dialog construction and button-flow test",
        "- Exact preservation of Wave 61 cell-write bindings",
        "- Protected import, Daily Close, audit, reports, backups, and Collector Route regressions",
        "- Permanent architecture map and repository audits",
        "- Exact-head Windows validation and desktop testing before merge",
        "",
        "## Raw analyzer report",
        "",
        "```json",
        json.dumps(report, indent=2),
        "```",
        "",
    ])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
