#!/usr/bin/env python3
"""Apply the fixed-principal 7x7 daily-interest rule to legacy report code."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

OLD_HELPER = '''        # Daily interest is STEP-based from BALANCE principal (1..1000=7/day, 1001..2000=14/day, ...)
        def _x7_daily_interest_for_balance(_bal):
            """Return 7x7 daily interest for a given remaining/balance principal.
            Rule: 1..1000 = 7/day, 1001..2000 = 14/day, etc.
            """
            try:
                b = float(_bal or 0.0)
            except Exception:
                b = 0.0
            if b <= 0:
                return 0.0
            try:
                # ceil(b/1000) without importing math
                units = int((b + 999.999999) // 1000)
            except Exception:
                units = 0
            if units < 1:
                units = 1
            return float(units) * 7.0
'''

NEW_HELPER = '''        # Daily interest is fixed from the recorded loan principal for the whole cycle.
        # Paying principal lowers the balance but does not lower this daily-interest basis.
        def _x7_daily_interest_for_principal(_loan_principal):
            return float(_wave74_x7_daily_interest(_loan_principal))
'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise AssertionError(f"{label}: expected one old block, found {count}")
    return source.replace(old, new, 1)


def patch(source: str) -> str:
    source = replace_once(source, OLD_HELPER, NEW_HELPER, "legacy 7x7 interest helper")

    replacements = (
        (
            "_x7_daily_interest_for_balance(principal)",
            "_x7_daily_interest_for_principal(principal)",
            3,
            "principal-based interest calls",
        ),
        (
            "_x7_daily_interest_for_balance(rem)",
            "_x7_daily_interest_for_principal(principal)",
            1,
            "payment allocation interest basis",
        ),
        (
            "_x7_daily_interest_for_balance(_x7_balance_principal)",
            "_x7_daily_interest_for_principal(principal)",
            1,
            "display interest basis",
        ),
        (
            "        # Keep daily interest display in-sync with the CURRENT balance bracket\n",
            "        # Keep daily interest display fixed to the recorded loan principal.\n",
            1,
            "daily-interest display comment",
        ),
    )
    for old, new, expected, label in replacements:
        if old not in source:
            if new in source:
                continue
            raise AssertionError(f"{label}: old and new text are both missing")
        count = source.count(old)
        if count != expected:
            raise AssertionError(f"{label}: expected {expected} occurrence(s), found {count}")
        source = source.replace(old, new)

    forbidden = (
        "_x7_daily_interest_for_balance(rem)",
        "_x7_daily_interest_for_balance(_x7_balance_principal)",
        "CURRENT balance bracket",
    )
    for token in forbidden:
        if token in source:
            raise AssertionError(f"Declining-balance 7x7 interest logic remains: {token}")
    return source


def main() -> None:
    before = APP.read_text(encoding="utf-8")
    after = patch(before)
    if after != before:
        APP.write_text(after, encoding="utf-8", newline="\n")
    print(f"Wave 74 fixed-principal report patch applied: changed={after != before}")


if __name__ == "__main__":
    main()
