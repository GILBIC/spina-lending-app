"""Data Bank repository extracted in SPINA Wave 82."""
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
_PROTECTED = {"__name__", "__file__", "__package__", "__builtins__", "_DEPENDENCIES", "_PROTECTED", "configure_data_bank_repository_dependencies"}


def configure_data_bank_repository_dependencies(namespace: Mapping[str, Any]) -> None:
    _DEPENDENCIES.clear()
    _DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED:
            globals()[name] = value

def _log_transaction_history(self, client_uid, action, old_row=None, new_row=None, source='', note=''):
        """Append-only audit entry for Data Bank transactions."""
        uid = (client_uid or '').strip()
        # Derive UID from rows if needed
        if not uid:
            try:
                uid = ((new_row or old_row or {}).get("client_uid") or "").strip()
            except Exception:
                uid = ""
        # Derive uid by (name, loan_type) if still missing
        if not uid:
            try:
                nm = (new_row or old_row or {}).get("name")
                lt = (new_row or old_row or {}).get("loan_type")
                uid = (self.get_client_uid(nm, loan_type=lt) or "").strip()
            except Exception:
                uid = ""
        # Still allow logging even if uid is missing (best-effort)
        person_uid = ""
        try:
            if uid:
                person_uid = (self.get_person_uid_for_client_uid(uid) or "").strip()
        except Exception:
            person_uid = ""

        def _safe_json(obj):
            try:
                return json.dumps(obj, ensure_ascii=False, default=str, sort_keys=True)
            except Exception:
                try:
                    return json.dumps(str(obj), ensure_ascii=False)
                except Exception:
                    return ""

        # identity fields
        nm = ""
        lt = ""
        dt = ""
        try:
            src_row = (new_row or old_row or {}) or {}
            nm = (src_row.get("name") or "") if isinstance(src_row, dict) else ""
            lt = (src_row.get("loan_type") or "") if isinstance(src_row, dict) else ""
            dt = (src_row.get("date") or "") if isinstance(src_row, dict) else ""
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0151', 'suppressed exception excpass_0151', __spina_exc)
            pass

        cur = self.conn.cursor()
        try:
            cur.execute(
                """INSERT INTO transaction_history
                   (person_uid, client_uid, name, loan_type, date, action, changed_at, old_json, new_json, source, note)
                   VALUES (?,?,?,?,?, ?, datetime('now'), ?,?,?,?)""",
                (
                    (person_uid or ""),
                    (uid or ""),
                    (nm or ""),
                    (lt or ""),
                    (dt or ""),
                    (action or ""),
                    _safe_json(old_row),
                    _safe_json(new_row),
                    (source or ""),
                    (note or ""),
                )
            )
            self.conn.commit()
            return True
        except Exception:
            return False

def get_databank_daily_total(self, date_s, loan_type=None):
        cur = self.conn.cursor()
        raw_lt = (str(loan_type or '').strip())
        try:
            if (not raw_lt) or (raw_lt.upper() in ('ALL', 'COMBINED', '__ALL__')):
                row = cur.execute(
                    """
                    SELECT COALESCE(SUM(COALESCE(payment, 0)), 0)
                    FROM transactions
                    WHERE date(date) = date(?)
                    """,
                    (date_s,),
                ).fetchone()
            else:
                lt = self._effective_lt(raw_lt)
                row = cur.execute(
                    """
                    SELECT COALESCE(SUM(COALESCE(payment, 0)), 0)
                    FROM transactions
                    WHERE date(date) = date(?)
                      AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular')
                    """,
                    (date_s, lt),
                ).fetchone()
            if not row:
                return 0.0
            try:
                return float(row[0] or 0.0)
            except Exception:
                return 0.0
        except Exception:
            return 0.0

