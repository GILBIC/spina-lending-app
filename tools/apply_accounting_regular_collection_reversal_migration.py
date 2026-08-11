from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
REVERSAL_MIGRATION = SQL_ROOT / "0043_add_controlled_regular_collection_reversals.sql"


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


def _transaction_body(source: str) -> str:
    body = source.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            "Stage 5D.18 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute(
        "SELECT to_regclass(%s)",
        (relation,),
    ).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])


def _function_count(connection: psycopg.Connection, name: str) -> int:
    return int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid = proc.pronamespace
            WHERE ns.nspname = 'accounting'
              AND proc.proname = %s
            """,
            (name,),
        ).fetchone()[0]
    )


def _loan_status_counts(connection: psycopg.Connection) -> Counter[str]:
    rows = connection.execute(
        "SELECT status, count(*)::bigint FROM lending.loans GROUP BY status"
    ).fetchall()
    return Counter({str(status): int(count) for status, count in rows})


def _void_state_counts(connection: psycopg.Connection) -> tuple[int, int]:
    row = connection.execute(
        """
        SELECT
            count(*) FILTER (WHERE is_voided = false)::bigint,
            count(*) FILTER (WHERE is_voided = true)::bigint
        FROM lending.collection_transactions
        """
    ).fetchone()
    return int(row[0]), int(row[1])


def _protected_regular_counts(connection: psycopg.Connection) -> tuple[int, ...]:
    return (
        _count(connection, "accounting.regular_journal_draft_preparations"),
        _count(connection, "accounting.regular_journal_draft_preparation_entries"),
        _count(connection, "accounting.regular_journal_posting_sets"),
        _count(connection, "accounting.regular_journal_posting_entries"),
    )


def _opening_anchor_counts(connection: psycopg.Connection) -> tuple[int, ...]:
    relations = (
        "accounting.opening_balance_workbooks",
        "accounting.opening_balance_journal_preparations",
        "accounting.opening_balance_journal_postings",
        "accounting.opening_balance_loan_snapshot_batches",
        "accounting.opening_balance_loan_measurement_snapshots",
    )
    return tuple(_count(connection, relation) for relation in relations)


def _dpd_safety(connection: psycopg.Connection) -> tuple[object, ...] | None:
    if not _exists(connection, "accounting.loan_contract_dpd_summary"):
        return None
    row = connection.execute(
        """
        SELECT
            loan_count,
            automatic_default_label_written,
            ecl_included,
            ecl_amount,
            ready_to_post
        FROM accounting.loan_contract_dpd_summary
        """
    ).fetchone()
    return tuple(row) if row is not None else None


def _trigger_names(connection: psycopg.Connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT tgname
        FROM pg_trigger
        WHERE NOT tgisinternal
          AND tgname IN (
              'accounting_regular_journal_reversal_set_guard',
              'accounting_regular_journal_reversal_entry_guard',
              'accounting_protected_regular_reversal_insert_guard',
              'accounting_accounted_regular_collection_void_guard',
              'accounting_00_regular_collection_void_reversal'
          )
        """
    ).fetchall()
    return {str(row[0]) for row in rows}


def _function_definition(connection: psycopg.Connection, name: str) -> str:
    row = connection.execute(
        """
        SELECT pg_get_functiondef(proc.oid)
        FROM pg_proc proc
        JOIN pg_namespace ns ON ns.oid = proc.pronamespace
        WHERE ns.nspname = 'accounting'
          AND proc.proname = %s
        """,
        (name,),
    ).fetchone()
    return str(row[0]) if row is not None else ""


