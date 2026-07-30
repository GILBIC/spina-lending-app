#!/usr/bin/env python3
"""Permanent read-only guard for the Wave 83-84 account architecture."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "accounts-cleanup-wave-84.yml"
TEMPORARY_PATHS = (
    ROOT / "tools" / "apply_accounts_cleanup_wave_84.py",
    ROOT / "tools" / "wave84_templates",
)


def main() -> None:
    for path in TEMPORARY_PATHS:
        assert not path.exists(), f"Temporary Wave 84 tooling still exists: {path}"

    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Accounts architecture validation Wave 85" in text
    assert "permissions:\n  contents: read" in text
    assert "contents: write" not in text

    for forbidden in (
        "Apply redundant account cleanup",
        "Commit validated cleanup to PR branch",
        "apply_accounts_cleanup_wave_84.py",
        "wave84_templates",
        "git commit",
        "git push",
    ):
        assert forbidden not in text, forbidden

    for required in (
        "test_accounts_validation_wave_85.py",
        "test_accounts_cleanup_wave_84.py",
        "test_accounts_feature_wave_83.py",
        "test_login_dialog_presentation_wave_45.py",
        "test_account_header_presentation_wave_46.py",
        "test_account_permission_presentation_wave_47.py",
        "python -m tools.test_architecture_map",
        "git diff --exit-code",
    ):
        assert required in text, required

    print("Wave 85 permanent account validation guard passed.")


if __name__ == "__main__":
    main()
