"""Pure Collector Route normalization and coverage rules."""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping


def normalize_area(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def normalize_loan_type(value: Any) -> str:
    text = str(value or "").strip().lower().replace("×", "x")
    return "7x7" if ("7x7" in text or "emer" in text) else "Regular"


def collector_name_from_values(values: Iterable[Any] | None) -> str:
    items = list(values or [])
    if not items:
        return ""
    first = str(items[0] or "").strip()
    markers = {"○", "●", "◯", "◉", "☐", "☑", "•", "∙", "·", "◦", "▪", "▫", "■", "□", ""}
    if len(items) >= 2:
        second = str(items[1] or "").strip()
        looks_like_marker = len(first) <= 2 and not any(char.isalnum() for char in first)
        if first in markers or (looks_like_marker and second):
            return second
    return first


def unique_areas(values: Iterable[Any] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        key = normalize_area(text)
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def build_route_coverage(
    collector_records: Mapping[str, Mapping[str, Any]],
    master_areas: Iterable[Any],
    *,
    split_area: Callable[[str], tuple[str, str]],
) -> dict[str, Any]:
    """Expand main/sub route entries and return coverage, conflicts, and unknowns."""
    cleaned_master = unique_areas(master_areas)
    master_name_map = {normalize_area(area): area for area in cleaned_master}
    master_set = set(master_name_map)
    main_to_full: dict[str, set[str]] = {}
    pair_to_full: dict[tuple[str, str], str] = {}
    for area in cleaned_master:
        try:
            main, sub = split_area(area)
        except Exception:
            main, sub = area, ""
        main_key = normalize_area(main)
        sub_key = normalize_area(sub)
        full_key = normalize_area(area)
        if main_key:
            main_to_full.setdefault(main_key, set()).add(full_key)
        if main_key and sub_key:
            pair_to_full.setdefault((main_key, sub_key), full_key)

    def expand(entry: str) -> list[str]:
        try:
            main, sub = split_area(entry)
        except Exception:
            main, sub = entry, ""
        main_key = normalize_area(main)
        sub_key = normalize_area(sub)
        full_key = normalize_area(entry)
        if sub_key:
            match = pair_to_full.get((main_key, sub_key))
            if match:
                return [match]
            return [full_key] if full_key in master_set else []
        if main_key in main_to_full:
            return sorted(main_to_full[main_key])
        return [full_key] if full_key in master_set else []

    assigned: set[str] = set()
    area_collectors: dict[str, set[str]] = {}
    collector_coverage: dict[str, set[str]] = {}
    unknown: set[str] = set()
    for collector, record in collector_records.items():
        coverage: set[str] = set()
        for route_area in unique_areas((record or {}).get("areas") or []):
            expanded = expand(route_area)
            if not expanded:
                unknown.add(route_area)
                continue
            for full_key in expanded:
                assigned.add(full_key)
                coverage.add(full_key)
                area_collectors.setdefault(full_key, set()).add(str(collector))
        collector_coverage[str(collector)] = coverage

    conflicts = {
        key: sorted(names, key=str.lower)
        for key, names in area_collectors.items()
        if len(names) > 1
    }
    return {
        "master_areas": cleaned_master,
        "master_name_map": master_name_map,
        "collector_coverage": collector_coverage,
        "unassigned_areas": [area for area in cleaned_master if normalize_area(area) not in assigned],
        "unknown_route_areas": sorted(unknown, key=str.lower),
        "conflicts": conflicts,
    }


def summarize_collector(
    collector: str,
    record: Mapping[str, Any],
    coverage: Mapping[str, set[str]],
    counts: Mapping[str, Mapping[str, int]],
    conflicts: Mapping[str, Iterable[str]],
    unknown_route_areas: Iterable[str],
) -> dict[str, Any]:
    areas = unique_areas((record or {}).get("areas") or [])
    covered = set(coverage.get(collector) or set())
    regular = sum(int((counts.get(area) or {}).get("regular", 0) or 0) for area in covered)
    x7 = sum(int((counts.get(area) or {}).get("7x7", 0) or 0) for area in covered)
    conflict_keys = set(conflicts)
    unknown_keys = {normalize_area(value) for value in unknown_route_areas}
    return {
        "collector": collector,
        "areas": areas,
        "notes": str((record or {}).get("notes") or ""),
        "areas_count": len(areas),
        "regular": regular,
        "7x7": x7,
        "clients": regular + x7,
        "has_conflict": bool(covered & conflict_keys),
        "has_unknown": any(normalize_area(area) in unknown_keys for area in areas),
    }


def regular_first_route_rows(
    regular_rows: Iterable[Mapping[str, Any]],
    x7_rows: Iterable[Mapping[str, Any]],
    *,
    name_key: str = "name",
) -> list[Mapping[str, Any]]:
    """Keep Regular rows first and append only 7x7-only clients."""
    regular = list(regular_rows or [])
    seen = {normalize_area((row or {}).get(name_key)) for row in regular}
    result = list(regular)
    for row in x7_rows or []:
        key = normalize_area((row or {}).get(name_key))
        if key and key not in seen:
            seen.add(key)
            result.append(row)
    return result
