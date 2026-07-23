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
