"""Read-only database access for the Reports feature."""
from __future__ import annotations

from typing import Any


def fetch_report_clients(
    app: Any,
    *,
    search: str = "",
    loan_type: str | None = None,
    include_archived: bool = False,
) -> list[str]:
    """Return client names visible in the Reports list."""
    try:
        rows = app.db.get_all_clients(
            search=search or None,
            loan_type=loan_type,
            search_by="all",
            include_archived=bool(include_archived),
        )
        return list(rows or [])
    except Exception:
        return []


def fetch_client_info(app: Any, name: str, loan_type: str | None = None) -> dict:
    try:
        return dict(app.db.get_client_info(name, loan_type=loan_type) or {})
    except Exception:
        return {}


def fetch_client_link_meta(app: Any, name: str, loan_type: str | None = None) -> dict:
    try:
        return dict(app.db.get_client_link_meta(name, loan_type=loan_type) or {})
    except Exception:
        return {}


def fetch_client_type_presence(app: Any, name: str) -> tuple[bool, bool]:
    """Return ``(has_regular, has_7x7)`` for one client name."""
    return (
        bool(fetch_client_info(app, name, "Regular")),
        bool(fetch_client_info(app, name, "7x7")),
    )
