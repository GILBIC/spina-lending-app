"""Checks for the CI acceleration change."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

WORKFLOWS = Path(".github/workflows")
MANUAL_ONLY = {
    WORKFLOWS / "reports-feature-wave-18.yml",
    WORKFLOWS / "clients-feature-wave-19.yml",
}
ALLOWED_CHANGED = {
    ".github/workflows/reports-feature-wave-18.yml",
    ".github/workflows/clients-feature-wave-19.yml",
    ".github/workflows/ci-acceleration.yml",
    "tools/test_ci_acceleration.py",
}


def exact_head_guard(text: str) -> bool:
    return bool(
        re.search(r"github\.head_ref\s*==\s*['\"][^'\"]+['\"]", text)
        or re.search(r"github\.event\.pull_request\.head\.ref\s*==\s*['\"][^'\"]+['\"]", text)
    )


def main() -> None:
    for path in MANUAL_ONLY:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"(?m)^\s*workflow_dispatch\s*:", text), f"{path} is not manual-only"
        assert not re.search(r"(?m)^\s*pull_request\s*:", text), f"{path} still triggers on pull requests"
        assert not re.search(r"(?m)^\s*push\s*:", text), f"{path} still triggers on pushes"

    unguarded: list[str] = []
    for path in sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        pull_request = bool(re.search(r"(?m)^\s*pull_request\s*:", text))
        self_hosted = "self-hosted" in text
        if pull_request and self_hosted and not exact_head_guard(text):
            unguarded.append(str(path).replace("\\", "/"))
    assert not unguarded, f"Unguarded self-hosted PR workflows remain: {unguarded}"

    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    changed = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    unexpected = changed - ALLOWED_CHANGED
    assert not unexpected, f"Unexpected non-CI files changed: {sorted(unexpected)}"

    print("CI acceleration checks passed: zero unguarded self-hosted PR workflows.")


if __name__ == "__main__":
    main()
