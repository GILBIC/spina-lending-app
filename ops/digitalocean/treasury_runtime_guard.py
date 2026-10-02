"""Reject cash-only runtimes after the first treasury-aware host rollout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_FILES = (
    "gilbic_backend/src/gilbic_backend/treasury_collection_posting.py",
    "gilbic_backend/sql/0137_add_collection_funding_source.sql",
    "gilbic_backend/sql/0138_add_collector_surplus.sql",
    "gilbic_backend/src/gilbic_backend/collector_settlement.py",
    "gilbic_backend/src/gilbic_backend/collector_surplus.py",
)


def compatible(candidate: Path) -> bool:
    try:
        manifest = json.loads(
            (candidate / "release-capabilities.json").read_text(encoding="utf-8")
        )
        version = manifest.get("treasury_funding_schema")
        return (
            type(version) is int
            and version >= 1
            and type(manifest.get("collector_surplus_schema")) is int
            and manifest["collector_surplus_schema"] >= 1
            and all((candidate / relative).is_file() for relative in REQUIRED_FILES)
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def main() -> int:
    passed = len(sys.argv) == 2 and compatible(Path(sys.argv[1]))
    print(
        "SPINA_TREASURY_RUNTIME: "
        + ("passed" if passed else "blocked: source-aware recovery required")
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
