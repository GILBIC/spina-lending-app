#!/usr/bin/env python3
"""Local startup diagnostics for SPINA PostgreSQL setup.

Run this before launching the desktop app when startup fails or PostgreSQL is
suspected. It does not import the SPINA Tkinter application.
"""

from __future__ import annotations

import os
import socket
import sys
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def check_python() -> CheckResult:
    return CheckResult(
        "Python version",
        sys.version_info >= (3, 10),
        sys.version.replace("\n", " "),
    )


def check_password() -> CheckResult:
    value = _env("SPINA_PG_PASSWORD")
    if value:
        return CheckResult("SPINA_PG_PASSWORD", True, "set in this environment")
    return CheckResult(
        "SPINA_PG_PASSWORD",
        False,
        "missing; run: setx SPINA_PG_PASSWORD \"your_password\" then reopen Command Prompt",
    )


def check_psycopg() -> CheckResult:
    try:
        import psycopg  # noqa: F401
        return CheckResult("psycopg", True, "installed")
    except Exception as exc:  # pragma: no cover - local environment diagnostic
        return CheckResult("psycopg", False, f"not available: {exc}")


def check_tcp(host: str, port: int) -> CheckResult:
    try:
        with socket.create_connection((host, port), timeout=3):
            return CheckResult("PostgreSQL TCP", True, f"{host}:{port} is reachable")
    except Exception as exc:
        return CheckResult("PostgreSQL TCP", False, f"cannot reach {host}:{port}: {exc}")


def check_login(host: str, port: int, dbname: str, user: str, password: str) -> CheckResult:
    try:
        import psycopg
        with psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5,
            application_name="SPINA diagnostics",
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                row = cur.fetchone()
        return CheckResult("PostgreSQL login", True, f"connected to {row[0]} as {row[1]}")
    except Exception as exc:
        return CheckResult("PostgreSQL login", False, str(exc))


def main() -> int:
    host = _env("SPINA_PG_HOST", "localhost")
    port = int(_env("SPINA_PG_PORT", "5432"))
    dbname = _env("SPINA_PG_DB", "spina_db")
    user = _env("SPINA_PG_USER", "spina_user")
    password = _env("SPINA_PG_PASSWORD", "")

    checks = [
        check_python(),
        check_password(),
        check_psycopg(),
        check_tcp(host, port),
    ]
    if password:
        checks.append(check_login(host, port, dbname, user, password))

    print("SPINA startup diagnostics")
    print("=" * 28)
    print(f"Host: {host}:{port}")
    print(f"Database: {dbname}")
    print(f"User: {user}")
    print()

    failed = False
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")
        failed = failed or not check.ok

    if failed:
        print("\nOne or more checks failed. Fix the failed item before launching SPINA.")
        return 1
    print("\nAll startup checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
