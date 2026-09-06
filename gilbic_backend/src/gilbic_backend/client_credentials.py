from __future__ import annotations

import re
import secrets


_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_LOWER = "abcdefghijkmnopqrstuvwxyz"
_DIGITS = "23456789"
_SYMBOLS = "@#$%"
_ALL = _UPPER + _LOWER + _DIGITS + _SYMBOLS


def client_username_base(client_code: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".", client_code.strip().lower()).strip(".")
    return f"spina.{normalized or 'client'}"


def generate_password(length: int = 16) -> str:
    if length < 4:
        raise ValueError("Generated passwords must contain at least 4 characters.")

    characters = [
        secrets.choice(_UPPER),
        secrets.choice(_LOWER),
        secrets.choice(_DIGITS),
        secrets.choice(_SYMBOLS),
    ]
    characters.extend(secrets.choice(_ALL) for _ in range(length - len(characters)))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)
