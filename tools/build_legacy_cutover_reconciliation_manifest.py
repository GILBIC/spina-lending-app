#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

REQUIRED_TABLES = {"clients", "transactions", "renewals"}
REQUIRED_CLIENT_COLUMNS = {
    "id","client_uid","person_uid","link_opt_out","name","contact_number","principal",
    "interest_rate","interest_amount","total_to_pay","date_released","due_date","area",
    "pay_start_offset_days","loan_type","is_archived","renew_count","last_released_cash",
    "payment_term","payment_amount","payment_mode",
}
REQUIRED_TRANSACTION_COLUMNS = {"id","client_uid","name","loan_type","date","payment","description"}
REQUIRED_RENEWAL_COLUMNS = {"id","client_uid","loan_type","renew_date","released_cash","principal_after","interest_rate"}

SUPPORTED_LOAN_TYPES = {"Regular", "7x7"}
MONEY = Decimal("0.01")


def money(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def require_schema(conn: sqlite3.Connection) -> None:
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing_tables = REQUIRED_TABLES - tables
    if missing_tables:
        raise RuntimeError(f"Missing required legacy tables: {sorted(missing_tables)}")

    checks = {
        "clients": REQUIRED_CLIENT_COLUMNS,
        "transactions": REQUIRED_TRANSACTION_COLUMNS,
        "renewals": REQUIRED_RENEWAL_COLUMNS,
    }
    for table, required in checks.items():
        missing = required - table_columns(conn, table)
        if missing:
            raise RuntimeError(f"Missing required columns on {table}: {sorted(missing)}")


def borrower_key(row: sqlite3.Row) -> str:
    person_uid = str(row["person_uid"] or "").strip()
    client_uid = str(row["client_uid"] or "").strip()
    opt_out = int(row["link_opt_out"] or 0) != 0
    return client_uid if opt_out or not person_uid else person_uid


def normalized_term(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("d"):
        return "Daily"
    if "week" in text or text.startswith("w"):
        return "Weekly"
    if "semi" in text or "bi" in text or "quin" in text:
        return "Semi"
    if "month" in text or text.startswith("m"):
        return "Monthly"
    return str(value or "").strip() or "Unknown"


def target_daily_amount(row: sqlite3.Row) -> tuple[Decimal | None, str | None]:
    principal = money(row["principal"])
    loan_type = str(row["loan_type"] or "").strip()
    term = normalized_term(row["payment_term"])
    source_payment = money(row["payment_amount"])

    if loan_type == "7x7":
        units = (principal / Decimal("1000")).to_integral_value(rounding="ROUND_CEILING")
        return (units * Decimal("7.00")).quantize(MONEY), None

    if loan_type == "Regular":
        if term != "Daily":
            return None, f"Regular payment term {term} requires explicit target schedule normalization."
        return source_payment, None

    return None, f"Unsupported loan type: {loan_type or '(blank)'}"


def latest_release_and_renewals(
    conn: sqlite3.Connection,
    client_uid: str,
    loan_type: str,
    source_release: date | None,
    cutoff: date,
) -> tuple[date | None, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT id, renew_date, released_cash, principal_after, interest_rate, note, whose_cash, delivered_by
        FROM renewals
        WHERE client_uid = ? AND loan_type = ? AND substr(renew_date, 1, 10) <= ?
        ORDER BY renew_date, id
        """,
        (client_uid, loan_type, cutoff.isoformat()),
    ).fetchall()
    lineage = []
    latest = source_release
    for row in rows:
        renew_date = parse_iso_date(row["renew_date"])
        if renew_date and (latest is None or renew_date > latest):
            latest = renew_date
        lineage.append(
            {
                "id": row["id"],
                "renew_date": renew_date.isoformat() if renew_date else None,
                "released_cash": str(money(row["released_cash"])),
                "principal_after": str(money(row["principal_after"])),
                "interest_rate": None if row["interest_rate"] is None else str(row["interest_rate"]),
                "note": row["note"],
                "whose_cash": row["whose_cash"],
                "delivered_by": row["delivered_by"],
            }
        )
    return latest, lineage


def paid_since_latest_release(
    conn: sqlite3.Connection,
    client_uid: str,
    loan_type: str,
    payment_start: date | None,
    cutoff: date,
) -> tuple[Decimal, int, int]:
    if payment_start is None:
        return Decimal("0.00"), 0, 0
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN payment > 0 THEN payment ELSE 0 END), 0) AS paid,
            COUNT(*) AS observation_count,
            SUM(CASE WHEN payment > 0 THEN 1 ELSE 0 END) AS positive_payment_count
        FROM transactions
        WHERE client_uid = ?
          AND loan_type = ?
          AND substr(date, 1, 10) >= ?
          AND substr(date, 1, 10) <= ?
        """,
        (client_uid, loan_type, payment_start.isoformat(), cutoff.isoformat()),
    ).fetchone()
    return money(row["paid"]), int(row["observation_count"] or 0), int(row["positive_payment_count"] or 0)


def source_integrity_findings(conn: sqlite3.Connection, cutoff: date) -> list[dict[str, Any]]:
    checks = [
        (
            "active_missing_client_uid",
            "block",
            "SELECT COUNT(*) FROM clients WHERE is_archived = 0 AND trim(COALESCE(client_uid,'')) = ''",
        ),
        (
            "active_nonpositive_principal",
            "block",
            "SELECT COUNT(*) FROM clients WHERE is_archived = 0 AND COALESCE(principal,0) <= 0",
        ),
        (
            "active_unsupported_loan_type",
            "block",
            "SELECT COUNT(*) FROM clients WHERE is_archived = 0 AND loan_type NOT IN ('Regular','7x7')",
        ),
        (
            "active_instruction_text_names",
            "block",
            """SELECT COUNT(*) FROM clients
               WHERE is_archived = 0
                 AND lower(name) LIKE 'enter collection for %'""",
        ),
        (
            "duplicate_active_client_uid",
            "block",
            """SELECT COUNT(*) FROM (
                   SELECT client_uid FROM clients WHERE is_archived = 0
                   GROUP BY client_uid HAVING COUNT(*) > 1
               ) x""",
        ),
        (
            "orphan_transactions",
            "block",
            """SELECT COUNT(*) FROM transactions t
               LEFT JOIN clients c ON c.client_uid = t.client_uid AND c.loan_type = t.loan_type
               WHERE c.id IS NULL""",
        ),
        (
            "negative_transactions",
            "block",
            "SELECT COUNT(*) FROM transactions WHERE COALESCE(payment,0) < 0",
        ),
        (
            "post_cutoff_transactions",
            "block",
            f"SELECT COUNT(*) FROM transactions WHERE substr(date,1,10) > '{cutoff.isoformat()}'",
        ),
        (
            "orphan_renewals",
            "block",
            """SELECT COUNT(*) FROM renewals r
               LEFT JOIN clients c ON c.client_uid = r.client_uid AND c.loan_type = r.loan_type
               WHERE c.id IS NULL""",
        ),
        (
            "post_cutoff_renewals",
            "block",
            f"SELECT COUNT(*) FROM renewals WHERE substr(renew_date,1,10) > '{cutoff.isoformat()}'",
        ),
    ]
    findings = []
    for code, severity, sql in checks:
        count = int(conn.execute(sql).fetchone()[0] or 0)
        findings.append(
            {
                "code": code,
                "severity": severity,
                "count": count,
                "status": "pass" if count == 0 else "fail",
            }
        )
    return findings


def client_group_findings(rows: list[sqlite3.Row]) -> list[str]:
    blockers = []
    names = {str(row["name"] or "").strip().casefold() for row in rows if str(row["name"] or "").strip()}
    phones = {str(row["contact_number"] or "").strip() for row in rows if str(row["contact_number"] or "").strip()}
    if len(names) > 1:
        blockers.append("Linked legacy rows disagree on borrower name.")
    if len(phones) > 1:
        blockers.append("Linked legacy rows disagree on borrower phone number.")
    return blockers


def build_manifest(db_path: Path, cutoff: date) -> dict[str, Any]:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        require_schema(conn)
        integrity = source_integrity_findings(conn, cutoff)

        active_rows = conn.execute(
            "SELECT * FROM clients WHERE is_archived = 0 ORDER BY id"
        ).fetchall()

        groups: dict[str, list[sqlite3.Row]] = {}
        for row in active_rows:
            groups.setdefault(borrower_key(row), []).append(row)

        client_manifest = []
        group_blockers: dict[str, list[str]] = {}
        for key, rows in sorted(groups.items()):
            blockers = client_group_findings(rows)
            group_blockers[key] = blockers
            first = rows[0]
            client_manifest.append(
                {
                    "target_client_match_key": key,
                    "target_client_legacy_id": key,
                    "source_client_uids": [str(r["client_uid"]) for r in rows],
                    "source_row_ids": [int(r["id"]) for r in rows],
                    "full_name": str(first["name"] or "").strip(),
                    "phone_number": str(first["contact_number"] or "").strip() or None,
                    "area": str(first["area"] or "").strip() or None,
                    "source_loan_types": sorted({str(r["loan_type"]) for r in rows}),
                    "mapping_status": "blocked" if blockers else "ready",
                    "blockers": blockers,
                }
            )

        loan_manifest = []
        for row in active_rows:
            client_uid = str(row["client_uid"] or "").strip()
            loan_type = str(row["loan_type"] or "").strip()
            source_release = parse_iso_date(row["date_released"])
            latest_release, lineage = latest_release_and_renewals(
                conn, client_uid, loan_type, source_release, cutoff
            )
            offset = int(row["pay_start_offset_days"] if row["pay_start_offset_days"] is not None else 1)
            payment_start = latest_release + timedelta(days=offset) if latest_release else None
            paid, observation_count, positive_payment_count = paid_since_latest_release(
                conn, client_uid, loan_type, payment_start, cutoff
            )

            principal = money(row["principal"])
            source_total = money(row["total_to_pay"])
            remaining = max(source_total - paid, Decimal("0.00"))
            daily_amount, daily_blocker = target_daily_amount(row)

            blockers = list(group_blockers[borrower_key(row)])
            if loan_type not in SUPPORTED_LOAN_TYPES:
                blockers.append("Unsupported loan type.")
            if not client_uid:
                blockers.append("Missing client_uid.")
            if principal <= 0:
                blockers.append("Principal must be positive.")
            if source_release is None:
                blockers.append("Missing original release date.")
            if latest_release and latest_release > cutoff:
                blockers.append("Latest release date is after cutoff.")
            if daily_blocker:
                blockers.append(daily_blocker)

            target_interest_rate = None
            if loan_type == "Regular":
                source_rate = Decimal(str(row["interest_rate"] or 0))
                if source_rate <= 0:
                    blockers.append("Regular interest rate is missing or non-positive.")
                elif abs(source_rate - Decimal("0.20")) > Decimal("0.0001") and abs(source_rate - Decimal("20")) > Decimal("0.01"):
                    blockers.append("Regular interest rate is not the fixed 20% product rule.")
                target_interest_rate = Decimal("20.0000")

                if normalized_term(row["payment_term"]) == "Daily" and daily_amount is not None:
                    expected = (principal * Decimal("1.20")).quantize(MONEY)
                    scheduled = (daily_amount * Decimal("120")).quantize(MONEY)
                    if abs(expected - scheduled) > MONEY:
                        blockers.append(
                            f"Regular 120-day scheduled amount {scheduled} does not equal principal plus 20% ({expected})."
                        )

            if loan_type == "7x7":
                target_interest_rate = None

            source_renew_count = int(row["renew_count"] or 0)
            if source_renew_count != len(lineage):
                blockers.append(
                    f"renew_count={source_renew_count} but {len(lineage)} renewal rows exist through cutoff."
                )

            loan_manifest.append(
                {
                    "source_row_id": int(row["id"]),
                    "source_client_uid": client_uid,
                    "source_person_uid": str(row["person_uid"] or "").strip() or None,
                    "target_client_match_key": borrower_key(row),
                    "target_loan_legacy_id": client_uid,
                    "loan_type": loan_type,
                    "target_calculation_mode": "fixed_daily" if loan_type == "Regular" else "seven_by_seven" if loan_type == "7x7" else None,
                    "principal": str(principal),
                    "source_total_to_pay": str(source_total),
                    "source_payment_term": normalized_term(row["payment_term"]),
                    "source_payment_amount": str(money(row["payment_amount"])),
                    "target_daily_amount_candidate": None if daily_amount is None else str(daily_amount),
                    "target_interest_rate_percent": None if target_interest_rate is None else str(target_interest_rate),
                    "original_release_date": source_release.isoformat() if source_release else None,
                    "latest_release_date": latest_release.isoformat() if latest_release else None,
                    "payment_start_date": payment_start.isoformat() if payment_start else None,
                    "source_due_date": parse_iso_date(row["due_date"]).isoformat() if parse_iso_date(row["due_date"]) else None,
                    "renewal_count_source": source_renew_count,
                    "renewal_count_observed": len(lineage),
                    "renewal_lineage": lineage,
                    "paid_since_latest_release": str(paid),
                    "transaction_observation_count": observation_count,
                    "positive_payment_count": positive_payment_count,
                    "operational_remaining_balance": str(remaining.quantize(MONEY)),
                    "mapping_status": "blocked" if blockers else "ready",
                    "blockers": blockers,
                }
            )

        global_failures = [f for f in integrity if f["status"] == "fail" and f["severity"] == "block"]
        blocked_loans = [r for r in loan_manifest if r["mapping_status"] == "blocked"]
        blocked_clients = [r for r in client_manifest if r["mapping_status"] == "blocked"]

        by_type: dict[str, dict[str, Any]] = {}
        for loan_type in sorted(SUPPORTED_LOAN_TYPES):
            rows = [r for r in loan_manifest if r["loan_type"] == loan_type]
            by_type[loan_type] = {
                "loan_count": len(rows),
                "principal": str(sum((money(r["principal"]) for r in rows), Decimal("0.00")).quantize(MONEY)),
                "operational_remaining_balance": str(
                    sum((money(r["operational_remaining_balance"]) for r in rows), Decimal("0.00")).quantize(MONEY)
                ),
                "ready_count": sum(1 for r in rows if r["mapping_status"] == "ready"),
                "blocked_count": sum(1 for r in rows if r["mapping_status"] == "blocked"),
            }

        overall = "blocked" if global_failures or blocked_loans or blocked_clients else "ready_for_disposable_target_load_test"

        return {
            "manifest_version": "spina_legacy_cutover_reconciliation_v1",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "source": {
                "filename": db_path.name,
                "size_bytes": db_path.stat().st_size,
                "sha256": sha256_file(db_path),
                "cutoff_date": cutoff.isoformat(),
                "read_only_open": True,
            },
            "target_contract": {
                "client_identity": "lending.clients.legacy_client_id",
                "loan_identity": "lending.loans.legacy_loan_id",
                "regular_calculation_mode": "fixed_daily",
                "seven_by_seven_calculation_mode": "seven_by_seven",
                "automatic_source_posting": False,
                "write_performed": False,
            },
            "summary": {
                "active_legacy_loan_rows": len(active_rows),
                "target_client_candidates": len(client_manifest),
                "ready_client_candidates": len(client_manifest) - len(blocked_clients),
                "blocked_client_candidates": len(blocked_clients),
                "ready_loan_candidates": len(loan_manifest) - len(blocked_loans),
                "blocked_loan_candidates": len(blocked_loans),
                "by_loan_type": by_type,
                "overall_status": overall,
            },
            "source_integrity": integrity,
            "clients": client_manifest,
            "loans": loan_manifest,
        }
    finally:
        conn.close()


def write_csv(manifest: dict[str, Any], path: Path) -> None:
    fields = [
        "source_row_id","source_client_uid","source_person_uid","target_client_match_key",
        "target_loan_legacy_id","loan_type","target_calculation_mode","principal",
        "source_total_to_pay","source_payment_term","source_payment_amount",
        "target_daily_amount_candidate","target_interest_rate_percent","original_release_date",
        "latest_release_date","payment_start_date","source_due_date","renewal_count_source",
        "renewal_count_observed","paid_since_latest_release","transaction_observation_count",
        "positive_payment_count","operational_remaining_balance","mapping_status","blockers",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in manifest["loans"]:
            out = {key: row.get(key) for key in fields}
            out["blockers"] = " | ".join(row.get("blockers") or [])
            writer.writerow(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a read-only SPINA legacy-to-target cutover reconciliation manifest."
    )
    parser.add_argument("legacy_db", type=Path)
    parser.add_argument("--cutoff-date", required=True, type=date.fromisoformat)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()

    manifest = build_manifest(args.legacy_db, args.cutoff_date)
    if args.json_out:
        args.json_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.csv_out:
        write_csv(manifest, args.csv_out)

    print(json.dumps(manifest["summary"], indent=2))
    return 0 if manifest["summary"]["overall_status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
