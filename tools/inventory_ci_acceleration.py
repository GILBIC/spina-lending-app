"""Read-only inventory of GitHub Actions workflows that consume the Windows runner."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

WORKFLOWS = Path(".github/workflows")
OUTPUT = Path("ci-acceleration-inventory.json")
EXPECTED_BASE = "037c086feed3c5dfb1491781d60f4799730af139"


def merge_base() -> str:
    result = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def workflow_name(text: str, fallback: str) -> str:
    match = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
    return match.group(1).strip(" '\"") if match else fallback


def exact_head_refs(text: str) -> list[str]:
    patterns = [
        r"github\.head_ref\s*==\s*['\"]([^'\"]+)['\"]",
        r"github\.event\.pull_request\.head\.ref\s*==\s*['\"]([^'\"]+)['\"]",
    ]
    refs: set[str] = set()
    for pattern in patterns:
        refs.update(re.findall(pattern, text))
    return sorted(refs)


def main() -> None:
    base = merge_base()
    if base != EXPECTED_BASE:
        raise SystemExit(f"Unexpected main base: {base}")

    records: list[dict[str, object]] = []
    for path in sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        refs = exact_head_refs(text)
        pull_request = bool(re.search(r"(?m)^\s*pull_request\s*:", text))
        workflow_dispatch = bool(re.search(r"(?m)^\s*workflow_dispatch\s*:", text))
        self_hosted = "self-hosted" in text
        exact_guard = bool(refs)
        automatic_runner_consumer = pull_request and self_hosted and not exact_guard
        records.append(
            {
                "path": str(path).replace("\\", "/"),
                "name": workflow_name(text, path.stem),
                "pull_request": pull_request,
                "workflow_dispatch": workflow_dispatch,
                "self_hosted": self_hosted,
                "exact_head_refs": refs,
                "has_exact_head_guard": exact_guard,
                "automatic_windows_runner_consumer": automatic_runner_consumer,
                "line_count": len(text.splitlines()),
            }
        )

    consumers = [r for r in records if r["automatic_windows_runner_consumer"]]
    guarded = [r for r in records if r["pull_request"] and r["self_hosted"] and r["has_exact_head_guard"]]
    payload = {
        "base_commit": base,
        "workflow_count": len(records),
        "automatic_windows_runner_consumer_count": len(consumers),
        "exact_head_guarded_count": len(guarded),
        "automatic_windows_runner_consumers": consumers,
        "exact_head_guarded_workflows": guarded,
        "workflows": records,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "workflow_count": len(records),
        "automatic_windows_runner_consumer_count": len(consumers),
        "automatic_windows_runner_consumers": [r["name"] for r in consumers],
        "exact_head_guarded_count": len(guarded),
    }, indent=2))
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
