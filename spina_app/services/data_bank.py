"""Pure Data Bank rules for SPINA Wave 82."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping

COMBINED_CLOSE_BUCKET = "__ALL__"


def combined_close_bucket(_loan_type: Any = None) -> str:
    """Data Bank daily close always combines Regular and 7x7."""
    return COMBINED_CLOSE_BUCKET


def normalize_close_workflow(workflow_status: Any, variance: Any = 0.0, is_closed: Any = True) -> str:
    wf = str(workflow_status or "").strip().title()
    if wf in ("Open", "Pending", "Resolved"):
        return wf
    if not bool(is_closed):
        return "Open"
    try:
        value = float(variance or 0.0)
    except Exception:
        value = 0.0
    return "Resolved" if abs(value) < 0.005 else "Pending"


def variance_status(variance: Any) -> str:
    try:
        value = float(variance or 0.0)
    except Exception:
        value = 0.0
    if abs(value) < 0.005:
        return "Balanced"
    return "Overage" if value > 0 else "Short"


def parse_auto_close_days(settings: Mapping[str, Any] | None, *, maximum: int = 365) -> int:
    try:
        days = int(float(str((settings or {}).get("auto_close_after_days", 0) or 0).strip()))
    except Exception:
        days = 0
    return max(0, min(int(maximum), days))


def auto_close_cutoff(days_after: Any, *, today: date | None = None) -> date | None:
    try:
        days = int(days_after)
    except Exception:
        return None
    if days <= 0:
        return None
    anchor = today or date.today()
    return anchor - timedelta(days=days)


def record_is_closed(record: Mapping[str, Any] | None) -> bool:
    if not record:
        return False
    try:
        return bool(int(record.get("is_closed") or 0))
    except Exception:
        return bool(record.get("is_closed"))
