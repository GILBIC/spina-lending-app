"""Pure row and summary transformations for the Reports feature."""
from __future__ import annotations

from typing import Any, Callable


def display_loan_type(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if "7x7" in lowered or "emer" in lowered:
        return "7x7 (Emer)"
    if lowered in {"regular", "reg"}:
        return "Regular"
    return text or "Regular"


def linked_label(active_filter: Any, has_regular: bool, has_7x7: bool) -> str:
    current = str(active_filter or "").strip().lower()
    if current == "regular":
        return "7x7" if has_7x7 else ""
    if current == "7x7":
        return "Regular" if has_regular else ""
    labels = []
    if has_regular:
        labels.append("Regular")
    if has_7x7:
        labels.append("7x7 (Emer)")
    return " + ".join(labels)


def build_report_row(
    name: str,
    info: dict,
    *,
    active_filter: Any,
    has_regular: bool,
    has_7x7: bool,
    due_label: str,
    format_money: Callable[[Any], str],
) -> tuple:
    return (
        name,
        info.get("contact_number", ""),
        display_loan_type(info.get("loan_type") or active_filter),
        info.get("payment_term", "") or "Daily",
        due_label or "",
        format_money(info.get("payment_amount", 0)),
        info.get("payment_mode", "Cash") or "Cash",
        linked_label(active_filter, has_regular, has_7x7),
        info.get("area", ""),
        format_money(info.get("principal", 0)),
        format_money(info.get("total_to_pay", 0)),
        info.get("date_released", ""),
        info.get("due_date", ""),
    )


def build_report_summary(
    count: int,
    *,
    active_filter: Any,
    start_date: str = "",
    end_date: str = "",
) -> str:
    mode = str(active_filter or "All").strip() or "All"
    start = str(start_date or "").strip()
    end = str(end_date or "").strip()
    if start and end:
        range_label = f"Generate: {start} to {end}"
    elif start:
        range_label = f"Generate from: {start}"
    elif end:
        range_label = f"Generate until: {end}"
    else:
        range_label = "Generate: default range"
    noun = "client" if int(count) == 1 else "clients"
    return f"{int(count)} {noun}  •  View: {mode}  •  {range_label}"
