"""Configurable Data Bank auto-close extracted in SPINA Wave 82."""
from __future__ import annotations

import calendar
import json
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

_DEPENDENCIES: dict[str, Any] = {}
_PROTECTED = {"__name__", "__file__", "__package__", "__builtins__", "_DEPENDENCIES", "_PROTECTED", "configure_data_bank_auto_close_dependencies"}


def configure_data_bank_auto_close_dependencies(namespace: Mapping[str, Any]) -> None:
    _DEPENDENCIES.clear()
    _DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED:
            globals()[name] = value

def _spina_auto_close_after_days_value():
    """Return the configured auto-close delay in days. 0 = disabled."""
    try:
        s = load_settings()
    except Exception:
        s = dict(_DEFAULT_SETTINGS)
    try:
        days = int(float(str(s.get('auto_close_after_days', 0) or 0).strip()))
    except Exception:
        days = 0
    if days < 0:
        days = 0
    if days > 365:
        days = 365
    return days

def _spina_auto_close_candidate_dates(db, cutoff_date_s):
    """Return transaction dates up to cutoff that are not already closed."""
    out = []
    try:
        cur = db.conn.cursor()
        rows = cur.execute(
            """
            SELECT DISTINCT date(date) AS close_date
              FROM transactions
             WHERE date(date) <= date(?)
               AND COALESCE(payment, 0) <> 0
             ORDER BY date(date) ASC
            """,
            (cutoff_date_s,),
        ).fetchall()
    except Exception:
        rows = []
    for r in rows or []:
        try:
            ds = (r['close_date'] if hasattr(r, 'keys') else r[0])
        except Exception:
            ds = ''
        ds = str(ds or '').strip()[:10]
        if not ds:
            continue
        try:
            rec = db.get_databank_day_close(ds)
            if rec and bool(int(rec.get('is_closed') or 0)):
                continue
        except Exception:
            pass
        out.append(ds)
    return out

def _spina_schedule_auto_daily_close(self):
    """Run auto close now and then check periodically while the app is open."""
    try:
        self.run_auto_daily_close(show_message=False)
    except Exception as e:
        try:
            _log_exc('auto_daily_close.initial', e)
        except Exception:
            pass

    try:
        root = getattr(self, 'root', None)
        if root is None:
            return
        # Check every hour. The date threshold comes from Settings each time.
        root.after(60 * 60 * 1000, lambda: self._schedule_auto_daily_close())
    except Exception:
        pass
