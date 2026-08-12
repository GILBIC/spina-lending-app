from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0062_add_7x7_classification_policy_evidence.sql"


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
            "7x7 classification policy live migration safety gate failed: expected BEGIN/COMMIT wrapper"
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
        "accounting.seven_by_seven_policy_decisions",
        "accounting.seven_by_seven_policy_decision_voids",
        "accounting.seven_by_seven_policy_decision_status",
        "accounting.seven_by_seven_classification_policy_readiness",
        "accounting.seven_by_seven_classification_policy_summary",
    ):
        if not _exists(connection, relation):
            raise SystemExit(
                "7x7 classification policy live verification failed: missing " + relation
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
        connection, "accounting.seven_by_seven_classification_policy_readiness"
    )
    if readiness_rows != seven_by_seven_loans:
        raise SystemExit(
            "7x7 classification policy live verification failed: readiness row count does not equal 7x7 loan count"
        )

    invalid_enabled = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_classification_policy_readiness
            where authoritative_daily_eir is not null
               or authoritative_initial_gross_carrying_amount is not null
               or authoritative_current_gross_carrying_amount is not null
               or eir_policy_ready = true
               or carrying_amount_ready = true
               or journal_lines_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_enabled:
        raise SystemExit(
            "7x7 classification policy live verification failed: authoritative EIR/carrying/posting was unexpectedly enabled"
        )

    stale_current = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_classification_policy_readiness
            where active_policy_decision_is_current
              and decision_review_token is distinct from current_policy_review_token
            """
        ).fetchone()[0]
    )
    if stale_current:
        raise SystemExit(
            "7x7 classification policy live verification failed: stale decision was marked current"
        )

    invalid_amortised_cost = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_classification_policy_readiness
            where amortised_cost_path_supported
              and (business_model_conclusion <> 'held_to_collect'
                   or sppi_conclusion <> 'passes'
                   or measurement_category <> 'amortised_cost')
            """
        ).fetchone()[0]
    )
    if invalid_amortised_cost:
        raise SystemExit(
            "7x7 classification policy live verification failed: amortised-cost support is inconsistent with reviewed classification"
        )

    active_decisions = _count(connection, "accounting.seven_by_seven_policy_decisions")
    active_voids = _count(connection, "accounting.seven_by_seven_policy_decision_voids")
    current_decisions = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_classification_policy_readiness
            where active_policy_decision_is_current
            """
        ).fetchone()[0]
    )
    promotion_review_ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_classification_policy_readiness
            where classification_policy_evidence_ready_for_eir_promotion
            """
        ).fetchone()[0]
    )
    return {
        "loans": seven_by_seven_loans,
        "readiness_rows": readiness_rows,
        "decisions": active_decisions,
        "voids": active_voids,
        "current_decisions": current_decisions,
        "promotion_review_ready": promotion_review_ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify protected 7x7 classification / expected-cash-flow policy "
            "evidence controls on the live database without creating lending history, "
            "Management decisions, journals, or postings."
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
            "7x7 classification policy migration file was not found: " + str(MIGRATION)
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
                "accounting.seven_by_seven_eir_carrying_policy_readiness",
                "accounting.journal_entries",
                "accounting.journal_lines",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "7x7 classification policy live migration prerequisite is not installed: "
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
            before_decisions = _count(connection, "accounting.seven_by_seven_policy_decisions")
            before_voids = _count(connection, "accounting.seven_by_seven_policy_decision_voids")

            connection.execute(body)
            summary = _verify_installed(connection)

            after_history = tuple(_count(connection, relation) for relation in tracked_relations)
            if after_history != before_history:
                raise SystemExit(
                    "7x7 classification policy live migration safety gate failed: installing controls changed live operational/accounting history"
                )
            if summary["decisions"] != before_decisions or summary["voids"] != before_voids:
                raise SystemExit(
                    "7x7 classification policy live migration safety gate failed: installation created or removed Management policy evidence"
                )

            print(
                "7x7 classification policy live summary: "
                f"loans={summary['loans']}, readiness_rows={summary['readiness_rows']}, "
                f"policy_decisions={summary['decisions']}, policy_voids={summary['voids']}, "
                f"current_decisions={summary['current_decisions']}, "
                f"eir_promotion_review_ready={summary['promotion_review_ready']}, "
                "history_unchanged=True, authoritative_daily_eir=None, carrying_amount=None, "
                "eir_policy_ready=False, carrying_amount_ready=False, journal_lines_enabled=False, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "7x7 classification policy live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
