#!/usr/bin/env python3
"""Repository and service regressions for Client Info Logs Wave 78."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from spina_app.repositories.client_info_logs import (
    ensure_client_history_schema,
    fetch_client_history_records,
)
from spina_app.services.client_info_logs import (
    client_info_field_label,
    transform_client_history_records,
)

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATH = ROOT / "spina_app" / "repositories" / "client_info_logs.py"
SERVICE_PATH = ROOT / "spina_app" / "services" / "client_info_logs.py"


class DummyDB:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row


def test_repository_and_schema() -> None:
    db = DummyDB()
    assert ensure_client_history_schema(db)
    db.conn.execute(
        """
        INSERT INTO client_history (
            client_uid, name_before, name_after,
            loan_type_before, loan_type_after,
            action, changed_at, old_json, new_json, source, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "UID-1",
            "Ana",
            "Ana Maria",
            "Regular",
            "Regular",
            "UPDATE",
            "2026-07-29 10:00:00",
            '{"name":"Ana","principal":5000,"id":1}',
            '{"name":"Ana Maria","principal":6000,"id":1}',
            "clients:edit",
            "corrected application",
        ),
    )
    db.conn.execute(
        """
        INSERT INTO client_history (
            client_uid, name_before, name_after,
            loan_type_before, loan_type_after,
            action, changed_at, old_json, new_json, source, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "UID-2",
            "Ben",
            "Ben",
            "7x7",
            "7x7",
            "UPDATE",
            "2026-07-29 11:00:00",
            '{"picture_path":"old.jpg"}',
            '{"picture_path":"new.jpg"}',
            "client_picture:update",
            "",
        ),
    )
    db.conn.commit()

    records = fetch_client_history_records(db, limit=10)
    assert len(records) == 2
    assert records[0]["name_after"] == "Ben"
    assert records[1]["name_after"] == "Ana Maria"


def test_service_transformation() -> None:
    records = [
        {
            "id": 2,
            "name_before": "Ben",
            "name_after": "Ben",
            "loan_type_before": "7x7",
            "loan_type_after": "7x7",
            "action": "UPDATE",
            "changed_at": "2026-07-29 11:00:00",
            "old_json": '{"picture_path":"old.jpg"}',
            "new_json": '{"picture_path":"new.jpg"}',
            "source": "client_picture:update",
            "note": "",
        },
        {
            "id": 1,
            "name_before": "Ana",
            "name_after": "Ana Maria",
            "loan_type_before": "Regular",
            "loan_type_after": "Regular",
            "action": "UPDATE",
            "changed_at": "2026-07-29 10:00:00",
            "old_json": '{"name":"Ana","principal":5000,"id":1}',
            "new_json": '{"name":"Ana Maria","principal":6000,"id":1}',
            "source": "clients:edit",
            "note": "corrected application",
        },
    ]
    rows = transform_client_history_records(records)
    assert len(rows) == 3

    picture = next(row for row in rows if row["field_key"] == "picture_path")
    assert picture["action"] == "PICTURE"
    assert picture["field"] == "Client Picture"
    assert picture["before"] == "old.jpg"
    assert picture["after"] == "new.jpg"

    principal = next(row for row in rows if row["field_key"] == "principal")
    assert principal["action"] == "EDIT"
    assert principal["field"] == "Principal"
    assert principal["before"] == "5,000.00"
    assert principal["after"] == "6,000.00"
    assert principal["client"] == "Ana Maria"

    assert client_info_field_label("semi_due_day1") == "Semi Due Day 1"
    assert client_info_field_label("custom_field") == "Custom Field"


def test_layer_boundaries() -> None:
    repository_source = REPOSITORY_PATH.read_text(encoding="utf-8").lower()
    service_source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    assert "import tkinter" not in repository_source
    assert "from tkinter" not in repository_source
    assert "import tkinter" not in service_source
    assert "from tkinter" not in service_source
    for mutation in ("insert into", "update clients", "delete from"):
        assert mutation not in service_source


def main() -> None:
    test_repository_and_schema()
    test_service_transformation()
    test_layer_boundaries()
    print("Wave 78 Client Info Logs layer tests passed.")


if __name__ == "__main__":
    main()
