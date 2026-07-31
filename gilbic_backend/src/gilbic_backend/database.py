from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection

from .config import Settings, get_settings


@contextmanager
def open_connection(settings: Settings | None = None) -> Iterator[Connection[Any]]:
    """Open a short-lived PostgreSQL connection for backend operations.

    Production credentials come only from ``GILBIC_DATABASE_URL``. Callers
    should keep transactions small and use an explicit connection-pool layer
    when request volume grows.
    """

    active_settings = settings or get_settings()
    connection = psycopg.connect(
        active_settings.database_url,
        connect_timeout=5,
        application_name="gilbic-backend",
    )
    try:
        yield connection
    finally:
        connection.close()


def database_ready(settings: Settings | None = None) -> bool:
    try:
        with open_connection(settings) as connection:
            with connection.cursor() as cursor:
                cursor.execute("select 1")
                return cursor.fetchone() == (1,)
    except psycopg.Error:
        return False
