"""Pure Dashboard display helpers extracted from SPINA."""

from __future__ import annotations


def _spina_dash__status_for(completion_pct, remaining, days_left):
    try:
        pct = float(completion_pct or 0)
    except Exception:
        pct = 0.0
    try:
        rem = float(remaining or 0)
    except Exception:
        rem = 0.0
    dl = None
    try:
        if days_left is not None and str(days_left) != '':
            dl = int(days_left)
    except Exception:
        dl = None

    if rem <= 0.004 or pct >= 100:
        return 'Complete', 90
    if pct >= 90:
        return 'Finishing Now', 10
    if pct >= 75:
        return 'Near Completion', 20
    if dl is not None and dl < 0:
        return 'Overdue', 30
    if dl is not None and dl <= 14:
        return 'Due Soon', 40
    return 'In Progress', 80
