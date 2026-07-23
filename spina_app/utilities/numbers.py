"""Pure numeric parsing helpers extracted from SPINA."""

from __future__ import annotations

import re

def _spina_dash__float(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(str(value).replace(',', '').strip() or default)
    except Exception:
        return float(default)

def _spina_v27_count_from_text(value):
    try:
        m = re.search(r"(\d+)", str(value or ""))
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def _spina_v25_parse_count_from_var(var_value):
    try:
        s = str(var_value or "")
        m = re.search(r"(\d+)", s)
        return m.group(1) if m else "0"
    except Exception:
        return "0"


def _spina_cashctl__parse_amount(value):
    try:
        s = str(value or '').replace(',', '').strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def _spina_cashctl__int_range(value, default, min_value=1, max_value=120):
    try:
        v = int(round(_spina_cashctl__parse_amount(value)))
    except Exception:
        v = int(default)
    if v < min_value:
        v = min_value
    if v > max_value:
        v = max_value
    return v
