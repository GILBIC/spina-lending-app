"""Validation checks for the generated SPINA architecture map."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "architecture-map.json"
DOCS = [
    ROOT / "docs" / "architecture" / "feature-map.md",
    ROOT / "docs" / "architecture" / "function-index.md",
    ROOT / "docs" / "architecture" / "dependency-map.md",
    ROOT / "docs" / "architecture" / "database-access-map.md",
    ROOT / "docs" / "architecture" / "risk-map.md",
]


def main() -> None:
    assert MAP_PATH.exists(), "architecture-map.json is missing"
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))

    assert data.get("schema_version") == 1
    summary = data["summary"]
    assert summary["python_files"] >= 10
    assert summary["application_python_files"] >= 2
    assert summary["total_python_lines"] >= 40_000
    assert summary["symbols"] >= 500
    assert summary["resolved_call_edges"] > 0
    assert summary["ui_callback_edges"] > 0
    assert summary["monkey_patches"] > 0
    assert summary["parse_errors"] == 0
    assert not data["parse_errors"]

    symbols = data["symbols"]
    ids = [symbol["id"] for symbol in symbols]
    assert len(ids) == len(set(ids)), "Architecture symbol IDs are not unique"
    known = set(ids)
    for symbol in symbols:
        assert symbol["purpose"].strip(), f"Missing purpose: {symbol['id']}"
        assert symbol["source_sha256"], f"Missing source hash: {symbol['id']}"
        assert all(target in known for target in symbol["calls_resolved"])
        assert all(caller in known for caller in symbol["callers"])

    module_files = {module["file"] for module in data["modules"]}
    assert any(name.startswith("OFFICIAL_SPINA_APP_") for name in module_files)
    assert "spina_app/tabs/collectors.py" in module_files

    indexes = data["indexes"]
    assert indexes["features"]
    assert indexes["risks"]
    assert indexes["database_tables"]
    assert indexes["callbacks"]
    assert indexes["monkey_patches"]
    assert indexes["modularization_suggestions"]

    source_commit = data["generated_from_commit"]
    assert len(source_commit) == 40 and all(c in "0123456789abcdef" for c in source_commit.lower())

    for path in DOCS:
        assert path.exists(), f"Missing architecture document: {path}"
        text = path.read_text(encoding="utf-8")
        assert len(text) > 500, f"Architecture document is unexpectedly small: {path}"
        assert source_commit in text, f"Source commit is missing from {path}"

    print(
        "Architecture map validation passed:",
        summary["python_files"],
        "files,",
        summary["symbols"],
        "symbols,",
        summary["resolved_call_edges"],
        "resolved calls.",
    )


if __name__ == "__main__":
    main()
