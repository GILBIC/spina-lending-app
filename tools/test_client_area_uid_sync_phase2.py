from __future__ import annotations

import sqlite3

from spina_app.area_hierarchy import add_area_node, ensure_area_hierarchy_schema
from spina_app.area_hierarchy_ops import sync_client_area_uid_from_path


def main() -> None:
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
        INSERT INTO clients(client_uid, name, area, area_uid)
        VALUES ('client-1', 'Test Client', '', 'stale-area-uid');
        """
    )
    ensure_area_hierarchy_schema(conn)

    cardona = add_area_node(conn, "Cardona")
    looc = add_area_node(conn, "Looc", cardona["area_uid"])

    conn.execute(
        "UPDATE clients SET area=?, area_uid=? WHERE client_uid='client-1'",
        (looc["full_path"], cardona["area_uid"]),
    )
    conn.commit()
    synced = sync_client_area_uid_from_path(conn, "client-1")
    assert synced is not None
    row = conn.execute(
        "SELECT area, area_uid FROM clients WHERE client_uid='client-1'"
    ).fetchone()
    assert row["area"] == "Cardona › Looc"
    assert row["area_uid"] == looc["area_uid"]

    conn.execute(
        "UPDATE clients SET area='', area_uid=? WHERE client_uid='client-1'",
        (looc["area_uid"],),
    )
    conn.commit()
    cleared = sync_client_area_uid_from_path(conn, "client-1")
    assert cleared is None
    row = conn.execute(
        "SELECT area, area_uid FROM clients WHERE client_uid='client-1'"
    ).fetchone()
    assert row["area"] == ""
    assert row["area_uid"] == ""

    conn.execute(
        "INSERT INTO areas(name, created_at) VALUES ('Imported Area', datetime('now'))"
    )
    conn.execute(
        "UPDATE clients SET area='Imported Area', area_uid='old-value' "
        "WHERE client_uid='client-1'"
    )
    conn.commit()
    imported = sync_client_area_uid_from_path(conn, "client-1")
    assert imported is not None
    row = conn.execute(
        "SELECT area, area_uid FROM clients WHERE client_uid='client-1'"
    ).fetchone()
    assert row["area"] == "Imported Area"
    assert row["area_uid"] == imported["area_uid"]
    assert imported["area_uid"] != "old-value"

    print("Immediate client Area UID synchronization tests passed")


if __name__ == "__main__":
    main()
