from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0061_add_7x7_eir_carrying_policy_readiness.sql"


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
            "7x7 EIR/carrying policy live migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute("select to_regclass(%s)", (relation,)).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    for relation in (
        "accounting.seven_by_seven_contractual_cash_flow_readiness",
        "accounting.seven_by_seven_eir_carrying_policy_readiness",
        "accounting.seven_by_seven_eir_carrying_policy_summary",
    ):
        if not _exists(connection, relation):
            raise SystemExit(
                "7x7 EIR/carrying policy live verification failed: missing " + relation
            )

    invalid_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_carrying_policy_readiness
            where sppi_classification_concluded = true
               or business_model_classification_concluded = true
               or expected_cash_flow_policy_approved = true
               or eir_policy_ready = true
               or carrying_amount_ready = true
               or journal_lines_enabled = true
               or automatic_source_posting = true
               or authoritative_daily_eir is not null
               or authoritative_initial_gross_carrying_amount is not null
               or authoritative_current_gross_carrying_amount is not null
            """
        ).fetchone()[0]
    )
    if invalid_flags:
        raise SystemExit(
            "7x7 EIR/carrying policy live verification failed: authoritative classification, EIR, carrying, or posting controls were unexpectedly enabled"
        )

    missing_review_gates = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_carrying_policy_readiness
            where business_model_assessment_required = false
               or sppi_assessment_required = false
               or prepayment_expected_cash_flow_policy_required = false
               or expected_life_assessment_required = false
            """
        ).fetchone()[0]
    )
    if missing_review_gates:
        raise SystemExit(
            "7x7 EIR/carrying policy live verification failed: a required IFRS 9 review gate was bypassed"
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
        connection, "accounting.seven_by_seven_eir_carrying_policy_readiness"
    )
    if readiness_rows != seven_by_seven_loans:
        raise SystemExit(
            "7x7 EIR/carrying policy live verification failed: policy-readiness row count does not equal 7x7 loan count"
        )

    preview_solved = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_carrying_policy_readiness
            where base_no_prepayment_daily_eir_preview is not null
            """
        ).fetchone()[0]
    )
    sppi_prepayment_review = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_carrying_policy_readiness
            where policy_readiness_status = 'sppi_and_prepayment_policy_review_required'
            """
        ).fetchone()[0]
    )
    contract_gate_required = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_eir_carrying_policy_readiness
            where policy_readiness_status = 'contractual_cash_flow_readiness_required'
            """
        ).fetchone()[0]
    )
    return {
        "seven_by_seven_loans": seven_by_seven_loans,
        "readiness_rows": readiness_rows,
        "preview_solved": preview_solved,
        "sppi_prepayment_review": sppi_prepayment_review,
        "contract_gate_required": contract_gate_required,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify read-only 7x7 EIR/carrying policy readiness on the live "
            "database without creating accounting decisions, lending history, journals, or postings."
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
            "7x7 EIR/carrying policy migration file was not found: " + str(MIGRATION)
        )
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "core.audit_logs",
                "lending.loans",
                "lending.loan_types",
                "lending.loan_contract_schedules",
                "lending.loan_contract_installments",
                "lending.loan_contract_schedule_registrations",
                "accounting.seven_by_seven_contractual_cash_flow_readiness",
                "accounting.journal_entries",
                "accounting.journal_lines",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "7x7 EIR/carrying policy live migration prerequisite is not installed: "
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
            before = tuple(_count(connection, relation) for relation in tracked_relations)

            connection.execute(body)
            summary = _verify_installed(connection)

            after = tuple(_count(connection, relation) for relation in tracked_relations)
            if after != before:
                raise SystemExit(
                    "7x7 EIR/carrying policy live migration safety gate failed: installing read-only controls changed live operational/accounting rows"
                )

            print(
                "7x7 EIR/carrying policy live summary: "
                f"loans={summary['seven_by_seven_loans']}, readiness_rows={summary['readiness_rows']}, "
                f"base_eir_preview_solved={summary['preview_solved']}, "
                f"contract_gate_required={summary['contract_gate_required']}, "
                f"sppi_prepayment_review_required={summary['sppi_prepayment_review']}, "
                "history_unchanged=True, authoritative_daily_eir=None, carrying_amount=None, "
                "sppi_classification_concluded=False, expected_cash_flow_policy_approved=False, "
                "eir_policy_ready=False, carrying_amount_ready=False, journal_lines_enabled=False, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "7x7 EIR/carrying policy live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
