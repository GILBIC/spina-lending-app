from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

_CLIENT_SERVICE_DEPENDENCIES: dict[str, Any] = {}


def configure_client_service_dependencies(namespace: Mapping[str, Any]) -> None:
    _CLIENT_SERVICE_DEPENDENCIES.clear()
    _CLIENT_SERVICE_DEPENDENCIES.update(namespace)
    protected = {"__name__", "__file__", "__package__", "__builtins__", "_CLIENT_SERVICE_DEPENDENCIES", "configure_client_service_dependencies"}
    for name, value in namespace.items():
        if name not in protected:
            globals()[name] = value


def _app__norm_lt_value(self, v):
    try:
        return self.db._effective_lt(v)
    except Exception:
        s = (str(v or '').strip() or '')
        s2 = s.lower().replace(' ', '')
        if s2 in ('7x7','7×7'):
            return '7x7'
        return 'Regular'

def _app__other_lt(self, lt):
    lt = _app__norm_lt_value(self, lt)
    return '7x7' if lt == 'Regular' else 'Regular'

def _spina__client_schedule_anchor(row: dict | None):
    row = row or {}
    anchor = _spina__parse_day_ymd((row or {}).get('payment_start_date') or (row or {}).get('date_released') or (row or {}).get('created_at') or (row or {}).get('due_date'))
    if anchor and not (row or {}).get('payment_start_date'):
        try:
            off = int((row or {}).get('pay_start_offset_days') or 0)
        except Exception:
            off = 0
        if off >= 1:
            try:
                anchor = anchor + timedelta(days=1)
            except Exception:
                pass
    return anchor

def _spina__client_due_meta_base(info: dict | None, as_of=None) -> tuple[str, bool]:
    """Return (day_due_label, due_today_bool) using stored schedule fields when present."""
    try:
        row = info or {}
        term = str(row.get('payment_term') or '').strip().title()
    except Exception:
        row = {}
        term = ''

    target = _spina__parse_day_ymd(as_of) if as_of else date.today()
    anchor = _spina__client_schedule_anchor(row)

    if term == 'Daily':
        due_today = bool(anchor and target and target >= anchor)
        return ('Daily', due_today)

    if term == 'Weekly':
        weekday = _spina__norm_weekday((row or {}).get('due_weekday'))
        if not weekday and anchor:
            try:
                weekday = anchor.strftime('%a')
            except Exception:
                weekday = ''
        if weekday:
            mp = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
            due_today = bool(anchor and target and target >= anchor and target.weekday() == mp.get(weekday, -99))
            return (weekday, due_today)
        return ('Weekly', False)

    if term == 'Monthly':
        dom = _spina__norm_dom((row or {}).get('monthly_due_day'))
        if dom is None and anchor:
            dom = anchor.day
        if dom is not None:
            import calendar as _cal
            label = f"Day {dom}"
            if target and anchor and target >= anchor:
                try:
                    due_dom = min(dom, _cal.monthrange(target.year, target.month)[1])
                    return (label, bool(target.day == due_dom))
                except Exception:
                    return (label, False)
            return (label, False)
        return ('Monthly', False)

    if term == 'Semi':
        d1 = _spina__norm_dom((row or {}).get('semi_due_day1'))
        d2 = _spina__norm_dom((row or {}).get('semi_due_day2'))
        if d1 is not None and d2 is not None:
            if d2 < d1:
                d1, d2 = d2, d1
            label = f"{d1}/{d2}"
            if target and anchor and target >= anchor:
                import calendar as _cal
                last_dom = _cal.monthrange(target.year, target.month)[1]
                v1 = min(d1, last_dom)
                v2 = min(d2, last_dom)
                return (label, bool(target.day in (v1, v2)))
            return (label, False)
        if anchor and target:
            delta = (target - anchor).days
            return ('15-day cycle', bool(delta >= 0 and (delta % 15 == 0)))
        return ('15-day cycle', False)

    return ('', False)

