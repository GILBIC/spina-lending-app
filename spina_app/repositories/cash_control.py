"""Read-only database adapter for SPINA Cash Control.

This module owns collection-history and current-cycle payment reads. It contains no
Tkinter code and performs no database writes or schema changes.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Callable

from spina_app.calculation_rules import normalize_loan_type
from spina_app.utilities.dates import _spina_cashctl__valid_date
from spina_app.utilities.numbers import _spina_cashctl__int_range

LogCallback = Callable[[str, BaseException | None], Any]


def _log(log_exc: LogCallback | None, context: str, exc: BaseException) -> None:
    if not callable(log_exc):
        return
    try:
        log_exc(context, exc)
    except Exception:
        pass


def _connection_from_app(app: Any) -> Any:
    try:
        return getattr(getattr(app, "db", None), "conn", None) or getattr(
            app, "conn", None
        )
    except Exception:
        return None


def _row_value(row: Any, key: str, index: int, default: Any = None) -> Any:
    try:
        return row[key]
    except Exception:
        try:
            return row[index]
        except Exception:
            return default


def _table_columns(cursor: Any, table_name: str) -> set[str]:
    try:
        return {
            str(row[1])
            for row in cursor.execute(
                "PRAGMA table_info(%s)" % table_name
            ).fetchall()
        }
    except Exception:
        return set()


def fetch_collection_totals(
    app: Any,
    date_s: Any,
    *,
    log_exc: LogCallback | None = None,
) -> dict[str, Any]:
    """Return Regular, 7x7, unclassified, and combined collection totals."""
    selected_date = _spina_cashctl__valid_date(date_s)
    regular = x7 = total = 0.0

    try:
        db = getattr(app, "db", None)
        if db is not None and hasattr(db, "get_databank_daily_total"):
            total = round(
                float(db.get_databank_daily_total(selected_date, loan_type="__ALL__") or 0.0),
                2,
            )
            regular = round(
                float(db.get_databank_daily_total(selected_date, loan_type="Regular") or 0.0),
                2,
            )
            x7 = round(
                float(db.get_databank_daily_total(selected_date, loan_type="7x7") or 0.0),
                2,
            )
            other = round(total - regular - x7, 2)
            if abs(other) < 0.005:
                other = 0.0
            return {
                "date": selected_date,
                "regular": regular,
                "7x7": x7,
                "other": other,
                "combined": total,
            }
    except Exception:
        # Preserve the existing direct-query fallback when the optimized DB method
        # is unavailable or fails.
        pass

    try:
        conn = _connection_from_app(app)
        if conn is None:
            raise RuntimeError("Cash Control database connection is unavailable")
        rows = conn.cursor().execute(
            """
            SELECT IFNULL(NULLIF(TRIM(loan_type),''),'Regular') AS loan_type,
                   COALESCE(SUM(COALESCE(payment,0)),0) AS total_payment
              FROM transactions
             WHERE date(date)=date(?)
             GROUP BY IFNULL(NULLIF(TRIM(loan_type),''),'Regular')
            """,
            (selected_date,),
        ).fetchall() or []

        other_total = 0.0
        for row in rows:
            raw_loan_type = _row_value(row, "loan_type", 0, "Regular")
            amount = float(_row_value(row, "total_payment", 1, 0.0) or 0.0)
            loan_type = normalize_loan_type(raw_loan_type)
            if loan_type == "7x7":
                x7 += amount
            elif loan_type == "Regular":
                regular += amount
            else:
                other_total += amount

        total = round(regular + x7 + other_total, 2)
        other = round(total - regular - x7, 2)
        if abs(other) < 0.005:
            other = 0.0
        return {
            "date": selected_date,
            "regular": round(regular, 2),
            "7x7": round(x7, 2),
            "other": other,
            "combined": total,
        }
    except Exception as exc:
        _log(log_exc, "cash_control.collection_totals", exc)
        return {
            "date": selected_date,
            "regular": 0.0,
            "7x7": 0.0,
            "other": 0.0,
            "combined": 0.0,
        }


def fetch_average_collection(
    app: Any,
    date_s: Any,
    window_days: Any = 30,
    *,
    log_exc: LogCallback | None = None,
) -> dict[str, Any]:
    """Average only active collection days before the selected date."""
    selected_date = _spina_cashctl__valid_date(date_s)
    days = _spina_cashctl__int_range(window_days, 30, 1, 365)
    try:
        end_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    except Exception:
        end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    start_s = start_date.strftime("%Y-%m-%d")
    end_s = end_date.strftime("%Y-%m-%d")

    total = 0.0
    active_days = 0
    average = 0.0
    try:
        conn = _connection_from_app(app)
        if conn is None:
            raise RuntimeError("Cash Control database connection is unavailable")
        rows = conn.cursor().execute(
            """
            SELECT date(date) AS d,
                   COALESCE(SUM(COALESCE(payment,0)),0) AS total_payment
              FROM transactions
             WHERE date(date) >= date(?)
               AND date(date) < date(?)
             GROUP BY date(date)
             ORDER BY date(date)
            """,
            (start_s, end_s),
        ).fetchall() or []
        daily_amounts: list[float] = []
        for row in rows:
            amount = float(_row_value(row, "total_payment", 1, 0.0) or 0.0)
            if abs(amount) >= 0.005:
                daily_amounts.append(amount)
        total = round(sum(daily_amounts), 2)
        active_days = len(daily_amounts)
        average = round(total / active_days, 2) if active_days else 0.0
    except Exception as exc:
        _log(log_exc, "cash_control.average_collection", exc)

    return {
        "selected_date": selected_date,
        "start_date": start_s,
        "end_date_exclusive": end_s,
        "window_days": days,
        "active_days": active_days,
        "total": total,
        "average": average,
    }


def fetch_x7_cycle_payments(
    app: Any,
    record: dict[str, Any],
    start_date: Any,
    end_date: Any,
    *,
    log_exc: LogCallback | None = None,
) -> list[tuple[Any, float]]:
    """Read positive 7x7 payments for one client's current cycle."""
    payments: list[tuple[Any, float]] = []
    try:
        conn = _connection_from_app(app)
        if conn is None:
            return payments
        cursor = conn.cursor()
        columns = _table_columns(cursor, "transactions")
        if not {"date", "payment"}.issubset(columns):
            return payments

        client_uid = str(record.get("client_uid") or "").strip()
        name = str(record.get("name") or "").strip()
        params: list[Any] = [
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        ]
        where = ["date(date) >= date(?)", "date(date) <= date(?)"]
        if "loan_type" in columns:
            normalized_sql = (
                "LOWER(REPLACE(REPLACE(TRIM(IFNULL(loan_type,'')),'×','x'),' ',''))"
            )
            where.append(
                "(%s IN ('7x7','7x7emer','emer','emergency') OR %s LIKE '%%7x7%%')"
                % (normalized_sql, normalized_sql)
            )
        if client_uid and "client_uid" in columns:
            where.append("IFNULL(client_uid,'') = ?")
            params.append(client_uid)
        elif name and "name" in columns:
            where.append("UPPER(IFNULL(name,'')) = ?")
            params.append(name.upper())
        else:
            where.append("1=0")

        sql = (
            "SELECT date, payment FROM transactions WHERE "
            + " AND ".join(where)
            + " ORDER BY date(date) ASC"
        )
        for row in cursor.execute(sql, tuple(params)).fetchall() or []:
            try:
                paid_on = datetime.strptime(
                    str(_row_value(row, "date", 0, ""))[:10], "%Y-%m-%d"
                ).date()
                amount = float(_row_value(row, "payment", 1, 0.0) or 0.0)
                if amount > 0:
                    payments.append((paid_on, amount))
            except Exception:
                continue
    except Exception as exc:
        _log(log_exc, "cash_control.x7_cycle_payments", exc)
    return payments
