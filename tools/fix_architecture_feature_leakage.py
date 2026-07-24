"""Remove main-module filename leakage from Wave 27 feature ownership."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_architecture_map.py"
TEST = ROOT / "tools" / "test_architecture_map.py"
EXPECTED_GENERATOR_BLOB = "d04c13618f19d76b3a37866e246b369b564d92e3"
EXPECTED_TEST_BLOB = "cbfa95fbe3b08d8c26ef05e20c08dc726fe9d35d"


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.DOTALL)
    assert count == 1, f"Expected one {label}, found {count}"
    return updated


def main() -> None:
    assert git_blob_sha(GENERATOR) == EXPECTED_GENERATOR_BLOB, "Generator changed since leakage review"
    assert git_blob_sha(TEST) == EXPECTED_TEST_BLOB, "Architecture test changed since leakage review"

    text = GENERATOR.read_text(encoding="utf-8-sig")
    rules = '''FEATURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dashboard", ("dashboard", "kpi", "summary_card")),
    ("cash_control", ("cash_control", "cashcontrol", "cashctl")),
    ("navigation", (
        "side_nav", "sidebar", "navigation", "build_header", "header_button",
        "header_palette", "mode_toggle", "toolbar", "mousewheel", "vscroll",
        "month_label", "tab_selector",
    )),
    ("clients", ("client", "borrower", "application_form", "client_info", "cilog")),
    ("collectors", (
        "collector", "route", "area_assignment", "show_conflict", "unassigned_area",
    )),
    ("data_bank", (
        "data_bank", "databank", "data_grid", "payment_grid", "monthly_grid",
        "system_data", "delete_day", "close_day", "databank_day", "build_data_tab",
        "data_tree", "selected_cell", "cell_edit", "audit_tab", "clear_preview",
        "import_from_excel", "resize_databank", "refresh_data_grid",
    )),
    ("payments", (
        "payment", "transaction", "advance", "pass", "allocation", "paid_",
        "missed_reason",
    )),
    ("loans", ("loan", "principal", "interest", "renew", "offset", "7x7", "x7")),
    ("reports", ("report", "statement", "receipt", "pdf", "ledger", "print")),
    ("payroll", ("payroll", "employee", "salary", "payslip", "sss", "pagibig", "philhealth")),
    ("backup", ("backup", "restore", "pg_dump", "archive")),
    ("settings", ("setting", "maintenance", "theme", "appearance", "preference")),
    ("database", ("postgres", "postgresql", "pg_", "sql", "database", "loandb", "cursor", "connection")),
    ("notes", ("note_editor", "noteeditor", "client_notes", "collector_notes", "notes", "note")),
    ("web_portal", ("fastapi", "router", "portal", "endpoint", "api")),
    ("utilities", (
        "util", "helper", "format", "parse", "normalize", "validate", "date_range",
        "open_path", "getv", "wrap_to_width", "walk_widgets",
    )),
    ("authentication", (
        "login", "password", "account", "permission", "role_access", "apply_role",
        "session", "users_db", "user_role", "switch_account", "account_based",
        "role", "make_salt", "access_prefs",
    )),
)
'''
    text = replace_once(
        text,
        r"FEATURE_RULES: tuple\[tuple\[str, tuple\[str, \.\.\.\]\], \.\.\.\] = \(.*?\n\)\n(?=\nAUTH_TERMS)",
        rules,
        "feature rules block",
    )

    old_path = "    path = file_path.lower()\n"
    new_path = '    path = file_path.lower() if file_path.startswith("spina_app/") else ""\n'
    assert text.count(old_path) == 1
    text = text.replace(old_path, new_path, 1)

    old_function_call = 'feature = infer_feature(qual, file_path, "")'
    new_function_call = '''feature_identity = ".".join(
            part for part in (class_name, parent, node.name) if part
        )
        feature = infer_feature(feature_identity, file_path, "")'''
    assert text.count(old_function_call) == 1
    text = text.replace(old_function_call, new_function_call, 1)

    old_class_call = 'feature = infer_feature(f"{module}.{node.name}", file_path, "")'
    assert text.count(old_class_call) == 1
    text = text.replace(old_class_call, 'feature = infer_feature(node.name, file_path, "")', 1)

    old_safe = '''        safe = [
            s for s in items
            if s.risk in {"ui_only", "support", "database_read"}
            and s.lines <= 300
        ]
'''
    new_safe = '''        safe = [
            s for s in items
            if feature != "other"
            and s.risk in {"ui_only", "support", "database_read"}
            and s.lines <= 300
        ]
'''
    assert text.count(old_safe) == 1
    text = text.replace(old_safe, new_safe, 1)

    old_git_args = '''                "*.py", ":(exclude)tools/generate_architecture_map.py",
'''
    new_git_args = '''                "*.py",
                ":(exclude)tools/generate_architecture_map.py",
                ":(exclude)tools/test_architecture_map.py",
'''
    assert text.count(old_git_args) == 1
    text = text.replace(old_git_args, new_git_args, 1)

    text = text.replace(
        '"""Return the latest commit that changed scanned Python source.\n\n    The generator itself is excluded from the map, so committing generated maps does\n    not change this marker. That keeps regeneration deterministic for CI.\n    """',
        '"""Return the latest commit that changed non-architecture Python source.\n\n    The generator and its validator are excluded from this marker, keeping generated\n    documentation deterministic when architecture tooling itself is improved.\n    """',
        1,
    )
    GENERATOR.write_text(text, encoding="utf-8")

    test = TEST.read_text(encoding="utf-8-sig")
    old_expected = '''        ".App._postgres_cfg": "database",
        ".NoteEditorDialog._save_note": "notes",
'''
    new_expected = '''        ".App._postgres_cfg": "database",
        ".App._side_nav_items": "navigation",
        ".App._build_data_tab": "data_bank",
        "._adv_paid_on_dates_covering": "payments",
        ".App._access_prefs_path": "authentication",
        ".App._show_conflicts": "collectors",
        ".App._locate_data_tree": "data_bank",
        ".App._walk_widgets": "utilities",
        ".NoteEditorDialog._save_note": "notes",
'''
    assert test.count(old_expected) == 1
    test = test.replace(old_expected, new_expected, 1)

    old_suggestion_assert = '''    for suggestion in indexes["modularization_suggestions"]:
        assert all(
'''
    new_suggestion_assert = '''    for suggestion in indexes["modularization_suggestions"]:
        assert suggestion["feature"] != "other", f"Low-confidence batch: {suggestion}"
        assert all(
'''
    assert test.count(old_suggestion_assert) == 1
    test = test.replace(old_suggestion_assert, new_suggestion_assert, 1)
    TEST.write_text(test, encoding="utf-8")
    print("Applied feature leakage and low-confidence batch fixes.")


if __name__ == "__main__":
    main()
