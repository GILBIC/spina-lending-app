"""Validation checks for the generated SPINA architecture map."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "architecture-map.json"
APP_PREFIXES = ("spina_app/", "OFFICIAL_SPINA_APP_")
DOCS = [
    ROOT / "docs" / "architecture" / "feature-map.md",
    ROOT / "docs" / "architecture" / "function-index.md",
    ROOT / "docs" / "architecture" / "dependency-map.md",
    ROOT / "docs" / "architecture" / "database-access-map.md",
    ROOT / "docs" / "architecture" / "risk-map.md",
]
BAD_TABLES = {
    "a", "an", "all", "any", "client", "data", "excel", "generate", "if",
    "postgresql", "reports", "routes", "row", "set", "spina", "sqlite",
    "variance", "workflow",
}


def is_app(file_path: str) -> bool:
    return file_path.startswith(APP_PREFIXES)


def main() -> None:
    assert MAP_PATH.exists(), "architecture-map.json is missing"
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))

    assert data.get("schema_version") == 2
    summary = data["summary"]
    assert summary["python_files"] >= 10
    assert summary["application_python_files"] >= 2
    assert summary["total_python_lines"] >= 40_000
    assert summary["symbols"] >= 500
    assert summary["application_symbols"] >= 500
    assert summary["resolved_call_edges"] > 0
    assert summary["application_resolved_call_edges"] > 0
    assert summary["ui_callback_edges"] > 0
    assert summary["application_ui_callback_edges"] > 0
    assert summary["monkey_patches"] > 0
    assert summary["application_monkey_patches"] > 0
    assert summary["parse_errors"] == 0
    assert not data["parse_errors"]

    symbols = data["symbols"]
    ids = [symbol["id"] for symbol in symbols]
    assert len(ids) == len(set(ids)), "Architecture symbol IDs are not unique"
    known = set(ids)
    by_id = {symbol["id"]: symbol for symbol in symbols}
    for symbol in symbols:
        assert symbol["purpose"].strip(), f"Missing purpose: {symbol['id']}"
        assert symbol["source_sha256"], f"Missing source hash: {symbol['id']}"
        assert all(target in known for target in symbol["calls_resolved"])
        assert all(caller in known for caller in symbol["callers"])
        if symbol["kind"] == "class":
            assert symbol["risk"] == "container", f"Class risk must be container: {symbol['id']}"

    module_files = {module["file"] for module in data["modules"]}
    assert any(name.startswith("OFFICIAL_SPINA_APP_") for name in module_files)
    assert "spina_app/tabs/collectors.py" in module_files

    indexes = data["indexes"]
    for key in (
        "features", "risks", "database_tables", "callbacks", "monkey_patches",
        "application_features", "application_risks", "application_database_tables",
        "application_callbacks", "application_monkey_patches",
        "modularization_suggestions",
    ):
        assert indexes[key], f"Missing architecture index: {key}"

    app_ids = {sid for values in indexes["application_features"].values() for sid in values}
    assert app_ids
    assert all(is_app(by_id[sid]["file"]) for sid in app_ids)

    app_tables = indexes["application_database_tables"]
    assert summary["database_tables"] == len(app_tables)
    assert summary["repository_database_tables"] >= len(app_tables)
    assert not (set(app_tables) & BAD_TABLES), f"False SQL tables detected: {set(app_tables) & BAD_TABLES}"
    for users in app_tables.values():
        assert all(is_app(by_id[sid]["file"]) for sid in users)

    for suggestion in indexes["modularization_suggestions"]:
        assert 150 <= suggestion["lines"] <= 800
        assert is_app(suggestion["file"])
        assert suggestion["functions"]
        assert all(is_app(by_id[sid]["file"]) for sid in suggestion["functions"])
        assert all(not by_id[sid]["file"].startswith("tools/") for sid in suggestion["functions"])

    ledgers = [
        symbol for symbol in symbols
        if symbol["name"] == "print_full_daily_ledger"
        and symbol["kind"] == "function"
        and symbol["parent"] is None
    ]
    assert ledgers and all(symbol["risk"] != "authentication" for symbol in ledgers)

    selected_name = [symbol for symbol in symbols if symbol["name"] == "_collectors_name_from_values"]
    assert selected_name and all(symbol["risk"] != "database_read" for symbol in selected_name)

    def feature_for_suffix(suffix: str) -> str:
        matches = [symbol for symbol in symbols if symbol["qualified_name"].endswith(suffix)]
        assert matches, f"Missing reviewed symbol: {suffix}"
        features = {symbol["feature"] for symbol in matches}
        assert len(features) == 1, f"Conflicting feature labels for {suffix}: {features}"
        return next(iter(features))

    expected_features = {
        "._open_path": "utilities",
        ".LoanDB.add_client": "clients",
        ".LoanDB.delete_transaction": "payments",
        ".App._postgres_cfg": "database",
        ".NoteEditorDialog._save_note": "notes",
        "._spina_apply_dashboard_role": "dashboard",
        "._spina_v32_prompt_login": "authentication",
        ".App.open_settings_dialog": "settings",
        "._spina_cashctl_apply_role": "cash_control",
    }
    for suffix, expected in expected_features.items():
        actual = feature_for_suffix(suffix)
        assert actual == expected, f"Feature mismatch for {suffix}: {actual} != {expected}"

    for suggestion in indexes["modularization_suggestions"]:
        assert all(
            by_id[sid]["feature"] == suggestion["feature"]
            for sid in suggestion["functions"]
        ), f"Mixed feature batch: {suggestion}"

    source_commit = data["generated_from_commit"]
    assert len(source_commit) == 40 and all(c in "0123456789abcdef" for c in source_commit.lower())

    for path in DOCS:
        assert path.exists(), f"Missing architecture document: {path}"
        doc = path.read_text(encoding="utf-8")
        assert len(doc) > 500, f"Architecture document is unexpectedly small: {path}"
        assert source_commit in doc, f"Source commit is missing from {path}"

    risk_text = DOCS[-1].read_text(encoding="utf-8")
    batch_section = risk_text.split("## Suggested larger application modularization batches", 1)[1]
    assert "tools/test_" not in batch_section
    assert "Source file:" in batch_section

    database_text = DOCS[3].read_text(encoding="utf-8")
    for bad in BAD_TABLES:
        assert f"### `{bad}`" not in database_text

    print(
        "Architecture map validation passed:",
        summary["python_files"],
        "files,",
        summary["application_symbols"],
        "application symbols,",
        summary["application_resolved_call_edges"],
        "application calls,",
        summary["database_tables"],
        "application tables.",
    )


if __name__ == "__main__":
    main()
