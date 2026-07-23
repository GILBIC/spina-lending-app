"""Small formatting helpers extracted from the SPINA desktop app."""

from __future__ import annotations

def fmt_currency(x):
    try:
        return f"PHP {float(x):,.2f}"
    except Exception:
        return "PHP 0.00"

def _spina_dash__fmt_pct(value):
    try:
        return '{:.2f}%'.format(float(value or 0))
    except Exception:
        return '0.00%'
def _spina_v23_money(v):
    try:
        n = float(v or 0)
    except Exception:
        return "PHP 0.00"
    return "PHP {:,.2f}".format(n)
def _spina_v23_percent(v):
    try:
        n = float(v or 0)
    except Exception:
        n = 0.0
    return "{:.0f}%".format(n)

def _spina_cilog_fmt_money(v):
    try:
        if v in (None, ''):
            return ''
        return f"{float(v):,.2f}"
    except Exception:
        try:
            return str(v or '')
        except Exception:
            return ''

def _spina_cilog_fmt_value(field, v):
    if v is None:
        return ''
    fld = str(field or '').lower()
    if fld in {'principal','interest_rate','interest_amount','total_to_pay','payment_amount','last_cash_released','released_cash','new_principal'}:
        if fld == 'interest_rate':
            try:
                return f"{float(v) * 100:.2f}%" if float(v) <= 1 else f"{float(v):.2f}%"
            except Exception:
                return str(v or '')
        return _spina_cilog_fmt_money(v)
    try:
        s = str(v).replace('\n', ' ').strip()
    except Exception:
        s = repr(v)
    return s


def _spina__fmt_client_money(v):
    try:
        n = float(v or 0)
    except Exception:
        return str(v or '')
    if abs(n - int(n)) < 0.000001:
        return f"{int(n):,}"
    return f"{n:,.2f}"


def _spina_v17_fmt_short_money(value):
    try:
        v = float(value or 0)
    except Exception:
        v = 0.0
    av = abs(v)
    if av >= 1_000_000:
        return "PHP {:.2f}M".format(v / 1_000_000)
    if av >= 1_000:
        return "PHP {:.1f}K".format(v / 1_000)
    return "PHP {:,.0f}".format(v)


def _spina_v18_fmt_money_compact(value):
    try:
        v = float(value or 0)
    except Exception:
        v = 0.0
    av = abs(v)
    if av >= 1_000_000:
        return "PHP {:.2f}M".format(v / 1_000_000)
    if av >= 100_000:
        return "PHP {:.0f}K".format(v / 1_000)
    if av >= 1_000:
        return "PHP {:.1f}K".format(v / 1_000)
    return "PHP {:,.0f}".format(v)
