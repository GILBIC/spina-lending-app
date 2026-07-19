"""Small formatting helpers extracted from the SPINA desktop app."""

from __future__ import annotations

def fmt_currency(x):
    try:
        return f"PHP {float(x):,.2f}"
    except Exception:
        return "PHP 0.00"
