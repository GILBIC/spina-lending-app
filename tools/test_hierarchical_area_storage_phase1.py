#!/usr/bin/env python3
"""Regression tests for hierarchical Area storage Phase 1."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app.area_hierarchy import (  # noqa: E402
    AREA_PATH_SEPARATOR,
    add_area_node,
    build_area_tree,
    ensure_area_hierarchy_schema,
    list_area_nodes,
    set_client_area_node,
)


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_uid TEXT,
            name TEXT,
            area TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE areas (
            name TEXT PRIMARY KEY,
            created_at TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO clients(client_uid, name, area) VALUES (?, ?, ?)",
        [
            ("client-a", "Ana", "Cardona"),
            ("client-b", "Ben", "Taytay"),
            ("client-c", "Cara", ""),
        ],
    )
    conn.executemany(
        "INSERT INTO areas(name, created_at) VALUES (?, '2026-01-01')",
        [("Cardona",), ("Binangonan",)],
    )
    conn.commit()
    return conn


def assert_legacy_migration() -> sqlite3.Connection:
    conn = make_db()
    first = ensure_area_hierarchy_schema(conn)
    assert first == {"paths_found": 3, "nodes_created": 3, "clients_linked": 2}, first

    columns = {row[1] for row in conn.execute("PRAGMA table_info(clients)").fetchall()}
    assert "area_uid" in columns

    nodes = list_area_nodes(conn)
    paths = {node["full_path"] for node in nodes}
    assert paths == {"Binangonan", "Cardona", "Taytay"}, paths
    assert all(node["depth"] == 0 for node in nodes)
    assert all(node["parent_uid"] == "" for node in nodes)

    rows = conn.execute(
        "SELECT client_uid, area, area_uid FROM clients ORDER BY client_uid"
    ).fetchall()
    assert rows[0][1] == "Cardona" and rows[0][2]
    assert rows[1][1] == "Taytay" and rows[1][2]
    assert rows[2][1] == "" and not rows[2][2]

    second = ensure_area_hierarchy_schema(conn)
    assert second == {"paths_found": 3, "nodes_created": 0, "clients_linked": 0}, second
    assert len(list_area_nodes(conn)) == 3
    return conn


def assert_unlimited_hierarchy(conn: sqlite3.Connection) -> None:
    nodes = {node["full_path"]: node for node in list_area_nodes(conn)}
    cardona = nodes["Cardona"]
    looc = add_area_node(conn, " Looc ", cardona["area_uid"])
    zone = add_area_node(conn, "Zone 1", looc["area_uid"])
    street = add_area_node(conn, "Street A", zone["area_uid"])
    group = add_area_node(conn, "Group 1", street["area_uid"])

    assert looc["full_path"] == f"Cardona{AREA_PATH_SEPARATOR}Looc"
    assert zone["depth"] == 2
    assert street["depth"] == 3
    assert group["depth"] == 4
    assert group["full_path"] == (
        f"Cardona{AREA_PATH_SEPARATOR}Looc{AREA_PATH_SEPARATOR}Zone 1"
        f"{AREA_PATH_SEPARATOR}Street A{AREA_PATH_SEPARATOR}Group 1"
    )

    duplicate = add_area_node(conn, "Group 1", street["area_uid"])
    assert duplicate["area_uid"] == group["area_uid"]

    tree = build_area_tree(list_area_nodes(conn))
    root = next(item for item in tree if item["full_path"] == "Cardona")
    assert root["children"][0]["name"] == "Looc"
    assert root["children"][0]["children"][0]["name"] == "Zone 1"
    assert (
        root["children"][0]["children"][0]["children"][0]["children"][0]["name"]
        == "Group 1"
    )

    assigned = set_client_area_node(conn, "client-a", group["area_uid"])
    row = conn.execute(
        "SELECT area_uid, area FROM clients WHERE client_uid='client-a'"
    ).fetchone()
    assert row[0] == group["area_uid"]
    assert row[1] == group["full_path"]
    assert assigned["full_path"] == group["full_path"]


def main() -> int:
    conn = assert_legacy_migration()
    assert_unlimited_hierarchy(conn)
    conn.close()
    print("Hierarchical Area storage Phase 1 tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