def _spina__parse_flexible_due_rule(row, target=None):
    """Return (label, due_today_bool) for optional flex_due_rule.

    Supported examples:
      - salary 15/30 window 2 -> due from 13-17 and last-day-2 through last-day+2 if valid
      - weekly Monday Thursday -> due every Monday and Thursday
      - 2nd Saturday             -> due every 2nd Saturday of the month
      - days 13,14,15,29,30,31   -> due on those dates of each month
    Blank/unknown rules return None so normal Payment Term logic is used.
    """
    try:
        rule = str((row or {}).get('flex_due_rule') or '').strip()
    except Exception:
        rule = ''
    if not rule:
        return None

    try:
        target = _spina__parse_day_ymd(target) if target else date.today()
    except Exception:
        target = date.today()
    try:
        anchor = _spina__client_schedule_anchor(row or {})
        if anchor and target < anchor:
            return (rule, False)
    except Exception:
        pass

    import re as _re
    import calendar as _cal
    rl = rule.lower().strip()
    rl_norm = _re.sub(r'\s+', ' ', rl)
    last_dom = _cal.monthrange(target.year, target.month)[1]

    # Salary date pairs with a before/after window.
    # Examples:
    #   salary 5/20 window 1  -> due on 4,5,6 and 19,20,21
    #   salary 10/25 window 1 -> due on 9,10,11 and 24,25,26
    #   salary 15/30 window 1 -> due on 14,15,16 and around month-end
    pair = None
    try:
        m_pair = _re.search(r'(?:salary\s*)?(\d{1,2})\s*(?:/|-|and|,)\s*(\d{1,2})', rl_norm)
        if m_pair:
            d1 = int(m_pair.group(1))
            d2 = int(m_pair.group(2))
            if 1 <= d1 <= 31 and 1 <= d2 <= 31:
                pair = (d1, d2)
    except Exception:
        pair = None

    if pair and (('salary' in rl_norm) or ('/' in rl_norm) or ('-' in rl_norm)):
        window = 1
        try:
            # New rule code: "window N" means N days before and N days after.
            m = _re.search(r'window\s*(\d+)', rl_norm)
            if not m:
                m = _re.search(r'before\s*(?:&|and)?\s*after\s*(\d+)', rl_norm)
            if not m:
                m = _re.search(r'(?:\+/-|±)\s*(\d+)', rl_norm)
            if not m:
                # Backward compatibility: old saved rules used "early N".
                # From this build onward, those are interpreted as before/after window rules.
                m = _re.search(r'early\s*(\d+)', rl_norm)
            if not m:
                m = _re.search(r'allow\s*(\d+)', rl_norm)
            if not m:
                m = _re.search(r'(\d+)\s*days?\s*early', rl_norm)
            if m:
                window = max(0, min(10, int(m.group(1))))
        except Exception:
            window = 1

        d1, d2 = pair
        # Treat 30/31 near month-end as the actual last day of the month.
        # This handles February and months with 31 days cleanly.
        d2_eff = last_dom if d2 >= 30 else min(d2, last_dom)
        d1_eff = min(d1, last_dom)

        first_start = max(1, d1_eff - window)
        first_end = min(last_dom, d1_eff + window)
        first_window = set(range(first_start, first_end + 1))
        second_start = max(1, d2_eff - window)
        second_end = min(last_dom, d2_eff + window)
        second_window = set(range(second_start, second_end + 1))
        label = f"{d1}/{d2} flex (±{window}d)"
        return (label, bool(target.day in first_window or target.day in second_window))

    # Weekly/twice-weekly weekday list.
    # Examples:
    #   weekly Monday Thursday      -> due every Monday and Thursday
    #   twice weekly Tuesday Friday -> due every Tuesday and Friday
    #   Monday and Saturday         -> due every Monday and Saturday
    weekdays = {
        'mon': 0, 'monday': 0,
        'tue': 1, 'tues': 1, 'tuesday': 1,
        'wed': 2, 'wednesday': 2,
        'thu': 3, 'thur': 3, 'thurs': 3, 'thursday': 3,
        'fri': 4, 'friday': 4,
        'sat': 5, 'saturday': 5,
        'sun': 6, 'sunday': 6,
    }
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    try:
        weekday_tokens = _re.findall(r'\b(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|thur|thurs|friday|fri|saturday|sat|sunday|sun)\b', rl_norm)
        weekday_nums = []
        for tok in weekday_tokens:
            wd = weekdays.get(tok)
            if wd is None:
                continue
            if wd not in weekday_nums:
                weekday_nums.append(wd)
        # Only treat plain weekday lists as flexible weekly rules if there are 2+ weekdays,
        # or if the rule explicitly says weekly/twice-weekly.
        if weekday_nums and (('weekly' in rl_norm) or ('twice' in rl_norm) or ('2x' in rl_norm) or len(weekday_nums) >= 2):
            label = 'Weekly ' + '/'.join(weekday_names[wd][:3] for wd in weekday_nums)
            return (label, bool(target.weekday() in set(weekday_nums)))
    except Exception:
        pass

    # Nth weekday monthly: "2nd Saturday", "last Friday", etc.
    ord_map = {
        '1': 1, '1st': 1, 'first': 1,
        '2': 2, '2nd': 2, 'second': 2,
        '3': 3, '3rd': 3, 'third': 3,
        '4': 4, '4th': 4, 'fourth': 4,
        '5': 5, '5th': 5, 'fifth': 5,
    }
    try:
        m = _re.search(r'\b(last|1st|2nd|3rd|4th|5th|first|second|third|fourth|fifth|[1-5])\s+(monday|mon|tuesday|tue|wednesday|wed|thursday|thu|thur|thurs|friday|fri|saturday|sat|sunday|sun)\b', rl_norm)
        if m:
            ord_txt = m.group(1)
            wd_txt = m.group(2)
            wd = weekdays.get(wd_txt, -1)
            if ord_txt == 'last':
                d = last_dom
                while d >= 1:
                    if date(target.year, target.month, d).weekday() == wd:
                        due_dom = d
                        break
                    d -= 1
                label = f"last {wd_txt[:3].title()}"
            else:
                n = ord_map.get(ord_txt, 1)
                hits = []
                for d in range(1, last_dom + 1):
                    if date(target.year, target.month, d).weekday() == wd:
                        hits.append(d)
                due_dom = hits[n - 1] if len(hits) >= n else None
                label = f"{n}{'st' if n==1 else 'nd' if n==2 else 'rd' if n==3 else 'th'} {wd_txt[:3].title()}"
            return (label, bool(due_dom and target.day == due_dom))
    except Exception:
        pass

    # Exact day list: "days 13,14,15,29,30,31".
    try:
        if rl_norm.startswith('days') or rl_norm.startswith('day '):
            nums = [int(x) for x in _re.findall(r'\b([1-9]|[12][0-9]|3[01])\b', rl_norm)]
            nums = [n for n in nums if 1 <= n <= last_dom]
            label = 'Days ' + ','.join(str(n) for n in nums[:8])
            return (label, bool(target.day in set(nums)))
    except Exception:
        pass

    return None

def _spina__client_due_meta(info: dict | None, as_of=None) -> tuple[str, bool]:
    try:
        flex = _spina__parse_flexible_due_rule(info or {}, target=as_of)
        if flex is not None:
            return flex
    except Exception:
        pass
    try:
        return _spina__client_due_meta_base(info, as_of=as_of)
    except Exception:
        return ("", False)

