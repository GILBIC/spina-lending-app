"""Pure date parsing and validation helpers extracted from SPINA."""

from __future__ import annotations

from datetime import datetime, date, timedelta

def _spina_cashctl__valid_date(value):
    try:
        s = str(value or '').strip()[:10]
        datetime.strptime(s, '%Y-%m-%d')
        return s
    except Exception:
        return date.today().strftime('%Y-%m-%d')

def _spina__parse_day_ymd(_v):
    try:
        _s = str(_v or '').strip()[:10]
        if not _s:
            return None
        return datetime.strptime(_s, "%Y-%m-%d").date()
    except Exception:
        return None

def _spina_dash__parse_date(value):
    try:
        s = str(value or '').strip()[:10]
        if not s:
            return None
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return None
