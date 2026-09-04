from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "gilbic_backend" / "tests"


def main() -> int:
    selected = sorted(
        {
            *TEST_DIR.glob("test_cif_*.py"),
            *TEST_DIR.glob("test_restricted_identity_*.py"),
        }
    )
    if not selected:
        raise RuntimeError("No CIF or restricted identity tests were discovered.")
    relative = [str(path.relative_to(ROOT)) for path in selected]
    return pytest.main(["-q", *relative])


if __name__ == "__main__":
    raise SystemExit(main())
