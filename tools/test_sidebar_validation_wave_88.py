#!/usr/bin/env python3
"""Permanent read-only guard for the Wave 86-87 sidebar architecture."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sidebar-cleanup-wave-87.yml"
TEMPORARY_PATHS = (
    ROOT / "tools" / "apply_sidebar_cleanup_wave_87.py",
)


def main() -> None:
    for path in TEMPORARY_PATHS:
        assert not path.exists(), f"Temporary Wave 87 tooling still exists: {path}"

    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Sidebar architecture validation Wave 88" in text
    assert "permissions:\n  contents: read" in text
    assert "contents: write" not in text
    assert "persist-credentials: false" in text
    assert "github.event.pull_request.head.sha || github.sha" in text

    for forbidden in (
        "Apply redundant sidebar cleanup",
        "Commit validated cleanup to PR branch",
        "apply_sidebar_cleanup_wave_87.py",
        "git commit",
        "git push",
        "persist-credentials: true",
    ):
        assert forbidden not in text, forbidden

    for required in (
        "test_sidebar_validation_wave_88.py",
        "test_sidebar_cleanup_wave_87.py",
        "test_side_navigation_feature_wave_86.py",
        "test_side_navigation_presentation_wave_48.py",
        "test_navigation_compatibility_wave_86.py",
        "test_login_cancel_startup_wave_46.py",
        "test_tk_shutdown_wave_46.py",
        "python -m tools.test_architecture_map",
        "git diff --exit-code",
        "git diff --cached --exit-code",
    ):
        assert required in text, required

    print("Wave 88 permanent sidebar validation guard passed.")


if __name__ == "__main__":
    main()
