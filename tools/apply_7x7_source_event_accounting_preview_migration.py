from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0064_add_7x7_source_event_accounting_preview.sql"


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
            "7x7 source-event preview live migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute("select to_regclass(%s)", (relation,)).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    if not _exists(connection, relation):
        return 0
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    required_relations = (
        "accounting.seven_by_seven_collection_source_inventory",
        "accounting.seven_by_seven_source_event_accounting_readiness",
        "accounting.seven_by_seven_source_event_accounting_preview",
        "accounting.seven_by_seven_operational_allocation_parity_preview",
        "accounting.seven_by_seven_source_event_journal_coordinate_preview",
        "accounting.seven_by_seven_source_event_accounting_summary",
    )
    for relation in required_relations:
        if not _exists(connection, relation):
            raise SystemExit(
                "7x7 source-event preview live verification failed: missing " + relation
            )

    loan_count = int(
        connection.execute(
            """
            select count(*)
            from lending.loans loan
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            where loan_type.calculation_mode = 'seven_by_seven'
            """
        ).fetchone()[0]
    )
    readiness_rows = _count(
        connection, "accounting.seven_by_seven_source_event_accounting_readiness"
    )
    if readiness_rows != loan_count:
        raise SystemExit(
            "7x7 source-event preview live verification failed: readiness row count does not equal 7x7 loan count"
        )

    unsafe_flag_count = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_source_event_accounting_summary
            where authoritative_current_gross_carrying_amount is not null
               or authoritative_current_carrying_amount_ready
               or journal_draft_enabled
               or journal_lines_enabled
               or automatic_source_posting
            """
        ).fetchone()[0]
    )
    if unsafe_flag_count:
        raise SystemExit(
            "7x7 source-event preview live verification failed: authoritative current carrying or posting was unexpectedly enabled"
        )

    invalid_coordinate_count = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_source_event_journal_coordinate_preview
            where journal_lines_enabled or automatic_source_posting
            """
        ).fetchone()[0]
    )
    if invalid_coordinate_count:
        raise SystemExit(
            "7x7 source-event preview live verification failed: coordinate preview unexpectedly enabled journal writing/posting"
        )

    source_ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_source_event_accounting_readiness
            where source_event_structure_ready
            """
        ).fetchone()[0]
    )
    active_cash_events = int(
        connection.execute(
            """
            select coalesce(sum(active_positive_cash_event_count), 0)
            from accounting.seven_by_seven_source_event_accounting_readiness
            """
        ).fetchone()[0]
    )
    preview_events = _count(
        connection, "accounting.seven_by_seven_source_event_accounting_preview"
    )
    coordinate_rows = _count(
        connection, "accounting.seven_by_seven_source_event_journal_coordinate_preview"
    )
    parity_rows = _count(
        connection, "accounting.seven_by_seven_operational_allocation_parity_preview"
    )
    return {
        "loans": loan_count,
        "readiness_rows": readiness_rows,
        "source_ready": source_ready,
        "active_cash_events": active_cash_events,
        "preview_events": preview_events,
        "coordinate_rows": coordinate_rows,
        "parity_rows": parity_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify read-only 7x7 source-event accounting preview controls on the live database "
            "without changing operational/accounting history, creating journals, or enabling current carrying/posting."
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
    if not MIGRATION.is_file():
        raise SystemExit("7x7 source-event preview migration file was not found: " + str(MIGRATION))
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.loan_types",
                "lending.collection_transactions",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.seven_by_seven_eir_initial_carrying_readiness",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "7x7 source-event preview live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            tracked_relations = (
                "lending.loans",
                "lending.loan_types",
                "lending.collection_transactions",
                "lending.collection_transaction_voids",
                "accounting.seven_by_seven_eir_initial_carrying_anchors",
                "accounting.seven_by_seven_eir_initial_carrying_anchor_voids",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "core.audit_logs",
            )
            before_history = tuple(_count(connection, relation) for relation in tracked_relations)

            connection.execute(body)
            summary = _verify_installed(connection)

            after_history = tuple(_count(connection, relation) for relation in tracked_relations)
            if after_history != before_history:
                raise SystemExit(
                    "7x7 source-event preview live migration safety gate failed: installing read-only controls changed live operational/accounting history"
                )

            print(
                "7x7 source-event preview live summary: "
                f"loans={summary['loans']}, readiness_rows={summary['readiness_rows']}, "
                f"source_ready={summary['source_ready']}, active_cash_events={summary['active_cash_events']}, "
                f"preview_events={summary['preview_events']}, coordinate_rows={summary['coordinate_rows']}, "
                f"parity_rows={summary['parity_rows']}, history_unchanged=True, "
                "authoritative_current_carrying_amount_ready=False, journal_draft_enabled=False, "
                "journal_lines_enabled=False, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "7x7 source-event preview live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