def get_databank_day_close(self, date_s, loan_type=None):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        try:
            row = cur.execute(
                "SELECT * FROM databank_day_close WHERE close_date=? AND loan_type=? LIMIT 1",
                (date_s, bucket),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d['expected_amount'] = round(float(d.get('expected_amount') or 0.0), 2)
            except Exception:
                d['expected_amount'] = 0.0
            try:
                d['actual_cash'] = round(float(d.get('actual_cash') or 0.0), 2)
            except Exception:
                d['actual_cash'] = 0.0
            try:
                d['variance'] = round(float(d.get('variance') or 0.0), 2)
            except Exception:
                d['variance'] = round(float(d.get('actual_cash') or 0.0) - float(d.get('expected_amount') or 0.0), 2)
            d['variance_status'] = (d.get('variance_status') or self._dayclose_variance_status(d.get('variance'))).strip() or 'Balanced'
            d['variance_workflow_status'] = self._dayclose_norm_workflow(
                d.get('variance_workflow_status'),
                variance=d.get('variance'),
                is_closed=bool(int(d.get('is_closed') or 0)),
            )
            return d
        except Exception:
            return None

def is_databank_day_closed(self, date_s, loan_type=None):
        rec = self.get_databank_day_close(date_s, loan_type=loan_type) or {}
        try:
            return bool(int(rec.get('is_closed') or 0))
        except Exception:
            return False

def _append_databank_day_close_history(self, date_s, action, rec=None, actor='', note='', loan_type=None, source='databank:history', payload=None):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        rr = dict(rec or {})
        try:
            payload_json = json.dumps(payload or {}, ensure_ascii=False, default=str, sort_keys=True)
        except Exception:
            payload_json = ''
        try:
            cur.execute(
                """
                INSERT INTO databank_day_close_history
                    (close_date, loan_type, action, variance_status, workflow_status,
                     expected_amount, actual_cash, variance, note, actor, event_at, source, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)
                """,
                (
                    date_s,
                    bucket,
                    str(action or '').strip() or 'update',
                    (rr.get('variance_status') or '').strip(),
                    self._dayclose_norm_workflow(rr.get('variance_workflow_status'), variance=rr.get('variance'), is_closed=bool(int(rr.get('is_closed') or 0)) if rr else True),
                    round(float(rr.get('expected_amount') or 0.0), 2),
                    round(float(rr.get('actual_cash') or 0.0), 2),
                    round(float(rr.get('variance') or 0.0), 2),
                    str(note if note is not None else rr.get('note') or ''),
                    str(actor or '').strip(),
                    source or 'databank:history',
                    payload_json,
                ),
            )
        except Exception as e:
            try:
                _log_exc('databank_day_close_history:insert', e)
            except Exception:
                pass

def list_databank_day_close_history(self, date_s, loan_type=None, limit=200):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        try:
            rows = cur.execute(
                """
                SELECT *
                  FROM databank_day_close_history
                 WHERE close_date=? AND loan_type=?
                 ORDER BY datetime(event_at) DESC, id DESC
                 LIMIT ?
                """,
                (date_s, bucket, int(limit or 200)),
            ).fetchall()
        except Exception:
            return []
        out = []
        for r in (rows or []):
            try:
                d = dict(r)
            except Exception:
                d = {}
            d['workflow_status'] = self._dayclose_norm_workflow(d.get('workflow_status'), variance=d.get('variance'), is_closed=True)
            out.append(d)
        return out

def list_databank_day_collectors(self, date_s, loan_type=None):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        try:
            rows = cur.execute(
                """
                SELECT *
                  FROM databank_day_collector_close
                 WHERE close_date=? AND loan_type=?
                 ORDER BY sort_order ASC, collector_name COLLATE NOCASE ASC, id ASC
                """,
                (date_s, bucket),
            ).fetchall()
        except Exception:
            return []
        out = []
        for r in (rows or []):
            try:
                d = dict(r)
            except Exception:
                d = {}
            try:
                d['expected_amount'] = round(float(d.get('expected_amount') or 0.0), 2)
            except Exception:
                d['expected_amount'] = 0.0
            try:
                d['actual_cash'] = round(float(d.get('actual_cash') or 0.0), 2)
            except Exception:
                d['actual_cash'] = 0.0
            try:
                d['variance'] = round(float(d.get('variance') or 0.0), 2)
            except Exception:
                d['variance'] = round(float(d.get('actual_cash') or 0.0) - float(d.get('expected_amount') or 0.0), 2)
            out.append(d)
        return out

def get_databank_day_collector_totals(self, date_s, loan_type=None):
        rows = self.list_databank_day_collectors(date_s, loan_type=loan_type)
        exp = 0.0
        act = 0.0
        for r in (rows or []):
            try:
                exp += float(r.get('expected_amount') or 0.0)
            except Exception:
                pass
            try:
                act += float(r.get('actual_cash') or 0.0)
            except Exception:
                pass
        exp = round(exp, 2)
        act = round(act, 2)
        var = round(act - exp, 2)
        if abs(var) < 0.005:
            var = 0.0
        return {
            'rows': rows,
            'expected_amount': exp,
            'actual_cash': act,
            'variance': var,
            'variance_status': self._dayclose_variance_status(var),
        }

def replace_databank_day_collectors(self, date_s, rows, changed_by='', loan_type=None, source='databank:collector_split'):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        cleaned = []
        seen = set()
        for idx, row in enumerate(rows or []):
            try:
                name = str((row or {}).get('collector_name') or '').strip()
            except Exception:
                name = ''
            if not name:
                continue
            key = name.lower()
            if key in seen:
                suffix = 2
                while f"{key}__{suffix}" in seen:
                    suffix += 1
                seen.add(f"{key}__{suffix}")
                name = f"{name} ({suffix})"
            else:
                seen.add(key)
            try:
                expected = round(float((row or {}).get('expected_amount') or 0.0), 2)
            except Exception:
                expected = 0.0
            try:
                actual = round(float((row or {}).get('actual_cash') or 0.0), 2)
            except Exception:
                actual = 0.0
            variance = round(actual - expected, 2)
            if abs(variance) < 0.005:
                variance = 0.0
            cleaned.append({
                'collector_name': name,
                'expected_amount': expected,
                'actual_cash': actual,
                'variance': variance,
                'note': str((row or {}).get('note') or '').strip(),
                'sort_order': idx,
            })
        try:
            cur.execute("DELETE FROM databank_day_collector_close WHERE close_date=? AND loan_type=?", (date_s, bucket))
            for row in cleaned:
                cur.execute(
                    """
                    INSERT INTO databank_day_collector_close
                        (close_date, loan_type, collector_name, expected_amount, actual_cash, variance,
                         note, sort_order, updated_by, created_at, updated_at, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?)
                    """,
                    (
                        date_s,
                        bucket,
                        row['collector_name'],
                        row['expected_amount'],
                        row['actual_cash'],
                        row['variance'],
                        row['note'],
                        int(row.get('sort_order') or 0),
                        str(changed_by or '').strip(),
                        source or 'databank:collector_split',
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        rec = self.get_databank_day_close(date_s, loan_type=loan_type) or {
            'close_date': date_s,
            'loan_type': bucket,
            'expected_amount': round(float(self.get_databank_daily_total(date_s, loan_type='__ALL__') or 0.0), 2),
            'actual_cash': 0.0,
            'variance': 0.0,
            'variance_status': 'Balanced',
            'variance_workflow_status': 'Open',
            'is_closed': 0,
            'note': '',
        }
        totals = self.get_databank_day_collector_totals(date_s, loan_type=loan_type)
        self._append_databank_day_close_history(
            date_s,
            'collector_split_saved',
            rec=rec,
            actor=changed_by,
            note=rec.get('note') or '',
            loan_type=loan_type,
            source=source,
            payload={'collector_rows': cleaned, 'collector_totals': totals},
        )
        self.conn.commit()
        return totals

def set_databank_day_close(self, date_s, actual_cash, note='', closed_by='', loan_type=None, source='databank:close', workflow_status=None, collector_rows=None):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        before = self.get_databank_day_close(date_s, loan_type=loan_type)
        expected = round(float(self.get_databank_daily_total(date_s, loan_type='__ALL__') or 0.0), 2)
        actual = round(float(actual_cash or 0.0), 2)
        variance = round(actual - expected, 2)
        if abs(variance) < 0.005:
            variance = 0.0
        variance_status = self._dayclose_variance_status(variance)
        workflow = self._dayclose_norm_workflow(workflow_status, variance=variance, is_closed=True)
        try:
            cur.execute(
                """
                INSERT INTO databank_day_close
                    (close_date, loan_type, expected_amount, actual_cash, variance, variance_status,
                     variance_workflow_status, is_closed, note, closed_by, closed_at, opened_by, opened_at, updated_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, datetime('now'), '', NULL, datetime('now'), ?)
                ON CONFLICT(close_date, loan_type) DO UPDATE SET
                    expected_amount=excluded.expected_amount,
                    actual_cash=excluded.actual_cash,
                    variance=excluded.variance,
                    variance_status=excluded.variance_status,
                    variance_workflow_status=excluded.variance_workflow_status,
                    is_closed=1,
                    note=excluded.note,
                    closed_by=excluded.closed_by,
                    closed_at=datetime('now'),
                    updated_at=datetime('now'),
                    source=excluded.source
                """,
                (
                    date_s,
                    bucket,
                    expected,
                    actual,
                    variance,
                    variance_status,
                    workflow,
                    note or '',
                    closed_by or '',
                    source or 'databank:close',
                ),
            )
            if collector_rows is not None:
                self.replace_databank_day_collectors(date_s, collector_rows, changed_by=closed_by, loan_type=loan_type, source=(source or 'databank:close') + ':collectors')
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        after = self.get_databank_day_close(date_s, loan_type=loan_type)
        self._append_databank_day_close_history(
            date_s,
            'close',
            rec=after,
            actor=closed_by,
            note=note or '',
            loan_type=loan_type,
            source=source,
            payload={
                'before': before or {},
                'after': after or {},
                'collector_totals': self.get_databank_day_collector_totals(date_s, loan_type=loan_type),
            },
        )
        self.conn.commit()
        return after

def reopen_databank_day(self, date_s, opened_by='', loan_type=None, source='databank:reopen'):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        existing = self.get_databank_day_close(date_s, loan_type=loan_type)
        if not existing:
            expected = round(float(self.get_databank_daily_total(date_s, loan_type='__ALL__') or 0.0), 2)
            cur.execute(
                """
                INSERT INTO databank_day_close
                    (close_date, loan_type, expected_amount, actual_cash, variance, variance_status,
                     variance_workflow_status, is_closed, note, closed_by, closed_at, opened_by, opened_at, updated_at, source)
                VALUES (?, ?, ?, 0, 0, 'Balanced', 'Open', 0, '', '', NULL, ?, datetime('now'), datetime('now'), ?)
                """,
                (date_s, bucket, expected, opened_by or '', source or 'databank:reopen'),
            )
        else:
            cur.execute(
                """
                UPDATE databank_day_close
                   SET is_closed=0,
                       variance_workflow_status='Open',
                       opened_by=?,
                       opened_at=datetime('now'),
                       updated_at=datetime('now'),
                       source=?
                 WHERE close_date=? AND loan_type=?
                """,
                (opened_by or '', source or 'databank:reopen', date_s, bucket),
            )
        self.conn.commit()
        after = self.get_databank_day_close(date_s, loan_type=loan_type)
        self._append_databank_day_close_history(
            date_s,
            'reopen',
            rec=after,
            actor=opened_by,
            note=(after or {}).get('note') or '',
            loan_type=loan_type,
            source=source,
            payload={'after': after or {}},
        )
        self.conn.commit()
        return after

def set_databank_day_workflow(self, date_s, workflow_status, note='', changed_by='', loan_type=None, source='databank:workflow'):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        existing = self.get_databank_day_close(date_s, loan_type=loan_type)
        if not existing:
            expected = round(float(self.get_databank_daily_total(date_s, loan_type='__ALL__') or 0.0), 2)
            actual = 0.0
            variance = round(actual - expected, 2)
            if abs(variance) < 0.005:
                variance = 0.0
            variance_status = self._dayclose_variance_status(variance)
            workflow = self._dayclose_norm_workflow(workflow_status, variance=variance, is_closed=False)
            cur.execute(
                """
                INSERT INTO databank_day_close
                    (close_date, loan_type, expected_amount, actual_cash, variance, variance_status,
                     variance_workflow_status, is_closed, note, closed_by, closed_at, opened_by, opened_at, updated_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, '', NULL, ?, datetime('now'), datetime('now'), ?)
                """,
                (date_s, bucket, expected, actual, variance, variance_status, workflow, note or '', changed_by or '', source or 'databank:workflow'),
            )
        else:
            workflow = self._dayclose_norm_workflow(workflow_status, variance=existing.get('variance'), is_closed=bool(int(existing.get('is_closed') or 0)))
            cur.execute(
                """
                UPDATE databank_day_close
                   SET variance_workflow_status=?,
                       note=?,
                       updated_at=datetime('now'),
                       source=?
                 WHERE close_date=? AND loan_type=?
                """,
                (workflow, note or '', source or 'databank:workflow', date_s, bucket),
            )
        self.conn.commit()
        after = self.get_databank_day_close(date_s, loan_type=loan_type)
        self._append_databank_day_close_history(
            date_s,
            'workflow_update',
            rec=after,
            actor=changed_by,
            note=note or '',
            loan_type=loan_type,
            source=source,
            payload={'after': after or {}},
        )
        self.conn.commit()
        return after

def list_databank_day_close_records(self, start_date=None, end_date=None, loan_type=None):
        cur = self.conn.cursor()
        bucket = self._databank_day_close_bucket(loan_type)
        start_date = (str(start_date or '').strip())
        end_date = (str(end_date or '').strip())
        params = [bucket]
        sql = [
            "SELECT * FROM databank_day_close WHERE loan_type=?"
        ]
        if start_date:
            sql.append("AND date(close_date) >= date(?)")
            params.append(start_date)
        if end_date:
            sql.append("AND date(close_date) <= date(?)")
            params.append(end_date)
        sql.append("ORDER BY date(close_date) DESC, id DESC")
        try:
            rows = cur.execute(" ".join(sql), tuple(params)).fetchall()
        except Exception:
            return []
        out = []
        for r in (rows or []):
            try:
                d = dict(r)
            except Exception:
                d = {}
            ds = (d.get('close_date') or '').strip()
            try:
                d['regular_total'] = round(float(self.get_databank_daily_total(ds, loan_type='Regular') or 0.0), 2)
            except Exception:
                d['regular_total'] = 0.0
            try:
                d['x7_total'] = round(float(self.get_databank_daily_total(ds, loan_type='7x7') or 0.0), 2)
            except Exception:
                d['x7_total'] = 0.0
            try:
                d['expected_amount'] = round(float(d.get('expected_amount') or 0.0), 2)
            except Exception:
                d['expected_amount'] = 0.0
            try:
                d['actual_cash'] = round(float(d.get('actual_cash') or 0.0), 2)
            except Exception:
                d['actual_cash'] = 0.0
            try:
                d['variance'] = round(float(d.get('variance') or 0.0), 2)
            except Exception:
                d['variance'] = round(float(d.get('actual_cash') or 0.0) - float(d.get('expected_amount') or 0.0), 2)
            d['variance_status'] = (d.get('variance_status') or self._dayclose_variance_status(d.get('variance'))).strip() or 'Balanced'
            d['variance_workflow_status'] = self._dayclose_norm_workflow(
                d.get('variance_workflow_status'),
                variance=d.get('variance'),
                is_closed=bool(int(d.get('is_closed') or 0)),
            )
            out.append(d)
        return out

def add_or_update_transaction(self, name, date_s, payment, description="", loan_type=None, source="databank"):
        """Insert or update a transaction (Data Bank) row.

        Key: prefer (client_uid, loan_type, date); fallback to legacy (name, loan_type, date)

        - Populates `client_uid` when possible so linked profiles can see the same Data Bank rows.
        - Writes an append-only audit row into `transaction_history`.
        """
        cur = self.conn.cursor()
        now = datetime.now().isoformat(sep=' ', timespec='seconds')
        lt = self._effective_lt(loan_type)
        nm = (name or "").strip()

        if self.is_databank_day_closed(date_s, loan_type=lt):
            raise ValueError(f"{date_s} is already closed for the combined Data Bank day (Regular + 7x7). Reopen it with a password before changing Data Bank entries.")

        # Resolve client_uid for this name/type (best-effort)
        client_uid = None
        try:
            client_uid = self.get_client_uid(nm, loan_type=lt)
        except Exception:
            client_uid = None

        # Stable-id path: prevents rename drift and duplicate same-day rows after a rename.
        if client_uid:
            return self.add_or_update_transaction_by_uid(
                client_uid,
                date_s,
                payment,
                description=description,
                loan_type=lt,
                source=source,
            )

        # Fetch old row for audit
        old_row = None
        try:
            r0 = cur.execute(
                "SELECT * FROM transactions WHERE name=? AND loan_type=? AND date=?",
                (nm, lt, date_s)
            ).fetchone()
            if r0:
                old_row = dict(r0)
        except Exception:
            old_row = None

        # Upsert
        cur.execute("SELECT id FROM transactions WHERE name = ? AND loan_type = ? AND date = ?", (nm, lt, date_s))
        r = cur.fetchone()
        if r:
            try:
                rid = r["id"] if isinstance(r, sqlite3.Row) else r[0]
            except Exception:
                rid = r[0]
            # Prefer updating client_uid too (if column exists)
            try:
                cur.execute(
                    "UPDATE transactions SET client_uid=?, payment=?, description=?, created_at=? WHERE id=?",
                    (client_uid, float(payment or 0), description, now, rid)
                )
            except Exception:
                cur.execute(
                    "UPDATE transactions SET payment=?, description=?, created_at=? WHERE id=?",
                    (float(payment or 0), description, now, rid)
                )
        else:
            try:
                cur.execute(
                    "INSERT INTO transactions (client_uid, name, loan_type, date, payment, description, created_at) VALUES (?,?,?,?,?,?,?)",
                    (client_uid, nm, lt, date_s, float(payment or 0), description, now)
                )
            except Exception:
                cur.execute(
                    "INSERT INTO transactions (name, loan_type, date, payment, description, created_at) VALUES (?,?,?,?,?,?)",
                    (nm, lt, date_s, float(payment or 0), description, now)
                )

        self.conn.commit()

        # Fetch new row and audit
        new_row = None
        try:
            r1 = cur.execute(
                "SELECT * FROM transactions WHERE name=? AND loan_type=? AND date=? ORDER BY id DESC LIMIT 1",
                (nm, lt, date_s)
            ).fetchone()
            if r1:
                new_row = dict(r1)
        except Exception:
            new_row = None

        try:
            self._log_transaction_history(
                (client_uid or (new_row or {}).get("client_uid")),
                "TX_UPDATE" if old_row else "TX_ADD",
                old_row=old_row,
                new_row=new_row,
                source=(source or "databank"),
            )
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0158', 'suppressed exception excpass_0158', __spina_exc)
            pass

def delete_transaction(self, name, date_s, loan_type=None, source="databank"):
        cur = self.conn.cursor()
        lt = self._effective_lt(loan_type)
        nm = (name or "").strip()

        if self.is_databank_day_closed(date_s, loan_type=lt):
            raise ValueError(f"{date_s} is already closed for the combined Data Bank day (Regular + 7x7). Reopen it with a password before deleting Data Bank entries.")

        cuid = None
        try:
            cuid = self.get_client_uid(nm, loan_type=lt)
        except Exception:
            cuid = None

        old_row = None
        try:
            if cuid:
                r0 = cur.execute(
                    "SELECT * FROM transactions WHERE client_uid=? AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular') AND date=? ORDER BY id DESC LIMIT 1",
                    (cuid, lt, date_s)
                ).fetchone()
            else:
                r0 = cur.execute(
                    "SELECT * FROM transactions WHERE name=? AND loan_type=? AND date=?",
                    (nm, lt, date_s)
                ).fetchone()
            if r0:
                old_row = dict(r0)
        except Exception:
            old_row = None

        if cuid:
            cur.execute(
                "DELETE FROM transactions WHERE client_uid=? AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular') AND date=?",
                (cuid, lt, date_s)
            )
        else:
            cur.execute("DELETE FROM transactions WHERE name = ? AND loan_type = ? AND date = ?", (nm, lt, date_s))
        self.conn.commit()

        try:
            if old_row and not cuid:
                cuid = (old_row.get("client_uid") or "").strip() or None
            if not cuid:
                cuid = self.get_client_uid(nm, loan_type=lt)
            self._log_transaction_history(
                cuid,
                "TX_DELETE",
                old_row=old_row,
                new_row=None,
                source=(source or "databank"),
            )
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0159', 'suppressed exception excpass_0159', __spina_exc)
            pass

def delete_transactions_for_day(self, date_s, changed_by='', source="databank:delete_day", reset_close=True):
        """Delete ALL Data Bank transaction rows for one calendar date.

        Safety behavior:
          - Validates YYYY-MM-DD.
          - Creates a JSON backup in data/day_delete_backups BEFORE deleting.
          - Deletes both Regular and 7x7 transactions for that date.
          - Clears the Data Bank close/collector-close lock rows for that date so the day can be re-imported.
          - Writes append-only audit rows into transaction_history and databank_day_close_history.
        """
        from datetime import datetime as _dt
        import os as _os
        import json as _json

        ds = str(date_s or "").strip()[:10]
        try:
            ds = _dt.strptime(ds, "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            raise ValueError("Invalid date. Use YYYY-MM-DD.")

        cur = self.conn.cursor()

        # Load rows that will be deleted.
        rows = cur.execute(
            """
            SELECT *
              FROM transactions
             WHERE date(date) = date(?)
             ORDER BY IFNULL(NULLIF(TRIM(loan_type),''),'Regular') COLLATE NOCASE,
                      name COLLATE NOCASE,
                      id
            """,
            (ds,),
        ).fetchall() or []

        old_rows = []
        for r in rows:
            try:
                old_rows.append(dict(r))
            except Exception:
                try:
                    old_rows.append({k: r[k] for k in r.keys()})
                except Exception:
                    old_rows.append({})

        # Also back up close records because they are reset for this day.
        close_rows = []
        collector_rows = []
        try:
            close_rows = [dict(r) for r in (cur.execute(
                "SELECT * FROM databank_day_close WHERE close_date=? ORDER BY id",
                (ds,),
            ).fetchall() or [])]
        except Exception:
            close_rows = []
        try:
            collector_rows = [dict(r) for r in (cur.execute(
                "SELECT * FROM databank_day_collector_close WHERE close_date=? ORDER BY sort_order, id",
                (ds,),
            ).fetchall() or [])]
        except Exception:
            collector_rows = []

        # Import re-run safeguard:
        # The encoder importer keeps a JSON dedupe log. Even though the importer is designed
        # to re-import if the DB row was deleted, clearing entries for this exact date makes
        # Delete Day deterministic: delete 2026-03-18 -> import 2026-03-18 again without
        # stale "already imported" state.
        import_log_path = ""
        import_log_obj = {}
        import_log_removed = {}
        try:
            import_log_path = data_path("encoder_import_log.json")
            if import_log_path and _os.path.exists(import_log_path):
                with open(import_log_path, "r", encoding="utf-8") as f:
                    import_log_obj = _json.load(f) or {}
                if not isinstance(import_log_obj, dict):
                    import_log_obj = {}
        except Exception:
            import_log_obj = {}

        try:
            if isinstance(import_log_obj, dict):
                for _k, _v in list(import_log_obj.items()):
                    _hit = False
                    try:
                        # Current log format stores {"date": "YYYY-MM-DD", ...}
                        if isinstance(_v, dict) and str(_v.get("date") or "").strip()[:10] == ds:
                            _hit = True
                    except Exception:
                        _hit = False
                    try:
                        # Fallback for stable key format: YYYY-MM-DD|loan_type|client_uid
                        if not _hit and str(_k or "").split("|", 1)[0] == ds:
                            _hit = True
                    except Exception:
                        pass
                    if _hit:
                        import_log_removed[str(_k)] = _v
        except Exception:
            import_log_removed = {}

        if not old_rows and not close_rows and not collector_rows and not import_log_removed:
            return {
                "date": ds,
                "deleted": 0,
                "backup_path": "",
                "close_reset": False,
                "import_log_cleared": 0,
                "message": "No transactions, close records, or import-log entries found for that date.",
            }

        # Backup FIRST. If backup fails, abort deletion.
        backup_dir = _os.path.join(DATA_DIR, "day_delete_backups")
        try:
            _os.makedirs(backup_dir, exist_ok=True)
        except Exception:
            pass
        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        backup_path = _os.path.join(backup_dir, f"delete_day_{ds}_{ts}.json")
        payload = {
            "action": "DELETE_DAY_BACKUP",
            "date": ds,
            "created_at": _dt.now().isoformat(sep=" ", timespec="seconds"),
            "changed_by": str(changed_by or "").strip(),
            "source": str(source or "databank:delete_day"),
            "transactions_count": len(old_rows),
            "transactions_total_payment": round(sum(float((r or {}).get("payment") or 0.0) for r in old_rows), 2),
            "transactions": old_rows,
            "databank_day_close": close_rows,
            "databank_day_collector_close": collector_rows,
            "encoder_import_log_path": import_log_path,
            "encoder_import_log_removed_count": len(import_log_removed),
            "encoder_import_log_removed": import_log_removed,
        }
        try:
            tmp = backup_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                _json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            _os.replace(tmp, backup_path)
        except Exception as e:
            raise IOError(f"Backup failed, so nothing was deleted. Error: {e}")

        # Delete in one transaction.
        try:
            cur.execute("DELETE FROM transactions WHERE date(date)=date(?)", (ds,))

            close_reset = False
            if reset_close:
                try:
                    cur.execute("DELETE FROM databank_day_collector_close WHERE close_date=?", (ds,))
                    cur.execute("DELETE FROM databank_day_close WHERE close_date=?", (ds,))
                    close_reset = bool(close_rows or collector_rows)
                except Exception:
                    close_reset = False

            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise

        # Clear stale encoder import-log entries for this date after the DB delete succeeds.
        import_log_cleared = 0
        try:
            if import_log_removed and isinstance(import_log_obj, dict):
                for _k in list(import_log_removed.keys()):
                    import_log_obj.pop(_k, None)
                if import_log_path:
                    if _write_json_atomic(import_log_path, import_log_obj):
                        import_log_cleared = len(import_log_removed)
                    else:
                        try:
                            _log_exc("delete_day.clear_encoder_import_log", Exception("atomic write failed"))
                        except Exception:
                            pass
        except Exception as e:
            try:
                _log_exc("delete_day.clear_encoder_import_log", e)
            except Exception:
                pass

        # Append audit rows after successful deletion.
        note = f"Delete Day {ds}. Backup: {backup_path}"
        if import_log_cleared:
            note += f" Import-log cleared: {import_log_cleared} entr(y/ies)."
        for old in old_rows:
            try:
                self._log_transaction_history(
                    (old.get("client_uid") or ""),
                    "TX_DELETE_DAY",
                    old_row=old,
                    new_row=None,
                    source=(source or "databank:delete_day"),
                    note=note,
                )
            except Exception:
                pass

        try:
            # Log the reset/clear of day close state in history.
            rec = close_rows[0] if close_rows else {
                "close_date": ds,
                "loan_type": self._databank_day_close_bucket(None),
                "expected_amount": 0.0,
                "actual_cash": 0.0,
                "variance": 0.0,
                "variance_status": "Balanced",
                "variance_workflow_status": "Open",
                "is_closed": 0,
                "note": "",
            }
            self._append_databank_day_close_history(
                ds,
                "delete_day_transactions",
                rec=rec,
                actor=str(changed_by or "").strip(),
                note=note,
                loan_type=None,
                source=(source or "databank:delete_day"),
                payload={
                    "backup_path": backup_path,
                    "deleted_transactions": len(old_rows),
                    "deleted_close_records": len(close_rows),
                    "deleted_collector_close_records": len(collector_rows),
                    "encoder_import_log_removed": len(import_log_removed),
                    "encoder_import_log_cleared": import_log_cleared,
                },
            )
            self.conn.commit()
        except Exception:
            pass

        return {
            "date": ds,
            "deleted": len(old_rows),
            "backup_path": backup_path,
            "close_reset": bool(close_rows or collector_rows),
            "import_log_cleared": import_log_cleared,
            "message": f"Deleted {len(old_rows)} transaction row(s) for {ds}.",
        }

def get_transaction(self, name, date_s, loan_type=None):
        cur = self.conn.cursor()
        lt = self._effective_lt(loan_type)
        nm = (name or '').strip()
        try:
            uid = self.get_client_uid(nm, loan_type=lt)
        except Exception:
            uid = None
        if uid:
            cur.execute(
                "SELECT * FROM transactions WHERE client_uid=? AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular') AND date = ? ORDER BY id DESC LIMIT 1",
                (uid, lt, date_s)
            )
        else:
            cur.execute("SELECT * FROM transactions WHERE name = ? AND loan_type = ? AND date = ?", (nm, lt, date_s))
        return cur.fetchone()

def get_transaction_by_uid(self, client_uid, date_s, loan_type=None):
        """Fetch a transaction by (client_uid, loan_type, date)."""
        uid = (client_uid or "").strip()
        if not uid:
            return None
        cur = self.conn.cursor()
        lt = self._effective_lt(loan_type)
        try:
            cur.execute(
                "SELECT * FROM transactions WHERE client_uid=? AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular') AND date=?",
                (uid, lt, date_s),
            )
            return cur.fetchone()
        except Exception:
            # Fallback: some old DBs may not have client_uid populated
            return None

def add_or_update_transaction_by_uid(self, client_uid, date_s, payment, description="", loan_type=None, source="databank"):
        """Insert or update a transaction using client_uid as the stable key.

        Key: (client_uid, loan_type, date)

        - Automatically pulls the current client name from clients table.
        - Updates the stored `name` in transactions if the client was renamed.
        - Writes append-only audit rows into transaction_history.
        """
        uid = (client_uid or "").strip()
        if not uid:
            # fallback to name-based if caller passes no uid
            return self.add_or_update_transaction("", date_s, payment, description=description, loan_type=loan_type, source=source)

        cur = self.conn.cursor()
        now = datetime.now().isoformat(sep=' ', timespec='seconds')

        # Resolve current client row/name
        row = None
        try:
            row = self.get_client_by_uid(uid) or None
        except Exception:
            row = None

        nm = ""
        lt_row = None
        try:
            if isinstance(row, dict):
                nm = (row.get("name") or "").strip()
                lt_row = (row.get("loan_type") or "").strip()
        except Exception:
            nm = ""
            lt_row = None

        # Determine effective loan_type
        lt = self._effective_lt(loan_type or lt_row or "Regular")

        if self.is_databank_day_closed(date_s, loan_type=lt):
            raise ValueError(f"{date_s} is already closed for the combined Data Bank day (Regular + 7x7). Reopen it with a password before changing Data Bank entries.")

        # Fetch old row for audit
        old_row = None
        try:
            r0 = cur.execute(
                "SELECT * FROM transactions WHERE client_uid=? AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular') AND date=?",
                (uid, lt, date_s),
            ).fetchone()
            if r0:
                old_row = dict(r0)
        except Exception:
            old_row = None

        # Upsert by client_uid
        try:
            rid_row = cur.execute(
                "SELECT id FROM transactions WHERE client_uid=? AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular') AND date=?",
                (uid, lt, date_s),
            ).fetchone()
        except Exception:
            rid_row = None

        if rid_row:
            try:
                rid = rid_row["id"] if isinstance(rid_row, sqlite3.Row) else rid_row[0]
            except Exception:
                rid = rid_row[0]
            # Update payment/desc and keep name in sync
            try:
                cur.execute(
                    "UPDATE transactions SET name=?, loan_type=?, payment=?, description=?, created_at=? WHERE id=?",
                    (nm, lt, float(payment or 0), description, now, rid),
                )
            except Exception:
                # minimal fallback
                cur.execute(
                    "UPDATE transactions SET payment=?, description=?, created_at=? WHERE id=?",
                    (float(payment or 0), description, now, rid),
                )
        else:
            try:
                cur.execute(
                    "INSERT INTO transactions (client_uid, name, loan_type, date, payment, description, created_at) VALUES (?,?,?,?,?,?,?)",
                    (uid, nm, lt, date_s, float(payment or 0), description, now),
                )
            except Exception:
                # fallback to legacy insert
                cur.execute(
                    "INSERT INTO transactions (name, loan_type, date, payment, description, created_at) VALUES (?,?,?,?,?,?)",
                    (nm, lt, date_s, float(payment or 0), description, now),
                )

        self.conn.commit()

        # Fetch new row and audit
        new_row = None
        try:
            r1 = cur.execute(
                "SELECT * FROM transactions WHERE client_uid=? AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular') AND date=? ORDER BY id DESC LIMIT 1",
                (uid, lt, date_s),
            ).fetchone()
            if r1:
                new_row = dict(r1)
        except Exception:
            new_row = None

        try:
            self._log_transaction_history(
                uid,
                "TX_UPDATE" if old_row else "TX_ADD",
                old_row=old_row,
                new_row=new_row,
                source=(source or "databank"),
            )
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_tx_uid_audit', 'suppressed exception excpass_tx_uid_audit', __spina_exc)
            pass

def import_missing_clients_from_transactions(self):
        """Ensure every (name, loan_type) in transactions has a matching row in clients.

        Older versions only tracked names (no loan_type). This version is multi-loan-type safe.
        For 7x7 loans, we default interest_rate to 0.0.
        """
        cur = self.conn.cursor()

        # Collect distinct (name, loan_type) from transactions
        tx = set()
        try:
            cur.execute("SELECT DISTINCT name, loan_type FROM transactions")
            for r in (cur.fetchall() or []):
                try:
                    nm = (r[0] or "").strip()
                    lt = self._norm_lt(r[1] if len(r) > 1 else None)
                    if nm:
                        tx.add((nm, lt))
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0160', 'suppressed exception excpass_0160', __spina_exc)
                    pass
        except Exception:
            # Legacy fallback (no loan_type column)
            try:
                cur.execute("SELECT DISTINCT name FROM transactions")
                for (nm,) in (cur.fetchall() or []):
                    nm = (nm or "").strip()
                    if nm:
                        tx.add((nm, self._effective_lt(None)))
            except Exception:
                return 0

        # Collect existing (name, loan_type) from clients
        cl = set()
        try:
            cur.execute("SELECT name, loan_type FROM clients")
            for r in (cur.fetchall() or []):
                try:
                    nm = (r[0] or "").strip()
                    lt = self._norm_lt(r[1] if len(r) > 1 else None)
                    if nm:
                        cl.add((nm, lt))
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0161', 'suppressed exception excpass_0161', __spina_exc)
                    pass
        except Exception:
            try:
                cur.execute("SELECT name FROM clients")
                for (nm,) in (cur.fetchall() or []):
                    nm = (nm or "").strip()
                    if nm:
                        cl.add((nm, self._effective_lt(None)))
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0162', 'suppressed exception excpass_0162', __spina_exc)
                pass

        miss = tx - cl
        if not miss:
            return 0

        today_s = date.today().isoformat()
        inserted = 0

        for nm, lt in miss:
            try:
                lt_norm = self._norm_lt(lt)
                is_7x7 = (lt_norm.lower().replace(" ", "") == "7x7")
                ir = 0.0 if is_7x7 else 0.20
                cur.execute(
                    "INSERT INTO clients (name, created_at, loan_type, interest_rate) VALUES (?,?,?,?)",
                    (nm, today_s, lt_norm, ir),
                )
                inserted += 1
            except Exception:
                # Try a minimal insert if schema differs
                try:
                    cur.execute(
                        "INSERT INTO clients (name, created_at, loan_type) VALUES (?,?,?)",
                        (nm, today_s, self._norm_lt(lt)),
                    )
                    inserted += 1
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0163', 'suppressed exception excpass_0163', __spina_exc)
                    pass

        self.conn.commit()
        return inserted

def _spina_perf_month_transactions(db, client_rows, start_date, end_date, loan_type):
    """Return {(row_key, yyyy-mm-dd): payment} for visible clients in the month using one range query."""
    _spina_perf_ensure_indexes(db)
    cur = db.conn.cursor()
    lt = _spina_perf_norm_lt(loan_type)

    uids = []
    names = []
    for r in client_rows or []:
        try:
            row_lt = _spina_perf_norm_lt(r.get("_spina_row_lt") or r.get("loan_type") or lt)
            if row_lt != lt:
                # Data Bank is current loan type only; skip 7x7 extras if ever present
                continue
            uid = str(r.get("client_uid") or "").strip()
            nm = str(r.get("name") or "").strip()
            if uid:
                uids.append(uid)
            elif nm:
                names.append(nm)
        except Exception:
            pass

    pay = {}
    def _chunks(seq, n=850):
        for i in range(0, len(seq), n):
            yield seq[i:i+n]

    # Prefer client_uid when available. Keep latest id for duplicate same-day records.
    for chunk in _chunks(uids):
        ph = ",".join(["?"] * len(chunk))
        sql = f"""
            SELECT client_uid, name, date, payment, id
            FROM transactions
            WHERE client_uid IN ({ph})
              AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular')=?
              AND date >= ? AND date <= ?
            ORDER BY id ASC
        """
        for tr in cur.execute(sql, list(chunk) + [lt, start_date, end_date]).fetchall():
            try:
                uid = tr["client_uid"] if hasattr(tr, "keys") else tr[0]
                ds = tr["date"] if hasattr(tr, "keys") else tr[2]
                val = tr["payment"] if hasattr(tr, "keys") else tr[3]
                pay[(str(uid), str(ds)[:10])] = val
            except Exception:
                pass

    # Fallback for legacy rows without uid
    for chunk in _chunks(names):
        ph = ",".join(["?"] * len(chunk))
        sql = f"""
            SELECT name, date, payment, id
            FROM transactions
            WHERE name IN ({ph})
              AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular')=?
              AND date >= ? AND date <= ?
            ORDER BY id ASC
        """
        for tr in cur.execute(sql, list(chunk) + [lt, start_date, end_date]).fetchall():
            try:
                nm = tr["name"] if hasattr(tr, "keys") else tr[0]
                ds = tr["date"] if hasattr(tr, "keys") else tr[1]
                val = tr["payment"] if hasattr(tr, "keys") else tr[2]
                pay[(str(nm).strip().lower(), str(ds)[:10])] = val
            except Exception:
                pass
    return pay
