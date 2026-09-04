from __future__ import annotations

import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "gilbic_backend" / "sql"
PREREQUISITES = (
    "0001_core_lending_foundation.sql",
    "0003_add_management_administration.sql",
    "0004_add_collector_routes.sql",
    "0005_add_idempotent_collections.sql",
)


def main() -> int:
    database_url = os.getenv("GILBIC_TEST_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("GILBIC_TEST_DATABASE_URL is required.")

    with psycopg.connect(database_url, autocommit=True) as connection:
        for filename in PREREQUISITES:
            connection.execute((SQL_DIR / filename).read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
