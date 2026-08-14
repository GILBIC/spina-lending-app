from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATIONS = tuple(
    SQL_ROOT / name
    for name in (
        "0082_add_v1_tax_evidence_readiness.sql",
        "0083_add_protected_v1_tax_liability_posting.sql",
        "0084_harden_v1_tax_liability_preparation.sql",
        "0085_add_protected_v1_tax_settlement.sql",
        "0086_add_protected_v1_tax_adjustment_reversal.sql",
        "0087_add_protected_v1_tax_additional_amendment.sql",
        "0088_add_protected_v1_tax_additional_settlement.sql",
        "0089_add_protected_v1_tax_recoverable_refund.sql",
        "0090_add_protected_v1_tax_recoverable_credit_application.sql",
    )
)

PROTECTED_HISTORY_RELATIONS = (
    "lending.loans",
    "lending.loan_disbursement_events",
    "lending.collection_transactions",
    "accounting.journal_entries",
    "accounting.journal_lines",
    "accounting.journal_events",
    "accounting.regular_journal_posting_entries",
    "accounting.seven_by_seven_journal_postings",
    "accounting.ecl_allowance_remeasurements",
    "accounting.ecl_accounting_writeoffs",
    "accounting.ecl_post_writeoff_recoveries",
    "core.audit_logs",
)

TAX_DATA_RELATIONS = (
    "accounting.v1_tax_rule_evidence",
    "accounting.v1_dst_evidence",
    "accounting.v1_percentage_tax_evidence",
    "accounting.v1_tax_liability_preparations",
    "accounting.v1_tax_liability_postings",
    "accounting.v1_tax_return_evidence",
    "accounting.v1_tax_return_liability_items",
    "accounting.v1_tax_payment_evidence",
    "accounting.v1_tax_settlement_preparations",
    "accounting.v1_tax_settlement_postings",
    "accounting.v1_tax_adjustment_evidence",
    "accounting.v1_tax_adjustment_preparations",
    "accounting.v1_tax_adjustment_postings",
    "accounting.v1_tax_additional_amendment_evidence",
    "accounting.v1_tax_additional_liability_preparations",
    "accounting.v1_tax_additional_liability_postings",
    "accounting.v1_tax_additional_payment_evidence",
    "accounting.v1_tax_additional_settlement_preparations",
    "accounting.v1_tax_additional_settlement_postings",
    "accounting.v1_tax_recoverable_refund_evidence",
    "accounting.v1_tax_recoverable_refund_preparations",
    "accounting.v1_tax_recoverable_refund_postings",
    "accounting.v1_tax_recoverable_credit_evidence",
    "accounting.v1_tax_recoverable_credit_preparations",
    "accounting.v1_tax_recoverable_credit_postings",
)

REQUIRED_RELATIONS = TAX_DATA_RELATIONS + (
    "accounting.v1_tax_dst_readiness",
    "accounting.v1_tax_percentage_readiness",
    "accounting.v1_tax_readiness_summary",
    "accounting.v1_tax_liability_queue",
    "accounting.v1_tax_settlement_queue",
    "accounting.v1_tax_adjustment_queue",
    "accounting.v1_tax_additional_amendment_queue",
    "accounting.v1_tax_recoverable_refund_queue",
    "accounting.v1_tax_recoverable_credit_queue",
    "accounting.v1_tax_recoverable_controls",
)

REQUIRED_FUNCTIONS = (
    "record_v1_tax_rule_evidence",
    "record_v1_dst_evidence",
    "record_v1_percentage_tax_evidence",
    "prepare_v1_tax_liability_journal",
    "post_v1_tax_liability_journal",
    "record_v1_tax_return_evidence",
    "record_v1_tax_payment_evidence",
    "prepare_v1_tax_settlement_journal",
    "post_v1_tax_settlement_journal",
    "record_v1_tax_adjustment_evidence",
    "prepare_v1_tax_adjustment_journal",
    "post_v1_tax_adjustment_journal",
    "record_v1_tax_additional_amendment_evidence",
    "prepare_v1_tax_additional_liability_journal",
    "post_v1_tax_additional_liability_journal",
    "record_v1_tax_additional_payment_evidence",
    "prepare_v1_tax_additional_settlement_journal",
    "post_v1_tax_additional_settlement_journal",
    "record_v1_tax_recoverable_refund_evidence",
    "prepare_v1_tax_recoverable_refund_journal",
    "post_v1_tax_recoverable_refund_journal",
    "record_v1_tax_recoverable_credit_evidence",
    "prepare_v1_tax_recoverable_credit_journal",
    "post_v1_tax_recoverable_credit_journal",
)

