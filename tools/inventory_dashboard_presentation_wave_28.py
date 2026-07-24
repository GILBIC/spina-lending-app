"""Read-only inventory for the high-volume Dashboard presentation Wave 28 batch."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "architecture-map.json"
SOURCE_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "tabs" / "dashboard.py"
OUT_DIR = ROOT / "artifacts"
OUT_JSON = OUT_DIR / "dashboard-presentation-wave-28-inventory.json"
OUT_MD = OUT_DIR / "dashboard-presentation-wave-28-inventory.md"


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], cwd=ROOT, text=True
    ).strip()


def source_segment(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def top_level_functions(path: Path) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> None:
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    suggestions = data["indexes"]["modularization_suggestions"]
    candidates = [
        item
        for item in suggestions
        if item["feature"] == "dashboard"
        and item["file"] == SOURCE_PATH.name
        and set(item["risk"]).issubset({"support", "ui_only"})
    ]
    assert candidates, "No low-risk Dashboard batch found in architecture-map.json"
    batch = max(candidates, key=lambda item: item["lines"])
    assert 350 <= batch["lines"] <= 800, batch

    symbols = {symbol["id"]: symbol for symbol in data["symbols"]}
    targets = [symbols[sid] for sid in batch["functions"]]
    assert targets
    assert all(symbol["file"] == SOURCE_PATH.name for symbol in targets)
    assert all(symbol["kind"] == "function" for symbol in targets)
    assert all(symbol["parent"] is None and not symbol["class_name"] for symbol in targets)
    assert all(symbol["risk"] in {"support", "ui_only"} for symbol in targets)
    assert all(not symbol["database_tables"] for symbol in targets)
    assert all(not symbol["file_paths"] for symbol in targets)

    source_text = SOURCE_PATH.read_text(encoding="utf-8")
    source_lines = source_text.splitlines()
    source_nodes = top_level_functions(SOURCE_PATH)
    module_nodes = top_level_functions(MODULE_PATH)

    checked: list[dict[str, object]] = []
    for symbol in targets:
        name = symbol["name"]
        assert name in source_nodes, f"Missing source function: {name}"
        node = source_nodes[name]
        segment = source_segment(source_lines, node)
        actual_hash = hashlib.sha256(segment.encode("utf-8")).hexdigest()
        assert actual_hash == symbol["source_sha256"], (
            name,
            actual_hash,
            symbol["source_sha256"],
        )
        checked.append(
            {
                "name": name,
                "line": node.lineno,
                "end_line": node.end_lineno,
                "lines": symbol["lines"],
                "source_sha256": actual_hash,
                "risk": symbol["risk"],
                "risk_flags": symbol["risk_flags"],
                "calls_raw": symbol["calls_raw"],
                "calls_resolved": symbol["calls_resolved"],
                "callers": symbol["callers"],
                "callbacks": symbol["callbacks"],
                "monkey_patches": symbol["monkey_patches"],
                "imports_used": symbol["imports_used"],
                "globals_read": symbol["globals_read"],
                "globals_written": symbol["globals_written"],
                "module_name_collision": name in module_nodes,
            }
        )

    collisions = sorted(item["name"] for item in checked if item["module_name_collision"])
    assert not collisions, f"Dashboard module already owns target names: {collisions}"

    target_names = {item["name"] for item in checked}
    all_imports = sorted({value for item in checked for value in item["imports_used"]})
    all_globals = sorted({value for item in checked for value in item["globals_read"]})
    resolved_external = sorted(
        {
            call
            for item in checked
            for call in item["calls_resolved"]
            if symbols[call]["name"] not in target_names
        }
    )
    unresolved_calls = sorted(
        {
            call
            for item in checked
            for call in item["calls_raw"]
            if call.rsplit(".", 1)[-1] not in target_names
        }
    )

    report = {
        "batch": batch,
        "architecture_generated_from_commit": data["generated_from_commit"],
        "current_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_sha256": sha256_bytes(SOURCE_PATH),
        "source_git_blob": git_blob(SOURCE_PATH),
        "dashboard_module_sha256": sha256_bytes(MODULE_PATH),
        "dashboard_module_git_blob": git_blob(MODULE_PATH),
        "target_count": len(checked),
        "target_lines": sum(int(item["lines"]) for item in checked),
        "targets": checked,
        "all_imports_used": all_imports,
        "all_globals_read": all_globals,
        "resolved_external_calls": resolved_external,
        "unresolved_or_external_call_names": unresolved_calls,
        "protected_checks": {
            "no_database_tables": True,
            "no_file_paths": True,
            "only_support_or_ui_risk": True,
            "no_existing_module_name_collisions": True,
        },
    }

    OUT_DIR.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Dashboard Presentation Wave 28 Inventory",
        "",
        f"- Batch: {batch['feature']} / {batch['lines']} mapped lines",
        f"- Exact targets: {len(checked)} functions / {report['target_lines']} source lines",
        f"- Source SHA-256: `{report['source_sha256']}`",
        f"- Source Git blob: `{report['source_git_blob']}`",
        f"- Dashboard module Git blob: `{report['dashboard_module_git_blob']}`",
        "- Database tables: none",
        "- File paths: none",
        "- Existing module name collisions: none",
        "",
        "## Target functions",
        "",
    ]
    for item in checked:
        lines.append(
            f"- `{item['name']}` — lines {item['line']}-{item['end_line']} "
            f"({item['lines']} lines), risk `{item['risk']}`, SHA-256 `{item['source_sha256']}`"
        )
    lines.extend(
        [
            "",
            "## Shared imports",
            "",
            *(f"- `{name}`" for name in all_imports),
            "",
            "## Main-module globals read",
            "",
            *(f"- `{name}`" for name in all_globals),
            "",
            "## Resolved calls outside the batch",
            "",
            *(f"- `{name}`" for name in resolved_external),
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "Wave 28 inventory passed:",
        len(checked),
        "functions,",
        report["target_lines"],
        "exact source lines.",
    )


if __name__ == "__main__":
    main()
