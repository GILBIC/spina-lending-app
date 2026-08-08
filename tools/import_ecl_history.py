from __future__ import annotations

import argparse
import os
from dataclasses import asdict
from pathlib import Path

import psycopg

from gilbic_backend.ecl_history_sqlite import reconstruct_sqlite_history


UPSERT_EPISODE_SQL = """
INSERT INTO accounting.ecl_historical_loan_episodes (
    import_batch_id,
    episode_key,
    borrower_key,
    episode_sequence,
    loan_type,
    source_event,
    release_date,
    due_date,
    principal,
    contractual_total,
    interest_rate,
    outcome_evidence,
    outcome_date,
    renewal_rollover_amount,
    cash_collected,
    positive_payment_count,
    zero_payment_observation_count,
    observed_collection_days,
    source_quality_status,
    source_quality_note
) VALUES (
    %(import_batch_id)s,
    %(episode_key)s,
    %(borrower_key)s,
    %(episode_sequence)s,
    %(loan_type)s,
    %(source_event)s,
    %(release_date)s,
    %(due_date)s,
    %(principal)s,
    %(contractual_total)s,
    %(interest_rate)s,
    %(outcome_evidence)s,
    %(outcome_date)s,
    %(renewal_rollover_amount)s,
    %(cash_collected)s,
    %(positive_payment_count)s,
    %(zero_payment_observation_count)s,
    %(observed_collection_days)s,
    %(source_quality_status)s,
    %(source_quality_note)s
)
ON CONFLICT (import_batch_id, episode_key) DO UPDATE SET
    borrower_key = EXCLUDED.borrower_key,
    episode_sequence = EXCLUDED.episode_sequence,
    loan_type = EXCLUDED.loan_type,
    source_event = EXCLUDED.source_event,
    release_date = EXCLUDED.release_date,
    due_date = EXCLUDED.due_date,
    principal = EXCLUDED.principal,
    contractual_total = EXCLUDED.contractual_total,
    interest_rate = EXCLUDED.interest_rate,
    outcome_evidence = EXCLUDED.outcome_evidence,
    outcome_date = EXCLUDED.outcome_date,
    renewal_rollover_amount = EXCLUDED.renewal_rollover_amount,
    cash_collected = EXCLUDED.cash_collected,
    positive_payment_count = EXCLUDED.positive_payment_count,
    zero_payment_observation_count = EXCLUDED.zero_payment_observation_count,
    observed_collection_days = EXCLUDED.observed_collection_days,
    source_quality_status = EXCLUDED.source_quality_status,
    source_quality_note = EXCLUDED.source_quality_note
"""


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