def _preexisting_uncontrolled_reversal_count(connection: psycopg.Connection) -> int:
    return int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.regular_journal_posting_entries posted
            JOIN accounting.journal_entries reversal
              ON reversal.reversal_of_entry_id = posted.journal_entry_id
            LEFT JOIN accounting.regular_journal_reversal_entries protected
              ON protected.reversal_journal_entry_id = reversal.id
            WHERE protected.reversal_journal_entry_id IS NULL
            """
        ).fetchone()[0]
    )


def _verify_installed(connection: psycopg.Connection) -> tuple[int, int]:
    required_relations = (
        "accounting.regular_journal_reversal_sets",
        "accounting.regular_journal_reversal_entries",
    )
    missing = [relation for relation in required_relations if not _exists(connection, relation)]
    if missing:
        raise SystemExit(
            "Stage 5D.18 live verification failed: missing " + ", ".join(missing)
        )

    for function_name in (
        "guard_regular_journal_reversal_record_write",
        "guard_protected_regular_reversal_insert",
        "reverse_posted_regular_collection",
        "guard_accounted_regular_collection_void",
        "perform_controlled_regular_collection_void_reversal",
    ):
        if _function_count(connection, function_name) != 1:
            raise SystemExit(
                "Stage 5D.18 live verification failed: protected function missing or ambiguous: "
                + function_name
            )

    required_triggers = {
        "accounting_regular_journal_reversal_set_guard",
        "accounting_regular_journal_reversal_entry_guard",
        "accounting_protected_regular_reversal_insert_guard",
        "accounting_accounted_regular_collection_void_guard",
        "accounting_00_regular_collection_void_reversal",
    }
    if _trigger_names(connection) != required_triggers:
        raise SystemExit(
            "Stage 5D.18 live verification failed: a protected reversal/void trigger is missing"
        )

    reverse_definition = _function_definition(
        connection,
        "reverse_posted_regular_collection",
    )
    for required_text in (
        "regular_journal_posting_entries",
        "reversal_of_entry_id",
        "regular_collection_void_reversal",
        "post_journal_entry",
        "Protected Regular collection reversal did not complete atomically",
    ):
        if required_text not in reverse_definition:
            raise SystemExit(
                "Stage 5D.18 live verification failed: protected reversal function lost a required safety boundary: "
                + required_text
            )

    void_definition = _function_definition(
        connection,
        "perform_controlled_regular_collection_void_reversal",
    )
    if (
        "AT TIME ZONE 'Asia/Manila'" not in void_definition
        or "reverse_posted_regular_collection" not in void_definition
    ):
        raise SystemExit(
            "Stage 5D.18 live verification failed: collection-void trigger is not using the protected Manila-dated reversal path"
        )

    uncontrolled_reversals = _preexisting_uncontrolled_reversal_count(connection)
    if uncontrolled_reversals != 0:
        raise SystemExit(
            "Stage 5D.18 live verification failed: a posted protected Regular journal already has an uncontrolled reversal"
        )

    reversal_sets = _count(connection, "accounting.regular_journal_reversal_sets")
    reversal_entries = _count(connection, "accounting.regular_journal_reversal_entries")
    invalid_reversal_count = int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.regular_journal_reversal_entries audit
            JOIN accounting.regular_journal_reversal_sets reversal_set
              ON reversal_set.id = audit.reversal_set_id
            JOIN accounting.journal_entries original
              ON original.id = audit.original_journal_entry_id
            JOIN accounting.journal_entries reversal
              ON reversal.id = audit.reversal_journal_entry_id
            WHERE original.status <> 'posted'
               OR reversal.status <> 'posted'
               OR reversal.reversal_of_entry_id IS DISTINCT FROM original.id
               OR reversal.entry_number IS DISTINCT FROM audit.reversal_entry_number
               OR reversal.source_event_key IS DISTINCT FROM audit.reversal_source_event_key
               OR reversal.source_type IS DISTINCT FROM 'regular_collection_void_reversal'
               OR reversal_set.expected_entry_count <> reversal_set.reversed_entry_count
            """
        ).fetchone()[0]
    )
    if invalid_reversal_count != 0:
        raise SystemExit(
            "Stage 5D.18 live verification failed: protected reversal audit disagrees with immutable journal history"
        )

    return reversal_sets, reversal_entries


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.18 controlled Regular collection reversal "
            "controls without creating, posting, voiding, or reversing any live transaction."
        )
    )
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument("--database-url-env", default="GILBIC_DATABASE_URL")
    args = parser.parse_args()

    for env_path in args.env_file:
        _load_env_file(env_path)

    database_url = os.getenv(args.database_url_env)
    if not database_url:
        raise SystemExit(f"{args.database_url_env} is not configured")
    if not REVERSAL_MIGRATION.is_file():
        raise SystemExit(
            "Stage 5D.18 migration file was not found: " + str(REVERSAL_MIGRATION)
        )
    migration_body = _transaction_body(REVERSAL_MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.collection_transactions",
                "lending.collection_transaction_voids",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "accounting.regular_journal_draft_preparations",
                "accounting.regular_journal_draft_preparation_entries",
                "accounting.regular_journal_posting_sets",
                "accounting.regular_journal_posting_entries",
                "accounting.opening_balance_workbooks",
                "accounting.opening_balance_journal_preparations",
                "accounting.opening_balance_journal_postings",
                "accounting.opening_balance_loan_snapshot_batches",
                "accounting.opening_balance_loan_measurement_snapshots",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "Stage 5D.18 live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before_loans = _count(connection, "lending.loans")
            before_loan_statuses = _loan_status_counts(connection)
            before_transactions = _count(connection, "lending.collection_transactions")
            before_void_state = _void_state_counts(connection)
            before_void_audits = _count(connection, "lending.collection_transaction_voids")
            before_journals = _count(connection, "accounting.journal_entries")
            before_lines = _count(connection, "accounting.journal_lines")
            before_events = _count(connection, "accounting.journal_events")
            before_regular = _protected_regular_counts(connection)
            before_opening = _opening_anchor_counts(connection)
            before_dpd = _dpd_safety(connection)
            reversal_tables_installed = _exists(
                connection,
                "accounting.regular_journal_reversal_sets",
            )
            before_reversal_sets = (
                _count(connection, "accounting.regular_journal_reversal_sets")
                if reversal_tables_installed
                else 0
            )
            before_reversal_entries = (
                _count(connection, "accounting.regular_journal_reversal_entries")
                if reversal_tables_installed
                else 0
            )

            # Migration 0043 is schema/control installation only. Running it may
            # create or refresh protected functions/triggers, but it must not
            # create any operational void or accounting reversal by itself.
            connection.execute(migration_body)

            after_loans = _count(connection, "lending.loans")
            after_loan_statuses = _loan_status_counts(connection)
            after_transactions = _count(connection, "lending.collection_transactions")
            after_void_state = _void_state_counts(connection)
            after_void_audits = _count(connection, "lending.collection_transaction_voids")
            after_journals = _count(connection, "accounting.journal_entries")
            after_lines = _count(connection, "accounting.journal_lines")
            after_events = _count(connection, "accounting.journal_events")
            after_regular = _protected_regular_counts(connection)
            after_opening = _opening_anchor_counts(connection)
            after_dpd = _dpd_safety(connection)
            reversal_sets, reversal_entries = _verify_installed(connection)

            if after_loans != before_loans or after_loan_statuses != before_loan_statuses:
                raise SystemExit(
                    "Stage 5D.18 live migration safety gate failed: live loans changed during schema install"
                )
            if (
                after_transactions != before_transactions
                or after_void_state != before_void_state
                or after_void_audits != before_void_audits
            ):
                raise SystemExit(
                    "Stage 5D.18 live migration safety gate failed: collection/void state changed during schema install"
                )
            if (
                after_journals != before_journals
                or after_lines != before_lines
                or after_events != before_events
            ):
                raise SystemExit(
                    "Stage 5D.18 live migration safety gate failed: journal history changed during schema install"
                )
            if after_regular != before_regular:
                raise SystemExit(
                    "Stage 5D.18 live migration safety gate failed: protected Stage 5D.16/5D.17 evidence changed during schema install"
                )
            if after_opening != before_opening or after_dpd != before_dpd:
                raise SystemExit(
                    "Stage 5D.18 live migration safety gate failed: opening/cutover/ECL state changed during schema install"
                )
            if (
                reversal_sets != before_reversal_sets
                or reversal_entries != before_reversal_entries
            ):
                raise SystemExit(
                    "Stage 5D.18 live migration safety gate failed: installing controls created reversal audit rows"
                )

            print(
                "Stage 5D.18 protected Regular reversal summary: "
                f"transactions={after_transactions}, voided={after_void_state[1]}, "
                f"void_audits={after_void_audits}, journals={after_journals}, "
                f"posting_sets={after_regular[2]}, posting_entries={after_regular[3]}, "
                f"reversal_sets={reversal_sets}, reversal_entries={reversal_entries}, "
                "controlled_reversal_enabled=True, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.18 protected Regular reversal migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
