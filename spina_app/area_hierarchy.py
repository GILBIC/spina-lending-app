"""Hierarchical Area storage with legacy flat-text compatibility.

The desktop app historically stores a client's Area as plain text in
``clients.area`` and keeps valid values in ``areas(name)``. This module adds
stable Area node IDs and unlimited parent/child nesting while continuing to
write the full display path back to those legacy fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid
from typing import Any, Iterable

AREA_PATH_SEPARATOR = " › "

# The first hierarchy setup may scan the full clients table to migrate legacy
# Area text. Keep that work once per live database connection instead of doing
# it again every time a selector or manager window refreshes.
_READY_CONNECTION_IDS: set[int] = set()
_EMPTY_STATS = {"paths_found": 0, "nodes_created": 0, "clients_linked": 0}


def _now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def normalize_area_segment(value: Any) -> str:
    """Return a trimmed single Area node name with internal spaces collapsed."""
    try:
        text = str(value or "")
    except Exception:
        text = ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_area_path(value: Any) -> str:
    """Normalize spacing without changing a legacy Area's visible wording."""
    try:
        text = str(value or "")
    except Exception:
        text = ""
    return re.sub(r"\s+", " ", text).strip()


def format_area_path(parts: Iterable[Any]) -> str:
    """Join any number of Area levels into one unambiguous display path."""
    clean = [normalize_area_segment(part) for part in parts]
    return AREA_PATH_SEPARATOR.join(part for part in clean if part)


def _path_key(value: Any) -> str:
    return normalize_area_path(value).casefold()


def _legacy_area_uid(path: str) -> str:
    """Return a stable ID so repeated migrations cannot duplicate a flat Area."""
    return uuid.uuid5(uuid.NAMESPACE_URL, "spina-area:" + _path_key(path)).hex


def _row_value(row: Any, key: str, index: int, default: Any = None) -> Any:
    if row is None:
        return default
    try:
        if hasattr(row, "keys") and key in row.keys():
            return row[key]
    except Exception:
        pass
    try:
        return row[index]
    except Exception:
        return default


def _table_columns(conn: Any, table: str) -> set[str]:
    cur = conn.cursor()
    try:
        rows = cur.execute(f"PRAGMA table_info({table})").fetchall() or []
        columns = {str(_row_value(row, "name", 1, "") or "") for row in rows}
        if columns:
            return columns
    except Exception:
        pass

    try:
        cur.execute(f"SELECT * FROM {table} WHERE 1=0")
        return {str(item[0]) for item in (cur.description or []) if item and item[0]}
    except Exception:
        return set()


def _ensure_client_area_uid(conn: Any) -> None:
    if "area_uid" in _table_columns(conn, "clients"):
        return
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE clients ADD COLUMN area_uid TEXT")
    except Exception as exc:
        message = str(exc).casefold()
        if "already exists" not in message and "duplicate column" not in message:
            raise


def _ensure_legacy_areas_table(conn: Any) -> None:
    conn.cursor().execute(
        """
        CREATE TABLE IF NOT EXISTS areas (
            name TEXT PRIMARY KEY,
            created_at TEXT
        )
        """
    )


def _ensure_area_nodes_table(conn: Any) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS area_nodes (
            area_uid TEXT PRIMARY KEY,
            parent_uid TEXT DEFAULT '',
            name TEXT NOT NULL,
            full_path TEXT NOT NULL,
            depth INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_area_nodes_full_path "
        "ON area_nodes(full_path)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_area_nodes_parent_sort "
        "ON area_nodes(parent_uid, sort_order, name)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_clients_area_uid ON clients(area_uid)"
    )


