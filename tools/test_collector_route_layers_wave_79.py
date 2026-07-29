#!/usr/bin/env python3
"""Repository and pure-service regressions for Collector Route Wave 79."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from spina_app.repositories.collector_route import (
    fetch_active_area_client_counts,
    fetch_active_areas,
    fetch_no_area_clients,
    load_collector_records,
    normalize_collector_records,
    save_collector_records,
)
from spina_app.services.collector_route import (
    build_route_coverage,
    collector_name_from_values,
    normalize_loan_type,
    regular_first_route_rows,
    summarize_collector,
)


def split_area(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    for separator in (" - ", " / ", "|", ":"):
        if separator in text:
            main, sub = text.split(separator, 1)
            return main.strip(), sub.strip()
    return text, ""


def test_schema_normalization() -> None:
    raw = [
        {"collector": "Ana", "route": ["Cardona - East"], "note": "Morning"},
        {"name": "Ana", "areas": ["Cardona - West"], "notes": "Updated"},
        "Ben: Morong, Teresa",
        "Cara",
    ]
    records = normalize_collector_records(raw)
    assert records["Ana"]["areas"] == ["Cardona - East", "Cardona - West"]
    assert records["Ana"]["notes"] == "Updated"
    assert records["Ben"]["areas"] == ["Morong", "Teresa"]
    assert records["Cara"] == {"areas": [], "notes": ""}

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "collectors.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = load_collector_records(path)
        assert loaded == records

        def write_atomic(target: str, data) -> bool:
            Path(target).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return True

        assert save_collector_records(path, loaded, write_json_atomic=write_atomic)
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["Ana"]["areas"] == ["Cardona - East", "Cardona - West"]


def test_repository_reads() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE clients (name TEXT, loan_type TEXT, area TEXT, is_archived INTEGER DEFAULT 0)"
    )
    connection.executemany(
        "INSERT INTO clients (name, loan_type, area, is_archived) VALUES (?, ?, ?, ?)",
        [
            ("Reg A", "Regular", "Cardona - East", 0),
            ("X7 A", "7x7", "Cardona - East", 0),
            ("Emer A", "Emergency", "Cardona - West", 0),
            ("No Area", "Regular", "", 0),
            ("Archived", "Regular", "Morong", 1),
        ],
    )
    connection.commit()

    class DB:
        conn = connection

    areas = fetch_active_areas(DB())
    assert areas == ["Cardona - East", "Cardona - West"]
    counts = fetch_active_area_client_counts(DB())
    assert counts["cardona - east"] == {"regular": 1, "7x7": 1}
    assert counts["cardona - west"] == {"regular": 0, "7x7": 1}
    assert fetch_no_area_clients(DB()) == [("No Area", "Regular")]


def test_coverage_and_ordering() -> None:
    records = {
        "Ana": {"areas": ["Cardona"], "notes": ""},
        "Ben": {"areas": ["Cardona - East", "Unknown"], "notes": ""},
    }
    coverage = build_route_coverage(
        records,
        ["Cardona - East", "Cardona - West", "Morong"],
        split_area=split_area,
    )
    assert coverage["unassigned_areas"] == ["Morong"]
    assert coverage["unknown_route_areas"] == ["Unknown"]
    assert coverage["conflicts"]["cardona - east"] == ["Ana", "Ben"]

    counts = {
        "cardona - east": {"regular": 2, "7x7": 1},
        "cardona - west": {"regular": 1, "7x7": 2},
    }
    summary = summarize_collector(
        "Ana",
        records["Ana"],
        coverage["collector_coverage"],
        counts,
        coverage["conflicts"],
        coverage["unknown_route_areas"],
    )
    assert summary["regular"] == 3
    assert summary["7x7"] == 3
    assert summary["has_conflict"] is True

    regular = [{"name": "Same"}, {"name": "Regular Only"}]
    x7 = [{"name": "same"}, {"name": "7x7 Only"}]
    combined = regular_first_route_rows(regular, x7)
    assert [row["name"] for row in combined] == ["Same", "Regular Only", "7x7 Only"]


def test_aliases_and_selection() -> None:
    assert normalize_loan_type("Regular") == "Regular"
    assert normalize_loan_type("7×7") == "7x7"
    assert normalize_loan_type("Emer") == "7x7"
    assert normalize_loan_type("Emergency") == "7x7"
    assert collector_name_from_values(("●", "Collector A", "2")) == "Collector A"
    assert collector_name_from_values(("Legacy Collector", "2")) == "Legacy Collector"


def main() -> None:
    test_schema_normalization()
    test_repository_reads()
    test_coverage_and_ordering()
    test_aliases_and_selection()
    print("Wave 79 Collector Route repository/service tests passed.")


if __name__ == "__main__":
    main()
