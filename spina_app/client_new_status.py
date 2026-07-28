from __future__ import annotations

from typing import Any, Callable, Mapping


_load_ledger_prefs: Callable[[], dict[str, Any]] = lambda: {}


def configure_client_new_status_dependencies(namespace: Mapping[str, Any]) -> None:
    """Configure the existing ledger-preferences loader used by the desktop app."""
    global _load_ledger_prefs

    loader = namespace.get("_load_ledger_prefs")
    if callable(loader):
        _load_ledger_prefs = loader


def _is_client_new(self, name, ledger_date, days=None):
    """Return True if client is NEW.

        Rules:
        - If 'new_until' is explicitly set in the DB:
            * If it's an empty string or unparsable -> treat as explicit OFF (return False).
            * If it's a valid date -> return (ledger_date <= new_until). No fallback.
        - Otherwise (no explicit 'new_until' value present):
            * If 'days' is None/blank, default to prefs 'new_highlight_days' (default 7).
            * If 'days' > 0, return (ledger_date <= (created_at or date_released) + days).
            * Else False.
        """
    nm = (name or "").strip()
    if not nm:
        return False

    lt = self._mode_filter()

    try:
        from datetime import datetime, timedelta, date as _date
    except Exception:
        return False

    # Parse ledger date (fallback to today on error)
    try:
        ld = datetime.strptime(str(ledger_date), "%Y-%m-%d").date()
    except Exception:
        ld = _date.today()

    # Get DB conn
    try:
        conn = getattr(self, "conn", None) or getattr(getattr(self, "db", None), "conn", None)
    except Exception:
        conn = None
    if conn is None:
        return False

    # Load row
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT new_until, created_at, date_released FROM clients WHERE name=? AND loan_type=?",
            (nm, lt)
        ).fetchone()
    except Exception:
        row = None
    if not row:
        return False

    # --- Explicit override via new_until ---
    nu_raw = None
    try:
        nu_raw = row["new_until"]
    except Exception:
        try:
            nu_raw = row[0]
        except Exception:
            nu_raw = None

    if nu_raw is not None:
        s = str(nu_raw).strip()
        if not s:
            # Explicit OFF
            return False
        # Try to parse; if bad -> treat as OFF
        try:
            nu = datetime.strptime(s[:10], "%Y-%m-%d").date()
            return ld <= nu
        except Exception:
            return False

    # --- Fallback: created_at/date_released + days ---
    if days is None or (isinstance(days, str) and not str(days).strip()):
        try:
            days = _load_ledger_prefs().get('new_highlight_days', 7)
        except Exception:
            days = 7

    try:
        d_int = int(days or 0)
    except Exception:
        d_int = 0
    if d_int <= 0:
        return False

    # Use created_at else date_released
    ca_raw = None
    dr_raw = None
    try:
        ca_raw = row["created_at"]
    except Exception:
        try:
            ca_raw = row[1]
        except Exception:
            ca_raw = None
    try:
        dr_raw = row["date_released"]
    except Exception:
        try:
            dr_raw = row[2]
        except Exception:
             dr_raw = None

    start_date = None
    for cand in (ca_raw, dr_raw):
        if cand:
            try:
                start_date = datetime.strptime(str(cand)[:10], "%Y-%m-%d").date()
                break
            except Exception:
                continue
    if not start_date:
        return False

    try:
        return ld <= (start_date + timedelta(days=d_int))
    except Exception:
        return False
