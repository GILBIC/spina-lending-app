"""Client Info Logs persistence access for SPINA Wave 78."""
from __future__ import annotations

from typing import Any


CLIENT_HISTORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS client_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_uid TEXT,
    name_before TEXT,
    name_after TEXT,
    loan_type_before TEXT,
    loan_type_after TEXT,
    action TEXT,
    changed_at TEXT,
    old_json TEXT,
    new_json TEXT,
    source TEXT,
    note TEXT
)
"""


def _connection_from_db(db: Any) -> Any:
    conn = getattr(db, "conn", None)
    if conn is None:
        raise RuntimeError("Client Info Logs database connection is unavailable")
    return conn


def ensure_client_history_schema(db: Any) -> bool:
    """Ensure the legacy-compatible history table exists."""
    conn = _connection_from_db(db)
    cur = conn.cursor()
    cur.execute(CLIENT_HISTORY_SCHEMA_SQL)
    conn.commit()
    return True


def fetch_client_history_records(
    db: Any,
    *,
    limit: int = 5000,
    ensure_schema: bool = True,
) -> list[dict[str, Any]]:
    """Return newest client-history records as plain dictionaries."""
    conn = _connection_from_db(db)
    if ensure_schema:
        try:
            ensure_client_history_schema(db)
        except Exception:
            # Preserve the old tolerant behavior: a schema failure should not make
            # the whole desktop app fail before the read attempt.
            pass

    try:
        row_limit = int(limit or 5000)
    except Exception:
        row_limit = 5000
    row_limit = max(1, min(100_000, row_limit))

    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM client_history "
        "ORDER BY COALESCE(changed_at,'') DESC, id DESC LIMIT ?",
        (row_limit,),
    ).fetchall() or []

    output: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            output.append(dict(row))
            continue
        try:
            output.append(dict(row))
            continue
        except Exception:
            pass
        try:
            keys = row.keys()
            output.append({key: row[key] for key in keys})
        except Exception:
            continue
    return output
