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

def _spina_dash__date_text(value):
    try:
        d = _spina_dash__parse_date(value)
        return d.strftime('%Y-%m-%d') if d else ''
    except Exception:
        return ''

def _spina_v24_cilog_parse_day(value):
    try:
        s = str(value or "").strip()
        if not s:
            return None
        # Common format is YYYY-MM-DD HH:MM:SS. Only first 10 characters are needed.
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _spina__norm_weekday(_v):
    try:
        _s = str(_v or '').strip()
    except Exception:
        _s = ''
    if not _s:
        return ''
    _k = _s[:3].lower()
    _mp = {
        'mon': 'Mon', 'tue': 'Tue', 'wed': 'Wed', 'thu': 'Thu',
        'fri': 'Fri', 'sat': 'Sat', 'sun': 'Sun'
    }
    return _mp.get(_k, '')


def _spina__norm_dom(_v):
    try:
        if _v in (None, ''):
            return None
        _n = int(str(_v).strip())
        return _n if 1 <= _n <= 31 else None
    except Exception:
        return None
