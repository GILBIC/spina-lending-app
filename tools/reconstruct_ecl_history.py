from __future__ import annotations

import argparse
import json
from pathlib import Path

from gilbic_backend.ecl_history_sqlite import reconstruct_sqlite_history


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconstruct accounting-only ECL history from a legacy SPINA SQLite backup."
    )
    parser.add_argument("sqlite_file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = reconstruct_sqlite_history(args.sqlite_file)
    args.output.write_text(
        json.dumps(result.to_json_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        f"Reconstructed {len(result.episodes)} episodes from {result.source_filename}; "
        f"SHA-256 {result.source_sha256}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
