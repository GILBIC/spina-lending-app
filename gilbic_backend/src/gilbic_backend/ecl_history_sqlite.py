from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
from typing import Any


@dataclass(frozen=True, slots=True)
class HistoricalEpisode:
    episode_key: str
    borrower_key: str
    episode_sequence: int
    loan_type: str
    source_event: str
    release_date: str | None
    due_date: str | None
    principal: str
    contractual_total: str | None
    interest_rate: str | None
    outcome_evidence: str
    outcome_date: str | None
    renewal_rollover_amount: str | None
    cash_collected: str
    positive_payment_count: int
    zero_payment_observation_count: int
    observed_collection_days: int
    source_quality_status: str
    source_quality_note: str | None


@dataclass(frozen=True, slots=True)
class HistoricalReconstruction:
    source_filename: str
    source_sha256: str
    source_size_bytes: int
    sqlite_integrity_check: str
    source_snapshot_date: str | None
    source_client_count: int
    source_renewal_count: int
    source_transaction_count: int
    episodes: tuple[HistoricalEpisode, ...]

    def to_json_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["episodes"] = [asdict(item) for item in self.episodes]
        result["reconstructed_episode_count"] = len(self.episodes)
        return result


def reconstruct_sqlite_history(path: str | Path) -> HistoricalReconstruction:
    source = Path(path)
    digest = _sha256_file(source)
    connection = sqlite3.connect(source)
    connection.row_factory = sqlite3.Row
    try:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity.lower() != "ok":
            raise ValueError(f"SQLite integrity check failed: {integrity}")

        required = {"clients", "client_history", "renewals", "transactions"}
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing = required - tables
        if missing:
            raise ValueError(
                "Legacy SQLite database is missing required tables: "
                + ", ".join(sorted(missing))
            )

        clients = {
            str(row["client_uid"]): dict(row)
            for row in connection.execute("SELECT * FROM clients")
            if row["client_uid"]
        }
        starts = _load_episode_starts(connection)
        terminals = _load_terminal_events(connection)
        transactions = _load_transactions(connection)

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in starts:
            grouped.setdefault(item["client_uid"], []).append(item)

        episodes: list[HistoricalEpisode] = []
        for client_uid, items in grouped.items():
            items.sort(key=_episode_sort_key)
            for sequence, item in enumerate(items, start=1):
                next_item = items[sequence] if sequence < len(items) else None
                current_client = clients.get(client_uid)
                outcome, outcome_date = _outcome_evidence(
                    item=item,
                    next_item=next_item,
                    terminal_events=terminals.get(client_uid, ()),
                    current_client=current_client,
                )
                cash = _episode_cash(
                    transactions.get(client_uid, ()),
                    release_date=item["release_date"],
                    next_release_date=(next_item["release_date"] if next_item else None),
                )
                quality_status, quality_note = _quality(item)
                rollover = _rollover_for_next_renewal(next_item)
                borrower_source = (
                    (current_client or {}).get("person_uid")
                    or client_uid
                )
                episode_key = _hash_text(
                    "|".join(
                        [
                            client_uid,
                            str(sequence),
                            item["release_date"] or "",
                            _decimal_text(item["principal"]) or "0.00",
                            item["loan_type"],
                        ]
                    )
                )
                episodes.append(
                    HistoricalEpisode(
                        episode_key=episode_key,
                        borrower_key=_hash_text(str(borrower_source)),
                        episode_sequence=sequence,
                        loan_type=item["loan_type"],
                        source_event=item["source_event"],
                        release_date=item["release_date"],
                        due_date=item["due_date"],
                        principal=_decimal_text(item["principal"]) or "0.00",
                        contractual_total=_decimal_text(item["contractual_total"]),
                        interest_rate=_decimal_text(item["interest_rate"], places=8),
                        outcome_evidence=outcome,
                        outcome_date=outcome_date,
                        renewal_rollover_amount=rollover,
                        cash_collected=cash["cash_collected"],
                        positive_payment_count=cash["positive_payment_count"],
                        zero_payment_observation_count=cash[
                            "zero_payment_observation_count"
                        ],
                        observed_collection_days=cash["observed_collection_days"],
                        source_quality_status=quality_status,
                        source_quality_note=quality_note,
                    )
                )

        snapshot_row = connection.execute(
            "SELECT MAX(date) FROM transactions"
        ).fetchone()
        snapshot_date = _date_text(snapshot_row[0] if snapshot_row else None)
        renewal_count = int(
            connection.execute("SELECT COUNT(*) FROM renewals").fetchone()[0]
        )
        transaction_count = int(
            connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        )
        return HistoricalReconstruction(
            source_filename=source.name,
            source_sha256=digest,
            source_size_bytes=source.stat().st_size,
            sqlite_integrity_check=integrity,
            source_snapshot_date=snapshot_date,
            source_client_count=len(clients),
            source_renewal_count=renewal_count,
            source_transaction_count=transaction_count,
            episodes=tuple(episodes),
        )
    finally:
        connection.close()


