#!/usr/bin/env python3
"""Navigation-only compatibility checks for the Wave 86 runtime boundary."""
from __future__ import annotations

from tools.test_navigation_databank_shell_wave_29 import (
    assert_exact_method_bodies,
    assert_navigation_behavior,
)


def main() -> None:
    # Preserve the extracted Wave 29 navigation implementation and behavior while
    # avoiding its obsolete pre-Wave-82 Data Bank startup-binding expectation.
    assert_exact_method_bodies()
    assert_navigation_behavior()
    print("Wave 86 navigation compatibility regression passed.")


if __name__ == "__main__":
    main()
