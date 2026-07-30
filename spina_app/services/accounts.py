"""Pure account metadata rules consolidated in Wave 83."""
from __future__ import annotations

from collections.abc import Mapping

VALID_ACCESS_PROFILES = ("Admin", "Encoder", "Viewer", "System")

_DEFAULT_ACCOUNT_NAMES = {
    "admin": "Owner Account",
    "encoder": "Encoding Account",
    "viewer": "Reports Account",
    "system": "Control Account",
    "collector": "Collector Account",
}


def normalize_access_profile(value, default: str = "Viewer") -> str:
    """Return a supported internal access profile."""
    text = str(value or "").strip()
    if text in VALID_ACCESS_PROFILES:
        return text
    fallback = str(default or "Viewer").strip()
    return fallback if fallback in VALID_ACCESS_PROFILES else "Viewer"


def default_account_name(username) -> str:
    """Return the stable display label used for legacy default accounts."""
    text = str(username or "").strip()
    return _DEFAULT_ACCOUNT_NAMES.get(text.lower(), text or "Account")


def account_choices(users) -> tuple[list[str], dict[str, str]]:
    """Build unique display labels while preserving username identity."""
    records: Mapping = users if isinstance(users, Mapping) else {}
    usernames = sorted(
        [name for name in records if isinstance(name, str) and name.strip()],
        key=str.lower,
    )
    if not usernames:
        usernames = ["admin"]

    choices: list[str] = []
    label_to_user: dict[str, str] = {}
    used: set[str] = set()
    for username in usernames:
        raw = records.get(username)
        record = raw if isinstance(raw, Mapping) else {}
        label = str(
            record.get("display_name")
            or record.get("account_name")
            or record.get("label")
            or ""
        ).strip()
        if not label:
            label = default_account_name(username)

        base = label
        suffix = 2
        while label.casefold() in used:
            label = f"{base} {suffix}"
            suffix += 1
        used.add(label.casefold())
        choices.append(label)
        label_to_user[label] = username
    return choices, label_to_user


def selected_label_for_user(
    username,
    choices,
    label_to_user,
) -> str:
    """Return the display label corresponding to a username."""
    target = str(username or "").strip()
    for label in list(choices or []):
        if str((label_to_user or {}).get(label) or "").strip() == target:
            return label
    return str((list(choices or []) or [""])[0])
