from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg
from psycopg import Connection

from .config import Settings, get_settings


_LOGGER = logging.getLogger(__name__)
_DATABASE_URL_ENV_NAMES = (
    "GILBIC_DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_URL_NON_POOLING",
    "DATABASE_URL",
)


def normalize_database_url_for_psycopg(database_url: str) -> str:
    """Remove provider-only query options that libpq/psycopg cannot parse.

    Supabase's Vercel integration may append
    ``workaround=supabase-pooler.vercel`` to ``POSTGRES_URL``. That flag is
    intended for Vercel's JavaScript Postgres client and is not a valid libpq
    connection option. All standard PostgreSQL parameters are preserved.
    """

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


def _database_url_source() -> str:
    for name in _DATABASE_URL_ENV_NAMES:
        if os.getenv(name, "").strip():
            return name
    return "default"


def _database_failure_reason(error: BaseException) -> str:
    text = str(error).lower()
    if isinstance(error, ValueError) or "invalid connection option" in text:
        return "configuration"
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
    return "database"


def connect_database(settings: Settings | None = None) -> Connection[Any]:
    """Create one configured PostgreSQL connection.

    Callers own the returned connection and must close it. This function exists
    for components such as the idempotent collection executor that need a real
    connection factory instead of a context manager.
    """

    active_settings = settings or get_settings()
    database_url = normalize_database_url_for_psycopg(active_settings.database_url)
    return psycopg.connect(
        database_url,
        connect_timeout=5,
        application_name="gilbic-backend",
    )


@contextmanager
def open_connection(settings: Settings | None = None) -> Iterator[Connection[Any]]:
    """Open one short-lived transactional PostgreSQL connection.

    Successful operations are committed when the context exits. Exceptions are
    rolled back by psycopg before the connection is closed. Production
    credentials come only from recognized server-side environment variables.
    Callers should keep transactions small and use an explicit connection-pool
    layer when request volume grows.
    """

    connection = connect_database(settings)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def database_ready(settings: Settings | None = None) -> bool:
    try:
        with open_connection(settings) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                return cursor.fetchone() == (1,)
    except (psycopg.Error, ValueError) as error:
        _LOGGER.warning(
            "Database readiness unavailable: source=%s reason=%s error=%s sqlstate=%s",
            _database_url_source(),
            _database_failure_reason(error),
            type(error).__name__,
            getattr(error, "sqlstate", None) or "none",
        )
        return False
