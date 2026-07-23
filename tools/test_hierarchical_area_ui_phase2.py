from __future__ import annotations

import sqlite3

from spina_app.area_hierarchy import add_area_node, ensure_area_hierarchy_schema, list_area_nodes
from spina_app.area_hierarchy_ops import (
    count_clients_for_area_node,
    find_area_node_by_path,
    move_area_node,
    move_area_node_order,
    rename_area_node,
    set_area_node_active,
    sync_client_area_uid_from_path,
)


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_uid TEXT,
            name TEXT,
            area TEXT DEFAULT '',
            area_uid TEXT DEFAULT '',
            is_archived INTEGER DEFAULT 0
        );
        CREATE TABLE areas (
            name TEXT PRIMARY KEY,
            created_at TEXT
        );
        INSERT INTO areas(name, created_at) VALUES ('Legacy Root', datetime('now'));
        INSERT INTO clients(client_uid, name, area) VALUES ('legacy-client', 'Legacy Client', 'Legacy Root');
        """
    )
    ensure_area_hierarchy_schema(conn)
    return conn


def node_paths(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(node["area_uid"]): str(node["full_path"])
        for node in list_area_nodes(conn, include_inactive=True)
    }


def main() -> None:
    conn = make_db()

    legacy = sync_client_area_uid_from_path(conn, "legacy-client")
    assert legacy is not None
    legacy_row = conn.execute(
        "SELECT area_uid, area FROM clients WHERE client_uid='legacy-client'"
    ).fetchone()
    assert legacy_row["area_uid"] == legacy["area_uid"]
    assert legacy_row["area"] == "Legacy Root"

    cardona = add_area_node(conn, "Cardona")
    looc = add_area_node(conn, "Looc", cardona["area_uid"])
    zone = add_area_node(conn, "Zone 1", looc["area_uid"])
    street = add_area_node(conn, "Street A", zone["area_uid"])
    group = add_area_node(conn, "Group 1", street["area_uid"])

    assert group["full_path"] == "Cardona › Looc › Zone 1 › Street A › Group 1"

    conn.execute(
        "INSERT INTO clients(client_uid, name, area, area_uid) VALUES (?,?,?,?)",
        ("nested-client", "Nested Client", group["full_path"], group["area_uid"]),
    )
    conn.commit()
    assert count_clients_for_area_node(conn, cardona["area_uid"], include_descendants=True) == 1

    conn.execute(
        "INSERT INTO clients(client_uid, name, area, area_uid) VALUES (?,?,?,?)",
        ("stale-client", "Stale Client", street["full_path"], "stale-area-uid"),
    )
    conn.commit()
    assert count_clients_for_area_node(conn, cardona["area_uid"], include_descendants=True) == 2

    rename_map = rename_area_node(conn, looc["area_uid"], "Looc Proper")
    assert rename_map["Cardona › Looc"] == "Cardona › Looc Proper"
    renamed_group = find_area_node_by_path(
        conn,
        "Cardona › Looc Proper › Zone 1 › Street A › Group 1",
    )
    assert renamed_group is not None
    nested_row = conn.execute(
        "SELECT area_uid, area FROM clients WHERE client_uid='nested-client'"
    ).fetchone()
    assert nested_row["area_uid"] == group["area_uid"]
    assert nested_row["area"] == renamed_group["full_path"]
    stale_row = conn.execute(
        "SELECT area_uid, area FROM clients WHERE client_uid='stale-client'"
    ).fetchone()
    assert stale_row["area_uid"] == street["area_uid"]
    assert stale_row["area"] == "Cardona › Looc Proper › Zone 1 › Street A"

    rizal = add_area_node(conn, "Rizal")
    move_map = move_area_node(conn, looc["area_uid"], rizal["area_uid"])
    assert move_map["Cardona › Looc Proper"] == "Rizal › Looc Proper"
    moved_group = find_area_node_by_path(
        conn,
        "Rizal › Looc Proper › Zone 1 › Street A › Group 1",
    )
    assert moved_group is not None
    nested_row = conn.execute(
        "SELECT area FROM clients WHERE client_uid='nested-client'"
    ).fetchone()
    assert nested_row["area"] == moved_group["full_path"]

    sibling_a = add_area_node(conn, "Alpha", rizal["area_uid"])
    sibling_b = add_area_node(conn, "Beta", rizal["area_uid"])
    before = [
        node["area_uid"]
        for node in list_area_nodes(conn, include_inactive=True)
        if node["parent_uid"] == rizal["area_uid"]
    ]
    assert sibling_a["area_uid"] in before and sibling_b["area_uid"] in before
    assert move_area_node_order(conn, sibling_b["area_uid"], -1) is True
    siblings = [
        node
        for node in list_area_nodes(conn, include_inactive=True)
        if node["parent_uid"] == rizal["area_uid"]
    ]
    siblings.sort(key=lambda node: (node["sort_order"], node["name"].casefold()))
    assert siblings.index(next(node for node in siblings if node["area_uid"] == sibling_b["area_uid"])) < siblings.index(
        next(node for node in siblings if node["area_uid"] == sibling_a["area_uid"])
    )

    try:
        set_area_node_active(conn, looc["area_uid"], False)
    except ValueError as exc:
        assert "assigned to 2 client" in str(exc)
    else:
        raise AssertionError("In-use subtree deactivation should be blocked")

    conn.execute(
        "UPDATE clients SET area_uid=?, area=? WHERE client_uid IN ('nested-client','stale-client')",
        (cardona["area_uid"], cardona["full_path"]),
    )
    conn.commit()
    deactivated = set_area_node_active(conn, looc["area_uid"], False)
    assert looc["area_uid"] in deactivated
    assert find_area_node_by_path(conn, "Rizal › Looc Proper", include_inactive=False) is None
    inactive = find_area_node_by_path(conn, "Rizal › Looc Proper", include_inactive=True)
    assert inactive is not None and inactive["is_active"] == 0
    legacy_paths = {row[0] for row in conn.execute("SELECT name FROM areas").fetchall()}
    assert "Rizal › Looc Proper" not in legacy_paths

    try:
        set_area_node_active(conn, zone["area_uid"], True)
    except ValueError as exc:
        assert "Activate the parent Area first" in str(exc)
    else:
        raise AssertionError("A child Area must not activate below an inactive parent")
    assert find_area_node_by_path(
        conn,
        "Rizal › Looc Proper › Zone 1",
        include_inactive=False,
    ) is None

    set_area_node_active(conn, looc["area_uid"], True)
    active = find_area_node_by_path(conn, "Rizal › Looc Proper", include_inactive=False)
    assert active is not None
    active_zone = find_area_node_by_path(
        conn,
        "Rizal › Looc Proper › Zone 1",
        include_inactive=False,
    )
    assert active_zone is not None
    legacy_paths = {row[0] for row in conn.execute("SELECT name FROM areas").fetchall()}
    assert "Rizal › Looc Proper" in legacy_paths

    current_paths = node_paths(conn)
    assert current_paths[group["area_uid"]] == "Rizal › Looc Proper › Zone 1 › Street A › Group 1"
    print("Hierarchical Area UI Phase 2 operation tests passed")


if __name__ == "__main__":
    main()
