from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection

from .config import Settings, get_settings


def connect_database(settings: Settings | None = None) -> Connection[Any]:
    """Create one configured PostgreSQL connection.

    Callers own the returned connection and must close it. This function exists
    for components such as the idempotent collection executor that need a real
    connection factory instead of a context manager.
    """

    active_settings = settings or get_settings()
    return psycopg.connect(
        active_settings.database_url,
        connect_timeout=5,
        application_name="gilbic-backend",
    )


@contextmanager
def open_connection(settings: Settings | None = None) -> Iterator[Connection[Any]]:
    """Open one short-lived transactional PostgreSQL connection.

    Successful operations are committed when the context exits. Exceptions are
    rolled back by psycopg before the connection is closed. Production
    credentials come only from ``GILBIC_DATABASE_URL``. Callers should keep
    transactions small and use an explicit connection-pool layer when request
    volume grows.
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
    except psycopg.Error:
        return False