def _fetch_nodes(conn: Any, *, include_inactive: bool = True) -> list[dict[str, Any]]:
    cur = conn.cursor()
    sql = (
        "SELECT area_uid, parent_uid, name, full_path, depth, sort_order, "
        "is_active, created_at, updated_at FROM area_nodes"
    )
    if not include_inactive:
        sql += " WHERE COALESCE(is_active,1)=1"
    sql += " ORDER BY depth, parent_uid, sort_order, name"
    rows = cur.execute(sql).fetchall() or []
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "area_uid": str(_row_value(row, "area_uid", 0, "") or ""),
                "parent_uid": str(_row_value(row, "parent_uid", 1, "") or ""),
                "name": str(_row_value(row, "name", 2, "") or ""),
                "full_path": str(_row_value(row, "full_path", 3, "") or ""),
                "depth": int(_row_value(row, "depth", 4, 0) or 0),
                "sort_order": int(_row_value(row, "sort_order", 5, 0) or 0),
                "is_active": int(_row_value(row, "is_active", 6, 1) or 0),
                "created_at": _row_value(row, "created_at", 7, None),
                "updated_at": _row_value(row, "updated_at", 8, None),
            }
        )
    return result


def migrate_flat_areas(conn: Any) -> dict[str, int]:
    """Migrate existing flat Area text to root nodes without changing text.

    Existing values are deliberately kept as root nodes. Staff can later move
    them under another Area through the hierarchy manager. This avoids guessing
    whether a dash or slash in an old Area name was intended as a separator.
    """
    cur = conn.cursor()
    known_paths: dict[str, str] = {}

    try:
        rows = cur.execute("SELECT name FROM areas").fetchall() or []
    except Exception:
        rows = []
    for row in rows:
        path = normalize_area_path(_row_value(row, "name", 0, ""))
        if path:
            known_paths.setdefault(_path_key(path), path)

    try:
        rows = cur.execute(
            "SELECT DISTINCT area FROM clients WHERE area IS NOT NULL AND TRIM(area)<>''"
        ).fetchall() or []
    except Exception:
        rows = []
    for row in rows:
        path = normalize_area_path(_row_value(row, "area", 0, ""))
        if path:
            known_paths.setdefault(_path_key(path), path)

    existing = {_path_key(node["full_path"]): node for node in _fetch_nodes(conn)}
    created = 0
    timestamp = _now_text()
    for key, path in sorted(known_paths.items(), key=lambda item: item[1].casefold()):
        if key in existing:
            continue
        area_uid = _legacy_area_uid(path)
        cur.execute(
            """
            INSERT OR IGNORE INTO area_nodes(
                area_uid, parent_uid, name, full_path, depth, sort_order,
                is_active, created_at, updated_at
            ) VALUES (?, '', ?, ?, 0, 0, 1, ?, ?)
            """,
            (area_uid, path, path, timestamp, timestamp),
        )
        created += 1

    nodes = {_path_key(node["full_path"]): node for node in _fetch_nodes(conn)}
    linked = 0
    try:
        client_rows = cur.execute("SELECT id, area, area_uid FROM clients").fetchall() or []
    except Exception:
        client_rows = []
    for row in client_rows:
        client_id = _row_value(row, "id", 0, None)
        path = normalize_area_path(_row_value(row, "area", 1, ""))
        current_uid = str(_row_value(row, "area_uid", 2, "") or "").strip()
        if client_id is None or not path or current_uid:
            continue
        node = nodes.get(_path_key(path))
        if not node:
            continue
        cur.execute("UPDATE clients SET area_uid=? WHERE id=?", (node["area_uid"], client_id))
        linked += 1

    conn.commit()
    return {"paths_found": len(known_paths), "nodes_created": created, "clients_linked": linked}


def ensure_area_hierarchy_schema(conn: Any) -> dict[str, int]:
    """Create hierarchy storage and explicitly rescan legacy values."""
    _ensure_legacy_areas_table(conn)
    _ensure_client_area_uid(conn)
    _ensure_area_nodes_table(conn)
    stats = migrate_flat_areas(conn)
    conn.commit()
    _READY_CONNECTION_IDS.add(id(conn))
    return stats


def ensure_area_hierarchy_ready(conn: Any) -> dict[str, int]:
    """Ensure hierarchy storage once for this live database connection."""
    if id(conn) in _READY_CONNECTION_IDS:
        return dict(_EMPTY_STATS)
    return ensure_area_hierarchy_schema(conn)


