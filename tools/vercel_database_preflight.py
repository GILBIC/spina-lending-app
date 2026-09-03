from __future__ import annotations

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg


_DATABASE_ENV_NAMES = (
    "GILBIC_DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_URL_NON_POOLING",
    "DATABASE_URL",
)


def _database_url() -> tuple[str, str]:
    for name in _DATABASE_ENV_NAMES:
        value = os.getenv(name, "").strip()
        if value:
            return name, value
    return "none", ""


def _normalize(database_url: str) -> str:
    parsed = urlsplit(database_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not (key == "workaround" and value == "supabase-pooler.vercel")
    ]
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


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
    source, database_url = _database_url()
    if not database_url:
        print("SPINA_DATABASE_PREFLIGHT status=missing source=none")
        return 0

    try:
        with psycopg.connect(
            _normalize(database_url),
            connect_timeout=5,
            application_name="spina-vercel-preflight",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                ready = cursor.fetchone() == (1,)
    except (psycopg.Error, ValueError) as error:
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
