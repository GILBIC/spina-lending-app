from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

_DATABASE_ENV_NAMES = (
    "GILBIC_DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_URL_NON_POOLING",
    "DATABASE_URL",
)


def _source_name() -> str:
    for name in _DATABASE_ENV_NAMES:
        if os.getenv(name, "").strip():
            return name
    return "none"


def _reason(error: BaseException) -> str:
    text = str(error).lower()
    if "password authentication failed" in text or "authentication failed" in text:
        return "authentication"
    if "could not translate host name" in text or "name or service not known" in text:
        return "dns"
    if "network is unreachable" in text or "no route to host" in text:
        return "network"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection refused" in text:
        return "refused"
    if "ssl" in text or "certificate" in text:
        return "tls"
    if "invalid connection option" in text or isinstance(error, ValueError):
        return "configuration"
    return "database"


def main() -> int:
    source = _source_name()
    if source == "none":
        print("SPINA_DATABASE_PREFLIGHT status=missing source=none")
        return 0

    try:
        from gilbic_backend.database import open_connection

        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                ready = cursor.fetchone() == (1,)
    except BaseException as error:  # Build diagnostic must never expose credentials.
        print(
            "SPINA_DATABASE_PREFLIGHT "
            f"status=unavailable source={source} reason={_reason(error)}"
        )
        return 0

    print(
        "SPINA_DATABASE_PREFLIGHT "
        f"status={'ok' if ready else 'unexpected'} source={source}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
