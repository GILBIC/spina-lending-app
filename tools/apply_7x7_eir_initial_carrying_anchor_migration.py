from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0063_add_7x7_eir_initial_carrying_anchor.sql"


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
            "7x7 EIR initial-carrying live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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
    for relation in (
        "accounting.seven_by_seven_eir_initial_carrying_anchors",
        "accounting.seven_by_seven_eir_initial_carrying_anchor_voids",
        "accounting.seven_by_seven_eir_initial_carrying_anchor_status",
        "accounting.seven_by_seven_eir_initial_carrying_readiness",
        "accounting.seven_by_seven_eir_initial_carrying_summary",
    ):
        if not _exists(connection, relation):
            raise SystemExit(
                "7x7 EIR initial-carrying live verification failed: missing " + relation
            )

    seven_by_seven_loans = int(
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
        connection, "accounting.seven_by_seven_eir_initial_carrying_readiness"
    )
    if readiness_rows != seven_by_seven_loans:
        raise SystemExit(
            "7x7 EIR initial-carrying live verification failed: readiness row count does not equal 7x7 loan count"
        )

    invalid_current_carrying = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_initial_carrying_readiness
            where authoritative_current_gross_carrying_amount is not null
               or current_carrying_amount_ready = true
               or carrying_amount_ready = true
               or journal_lines_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_current_carrying:
        raise SystemExit(
            "7x7 EIR initial-carrying live verification failed: current carrying or posting was unexpectedly enabled"
        )

    invalid_ready_anchor = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_initial_carrying_readiness
            where eir_policy_ready
              and (not active_anchor_exists
                   or not active_anchor_is_current
                   or not anchor_eir_reconciles
                   or authoritative_daily_eir is null
                   or authoritative_initial_gross_carrying_amount is null
                   or measurement_category <> 'amortised_cost'
                   or business_model_conclusion <> 'held_to_collect'
                   or sppi_conclusion <> 'passes')
            """
        ).fetchone()[0]
    )
    if invalid_ready_anchor:
        raise SystemExit(
            "7x7 EIR initial-carrying live verification failed: a ready anchor was not exactly current/reconciled or lacked supported policy evidence"
        )

    anchors = _count(connection, "accounting.seven_by_seven_eir_initial_carrying_anchors")
    voids = _count(connection, "accounting.seven_by_seven_eir_initial_carrying_anchor_voids")
    current_anchors = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_initial_carrying_readiness
            where active_anchor_is_current
            """
        ).fetchone()[0]
    )
    eir_ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_initial_carrying_readiness
            where eir_policy_ready
            """
        ).fetchone()[0]
    )
    lifecycle_ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_initial_carrying_readiness
            where eir_initial_carrying_readiness_status = 'eir_initial_carrying_anchor_ready_for_7x7_accounting_lifecycle'
            """
        ).fetchone()[0]
    )
    return {
        "loans": seven_by_seven_loans,
        "readiness_rows": readiness_rows,
        "anchors": anchors,
        "voids": voids,
        "current_anchors": current_anchors,
        "eir_ready": eir_ready,
        "lifecycle_ready": lifecycle_ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify protected 7x7 original-EIR/initial-carrying anchor controls "
            "on the live database without creating Management evidence, lending history, "
            "current carrying amounts, journals, or postings."
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
        raise SystemExit(
            "7x7 EIR initial-carrying migration file was not found: " + str(MIGRATION)
        )
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "core.audit_logs",
                "core.users",
                "core.user_roles",
                "core.role_permissions",
                "lending.loans",
                "lending.loan_types",
                "lending.loan_contract_schedules",
                "lending.loan_contract_installments",
                "lending.loan_contract_schedule_registrations",
                "accounting.seven_by_seven_classification_policy_readiness",
                "accounting.seven_by_seven_policy_decisions",
                "accounting.journal_entries",
                "accounting.journal_lines",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "7x7 EIR initial-carrying live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            tracked_relations = (
                "core.audit_logs",
                "lending.loans",
                "lending.loan_types",
                "lending.loan_contract_schedules",
                "lending.loan_contract_installments",
                "lending.loan_contract_schedule_registrations",
                "accounting.journal_entries",
                "accounting.journal_lines",
            )
            before_history = tuple(_count(connection, relation) for relation in tracked_relations)
            before_anchors = _count(
                connection, "accounting.seven_by_seven_eir_initial_carrying_anchors"
            )
            before_voids = _count(
                connection, "accounting.seven_by_seven_eir_initial_carrying_anchor_voids"
            )

            connection.execute(body)
            summary = _verify_installed(connection)

            after_history = tuple(_count(connection, relation) for relation in tracked_relations)
            if after_history != before_history:
                raise SystemExit(
                    "7x7 EIR initial-carrying live migration safety gate failed: installing controls changed live operational/accounting history"
                )
            if summary["anchors"] != before_anchors or summary["voids"] != before_voids:
                raise SystemExit(
                    "7x7 EIR initial-carrying live migration safety gate failed: installation created or removed Management anchor evidence"
                )

            print(
                "7x7 EIR initial-carrying live summary: "
                f"loans={summary['loans']}, readiness_rows={summary['readiness_rows']}, "
                f"anchors={summary['anchors']}, anchor_voids={summary['voids']}, "
                f"current_anchors={summary['current_anchors']}, eir_policy_ready={summary['eir_ready']}, "
                f"accounting_lifecycle_ready={summary['lifecycle_ready']}, history_unchanged=True, "
                "current_carrying_amount_ready=False, journal_lines_enabled=False, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "7x7 EIR initial-carrying live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
