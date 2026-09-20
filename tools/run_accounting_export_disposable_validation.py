"""Opt-in current-schema export proof in one owned loopback disposable database."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import run_release_recovery_drill as recovery
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]


def run(
    dsn: str,
    *,
    allow_disposable: bool,
    sample_output: Path | None,
    proof_output: Path | None,
) -> int:
    if not allow_disposable:
        raise recovery.DrillError("Explicit --allow-disposable is required.")
    params = recovery.safe_admin_params(dsn)
    for path in (sample_output, proof_output):
        if path is not None and (
            not path.is_absolute() or path.exists() or not path.parent.is_dir()
        ):
            raise recovery.DrillError(
                "Output must be a new absolute file in an existing directory."
            )
    name = "spina_export_test_" + uuid4().hex
    created = False
    with recovery.isolated_pg_environment():
        try:
            with psycopg.connect(make_conninfo(**params), autocommit=True) as admin:
                admin.execute(
                    sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                        sql.Identifier(name)
                    )
                )
                created = True
            target = make_conninfo(**{**params, "dbname": name})
            recovery.bootstrap(target)
            env = dict(os.environ)
            env["GILBIC_ACCOUNTING_EXPORT_TEST_DSN"] = target
            env.pop("GILBIC_ACCOUNTING_EXPORT_SAMPLE_OUTPUT", None)
            env.pop("GILBIC_ACCOUNTING_EXPORT_PROOF_OUTPUT", None)
            if sample_output is not None:
                env["GILBIC_ACCOUNTING_EXPORT_SAMPLE_OUTPUT"] = str(sample_output)
            if proof_output is not None:
                env["GILBIC_ACCOUNTING_EXPORT_PROOF_OUTPUT"] = str(proof_output)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    str(
                        ROOT / "gilbic_backend/tests/test_accounting_export_postgres.py"
                    ),
                    "-q",
                    "--tb=short",
                ],
                cwd=ROOT,
                env=env,
                check=False,
                timeout=180,
            )
            return completed.returncode
        finally:
            if created and re.fullmatch(r"spina_export_test_[0-9a-f]{32}", name):
                with psycopg.connect(make_conninfo(**params), autocommit=True) as admin:
                    recovery.disposable._drop_database(admin, name)
                    if recovery.disposable._database_exists(admin, name):
                        raise recovery.DrillError(
                            "Owned export test database cleanup failed."
                        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-dsn-file", type=Path, required=True)
    parser.add_argument("--allow-disposable", action="store_true")
    parser.add_argument("--sample-output", type=Path)
    parser.add_argument("--proof-output", type=Path)
    args = parser.parse_args()
    try:
        result = run(
            args.admin_dsn_file.read_text(encoding="utf-8").strip(),
            allow_disposable=args.allow_disposable,
            sample_output=args.sample_output,
            proof_output=args.proof_output,
        )
    except (OSError, psycopg.Error, recovery.DrillError, subprocess.SubprocessError):
        print(
            "Disposable accounting export validation failed; no production database was selected.",
            file=sys.stderr,
        )
        return 1
    print("Disposable accounting export validation finished; owned database removed.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
