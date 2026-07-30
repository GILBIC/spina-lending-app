#!/usr/bin/env python3
"""Normalize and verify the malformed weekday-regex boundaries for Clients Wave 81.

This guard also provides the owner-authored exact-head validation trigger after
older compatibility publishers, such as Wave 73, finish reconciling the branch.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "spina_app" / "services" / "clients.py"
BAD_BOUNDARY = "\x08"
GOOD_BOUNDARY = "\\b"
EXPECTED_FRAGMENT = "weekday_tokens = _re.findall(r'\\b("


def normalize() -> int:
    if not TARGET.exists():
        raise AssertionError(f"Generated Clients service is missing: {TARGET}")

    source = TARGET.read_text(encoding="utf-8")
    malformed = source.count(BAD_BOUNDARY)
    if malformed not in (0, 2):
        raise AssertionError(
            f"Expected zero or two malformed weekday boundaries, found {malformed}"
        )

    if malformed:
        source = source.replace(BAD_BOUNDARY, GOOD_BOUNDARY)
        TARGET.write_text(source, encoding="utf-8")

    verified = TARGET.read_text(encoding="utf-8")
    if BAD_BOUNDARY in verified:
        raise AssertionError("Malformed control-character boundary remains")
    if EXPECTED_FRAGMENT not in verified:
        raise AssertionError("Corrected weekday word-boundary regex is missing")

    return malformed


def main() -> None:
    changed = normalize()
    print(f"Clients weekday regex normalized: replaced {changed} malformed boundaries")


if __name__ == "__main__":
    main()
