"""Pure Client Info Logs transformation rules for SPINA Wave 78."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from spina_app.utilities.diffs import _spina_cilog_diff_pairs
from spina_app.utilities.formatting import _spina_cilog_fmt_value
from spina_app.utilities.serialization import _spina_cilog_safe_json
from spina_app.utilities.text import _spina_cilog_action_label


FIELD_LABELS = {
    "name": "Client Name",
    "loan_type": "Loan Type",
    "area": "Area",
    "principal": "Principal",
    "interest_rate": "Interest Rate",
    "interest_amount": "Interest Amount",
    "total_to_pay": "Total To Pay",
    "date_released": "Released Date",
    "due_date": "Due Date",
    "contact_number": "Contact Number",
    "payment_term": "Payment Term",
    "payment_amount": "Payment Amount",
    "payment_mode": "Payment Mode",
    "pay_start_offset_days": "Payment Start Rule",
    "due_weekday": "Weekly Due Day",
    "semi_due_day1": "Semi Due Day 1",
    "semi_due_day2": "Semi Due Day 2",
    "monthly_due_day": "Monthly Due Day",
    "new_until": "New Highlight Until",
    "person_uid": "Link Group",
    "link_opt_out": "Link Opt-Out",
    "archived": "Archived",
    "picture_path": "Client Picture",
    "last_cash_released": "Last Cash Released",
    "renew_count": "Renew Count",
    "last_renew_date": "Last Renew Date",
}


def client_info_field_label(field: Any) -> str:
    key = str(field or "").strip()
    return FIELD_LABELS.get(key, key.replace("_", " ").title())


def transform_client_history_records(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Expand history records into one presentation row per changed field."""
    rows_out: list[dict[str, Any]] = []
    for record in records or []:
        row = dict(record or {})
        old_obj = _spina_cilog_safe_json(
            row.get("old_json") or row.get("before_json")
        )
        new_obj = _spina_cilog_safe_json(
            row.get("new_json") or row.get("after_json")
        )
        pairs = _spina_cilog_diff_pairs(old_obj, new_obj)
        if not pairs:
            pairs = [("Record", "", "")]

        action = _spina_cilog_action_label(row.get("action"), row.get("source"))
        client_name = row.get("name_after") or row.get("name_before") or ""
        loan_type = (
            row.get("loan_type_after") or row.get("loan_type_before") or ""
        )
        for field, before, after in pairs:
            rows_out.append(
                {
                    "id": row.get("id"),
                    "when": row.get("changed_at") or row.get("ts") or "",
                    "client": client_name,
                    "loan_type": loan_type,
                    "action": action,
                    "field": client_info_field_label(field),
                    "field_key": str(field or ""),
                    "before": _spina_cilog_fmt_value(field, before),
                    "after": _spina_cilog_fmt_value(field, after),
                    "source": row.get("source") or "",
                    "note": row.get("note") or "",
                }
            )
    return rows_out
