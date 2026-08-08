from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "gilbic_backend"
    / "sql"
    / "0033_add_accounting_ecl_outcome_review.sql"
)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _dataset_counts(connection: psycopg.Connection) -> tuple[int, int, int]:
    row = connection.execute(
        """
        SELECT
            count(*)::bigint AS episode_count,
            count(*) FILTER (
                WHERE source_quality_status = 'ready_for_outcome_labeling'
            )::bigint AS usable_count,
            count(*) FILTER (
                WHERE explicit_default_label IS NOT NULL
            )::bigint AS reviewed_count
        FROM accounting.ecl_historical_loan_episodes
        """
    ).fetchone()
    return int(row[0]), int(row[1]), int(row[2])


def _verify_stage5e3(
    connection: psycopg.Connection,
    *,
    expected_episodes: int,
    expected_usable: int,
) -> None:
    objects = connection.execute(
        """
        SELECT
            to_regclass('accounting.ecl_outcome_label_reviews'),
            to_regclass('accounting.ecl_outcome_label_review_queue'),
            to_regclass('accounting.ecl_outcome_label_review_summary')
        """
    ).fetchone()
    if any(item is None for item in objects):
        raise SystemExit(
            "Stage 5E.3 verification failed: required review objects are missing"
        )

    summary = connection.execute(
        """
        SELECT
            episode_count,
            structurally_usable_count,
            source_review_required_count,
            pending_outcome_review_count,
            reviewed_outcome_count,
            reviewed_default_count,
            reviewed_non_default_count,
            review_status,
            ecl_included,
            ecl_amount,
            ready_to_post
        FROM accounting.ecl_outcome_label_review_summary
        """
    ).fetchone()

    if int(summary[0]) != expected_episodes:
        raise SystemExit(
            f"Stage 5E.3 verification failed: expected {expected_episodes} episodes, found {summary[0]}"
        )
    if int(summary[1]) != expected_usable:
        raise SystemExit(
            f"Stage 5E.3 verification failed: expected {expected_usable} usable episodes, found {summary[1]}"
        )
    if bool(summary[8]) or summary[9] is not None or bool(summary[10]):
        raise SystemExit(
            "Stage 5E.3 verification failed: ECL or posting was unexpectedly enabled"
        )

    print(
        "Stage 5E.3 review summary: "
        f"episodes={summary[0]}, usable={summary[1]}, source_review={summary[2]}, "
        f"pending={summary[3]}, reviewed={summary[4]}, defaults={summary[5]}, "
        f"non_defaults={summary[6]}, status={summary[7]}, "
        f"ecl_included={summary[8]}, ecl_amount={summary[9]}, ready_to_post={summary[10]}."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the guarded Stage 5E.3 historical ECL outcome-review "
            "migration to the live SPINA database."
        )
    )
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument("--database-url-env", default="GILBIC_DATABASE_URL")
    parser.add_argument("--expected-episodes", type=int, default=992)
    parser.add_argument("--expected-usable", type=int, default=919)
    args = parser.parse_args()

    for env_path in args.env_file:
        _load_env_file(env_path)

    database_url = os.getenv(args.database_url_env)
    if not database_url:
        raise SystemExit(f"{args.database_url_env} is not configured")

    if not MIGRATION.is_file():
        raise SystemExit(f"Stage 5E.3 migration file was not found: {MIGRATION}")

    with psycopg.connect(database_url, autocommit=True) as connection:
        stage5e2 = connection.execute(
            "SELECT to_regclass('accounting.ecl_historical_loan_episodes')"
        ).fetchone()[0]
        if stage5e2 is None:
            raise SystemExit("Stage 5E.2 historical dataset schema is not installed")

        episode_count, usable_count, reviewed_count = _dataset_counts(connection)
        if episode_count != args.expected_episodes:
            raise SystemExit(
                f"Live dataset gate failed: expected {args.expected_episodes} episodes, found {episode_count}"
            )
        if usable_count != args.expected_usable:
            raise SystemExit(
                f"Live dataset gate failed: expected {args.expected_usable} usable episodes, found {usable_count}"
            )

        already_installed = connection.execute(
            "SELECT to_regclass('accounting.ecl_outcome_label_reviews')"
        ).fetchone()[0]
        if already_installed is not None:
            print(
                "Stage 5E.3 is already installed; skipping migration application. "
                f"Current explicit labels={reviewed_count}."
            )
            _verify_stage5e3(
                connection,
                expected_episodes=args.expected_episodes,
                expected_usable=args.expected_usable,
            )
            return 0

        if reviewed_count != 0:
            raise SystemExit(
                "Live dataset gate failed: explicit historical labels already exist "
                "before Stage 5E.3 review controls are installed"
            )

        migration_sql = MIGRATION.read_text(encoding="utf-8")
        try:
            # No query parameters are passed. Psycopg therefore supports the
            # migration's multi-statement BEGIN ... COMMIT script directly.
            connection.execute(migration_sql)
        except psycopg.Error as error:
            raise SystemExit(f"Stage 5E.3 migration failed: {error}") from error

        _verify_stage5e3(
            connection,
            expected_episodes=args.expected_episodes,
            expected_usable=args.expected_usable,
        )

    print(
        "Stage 5E.3 live migration complete. Historical outcome review is ready; "
        "ECL and posting remain disabled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
