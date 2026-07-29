#!/usr/bin/env python3
"""Wire the Wave 75 loan-cycle service into the desktop dashboard."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

IMPORT_ANCHOR = '''from spina_app.calculation_rules import (
    allocate_x7_payments as _wave74_allocate_x7_payments,
    ceil_thousand_units as _wave74_ceil_thousand_units,
    normalized_total_to_pay as _wave74_normalized_total_to_pay,
    shift_due_date_for_renewal as _wave74_shift_due_date_for_renewal,
    x7_daily_interest as _wave74_x7_daily_interest,
)
'''

SERVICE_IMPORT = '''from spina_app.services.loan_cycles import (
    build_cycle_timing as _wave75_build_cycle_timing,
    cycle_sort_key as _wave75_cycle_sort_key,
    finalize_cycle_record as _wave75_finalize_cycle_record,
)
'''

OLD_TIMING = '''            base_release = _spina_dash__parse_date(_rv(r, 'date_released', 9, ''))
            original_due = _spina_dash__parse_date(_rv(r, 'due_date', 10, ''))
            latest_renew = renew_latest.get((uid, lt)) if uid else None
            latest_release = base_release
            if latest_renew and (latest_release is None or latest_renew > latest_release):
                latest_release = latest_renew
            if latest_release is None:
                latest_release = base_release or today

            try:
                off = int(_rv(r, 'pay_start_offset_days', 12, 1) or 0)
            except Exception:
                off = 1
            off = 1 if off >= 1 else 0
            payment_start = latest_release + timedelta(days=off)

            # Preserve the original cycle length for every later renewal.
            due_date = _wave74_shift_due_date_for_renewal(
                base_release, original_due, latest_release
            )

            days_left = None
            time_passed_pct = 0.0
            if due_date:
                try:
                    days_left = (due_date - today).days
                except Exception:
                    days_left = None
                try:
                    cycle_days = max(1, (due_date - payment_start).days)
                    elapsed = max(0, (today - payment_start).days)
                    time_passed_pct = min(999.0, (elapsed / cycle_days) * 100.0)
                except Exception:
                    time_passed_pct = 0.0
'''

NEW_TIMING = '''            latest_renew = renew_latest.get((uid, lt)) if uid else None
            timing = _wave75_build_cycle_timing(
                _rv(r, 'date_released', 9, ''),
                _rv(r, 'due_date', 10, ''),
                latest_renew,
                _rv(r, 'pay_start_offset_days', 12, 1),
                today,
            )
            base_release = timing.get('date_released')
            latest_release = timing.get('latest_released')
            payment_start = timing.get('payment_start')
            due_date = timing.get('due_date')
            days_left = timing.get('days_left')
            time_passed_pct = timing.get('time_passed_pct', 0.0)
'''

OLD_FINALIZE = '''    for rec in rows:
        try:
            total = float(rec.get('total_to_pay') or 0)
            if _spina_dash__norm_lt(rec.get('loan_type')) == '7x7':
                allocation = _wave74_allocate_x7_payments(
                    rec.get('principal'),
                    rec.get('payment_start'),
                    rec.get('_x7_payments') or [],
                    today,
                )
                paid = float(allocation.get('principal_paid') or 0.0)
                remaining = float(allocation.get('remaining_principal') or 0.0)
                completion = float(allocation.get('completion_pct') or 0.0)
                rec['total_collected'] = float(allocation.get('total_collected') or 0.0)
                rec['interest_paid'] = float(allocation.get('interest_paid') or 0.0)
                rec['interest_arrears'] = float(allocation.get('interest_arrears') or 0.0)
                rec['payoff_with_interest'] = float(allocation.get('payoff_with_interest') or 0.0)
            else:
                paid = float(rec.get('paid') or 0)
                remaining = max(0.0, total - paid)
                completion = (paid / total * 100.0) if total > 0 else 0.0
            status, priority = _spina_dash__status_for(completion, remaining, rec.get('days_left'))
            rec['paid'] = paid
            rec['remaining'] = remaining
            rec['completion_pct'] = completion
            rec['status'] = status
            rec['priority'] = priority
            rec.pop('_x7_payments', None)
        except Exception:
            pass

    rows.sort(key=lambda x: (x.get('priority', 99), -float(x.get('principal') or 0), -float(x.get('completion_pct') or 0), str(x.get('name') or '')))
'''

NEW_FINALIZE = '''    finalized_rows = []
    for rec in rows:
        try:
            finalized_rows.append(_wave75_finalize_cycle_record(rec, today))
        except Exception:
            try:
                rec.pop('_x7_payments', None)
            except Exception:
                pass
            finalized_rows.append(rec)
    rows = finalized_rows

    rows.sort(key=_wave75_cycle_sort_key)
'''


def replace_exact(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise AssertionError(f"{label}: expected one old block, found {count}")
    return source.replace(old, new, 1)


def patch(source: str) -> str:
    if SERVICE_IMPORT not in source:
        count = source.count(IMPORT_ANCHOR)
        if count != 1:
            raise AssertionError(f"Wave 74 import anchor: expected one block, found {count}")
        source = source.replace(
            IMPORT_ANCHOR,
            IMPORT_ANCHOR + "\n# Wave 75: reusable loan-cycle timing and finalization service.\n" + SERVICE_IMPORT,
            1,
        )

    source = replace_exact(source, OLD_TIMING, NEW_TIMING, "dashboard cycle timing")
    source = replace_exact(source, OLD_FINALIZE, NEW_FINALIZE, "dashboard cycle finalization")

    required = (
        "_wave75_build_cycle_timing(",
        "_wave75_finalize_cycle_record(rec, today)",
        "rows.sort(key=_wave75_cycle_sort_key)",
    )
    for token in required:
        if token not in source:
            raise AssertionError(f"Wave 75 wiring missing: {token}")
    return source


def main() -> None:
    before = APP.read_text(encoding="utf-8")
    after = patch(before)
    if after != before:
        APP.write_text(after, encoding="utf-8", newline="\n")
    print(f"Wave 75 loan-cycle service patch applied: changed={after != before}")


if __name__ == "__main__":
    main()