def _load_episode_starts(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, client_uid, action, changed_at, new_json
        FROM client_history
        WHERE action IN ('SNAPSHOT', 'ADD', 'RENEW')
          AND new_json IS NOT NULL
        ORDER BY changed_at, id
        """
    ).fetchall()
    unique: dict[tuple[str, str | None, str, str], dict[str, Any]] = {}
    for row in rows:
        try:
            payload = json.loads(row["new_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        client_uid = str(row["client_uid"] or "").strip()
        if not client_uid:
            continue
        loan_type = str(payload.get("loan_type") or "").strip() or "Unknown"
        release_date = _date_text(payload.get("date_released"))
        principal = _decimal_text(payload.get("principal")) or "0.00"
        key = (client_uid, release_date, principal, loan_type)
        # Keep the earliest event for exact duplicate renewals. This preserves the
        # original cash-release evidence rather than a later duplicate edit.
        if key in unique:
            continue
        unique[key] = {
            "client_uid": client_uid,
            "source_event": str(row["action"]),
            "changed_at": str(row["changed_at"] or ""),
            "release_date": release_date,
            "due_date": _date_text(payload.get("due_date")),
            "principal": payload.get("principal"),
            "contractual_total": payload.get("total_to_pay"),
            "interest_rate": payload.get("interest_rate"),
            "last_released_cash": payload.get("last_released_cash"),
            "loan_type": loan_type,
        }
    return list(unique.values())


def _load_terminal_events(
    connection: sqlite3.Connection,
) -> dict[str, tuple[dict[str, str], ...]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in connection.execute(
        """
        SELECT client_uid, action, changed_at
        FROM client_history
        WHERE action IN ('ARCHIVE', 'RESTORE', 'DELETE')
        ORDER BY changed_at, id
        """
    ):
        uid = str(row["client_uid"] or "").strip()
        if uid:
            grouped.setdefault(uid, []).append(
                {
                    "action": str(row["action"]),
                    "changed_at": str(row["changed_at"] or ""),
                }
            )
    return {key: tuple(value) for key, value in grouped.items()}


def _load_transactions(
    connection: sqlite3.Connection,
) -> dict[str, tuple[dict[str, Any], ...]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in connection.execute(
        "SELECT client_uid, date, payment FROM transactions ORDER BY date, id"
    ):
        uid = str(row["client_uid"] or "").strip()
        if not uid:
            continue
        grouped.setdefault(uid, []).append(
            {
                "date": _date_text(row["date"]),
                "payment": row["payment"],
            }
        )
    return {key: tuple(value) for key, value in grouped.items()}


def _episode_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (item["release_date"] or "9999-12-31", item["changed_at"])


def _outcome_evidence(
    *,
    item: dict[str, Any],
    next_item: dict[str, Any] | None,
    terminal_events: tuple[dict[str, str], ...],
    current_client: dict[str, Any] | None,
) -> tuple[str, str | None]:
    if next_item is not None:
        return "renewed", next_item["release_date"] or _date_text(next_item["changed_at"])

    after = [
        event
        for event in terminal_events
        if event["changed_at"] >= item["changed_at"]
    ]
    if after:
        final = after[-1]
        if final["action"] == "DELETE":
            return "deleted", _date_text(final["changed_at"])
        if final["action"] == "ARCHIVE":
            return "archived", _date_text(final["changed_at"])
        if final["action"] == "RESTORE":
            return "open_at_snapshot", None

    if current_client and int(current_client.get("is_archived") or 0) == 1:
        return "archived_at_snapshot", _date_text(current_client.get("archived_at"))
    return "open_at_snapshot", None


def _episode_cash(
    rows: tuple[dict[str, Any], ...],
    *,
    release_date: str | None,
    next_release_date: str | None,
) -> dict[str, Any]:
    if release_date is None:
        return {
            "cash_collected": "0.00",
            "positive_payment_count": 0,
            "zero_payment_observation_count": 0,
            "observed_collection_days": 0,
        }
    selected = [
        row
        for row in rows
        if row["date"] is not None
        and row["date"] >= release_date
        and (next_release_date is None or row["date"] < next_release_date)
    ]
    total = Decimal("0")
    positive = 0
    zero = 0
    dates: set[str] = set()
    for row in selected:
        dates.add(row["date"])
        amount = _decimal(row["payment"]) or Decimal("0")
        if amount > 0:
            total += amount
            positive += 1
        elif amount == 0:
            zero += 1
    return {
        "cash_collected": _decimal_text(total) or "0.00",
        "positive_payment_count": positive,
        "zero_payment_observation_count": zero,
        "observed_collection_days": len(dates),
    }


def _rollover_for_next_renewal(next_item: dict[str, Any] | None) -> str | None:
    if not next_item or next_item["source_event"] != "RENEW":
        return None
    principal = _decimal(next_item.get("principal"))
    released = _decimal(next_item.get("last_released_cash"))
    if principal is None or released is None:
        return None
    return _decimal_text(max(principal - released, Decimal("0")))


def _quality(item: dict[str, Any]) -> tuple[str, str | None]:
    blockers: list[str] = []
    principal = _decimal(item.get("principal"))
    if item.get("release_date") is None:
        blockers.append("missing release date")
    if item.get("due_date") is None:
        blockers.append("missing due date")
    if principal is None or principal <= 0:
        blockers.append("non-positive principal")
    if item.get("loan_type") not in {"Regular", "7x7"}:
        blockers.append("unsupported loan type")
    if blockers:
        return "source_review_required", "; ".join(blockers)
    return "ready_for_outcome_labeling", None


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    candidate = text[:10]
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        try:
            return datetime.fromisoformat(text).date().isoformat()
        except ValueError:
            return None


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _decimal_text(value: Any, *, places: int = 2) -> str | None:
    number = _decimal(value)
    if number is None:
        return None
    quantum = Decimal(1).scaleb(-places)
    return format(number.quantize(quantum), f".{places}f")


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