def list_area_nodes(conn: Any, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    ensure_area_hierarchy_ready(conn)
    return _fetch_nodes(conn, include_inactive=include_inactive)


def build_area_tree(nodes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a nested tree from a flat list without imposing a depth limit."""
    copies: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for raw in nodes:
        node = dict(raw)
        node["children"] = []
        uid = str(node.get("area_uid") or "")
        if not uid:
            continue
        copies[uid] = node
        ordered.append(node)

    roots: list[dict[str, Any]] = []
    for node in ordered:
        parent_uid = str(node.get("parent_uid") or "")
        parent = copies.get(parent_uid)
        if parent is None or parent is node:
            roots.append(node)
        else:
            parent["children"].append(node)

    def sort_branch(items: list[dict[str, Any]]) -> None:
        items.sort(
            key=lambda item: (
                int(item.get("sort_order") or 0),
                str(item.get("name") or "").casefold(),
            )
        )
        for item in items:
            sort_branch(item["children"])

    sort_branch(roots)
    return roots


def _node_by_uid(conn: Any, area_uid: str) -> dict[str, Any] | None:
    uid = str(area_uid or "").strip()
    if not uid:
        return None
    for node in _fetch_nodes(conn):
        if node["area_uid"] == uid:
            return node
    return None


def add_area_node(conn: Any, name: Any, parent_uid: str = "") -> dict[str, Any]:
    """Add one Area node under any parent and return the saved node."""
    ensure_area_hierarchy_ready(conn)
    segment = normalize_area_segment(name)
    if not segment:
        raise ValueError("Area name is required.")
    if AREA_PATH_SEPARATOR.strip() in segment:
        raise ValueError("Area name cannot contain the hierarchy separator.")

    parent = _node_by_uid(conn, parent_uid) if str(parent_uid or "").strip() else None
    if parent_uid and parent is None:
        raise ValueError("Parent Area was not found.")
    if parent is not None and not int(parent.get("is_active") or 0):
        raise ValueError("Parent Area is inactive.")

    full_path = format_area_path([parent.get("full_path") if parent else "", segment])
    existing = {_path_key(node["full_path"]): node for node in _fetch_nodes(conn)}
    found = existing.get(_path_key(full_path))
    if found is not None:
        return found

    cur = conn.cursor()
    siblings = [
        node for node in existing.values()
        if str(node.get("parent_uid") or "") == str(parent_uid or "")
    ]
    next_order = max((int(node.get("sort_order") or 0) for node in siblings), default=-1) + 1
    timestamp = _now_text()
    area_uid = uuid.uuid4().hex
    depth = int(parent.get("depth") or 0) + 1 if parent else 0
    cur.execute(
        """
        INSERT INTO area_nodes(
            area_uid, parent_uid, name, full_path, depth, sort_order,
            is_active, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (area_uid, str(parent_uid or ""), segment, full_path, depth, next_order, timestamp, timestamp),
    )
    cur.execute(
        "INSERT OR IGNORE INTO areas(name, created_at) VALUES (?, ?)",
        (full_path, timestamp),
    )
    conn.commit()
    saved = _node_by_uid(conn, area_uid)
    if saved is None:
        raise RuntimeError("Area node was not saved.")
    return saved


def set_client_area_node(conn: Any, client_uid: str, area_uid: str) -> dict[str, Any]:
    """Assign a client to a node while synchronizing the legacy Area path text."""
    ensure_area_hierarchy_ready(conn)
    client_key = str(client_uid or "").strip()
    if not client_key:
        raise ValueError("Client UID is required.")
    node = _node_by_uid(conn, area_uid)
    if node is None or not int(node.get("is_active") or 0):
        raise ValueError("Selected Area is unavailable.")
    cur = conn.cursor()
    cur.execute(
        "UPDATE clients SET area_uid=?, area=? WHERE client_uid=?",
        (node["area_uid"], node["full_path"], client_key),
    )
    conn.commit()
    return node
