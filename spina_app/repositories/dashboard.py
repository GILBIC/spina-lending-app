"""Database adapter for the SPINA dashboard.

This module owns dashboard-specific reads from clients, renewals, and transactions.
It deliberately contains no Tkinter code. Reusable loan-cycle calculations remain
in :mod:`spina_app.services.loan_cycles`.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Callable

from spina_app.calculation_rules import normalize_loan_type, normalized_total_to_pay
from spina_app.services.loan_cycles import (
    build_cycle_timing,
    cycle_sort_key,
    finalize_cycle_record,
)
from spina_app.utilities.dates import _spina_dash__parse_date
from spina_app.utilities.numbers import _spina_dash__float

LogCallback = Callable[[str, BaseException | None], Any]


def _log(log_exc: LogCallback | None, context: str, exc: BaseException) -> None:
    if not callable(log_exc):
        return
    try:
        log_exc(context, exc)
    except Exception:
        pass


def _row_value(row: Any, key: str, index: int, default: Any = None) -> Any:
    try:
        return row[key]
    except Exception:
        try:
            return row[index]
        except Exception:
            return default


def _table_exists(cursor: Any, table_name: str) -> bool:
    try:
        row = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return bool(row)
    except Exception:
        return False


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


def _connection_from_app(app: Any) -> Any:
    try:
        return getattr(getattr(app, "db", None), "conn", None) or getattr(
            app, "conn", None
        )
    except Exception:
        return None


def fetch_dashboard_rows(
    app: Any,
    *,
    log_exc: LogCallback | None = None,
    today: date | str | None = None,
) -> list[dict[str, Any]]:
    """Return active dashboard rows for each client's current loan cycle.

    The SQL remains compatible with SPINA's SQLite-style PostgreSQL wrapper. The
    repository performs one client read, one renewal aggregation, and one
    transaction pass beginning at the earliest active-cycle payment date.
    """
    conn = _connection_from_app(app)
    if conn is None:
        return []

    cursor = conn.cursor()
    client_columns = _table_columns(cursor, "clients")
    transaction_columns = _table_columns(cursor, "transactions")
    renewal_columns = (
        _table_columns(cursor, "renewals")
        if _table_exists(cursor, "renewals")
        else set()
    )
    if not client_columns or not _table_exists(cursor, "clients"):
        return []

    def client_column(name: str, default_sql: str = "''") -> str:
        if name in client_columns:
            return "c.%s" % name
        return "%s AS %s" % (default_sql, name)

    select_columns = [
        client_column("id", "0"),
        client_column("client_uid", "''"),
        client_column("person_uid", "''"),
        client_column("name", "''"),
        client_column("loan_type", "'Regular'"),
        client_column("area", "''"),
        client_column("principal", "0"),
        client_column("interest_amount", "0"),
        client_column("total_to_pay", "0"),
        client_column("date_released", "''"),
        client_column("due_date", "''"),
        client_column("payment_start_date", "''"),
        client_column("pay_start_offset_days", "1"),
        client_column("is_archived", "0"),
    ]

    try:
        client_rows = cursor.execute(
            "SELECT %s FROM clients c "
            "WHERE IFNULL(c.is_archived,0)=0 "
            "ORDER BY c.name COLLATE NOCASE" % ", ".join(select_columns)
        ).fetchall()
    except Exception:
        try:
            client_rows = cursor.execute(
                "SELECT %s FROM clients c ORDER BY c.name COLLATE NOCASE"
                % ", ".join(select_columns)
            ).fetchall()
        except Exception as exc:
            _log(log_exc, "dashboard.fetch_clients", exc)
            return []

    renewal_latest: dict[tuple[str, str], date] = {}
    if _table_exists(cursor, "renewals") and {
        "client_uid",
        "renew_date",
    }.issubset(renewal_columns):
        try:
            loan_type_expression = (
                "IFNULL(NULLIF(TRIM(loan_type),''),'Regular')"
                if "loan_type" in renewal_columns
                else "'Regular'"
            )
            sql = (
                "SELECT client_uid, %s AS loan_type, "
                "MAX(date(renew_date)) AS latest_renew_date "
                "FROM renewals "
                "WHERE client_uid IS NOT NULL AND TRIM(client_uid)<>'' "
                "GROUP BY client_uid, %s"
            ) % (loan_type_expression, loan_type_expression)
            for row in cursor.execute(sql).fetchall() or []:
                try:
                    uid = str(_row_value(row, "client_uid", 0, "") or "").strip()
                    loan_type = normalize_loan_type(
                        _row_value(row, "loan_type", 1, "Regular")
                    )
                    renewed = _spina_dash__parse_date(
                        _row_value(row, "latest_renew_date", 2, None)
                    )
                    if uid and renewed:
                        renewal_latest[(uid, loan_type)] = renewed
                except Exception:
                    continue
        except Exception as exc:
            _log(log_exc, "dashboard.fetch_renewals", exc)

    effective_today = _spina_dash__parse_date(today) or date.today()
    rows: list[dict[str, Any]] = []
    row_by_uid: dict[tuple[str, str], dict[str, Any]] = {}
    row_by_name: dict[tuple[str, str], dict[str, Any]] = {}
    earliest_payment_start: date | None = None

    for row in client_rows or []:
        try:
            uid = str(_row_value(row, "client_uid", 1, "") or "").strip()
            name = str(_row_value(row, "name", 3, "") or "").strip()
            if not name:
                continue

            loan_type = normalize_loan_type(
                _row_value(row, "loan_type", 4, "Regular")
            )
            area = str(_row_value(row, "area", 5, "") or "").strip()
            principal = _spina_dash__float(
                _row_value(row, "principal", 6, 0)
            )
            interest = _spina_dash__float(
                _row_value(row, "interest_amount", 7, 0)
            )
            total_to_pay = normalized_total_to_pay(
                loan_type,
                principal,
                interest,
                _spina_dash__float(_row_value(row, "total_to_pay", 8, 0)),
            )

            timing = build_cycle_timing(
                _row_value(row, "date_released", 9, ""),
                _row_value(row, "due_date", 10, ""),
                renewal_latest.get((uid, loan_type)) if uid else None,
                _row_value(row, "pay_start_offset_days", 12, 1),
                effective_today,
            )
            payment_start = timing.get("payment_start")
            record = {
                "client_uid": uid,
                "person_uid": str(
                    _row_value(row, "person_uid", 2, "") or ""
                ).strip(),
                "name": name,
                "loan_type": loan_type,
                "area": area,
                "principal": principal,
                "interest_amount": interest,
                "total_to_pay": total_to_pay,
                "date_released": timing.get("date_released"),
                "latest_released": timing.get("latest_released"),
                "payment_start": payment_start,
                "due_date": timing.get("due_date"),
                "paid": 0.0,
                "_x7_payments": [],
                "completion_pct": 0.0,
                "time_passed_pct": timing.get("time_passed_pct", 0.0),
                "remaining": total_to_pay,
                "days_left": timing.get("days_left"),
                "status": "In Progress",
                "priority": 80,
            }
            rows.append(record)

            if uid:
                row_by_uid[(uid, loan_type)] = record
            row_by_name[(name.upper(), loan_type)] = record
            if payment_start and (
                earliest_payment_start is None
                or payment_start < earliest_payment_start
            ):
                earliest_payment_start = payment_start
        except Exception:
            continue

    if not rows:
        return []

    if _table_exists(cursor, "transactions") and {
        "date",
        "payment",
    }.issubset(transaction_columns):
        try:
            transaction_select = [
                "client_uid"
                if "client_uid" in transaction_columns
                else "'' AS client_uid",
                "name" if "name" in transaction_columns else "'' AS name",
                "loan_type"
                if "loan_type" in transaction_columns
                else "'Regular' AS loan_type",
                "date",
                "payment",
            ]
            parameters: list[Any] = []
            where: list[str] = []
            if earliest_payment_start:
                where.append("date(date) >= date(?)")
                parameters.append(earliest_payment_start.strftime("%Y-%m-%d"))
            sql = "SELECT %s FROM transactions" % ", ".join(
                transaction_select
            )
            if where:
                sql += " WHERE " + " AND ".join(where)

            for transaction in cursor.execute(
                sql, tuple(parameters)
            ).fetchall() or []:
                try:
                    uid = str(
                        _row_value(transaction, "client_uid", 0, "") or ""
                    ).strip()
                    name = str(
                        _row_value(transaction, "name", 1, "") or ""
                    ).strip().upper()
                    loan_type = normalize_loan_type(
                        _row_value(transaction, "loan_type", 2, "Regular")
                    )
                    paid_on = _spina_dash__parse_date(
                        _row_value(transaction, "date", 3, None)
                    )
                    payment = _spina_dash__float(
                        _row_value(transaction, "payment", 4, 0)
                    )
                    if payment == 0 or not paid_on:
                        continue

                    record = row_by_uid.get((uid, loan_type)) if uid else None
                    if record is not None and paid_on < record.get(
                        "payment_start"
                    ):
                        record = None
                    if record is None and name:
                        record = row_by_name.get((name, loan_type))
                        if record is not None and paid_on < record.get(
                            "payment_start"
                        ):
                            record = None
                    if record is None:
                        continue

                    if normalize_loan_type(record.get("loan_type")) == "7x7":
                        record.setdefault("_x7_payments", []).append(
                            (paid_on, payment)
                        )
                    else:
                        record["paid"] = float(record.get("paid") or 0.0) + payment
                except Exception:
                    continue
        except Exception as exc:
            _log(log_exc, "dashboard.fetch_transactions", exc)

    finalized_rows: list[dict[str, Any]] = []
    for record in rows:
        try:
            finalized_rows.append(
                finalize_cycle_record(record, effective_today)
            )
        except Exception:
            fallback = dict(record)
            fallback.pop("_x7_payments", None)
            finalized_rows.append(fallback)

    finalized_rows.sort(key=cycle_sort_key)
    return finalized_rows


# Compatibility name used by the existing presentation bridge and older tests.
_spina_dashboard_fetch_rows = fetch_dashboard_rows