def _resolve_source(
    direct: Path | None,
    *,
    filename: str | None,
    roots: list[Path],
) -> Path:
    if direct is not None:
        if direct.is_file():
            return direct
        raise SystemExit(f"SQLite source file was not found: {direct}")
    if not filename:
        raise SystemExit("Provide sqlite_file or --find-source-name")

    for root in roots:
        if not root.exists():
            continue
        direct_candidate = root / filename
        if direct_candidate.is_file():
            return direct_candidate
        try:
            for candidate in root.rglob(filename):
                if candidate.is_file():
                    return candidate
        except (OSError, PermissionError):
            continue
    raise SystemExit(
        f"Stage 5E.2 source file {filename!r} was not found under the configured search roots."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import reconstructed legacy SPINA loan episodes into the accounting-only Stage 5E.2 history tables."
    )
    parser.add_argument("sqlite_file", type=Path, nargs="?")
    parser.add_argument("--find-source-name")
    parser.add_argument("--search-root", action="append", type=Path, default=[])
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument(
        "--database-url-env",
        default="GILBIC_DATABASE_URL",
        help="Environment variable containing the PostgreSQL connection URL.",
    )
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-episodes", type=int)
    args = parser.parse_args()

    for env_path in args.env_file:
        _load_env_file(env_path)

    database_url = os.getenv(args.database_url_env)
    if not database_url and args.database_url_env != "GILBIC_TEST_DATABASE_URL":
        database_url = os.getenv("GILBIC_TEST_DATABASE_URL")
    if not database_url:
        raise SystemExit(
            f"Neither {args.database_url_env} nor GILBIC_TEST_DATABASE_URL is configured"
        )

    source = _resolve_source(
        args.sqlite_file,
        filename=args.find_source_name,
        roots=args.search_root,
    )
    result = reconstruct_sqlite_history(source)
    if args.expected_sha256 and result.source_sha256 != args.expected_sha256:
        raise SystemExit(
            f"Source SHA-256 mismatch: expected {args.expected_sha256}, got {result.source_sha256}"
        )
    if args.expected_episodes is not None and len(result.episodes) != args.expected_episodes:
        raise SystemExit(
            f"Episode count mismatch: expected {args.expected_episodes}, got {len(result.episodes)}"
        )

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            installed = cursor.execute(
                "SELECT to_regclass('accounting.ecl_historical_loan_episodes')"
            ).fetchone()[0]
            if installed is None:
                raise SystemExit("Stage 5E.2 historical dataset schema is not installed")

            batch_id = cursor.execute(
                """
                INSERT INTO accounting.ecl_history_import_batches (
                    source_filename,
                    source_sha256,
                    source_size_bytes,
                    sqlite_integrity_check,
                    source_snapshot_date,
                    source_client_count,
                    source_renewal_count,
                    source_transaction_count,
                    reconstructed_episode_count,
                    import_note
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_sha256) DO UPDATE SET
                    source_filename = EXCLUDED.source_filename,
                    source_size_bytes = EXCLUDED.source_size_bytes,
                    sqlite_integrity_check = EXCLUDED.sqlite_integrity_check,
                    source_snapshot_date = EXCLUDED.source_snapshot_date,
                    source_client_count = EXCLUDED.source_client_count,
                    source_renewal_count = EXCLUDED.source_renewal_count,
                    source_transaction_count = EXCLUDED.source_transaction_count,
                    reconstructed_episode_count = EXCLUDED.reconstructed_episode_count,
                    import_note = EXCLUDED.import_note
                RETURNING id
                """,
                (
                    result.source_filename,
                    result.source_sha256,
                    result.source_size_bytes,
                    result.sqlite_integrity_check,
                    result.source_snapshot_date,
                    result.source_client_count,
                    result.source_renewal_count,
                    result.source_transaction_count,
                    len(result.episodes),
                    "Stage 5E.2 reconstruction from legacy SPINA SQLite. Borrower identities are SHA-256 keys; no names/contact data imported.",
                ),
            ).fetchone()[0]

            rows = []
            for episode in result.episodes:
                row = asdict(episode)
                row["import_batch_id"] = batch_id
                rows.append(row)
            cursor.executemany(UPSERT_EPISODE_SQL, rows)

            imported_count = cursor.execute(
                """
                SELECT count(*)
                FROM accounting.ecl_historical_loan_episodes
                WHERE import_batch_id = %s
                """,
                (batch_id,),
            ).fetchone()[0]
            if imported_count != len(result.episodes):
                raise RuntimeError(
                    f"Historical import verification failed: expected {len(result.episodes)} rows, found {imported_count}"
                )

            summary = cursor.execute(
                """
                SELECT
                    import_batch_count,
                    episode_count,
                    usable_episode_count,
                    source_review_required_count,
                    renewed_episode_count,
                    archived_episode_count,
                    deleted_episode_count,
                    open_episode_count,
                    explicitly_labeled_outcome_count,
                    historical_dataset_status
                FROM accounting.ecl_historical_dataset_summary
                """
            ).fetchone()

        connection.commit()

    print(
        "Stage 5E.2 import complete: "
        f"batch={batch_id}, source={result.source_filename}, sha256={result.source_sha256}, "
        f"episodes={imported_count}."
    )
    print(
        "Dataset summary: "
        f"batches={summary[0]}, episodes={summary[1]}, usable={summary[2]}, "
        f"review_required={summary[3]}, renewed={summary[4]}, archived={summary[5]}, "
        f"deleted={summary[6]}, open={summary[7]}, explicit_labels={summary[8]}, "
        f"status={summary[9]}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
