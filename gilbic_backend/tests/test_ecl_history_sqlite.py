from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from gilbic_backend.ecl_history_sqlite import reconstruct_sqlite_history


def _client_payload(*, release: str, principal: float, archived: int = 0) -> dict:
    return {
        "name": "TEST CLIENT",
        "loan_type": "Regular",
        "principal": principal,
        "interest_rate": 0.20,
        "total_to_pay": principal * 1.20,
        "date_released": release,
        "due_date": "2026-06-01",
        "last_released_cash": principal,
        "is_archived": archived,
    }


def test_reconstructs_renewed_episode_without_calling_it_default(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE clients (
            client_uid TEXT, person_uid TEXT, is_archived INTEGER, archived_at TEXT
        );
        CREATE TABLE client_history (
            id INTEGER PRIMARY KEY, client_uid TEXT, action TEXT,
            changed_at TEXT, new_json TEXT
        );
        CREATE TABLE renewals (id INTEGER PRIMARY KEY, client_uid TEXT);
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY, client_uid TEXT, date TEXT, payment REAL
        );
        """
    )
    connection.execute(
        "INSERT INTO clients VALUES (?, ?, 0, NULL)",
        ("client-1", "person-1"),
    )
    first = _client_payload(release="2026-01-01", principal=5000)
    second = _client_payload(release="2026-02-01", principal=5000)
    second["last_released_cash"] = 1000
    connection.execute(
        "INSERT INTO client_history VALUES (1, ?, 'SNAPSHOT', ?, ?)",
        ("client-1", "2026-01-10 00:00:00", json.dumps(first)),
    )
    connection.execute(
        "INSERT INTO client_history VALUES (2, ?, 'RENEW', ?, ?)",
        ("client-1", "2026-02-01 00:00:00", json.dumps(second)),
    )
    connection.execute("INSERT INTO renewals VALUES (1, ?)", ("client-1",))
    connection.execute(
        "INSERT INTO transactions VALUES (1, ?, '2026-01-05', 500)",
        ("client-1",),
    )
    connection.execute(
        "INSERT INTO transactions VALUES (2, ?, '2026-02-05', 100)",
        ("client-1",),
    )
    connection.commit()
    connection.close()

    result = reconstruct_sqlite_history(database)

    assert len(result.episodes) == 2
    first_episode, second_episode = result.episodes
    assert first_episode.outcome_evidence == "renewed"
    assert first_episode.outcome_date == "2026-02-01"
    assert first_episode.renewal_rollover_amount == "4000.00"
    assert first_episode.cash_collected == "500.00"
    assert second_episode.outcome_evidence == "open_at_snapshot"
    assert second_episode.cash_collected == "100.00"
    assert first_episode.source_quality_status == "ready_for_outcome_labeling"
    assert "default" not in first_episode.outcome_evidence


def test_missing_contract_fields_are_flagged_for_source_review(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE clients (
            client_uid TEXT, person_uid TEXT, is_archived INTEGER, archived_at TEXT
        );
        CREATE TABLE client_history (
            id INTEGER PRIMARY KEY, client_uid TEXT, action TEXT,
            changed_at TEXT, new_json TEXT
        );
        CREATE TABLE renewals (id INTEGER PRIMARY KEY, client_uid TEXT);
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY, client_uid TEXT, date TEXT, payment REAL
        );
        """
    )
    connection.execute(
        "INSERT INTO clients VALUES ('client-2', NULL, 0, NULL)"
    )
    payload = {
        "loan_type": "7x7",
        "principal": 0,
        "date_released": None,
        "due_date": None,
    }
    connection.execute(
        "INSERT INTO client_history VALUES (1, 'client-2', 'ADD', '2026-01-01 00:00:00', ?)",
        (json.dumps(payload),),
    )
    connection.commit()
    connection.close()

    result = reconstruct_sqlite_history(database)

    assert len(result.episodes) == 1
    episode = result.episodes[0]
    assert episode.source_quality_status == "source_review_required"
    assert "missing release date" in (episode.source_quality_note or "")
    assert "non-positive principal" in (episode.source_quality_note or "")
