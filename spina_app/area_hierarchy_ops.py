"""Advanced operations for the SPINA hierarchical Area tree.

These functions keep ``area_nodes`` authoritative while synchronizing the
legacy ``areas.name`` and ``clients.area`` fields used by existing reports,
Collector Route, and Data Bank code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from spina_app.area_hierarchy import (
    add_area_node,
    ensure_area_hierarchy_schema,
    format_area_path,
    list_area_nodes,
    normalize_area_path,
    normalize_area_segment,
)


def _now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _key(value: Any) -> str:
    return normalize_area_path(value).casefold()


def _node_map(conn: Any) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("area_uid") or ""): dict(node)
        for node in list_area_nodes(conn, include_inactive=True)
        if str(node.get("area_uid") or "")
    }


def find_area_node_by_path(
    conn: Any,
    path: Any,
    *,
    include_inactive: bool = True,
) -> dict[str, Any] | None:
    """Return the node whose full path matches ``path`` case-insensitively."""
    wanted = _key(path)
    if not wanted:
        return None
    for node in list_area_nodes(conn, include_inactive=include_inactive):
        if _key(node.get("full_path")) == wanted:
            return dict(node)
    return None


def sync_client_area_uid_from_path(conn: Any, client_uid: Any) -> dict[str, Any] | None:
    """Link one legacy client Area path to its stable Area node ID."""
    ensure_area_hierarchy_schema(conn)
    key = str(client_uid or "").strip()
    if not key:
        raise ValueError("Client UID is required.")
    cur = conn.cursor()
    row = cur.execute(
        "SELECT area FROM clients WHERE client_uid=?",
        (key,),
    ).fetchone()
    if row is None:
        raise ValueError("Client was not found.")
    try:
        path = row["area"]
    except Exception:
        path = row[0]
    path_text = normalize_area_path(path)
    if not path_text:
        cur.execute("UPDATE clients SET area_uid='' WHERE client_uid=?", (key,))
        conn.commit()
        return None
    node = find_area_node_by_path(conn, path_text, include_inactive=True)
    if node is None:
        return None
    cur.execute(
        "UPDATE clients SET area_uid=?, area=? WHERE client_uid=?",
        (node["area_uid"], node["full_path"], key),
    )
    conn.commit()
    return node


def _subtree_uids(nodes: dict[str, dict[str, Any]], root_uid: str) -> list[str]:
    children: dict[str, list[str]] = {}
    for uid, node in nodes.items():
        children.setdefault(str(node.get("parent_uid") or ""), []).append(uid)
    result: list[str] = []
    queue = [root_uid]
    seen: set[str] = set()
    while queue:
        uid = queue.pop(0)
        if uid in seen:
            continue
        seen.add(uid)
        if uid in nodes:
            result.append(uid)
            queue.extend(children.get(uid, []))
    return result


def _direct_client_count(conn: Any, node: dict[str, Any]) -> int:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT COUNT(*) FROM clients "
        "WHERE area_uid=? OR (IFNULL(TRIM(area_uid),'')='' AND TRIM(IFNULL(area,''))=?)",
        (node["area_uid"], node["full_path"]),
    ).fetchone()
    try:
        return int(row[0] or 0)
    except Exception:
        try:
            return int(row["COUNT(*)"] or 0)
        except Exception:
            return 0


def count_clients_for_area_node(
    conn: Any,
    area_uid: Any,
    *,
    include_descendants: bool = False,
) -> int:
    """Count clients assigned directly to a node or its whole subtree."""
    ensure_area_hierarchy_schema(conn)
    uid = str(area_uid or "").strip()
    nodes = _node_map(conn)
    if uid not in nodes:
        return 0
    targets = _subtree_uids(nodes, uid) if include_descendants else [uid]
    return sum(_direct_client_count(conn, nodes[target]) for target in targets)


def _planned_subtree(
    nodes: dict[str, dict[str, Any]],
    root_uid: str,
    *,
    new_parent_uid: str | None = None,
    new_name: Any | None = None,
) -> dict[str, dict[str, Any]]:
    if root_uid not in nodes:
        raise ValueError("Selected Area was not found.")
    subtree = _subtree_uids(nodes, root_uid)
    subtree_set = set(subtree)

    root = nodes[root_uid]
    parent_uid = (
        str(root.get("parent_uid") or "")
        if new_parent_uid is None
        else str(new_parent_uid or "").strip()
    )
    if parent_uid in subtree_set:
        raise ValueError("An Area cannot be moved under itself or one of its children.")
    parent = nodes.get(parent_uid) if parent_uid else None
    if parent_uid and parent is None:
        raise ValueError("The new parent Area was not found.")
    if parent is not None and not int(parent.get("is_active") or 0):
        raise ValueError("The new parent Area is inactive.")

    root_name = normalize_area_segment(root.get("name") if new_name is None else new_name)
    if not root_name:
        raise ValueError("Area name is required.")
    if "›" in root_name:
        raise ValueError("Area name cannot contain the hierarchy separator.")

    children: dict[str, list[str]] = {}
    for uid, node in nodes.items():
        children.setdefault(str(node.get("parent_uid") or ""), []).append(uid)
    for values in children.values():
        values.sort(
            key=lambda uid: (
                int(nodes[uid].get("sort_order") or 0),
                str(nodes[uid].get("name") or "").casefold(),
            )
        )

    parent_path = str(parent.get("full_path") or "") if parent else ""
    parent_depth = int(parent.get("depth") or 0) if parent else -1
    planned: dict[str, dict[str, Any]] = {}

    def walk(uid: str, path_before: str, depth_before: int) -> None:
        original = nodes[uid]
        name = root_name if uid == root_uid else normalize_area_segment(original.get("name"))
        full_path = format_area_path([path_before, name])
        planned[uid] = {
            **original,
            "parent_uid": parent_uid if uid == root_uid else str(original.get("parent_uid") or ""),
            "name": name,
            "full_path": full_path,
            "depth": depth_before + 1,
        }
        for child_uid in children.get(uid, []):
            walk(child_uid, full_path, depth_before + 1)

    walk(root_uid, parent_path, parent_depth)

    outside_paths = {
        _key(node.get("full_path"))
        for uid, node in nodes.items()
        if uid not in subtree_set
    }
    planned_paths: set[str] = set()
    for item in planned.values():
        path_key = _key(item.get("full_path"))
        if not path_key or path_key in outside_paths or path_key in planned_paths:
            raise ValueError(f"Area path already exists: {item.get('full_path')}")
        planned_paths.add(path_key)
    return planned


def _apply_planned_subtree(
    conn: Any,
    nodes: dict[str, dict[str, Any]],
    planned: dict[str, dict[str, Any]],
) -> dict[str, str]:
    cur = conn.cursor()
    timestamp = _now_text()
    mapping: dict[str, str] = {}

    ordered = sorted(planned, key=lambda uid: int(planned[uid].get("depth") or 0))
    for uid in ordered:
        old = nodes[uid]
        new = planned[uid]
        mapping[str(old.get("full_path") or "")] = str(new.get("full_path") or "")
        cur.execute(
            "UPDATE area_nodes SET parent_uid=?, name=?, full_path=?, depth=?, updated_at=? "
            "WHERE area_uid=?",
            (
                str(new.get("parent_uid") or ""),
                str(new.get("name") or ""),
                str(new.get("full_path") or ""),
                int(new.get("depth") or 0),
                timestamp,
                uid,
            ),
        )

    for old_path in mapping:
        cur.execute("DELETE FROM areas WHERE name=?", (old_path,))
    for uid in ordered:
        old = nodes[uid]
        new = planned[uid]
        new_path = str(new.get("full_path") or "")
        old_path = str(old.get("full_path") or "")
        cur.execute(
            "INSERT OR IGNORE INTO areas(name, created_at) VALUES (?, ?)",
            (new_path, timestamp),
        )
        cur.execute(
            "UPDATE clients SET area_uid=?, area=? "
            "WHERE area_uid=? OR TRIM(IFNULL(area,''))=?",
            (uid, new_path, uid, old_path),
        )
    conn.commit()
    return mapping


def rename_area_node(conn: Any, area_uid: Any, new_name: Any) -> dict[str, str]:
    """Rename one node and cascade full paths through all descendants and clients."""
    ensure_area_hierarchy_schema(conn)
    uid = str(area_uid or "").strip()
    nodes = _node_map(conn)
    planned = _planned_subtree(nodes, uid, new_name=new_name)
    return _apply_planned_subtree(conn, nodes, planned)


def move_area_node(conn: Any, area_uid: Any, new_parent_uid: Any = "") -> dict[str, str]:
    """Move a node to another parent or to the root, preserving its subtree."""
    ensure_area_hierarchy_schema(conn)
    uid = str(area_uid or "").strip()
    parent_uid = str(new_parent_uid or "").strip()
    nodes = _node_map(conn)
    planned = _planned_subtree(nodes, uid, new_parent_uid=parent_uid)
    return _apply_planned_subtree(conn, nodes, planned)


def move_area_node_order(conn: Any, area_uid: Any, direction: int) -> bool:
    """Move one Area up or down among siblings."""
    ensure_area_hierarchy_schema(conn)
    uid = str(area_uid or "").strip()
    nodes = _node_map(conn)
    node = nodes.get(uid)
    if node is None:
        return False
    siblings = [
        item for item in nodes.values()
        if str(item.get("parent_uid") or "") == str(node.get("parent_uid") or "")
    ]
    siblings.sort(
        key=lambda item: (
            int(item.get("sort_order") or 0),
            str(item.get("name") or "").casefold(),
        )
    )
    index = next((i for i, item in enumerate(siblings) if item["area_uid"] == uid), -1)
    target = index + (-1 if int(direction) < 0 else 1)
    if index < 0 or target < 0 or target >= len(siblings):
        return False
    siblings[index], siblings[target] = siblings[target], siblings[index]
    cur = conn.cursor()
    timestamp = _now_text()
    for order, item in enumerate(siblings):
        cur.execute(
            "UPDATE area_nodes SET sort_order=?, updated_at=? WHERE area_uid=?",
            (order, timestamp, item["area_uid"]),
        )
    conn.commit()
    return True


def set_area_node_active(conn: Any, area_uid: Any, active: bool) -> list[str]:
    """Activate or deactivate a whole subtree.

    Deactivation is blocked while any client is assigned to the subtree.
    """
    ensure_area_hierarchy_schema(conn)
    uid = str(area_uid or "").strip()
    nodes = _node_map(conn)
    if uid not in nodes:
        raise ValueError("Selected Area was not found.")
    subtree = _subtree_uids(nodes, uid)
    if not active:
        used = sum(_direct_client_count(conn, nodes[item_uid]) for item_uid in subtree)
        if used:
            raise ValueError(
                f"This Area subtree is assigned to {used} client(s). Reassign them before deactivating it."
            )

    cur = conn.cursor()
    timestamp = _now_text()
    for item_uid in subtree:
        node = nodes[item_uid]
        cur.execute(
            "UPDATE area_nodes SET is_active=?, updated_at=? WHERE area_uid=?",
            (1 if active else 0, timestamp, item_uid),
        )
        if active:
            cur.execute(
                "INSERT OR IGNORE INTO areas(name, created_at) VALUES (?, ?)",
                (node["full_path"], timestamp),
            )
        else:
            cur.execute("DELETE FROM areas WHERE name=?", (node["full_path"],))
    conn.commit()
    return subtree


def add_child_area_node(conn: Any, parent_uid: Any, name: Any) -> dict[str, Any]:
    """Named wrapper used by the Area Manager for unlimited child levels."""
    return add_area_node(conn, name, str(parent_uid or "").strip())


def active_area_paths(conn: Any) -> list[str]:
    """Return active hierarchy paths in tree order for legacy dropdowns."""
    nodes = list_area_nodes(conn, include_inactive=False)
    return [str(node.get("full_path") or "") for node in nodes if str(node.get("full_path") or "")]
