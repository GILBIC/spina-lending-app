"""Persistence and read adapters for the Collector Route feature."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


def _row_value(row: Any, key: str, index: int, default: Any = None) -> Any:
    try:
        if hasattr(row, "keys"):
            return row[key]
    except Exception:
        pass
    try:
        return row[index]
    except Exception:
        return default


def normalize_collector_records(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalize all historical collectors.json shapes to the current dict schema."""
    result: dict[str, dict[str, Any]] = {}

    def add(name: Any, areas: Any = None, notes: Any = "") -> None:
        clean_name = str(name or "").strip()
        if not clean_name:
            return
        if isinstance(areas, str):
            area_values = [part.strip() for part in areas.split(",") if part.strip()]
        elif isinstance(areas, (list, tuple, set)):
            area_values = [str(area or "").strip() for area in areas if str(area or "").strip()]
        else:
            area_values = []
        entry = result.setdefault(clean_name, {"areas": [], "notes": ""})
        for area in area_values:
            if area not in entry["areas"]:
                entry["areas"].append(area)
        if notes not in (None, ""):
            entry["notes"] = str(notes)

    if isinstance(raw, Mapping):
        for name, value in raw.items():
            if isinstance(value, Mapping):
                add(
                    name,
                    value.get("areas") or value.get("route") or value.get("areas_list") or [],
                    value.get("notes") if value.get("notes") is not None else value.get("note", ""),
                )
            elif isinstance(value, (list, tuple, set)):
                add(name, value, "")
            elif isinstance(value, str):
                add(name, [], value)
            else:
                add(name)
    elif isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, Mapping):
                add(
                    item.get("name") or item.get("collector"),
                    item.get("areas") or item.get("route") or [],
                    item.get("notes") if item.get("notes") is not None else item.get("note", ""),
                )
            elif isinstance(item, str):
                text = item.strip()
                if not text:
                    continue
                separator = ":" if ":" in text else ("|" if "|" in text else None)
                if separator:
                    name, areas = text.split(separator, 1)
                    add(name, areas, "")
                else:
                    add(text)
    return result


def load_collector_records(
    path: str | Path,
    *,
    read_json: Callable[[str], Any] | None = None,
) -> dict[str, dict[str, Any]]:
    target = str(path)
    raw: Any = {}
    if callable(read_json):
        try:
            raw = read_json(target)
        except Exception:
            raw = {}
    else:
        try:
            import json

            raw = json.loads(Path(target).read_text(encoding="utf-8"))
        except Exception:
            raw = {}
    return normalize_collector_records(raw)


def save_collector_records(
    path: str | Path,
    records: Mapping[str, Mapping[str, Any]],
    *,
    write_json_atomic: Callable[[str, Any], bool],
) -> bool:
    normalized = normalize_collector_records(records)
    return bool(write_json_atomic(str(path), normalized))


def fetch_active_areas(db: Any) -> list[str]:
    """Return distinct nonblank areas used by active clients."""
    try:
        rows = db.conn.cursor().execute(
            "SELECT DISTINCT TRIM(area) AS area_name "
            "FROM clients "
            "WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 "
            "ORDER BY area_name COLLATE NOCASE"
        ).fetchall()
    except Exception:
        try:
            rows = [(area,) for area in (db.get_all_areas() or [])]
        except Exception:
            rows = []
    result: list[str] = []
    seen: set[str] = set()
    for row in rows or []:
        area = str(_row_value(row, "area_name", 0, "") or "").strip()
        key = " ".join(area.split()).lower()
        if area and key not in seen:
            seen.add(key)
            result.append(area)
    return result


def fetch_active_area_client_counts(db: Any) -> dict[str, dict[str, int]]:
    """Return normalized-area Regular/7x7 active-client counts."""
    try:
        rows = db.conn.cursor().execute(
            "SELECT TRIM(area) AS area_name, loan_type, COUNT(*) AS client_count "
            "FROM clients "
            "WHERE IFNULL(TRIM(area),'')<>'' AND COALESCE(is_archived,0)=0 "
            "GROUP BY TRIM(area), loan_type"
        ).fetchall()
    except Exception:
        rows = []
    result: dict[str, dict[str, int]] = {}
    for row in rows or []:
        area = str(_row_value(row, "area_name", 0, "") or "").strip()
        loan_type = str(_row_value(row, "loan_type", 1, "Regular") or "Regular")
        count = int(_row_value(row, "client_count", 2, 0) or 0)
        key = " ".join(area.split()).lower()
        if not key:
            continue
        bucket = result.setdefault(key, {"regular": 0, "7x7": 0})
        normalized_type = "7x7" if any(token in loan_type.lower().replace("×", "x") for token in ("7x7", "emer")) else "regular"
        bucket[normalized_type] = bucket.get(normalized_type, 0) + count
    return result


def fetch_no_area_clients(db: Any, *, limit: int = 200) -> list[tuple[str, str]]:
    try:
        rows = db.conn.cursor().execute(
            "SELECT name, loan_type FROM clients "
            "WHERE IFNULL(TRIM(area),'')='' AND COALESCE(is_archived,0)=0 "
            "ORDER BY loan_type, name COLLATE NOCASE LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
    except Exception:
        rows = []
    return [
        (
            str(_row_value(row, "name", 0, "") or ""),
            str(_row_value(row, "loan_type", 1, "Regular") or "Regular"),
        )
        for row in rows or []
    ]
