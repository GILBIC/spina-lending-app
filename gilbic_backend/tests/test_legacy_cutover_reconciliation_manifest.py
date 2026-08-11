from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "build_legacy_cutover_reconciliation_manifest.py"
spec = importlib.util.spec_from_file_location("legacy_cutover_manifest", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _create_legacy(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE clients (
                id INTEGER PRIMARY KEY,
                client_uid TEXT,
                person_uid TEXT,
                link_opt_out INTEGER DEFAULT 0,
                name TEXT NOT NULL,
                contact_number TEXT DEFAULT '',
                principal REAL DEFAULT 0,
                interest_rate REAL DEFAULT 0.20,
                interest_amount REAL DEFAULT 0,
                total_to_pay REAL DEFAULT 0,
                date_released TEXT,
                due_date TEXT,
                area TEXT DEFAULT '',
                pay_start_offset_days INTEGER DEFAULT 1,
                loan_type TEXT DEFAULT 'Regular',
                is_archived INTEGER DEFAULT 0,
                renew_count INTEGER DEFAULT 0,
                last_released_cash REAL,
                payment_term TEXT DEFAULT 'Daily',
                payment_amount REAL DEFAULT 0,
                payment_mode TEXT DEFAULT 'Cash'
            );
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY,
                client_uid TEXT,
                name TEXT NOT NULL,
                loan_type TEXT DEFAULT 'Regular',
                date TEXT NOT NULL,
                payment REAL DEFAULT 0,
                description TEXT
            );
            CREATE TABLE renewals (
                id INTEGER PRIMARY KEY,
                client_uid TEXT,
                loan_type TEXT DEFAULT 'Regular',
                renew_date TEXT NOT NULL,
                released_cash REAL DEFAULT 0,
                principal_after REAL DEFAULT 0,
                interest_rate REAL DEFAULT 0,
                note TEXT,
                whose_cash TEXT,
                delivered_by TEXT
            );
            """
        )
        conn.execute(
            """INSERT INTO clients VALUES
               (1,'R-1','P-1',0,'Ready Regular','0917',10000,0.20,2000,12000,
                '2026-07-01','2026-10-29','A',1,'Regular',0,0,10000,'Daily',100,'Cash')"""
        )
        conn.execute(
            """INSERT INTO clients VALUES
               (2,'R-2','P-2',0,'Weekly Regular','0918',10000,0.20,2000,12000,
                '2026-07-01','2026-10-29','A',1,'Regular',0,0,10000,'Weekly',700,'Cash')"""
        )
        conn.execute(
            """INSERT INTO clients VALUES
               (3,'X-1','P-3',0,'Seven Client','0919',5000,0,0,5000,
                '2026-07-01','2026-10-29','A',1,'7x7',0,0,5000,'Daily',100,'Cash')"""
        )
        conn.execute(
            "INSERT INTO transactions VALUES (1,'R-1','Ready Regular','Regular','2026-07-02',100,'Collection')"
        )
        conn.execute(
            "INSERT INTO transactions VALUES (2,'X-1','Seven Client','7x7','2026-07-02',100,'Collection')"
        )
        conn.commit()
    finally:
        conn.close()


def test_manifest_is_read_only_and_fail_closes_unsupported_regular_term(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    _create_legacy(db)
    before = _hash(db)

    manifest = module.build_manifest(db, module.date.fromisoformat("2026-08-07"))

    after = _hash(db)
    assert before == after
    assert manifest["target_contract"]["write_performed"] is False
    assert manifest["source"]["read_only_open"] is True
    assert manifest["summary"]["active_legacy_loan_rows"] == 3
    assert manifest["summary"]["ready_loan_candidates"] == 2
    assert manifest["summary"]["blocked_loan_candidates"] == 1
    assert manifest["summary"]["overall_status"] == "blocked"

    weekly = next(row for row in manifest["loans"] if row["source_client_uid"] == "R-2")
    assert weekly["mapping_status"] == "blocked"
    assert any("requires explicit target schedule normalization" in b for b in weekly["blockers"])

    seven = next(row for row in manifest["loans"] if row["source_client_uid"] == "X-1")
    assert seven["target_daily_amount_candidate"] == "35.00"


def test_linked_regular_and_7x7_rows_map_to_one_target_client(tmp_path: Path) -> None:
    db = tmp_path / "linked.db"
    _create_legacy(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute("UPDATE clients SET person_uid='P-SAME' WHERE id IN (1,3)")
        conn.commit()
    finally:
        conn.close()

    manifest = module.build_manifest(db, module.date.fromisoformat("2026-08-07"))
    linked = [c for c in manifest["clients"] if c["target_client_match_key"] == "P-SAME"]
    assert len(linked) == 1
    assert set(linked[0]["source_client_uids"]) == {"R-1", "X-1"}
