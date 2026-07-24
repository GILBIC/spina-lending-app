"""Checks for the CI acceleration change."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

WORKFLOWS = Path(".github/workflows")
ACTIVE_PR_WORKFLOW = WORKFLOWS / "ci-acceleration.yml"


def exact_head_guard(text: str) -> bool:
    return bool(
        re.search(r"github\.head_ref\s*==\s*['\"][^'\"]+['\"]", text)
        or re.search(r"github\.event\.pull_request\.head\.ref\s*==\s*['\"][^'\"]+['\"]", text)
    )


def main() -> None:
    automatic: list[str] = []
    for path in sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        rel = str(path).replace("\\", "/")
        pull_request = bool(re.search(r"(?m)^\s*pull_request\s*:", text))
        push = bool(re.search(r"(?m)^\s*push\s*:", text))

        if path == ACTIVE_PR_WORKFLOW:
            assert pull_request, "CI acceleration validation must run on its own PR"
            assert exact_head_guard(text), "CI acceleration validation must have an exact head guard"
            continue

        assert re.search(r"(?m)^\s*workflow_dispatch\s*:", text), f"{rel} is not manual-only"
        if pull_request or push:
            automatic.append(rel)

    assert not automatic, f"Completed workflows still trigger automatically: {automatic}"

    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    changed = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    unexpected = [
        path for path in sorted(changed)
        if not path.startswith(".github/workflows/") and path != "tools/test_ci_acceleration.py"
    ]
    assert not unexpected, f"Unexpected non-CI files changed: {unexpected}"

    print("CI acceleration checks passed: completed workflows are manual-only.")


if __name__ == "__main__":
    main()
