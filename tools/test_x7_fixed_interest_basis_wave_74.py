#!/usr/bin/env python3
"""Protect the fixed-principal 7x7 daily-interest business rule."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app.calculation_rules import allocate_x7_payments, x7_daily_interest  # noqa: E402

APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT_ENGINE = ROOT / "spina_app" / "report_engine.py"


def close(actual: float, expected: float, tolerance: float = 0.001) -> None:
    assert math.isclose(float(actual), float(expected), abs_tol=tolerance), (actual, expected)


def main() -> None:
    close(x7_daily_interest(1000), 7)
    close(x7_daily_interest(5000), 35)

    # The first payment takes a ₱2,000 loan below ₱1,000 remaining. The second
    # day must still charge ₱14 because the cycle's recorded principal is ₱2,000.
    allocation = allocate_x7_payments(
        2000,
        "2026-01-01",
        [("2026-01-01", 1100), ("2026-01-02", 100)],
        "2026-01-02",
    )
    close(allocation["daily_interest"], 14)
    close(allocation["interest_basis_principal"], 2000)
    close(allocation["interest_paid"], 28)
    close(allocation["principal_paid"], 1172)
    close(allocation["remaining_principal"], 828)

    updated_cycle = allocate_x7_payments(
        1000,
        "2026-02-01",
        [("2026-02-01", 100)],
        "2026-02-01",
    )
    close(updated_cycle["daily_interest"], 7)
    close(updated_cycle["interest_paid"], 7)
    close(updated_cycle["principal_paid"], 93)

    app_source = APP.read_text(encoding="utf-8")
    source = app_source
    if "# --- BEGIN: Reports feature installer Wave 80 ---" in app_source:
        assert REPORT_ENGINE.exists()
        source = REPORT_ENGINE.read_text(encoding="utf-8")

    assert "def _x7_daily_interest_for_principal(_loan_principal):" in source
    assert "_x7_daily_interest_for_principal(principal)" in source
    assert "_x7_daily_interest_for_balance(rem)" not in source
    assert "CURRENT balance bracket" not in source

    print("Wave 74 fixed-principal 7x7 interest tests passed")


if __name__ == "__main__":
    main()
