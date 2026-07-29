#!/usr/bin/env python3
"""Apply Wave 74 calculation rules to the current SPINA desktop foundation."""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MARKER = "# --- BEGIN: Dashboard tab - finishing loans based on latest released date ---"
IMPORT_MARKER = "# Wave 74: shared calculation rules."
IMPORT_BLOCK = '''# Wave 74: shared calculation rules.
from spina_app.calculation_rules import (
    allocate_x7_payments as _wave74_allocate_x7_payments,
    ceil_thousand_units as _wave74_ceil_thousand_units,
    normalized_total_to_pay as _wave74_normalized_total_to_pay,
    shift_due_date_for_renewal as _wave74_shift_due_date_for_renewal,
    x7_daily_interest as _wave74_x7_daily_interest,
)


'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise AssertionError(f"{label}: expected one old block, found {count}")
    return source.replace(old, new, 1)


def node_offsets(source: str, node: ast.AST) -> tuple[int, int]:
    lines = source.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: node.lineno - 1])
    end = sum(len(line) for line in lines[: node.end_lineno])
    return start, end


def replace_top_level_function(source: str, name: str, replacement: str) -> str:
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError(f"Expected one top-level {name}, found {len(matches)}")
    current = ast.get_source_segment(source, matches[0]) or ""
    normalized = textwrap.dedent(replacement).strip()
    if textwrap.dedent(current).strip() == normalized:
        return source
    start, end = node_offsets(source, matches[0])
    return source[:start] + normalized + "\n" + source[end:]


def patch(source: str) -> str:
    if IMPORT_MARKER not in source:
        if MARKER not in source:
            raise AssertionError("Dashboard marker not found")
        source = source.replace(MARKER, MARKER + "\n" + IMPORT_BLOCK, 1)

    source = replace_once(
        source,
        '''            total_to_pay = _spina_dash__float(_rv(r, 'total_to_pay', 8, 0))
            if total_to_pay <= 0 or (lt == 'Regular' and interest > 0 and abs(total_to_pay - principal) < 0.01):
                total_to_pay = principal + interest
            if lt == '7x7' and total_to_pay <= 0:
                total_to_pay = principal
''',
        '''            total_to_pay = _wave74_normalized_total_to_pay(
                lt,
                principal,
                interest,
                _spina_dash__float(_rv(r, 'total_to_pay', 8, 0)),
            )
''',
        "normalized total-to-pay",
    )

    source = replace_once(
        source,
        '''            # Keep due date aligned with the latest release when renewals exist but due_date is stale.
            due_date = original_due
            if base_release and original_due and latest_release and latest_release > base_release:
                try:
                    cycle_days = (original_due - base_release).days
                    if cycle_days > 0 and (due_date is None or due_date < latest_release):
                        due_date = latest_release + timedelta(days=cycle_days)
                except Exception:
                    pass
''',
        '''            # Preserve the original cycle length for every later renewal.
            due_date = _wave74_shift_due_date_for_renewal(
                base_release, original_due, latest_release
            )
''',
        "renewal due date",
    )

    source = replace_once(
        source,
        "                'paid': 0.0,\n                'completion_pct': 0.0,\n",
        "                'paid': 0.0,\n                '_x7_payments': [],\n                'completion_pct': 0.0,\n",
        "7x7 payment buffer",
    )

    source = replace_once(
        source,
        '''                    if rec is not None:
                        rec['paid'] = float(rec.get('paid') or 0) + pay
''',
        '''                    if rec is not None:
                        if _spina_dash__norm_lt(rec.get('loan_type')) == '7x7':
                            rec.setdefault('_x7_payments', []).append((tdate, pay))
                        else:
                            rec['paid'] = float(rec.get('paid') or 0) + pay
''',
        "transaction allocation",
    )

    source = replace_once(
        source,
        '''    for rec in rows:
        try:
            total = float(rec.get('total_to_pay') or 0)
            paid = float(rec.get('paid') or 0)
            remaining = max(0.0, total - paid)
            completion = (paid / total * 100.0) if total > 0 else 0.0
            status, priority = _spina_dash__status_for(completion, remaining, rec.get('days_left'))
            rec['paid'] = paid
            rec['remaining'] = remaining
            rec['completion_pct'] = completion
            rec['status'] = status
            rec['priority'] = priority
        except Exception:
            pass
''',
        '''    for rec in rows:
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
''',
        "dashboard final calculation",
    )

    source = replace_top_level_function(
        source,
        "_spina_cashctl__ceil_thousand_units",
        '''
def _spina_cashctl__ceil_thousand_units(_amount):
    return _wave74_ceil_thousand_units(_amount)
''',
    )
    source = replace_top_level_function(
        source,
        "_spina_cashctl__x7_daily_interest",
        '''
def _spina_cashctl__x7_daily_interest(_remaining_principal):
    """7x7 daily interest: 1..1000=7/day, 1001..2000=14/day, etc."""
    return _wave74_x7_daily_interest(_remaining_principal)
''',
    )

    source = replace_once(
        source,
        '''    remaining_principal = float(principal)
    interest_arrears = 0.0
    prev_dt = start_dt - timedelta(days=1)

    for pay_dt, amount in payments:
        if pay_dt < start_dt:
            continue
        if pay_dt > end_dt:
            break
        try:
            gap = (pay_dt - prev_dt).days
        except Exception:
            gap = 1
        if gap <= 0:
            gap = 1
        daily_interest = _spina_cashctl__x7_daily_interest(remaining_principal)
        interest_due = (daily_interest * float(gap)) + float(interest_arrears)
        interest_paid = min(float(amount), float(interest_due))
        principal_paid = max(0.0, float(amount) - float(interest_paid))
        remaining_principal = max(0.0, float(remaining_principal) - float(principal_paid))
        interest_arrears = max(0.0, float(interest_due) - float(interest_paid))
        prev_dt = pay_dt
        if remaining_principal <= 0.004 and interest_arrears <= 0.004:
            remaining_principal = 0.0
            interest_arrears = 0.0
            break

    if remaining_principal > 0:
        try:
            tail_gap = (end_dt - prev_dt).days
        except Exception:
            tail_gap = 0
        if tail_gap > 0:
            interest_arrears += _spina_cashctl__x7_daily_interest(remaining_principal) * float(tail_gap)

    return round(max(0.0, float(remaining_principal) + float(interest_arrears)), 2)
''',
        '''    allocation = _wave74_allocate_x7_payments(
        principal, start_dt, payments, end_dt
    )
    return round(float(allocation.get('payoff_with_interest') or 0.0), 2)
''',
        "cash-control 7x7 allocation",
    )
    return source


def main() -> None:
    before = APP.read_text(encoding="utf-8")
    after = patch(before)
    if after != before:
        APP.write_text(after, encoding="utf-8", newline="\n")
    print(f"Wave 74 calculation patch applied: changed={after != before}")


if __name__ == "__main__":
    main()
