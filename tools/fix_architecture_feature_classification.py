"""Correct Wave 27 feature ownership after architecture review."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_architecture_map.py"
TEST = ROOT / "tools" / "test_architecture_map.py"
EXPECTED_GENERATOR_BLOB = "a6d8e92f0bba3332886dda28fe708dae62a8763e"
EXPECTED_TEST_BLOB = "ef480811151a246e281764fdd53d819aa2d16601"


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.DOTALL)
    assert count == 1, f"Expected one {label}, found {count}"
    return updated


def main() -> None:
    assert git_blob_sha(GENERATOR) == EXPECTED_GENERATOR_BLOB, "Generator changed since feature review"
    assert git_blob_sha(TEST) == EXPECTED_TEST_BLOB, "Architecture test changed since feature review"

    text = GENERATOR.read_text(encoding="utf-8-sig")
    rules = '''FEATURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dashboard", ("dashboard", "kpi", "summary_card")),
    ("cash_control", ("cash_control", "cashcontrol", "cashctl")),
    ("clients", ("client", "borrower", "application_form", "client_info", "cilog")),
    ("collectors", ("collector", "route", "area_assignment")),
    ("data_bank", (
        "data_bank", "databank", "data_grid", "payment_grid", "monthly_grid",
        "system_data", "delete_day", "close_day", "databank_day",
    )),
    ("payments", ("payment", "transaction", "advance", "pass", "allocation")),
    ("loans", ("loan", "principal", "interest", "renew", "offset", "7x7", "x7")),
    ("reports", ("report", "statement", "receipt", "pdf", "ledger", "print")),
    ("payroll", ("payroll", "employee", "salary", "payslip", "sss", "pagibig", "philhealth")),
    ("backup", ("backup", "restore", "pg_dump", "archive")),
    ("settings", ("setting", "maintenance", "theme", "appearance", "preference")),
    ("database", ("postgres", "postgresql", "pg_", "sql", "database", "loandb", "cursor", "connection")),
    ("notes", ("note_editor", "noteeditor", "client_notes", "collector_notes", "notes", "note")),
    ("web_portal", ("fastapi", "router", "portal", "endpoint", "api")),
    ("utilities", ("util", "helper", "format", "parse", "normalize", "validate", "date_range", "open_path")),
    ("authentication", (
        "login", "password", "account", "permission", "role_access", "apply_role",
        "session", "users_db", "user_role", "switch_account", "account_based", "role",
    )),
)
'''
    text = replace_once(
        text,
        r"FEATURE_RULES: tuple\[tuple\[str, tuple\[str, \.\.\.\]\], \.\.\.\] = \(.*?\n\)\n(?=\nAUTH_TERMS)",
        rules,
        "feature rules block",
    )

    infer = '''def infer_feature(name: str, file_path: str, source: str) -> str:
    """Infer feature ownership from symbol identity, not implementation-body text.

    Leaf function names receive the strongest weight, module paths receive medium
    weight, and parent qualified names provide context for nested/generic helpers.
    Rule order resolves ties in favor of domain features before authentication.
    """
    full = name.lower()
    leaf = full.rsplit(".", 1)[-1]
    parent = full.rsplit(".", 1)[0] if "." in full else ""
    path = file_path.lower()
    ranked: list[tuple[int, int, str]] = []
    for order, (feature, terms) in enumerate(FEATURE_RULES):
        score = 0
        for term in terms:
            if term in leaf:
                score = max(score, 12)
            elif term in parent:
                score = max(score, 4)
            if term in path:
                score = max(score, 8)
        if score:
            ranked.append((score, -order, feature))
    return max(ranked)[2] if ranked else "other"
'''
    text = replace_once(
        text,
        r"def infer_feature\(.*?(?=\ndef explain_symbol)",
        infer + "\n\n",
        "feature inference function",
    )

    old_function_call = "feature = infer_feature(node.name, file_path, src)"
    assert text.count(old_function_call) == 1
    text = text.replace(old_function_call, "feature = infer_feature(qual, file_path, \"\")", 1)

    old_class_call = 'feature = infer_feature(node.name, file_path, "")'
    assert text.count(old_class_call) == 1
    text = text.replace(
        old_class_call,
        'feature = infer_feature(f"{module}.{node.name}", file_path, "")',
        1,
    )
    GENERATOR.write_text(text, encoding="utf-8")

    test = TEST.read_text(encoding="utf-8-sig")
    marker = '''    source_commit = data["generated_from_commit"]
'''
    assert test.count(marker) == 1
    checks = '''    def feature_for_suffix(suffix: str) -> str:
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

'''
    test = test.replace(marker, checks + marker, 1)
    TEST.write_text(test, encoding="utf-8")
    print("Applied qualified-name feature classification review fix.")


if __name__ == "__main__":
    main()
