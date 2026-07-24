"""Archive completed automatic workflows while preserving manual run access."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(".github/workflows")
ACTIVE = WORKFLOWS / "ci-acceleration.yml"
TEMP = WORKFLOWS / "apply-ci-acceleration-cleanup.yml"
SELF = Path("tools/apply_ci_acceleration_cleanup.py")


def event_block_range(lines: list[str]) -> tuple[int, int]:
    start = next((i for i, line in enumerate(lines) if line.rstrip("\r\n") == "on:"), -1)
    if start < 0:
        raise ValueError("Missing top-level on block")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if lines[i][0] not in " \t":
            end = i
            break
    return start, end


def archive_workflow(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    has_pr = bool(re.search(r"(?m)^\s*pull_request\s*:", text))
    has_push = bool(re.search(r"(?m)^\s*push\s*:", text))
    if not (has_pr or has_push):
        return False

    lines = text.splitlines(keepends=True)
    start, end = event_block_range(lines)
    newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
    replacement = [f"on:{newline}", f"  workflow_dispatch:{newline}", newline]
    new_text = "".join(lines[:start] + replacement + lines[end:])
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    archived: list[str] = []
    for path in sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]):
        if path in {ACTIVE, TEMP}:
            continue
        if archive_workflow(path):
            archived.append(str(path).replace("\\", "/"))

    if not archived:
        raise SystemExit("No completed automatic workflows were archived")

    TEMP.unlink(missing_ok=True)
    SELF.unlink(missing_ok=True)
    print(f"Archived {len(archived)} completed workflows as manual-only:")
    for path in archived:
        print(path)


if __name__ == "__main__":
    main()