MANAGEMENT_PERMISSIONS = (
    "accounting.tax.rule_evidence.record",
    "accounting.tax.dst_evidence.record",
    "accounting.tax.percentage_evidence.record",
    "accounting.tax.liability.prepare",
    "accounting.tax.liability.post",
    "accounting.tax.return_evidence.record",
    "accounting.tax.payment_evidence.record",
    "accounting.tax.settlement.prepare",
    "accounting.tax.settlement.post",
    "accounting.tax.adjustment_evidence.record",
    "accounting.tax.adjustment.prepare",
    "accounting.tax.adjustment.post",
    "accounting.tax.additional_amendment_evidence.record",
    "accounting.tax.additional_amendment.prepare",
    "accounting.tax.additional_amendment.post",
    "accounting.tax.additional_payment_evidence.record",
    "accounting.tax.additional_settlement.prepare",
    "accounting.tax.additional_settlement.post",
    "accounting.tax.recoverable_refund_evidence.record",
    "accounting.tax.recoverable_refund.prepare",
    "accounting.tax.recoverable_refund.post",
    "accounting.tax.recoverable_credit_evidence.record",
    "accounting.tax.recoverable_credit.prepare",
    "accounting.tax.recoverable_credit.post",
)

EXPECTED_ACCOUNTS = (
    ("1010", "cash_office", "asset", "debit", True, True),
    ("1030", "cash_bank_gcash", "asset", "debit", True, True),
    ("1130", "tax_recoverable", "asset", "debit", True, True),
    ("2100", "tax_payables", "liability", "credit", True, True),
    ("5300", "percentage_tax_lending_expense", "expense", "debit", True, True),
    ("5310", "documentary_stamp_tax_expense", "expense", "debit", True, True),
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


def _transaction_body(source: str, migration: Path) -> str:
    text = source.strip()
    if not text.startswith("BEGIN;") or not text.endswith("COMMIT;"):
        raise SystemExit(
            "A6.2 live migration safety gate failed: expected BEGIN/COMMIT wrapper for "
            + migration.name
        )
    return text[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute("SELECT to_regclass(%s)", (relation,)).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])


def _count_if_exists(connection: psycopg.Connection, relation: str) -> int:
    return _count(connection, relation) if _exists(connection, relation) else 0


def _snapshot(connection: psycopg.Connection, relations: tuple[str, ...]) -> tuple[int, ...]:
    return tuple(_count_if_exists(connection, relation) for relation in relations)


def _function_count(connection: psycopg.Connection, name: str) -> int:
    return int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid=proc.pronamespace
            WHERE ns.nspname='accounting' AND proc.proname=%s
            """,
            (name,),
        ).fetchone()[0]
    )


def _verify_prerequisites(connection: psycopg.Connection) -> None:
    prerequisites = (
        "core.users",
        "core.roles",
        "core.permissions",
        "core.role_permissions",
        "core.audit_logs",
        "lending.loans",
        "lending.loan_disbursement_events",
        "lending.collection_transactions",
        "accounting.accounts",
        "accounting.fiscal_periods",
        "accounting.journal_entries",
        "accounting.journal_lines",
        "accounting.journal_events",
        "accounting.initial_capital_funding_evidence",
    )
    missing = [relation for relation in prerequisites if not _exists(connection, relation)]
    if missing:
        raise SystemExit(
            "A6.2 live migration prerequisite is not installed: " + ", ".join(missing)
        )


def _verify_installed(connection: psycopg.Connection) -> None:
    missing = [relation for relation in REQUIRED_RELATIONS if not _exists(connection, relation)]
    if missing:
        raise SystemExit(
            "A6.2 live verification failed: required relation missing: " + ", ".join(missing)
        )

    ambiguous_functions = [
        name for name in REQUIRED_FUNCTIONS if _function_count(connection, name) != 1
    ]
    if ambiguous_functions:
        raise SystemExit(
            "A6.2 live verification failed: protected function missing or ambiguous: "
            + ", ".join(ambiguous_functions)
        )

    accounts = connection.execute(
        """
        SELECT code, system_key, account_type, normal_balance, is_active, is_posting
        FROM accounting.accounts
        WHERE code IN ('1010','1030','1130','2100','5300','5310')
        ORDER BY code
        """
    ).fetchall()
    if accounts != list(EXPECTED_ACCOUNTS):
        raise SystemExit(
            "A6.2 live verification failed: protected cash/tax account coordinates changed"
        )

    placeholders = ",".join(["%s"] * len(MANAGEMENT_PERMISSIONS))
    grants = connection.execute(
        f"""
        SELECT permission.code,
               count(*) FILTER (WHERE role.code='management') AS management_grants
        FROM core.permissions permission
        LEFT JOIN core.role_permissions role_permission
          ON role_permission.permission_code=permission.code
        LEFT JOIN core.roles role ON role.id=role_permission.role_id
        WHERE permission.code IN ({placeholders})
        GROUP BY permission.code
        ORDER BY permission.code
        """,
        MANAGEMENT_PERMISSIONS,
    ).fetchall()
    if len(grants) != len(MANAGEMENT_PERMISSIONS) or any(row[1] != 1 for row in grants):
        raise SystemExit(
            "A6.2 live verification failed: exact Management tax permissions are missing"
        )

    readiness_flags = connection.execute(
        """
        SELECT evidence_backed_tax_readiness_enabled, tax_posting_enabled,
               automatic_source_posting
        FROM accounting.v1_tax_readiness_summary
        """
    ).fetchone()
    if readiness_flags != (True, False, False):
        raise SystemExit(
            "A6.2 live verification failed: evidence layer flags no longer preserve non-posting readiness"
        )

    recoverable_flags = connection.execute(
        """
        SELECT tax_recoverable_refund_realization_enabled,
               tax_recoverable_credit_application_enabled,
               partial_tax_recoverable_realization_enabled,
               automatic_source_posting
        FROM accounting.v1_tax_recoverable_controls
        """
    ).fetchone()
    if recoverable_flags != (True, True, False, False):
        raise SystemExit(
            "A6.2 live verification failed: final Tax Recoverable controls are not exact"
        )

    if connection.execute(
        """
        SELECT count(*) FROM accounting.v1_tax_liability_queue
        WHERE automatic_source_posting IS DISTINCT FROM false
        """
    ).fetchone()[0]:
        raise SystemExit("A6.2 live verification failed: liability queue enabled automatic posting")
    if connection.execute(
        """
        SELECT count(*) FROM accounting.v1_tax_settlement_queue
        WHERE automatic_source_posting IS DISTINCT FROM false
        """
    ).fetchone()[0]:
        raise SystemExit("A6.2 live verification failed: settlement queue enabled automatic posting")
    if connection.execute(
        """
        SELECT count(*) FROM accounting.v1_tax_adjustment_queue
        WHERE automatic_source_posting IS DISTINCT FROM false
        """
    ).fetchone()[0]:
        raise SystemExit("A6.2 live verification failed: adjustment queue enabled automatic posting")
    if connection.execute(
        """
        SELECT count(*) FROM accounting.v1_tax_recoverable_refund_queue
        WHERE automatic_source_posting IS DISTINCT FROM false
        """
    ).fetchone()[0]:
        raise SystemExit("A6.2 live verification failed: refund queue enabled automatic posting")
    if connection.execute(
        """
        SELECT count(*) FROM accounting.v1_tax_recoverable_credit_queue
        WHERE automatic_source_posting IS DISTINCT FROM false
           OR partial_tax_recoverable_realization_enabled IS DISTINCT FROM false
        """
    ).fetchone()[0]:
        raise SystemExit(
            "A6.2 live verification failed: tax-credit queue enabled automatic or partial realization"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify the complete SPINA V1 A6.2 tax-accounting schema/control "
            "capability on the approved live database without creating tax evidence, journal "
            "drafts/postings, liabilities, returns, payments, settlements, adjustments, "
            "amendments, refunds or tax-credit applications, and without changing protected history."
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
    missing_files = [str(path) for path in MIGRATIONS if not path.is_file()]
    if missing_files:
        raise SystemExit("A6.2 live migration file missing: " + ", ".join(missing_files))

    bodies = [
        _transaction_body(path.read_text(encoding="utf-8"), path) for path in MIGRATIONS
    ]

    try:
        with psycopg.connect(database_url) as connection:
            _verify_prerequisites(connection)
            before_history = _snapshot(connection, PROTECTED_HISTORY_RELATIONS)
            before_tax = _snapshot(connection, TAX_DATA_RELATIONS)

            for body in bodies:
                connection.execute(body)

            _verify_installed(connection)
            after_history = _snapshot(connection, PROTECTED_HISTORY_RELATIONS)
            after_tax = _snapshot(connection, TAX_DATA_RELATIONS)

            if after_history != before_history:
                raise SystemExit(
                    "A6.2 live migration safety gate failed: installing controls changed protected operational/accounting history"
                )
            if after_tax != before_tax:
                changed = [
                    relation
                    for relation, before, after in zip(
                        TAX_DATA_RELATIONS, before_tax, after_tax, strict=True
                    )
                    if before != after
                ]
                raise SystemExit(
                    "A6.2 live migration safety gate failed: installing controls created or removed protected tax business rows: "
                    + ", ".join(changed)
                )

            print(
                "A6.2 V1 tax live schema/control verification passed: migrations=0082-0090, "
                "protected_history_unchanged=True, protected_tax_rows_unchanged=True, "
                "evidence_backed_tax_readiness_enabled=True, tax_recoverable_refund_realization_enabled=True, "
                "tax_recoverable_credit_application_enabled=True, partial_tax_recoverable_realization_enabled=False, "
                "automatic_source_posting=False. No tax business evidence or General Journal event was created by installation."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "A6.2 live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
