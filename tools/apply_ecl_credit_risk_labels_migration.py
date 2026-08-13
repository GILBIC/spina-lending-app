from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATIONS = (
    SQL_ROOT / "0070_add_ecl_credit_risk_labels.sql",
    SQL_ROOT / "0071_harden_ecl_cash_recovery_chronology.sql",
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


def _relation_count(connection: psycopg.Connection, relation: str) -> int:
    exists = connection.execute("SELECT to_regclass(%s)", (relation,)).fetchone()[0]
    if exists is None:
        return 0
    if relation == "accounting.ecl_credit_risk_label_reviews":
        return int(
            connection.execute(
                "SELECT count(*) FROM accounting.ecl_credit_risk_label_reviews"
            ).fetchone()[0]
        )
    raise ValueError(f"Unsupported relation count: {relation}")


def _history_counts(connection: psycopg.Connection) -> tuple[int, int, int, int]:
    fixed = connection.execute(
        """
        SELECT
            (SELECT count(*) FROM accounting.journal_entries),
            (SELECT count(*) FROM accounting.journal_lines),
            (SELECT count(*) FROM accounting.ecl_outcome_label_reviews)
        """
    ).fetchone()
    return (
        int(fixed[0]),
        int(fixed[1]),
        int(fixed[2]),
        _relation_count(connection, "accounting.ecl_credit_risk_label_reviews"),
    )


def _verify(connection: psycopg.Connection) -> tuple:
    objects = connection.execute(
        """
        SELECT
            to_regclass('accounting.ecl_credit_risk_label_reviews'),
            to_regclass('accounting.ecl_credit_risk_label_policy_v1'),
            to_regclass('accounting.ecl_credit_risk_label_queue'),
            to_regclass('accounting.ecl_credit_risk_label_summary'),
            to_regprocedure(
                'accounting.review_ecl_credit_risk_labels(uuid,text,boolean,text,text,text,text,text,boolean,boolean,text,text,text,text,uuid,uuid)'
            ),
            to_regprocedure('accounting.guard_ecl_cash_recovery_chronology()')
        """
    ).fetchone()
    if any(item is None for item in objects):
        raise SystemExit(
            "ECL credit-risk label verification failed: required protected objects are missing"
        )

    chronology_trigger_count = connection.execute(
        """
        SELECT count(*)
        FROM pg_trigger trigger
        JOIN pg_class relation ON relation.oid = trigger.tgrelid
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'accounting'
          AND relation.relname = 'ecl_credit_risk_label_reviews'
          AND trigger.tgname = 'ecl_cash_recovery_chronology_guard'
          AND NOT trigger.tgisinternal
        """
    ).fetchone()[0]
    if int(chronology_trigger_count) != 1:
        raise SystemExit(
            "ECL credit-risk label verification failed: strict cash-recovery chronology trigger is missing"
        )

    invalid_recovery_chronology = connection.execute(
        """
        SELECT count(*)
        FROM accounting.ecl_credit_risk_label_reviews current_review
        LEFT JOIN accounting.ecl_credit_risk_label_reviews prior_review
          ON prior_review.id = current_review.supersedes_review_id
        LEFT JOIN lending.collection_transactions recovery_tx
          ON recovery_tx.id = current_review.recovery_transaction_id
        WHERE current_review.recovery_label = 'cash_recovery_observed'
          AND (
                prior_review.id IS NULL
             OR prior_review.loan_id <> current_review.loan_id
             OR prior_review.review_version + 1 <> current_review.review_version
             OR recovery_tx.id IS NULL
             OR recovery_tx.loan_id <> current_review.loan_id
             OR recovery_tx.is_voided
             OR recovery_tx.amount <= 0
             OR recovery_tx.entry_type NOT IN ('payment', 'advance')
             OR recovery_tx.accepted_at IS NULL
             OR recovery_tx.accepted_at <= prior_review.created_at
          )
        """
    ).fetchone()[0]
    if int(invalid_recovery_chronology) != 0:
        raise SystemExit(
            "ECL credit-risk label verification failed: existing cash-recovery evidence does not match the exact prior deteriorated review and strict accepted_at chronology"
        )

    permission = connection.execute(
        """
        SELECT count(*)
        FROM core.role_permissions role_permission
        JOIN core.roles role ON role.id = role_permission.role_id
        WHERE role.code = 'management'
          AND role_permission.permission_code = 'accounting.ecl.credit_risk_label.review'
        """
    ).fetchone()[0]
    if int(permission) != 1:
        raise SystemExit(
            "ECL credit-risk label verification failed: Management permission is missing"
        )

    policy = connection.execute(
        """
        SELECT
            policy_version,
            explicit_management_review_required,
            thirty_dpd_sicr_backstop_rebuttable,
            ninety_dpd_default_backstop_rebuttable,
            qualitative_evidence_can_require_earlier_stage_or_default,
            write_off_support_is_not_write_off_execution,
            cure_requires_explicit_review,
            cash_recovery_requires_exact_protected_transaction,
            automatic_staging_enabled,
            automatic_default_enabled,
            automatic_write_off_enabled,
            automatic_recovery_enabled,
            quantitative_ecl_ready,
            ecl_calculation_enabled,
            account_1190_posting_enabled,
            automatic_source_posting
        FROM accounting.ecl_credit_risk_label_policy_v1
        """
    ).fetchone()
    expected_prefix = (
        "ecl_credit_risk_labels_v1",
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    )
    if policy[:8] != expected_prefix or any(bool(value) for value in policy[8:]):
        raise SystemExit(
            f"ECL credit-risk label verification failed: policy mismatch {policy!r}"
        )

    summary = connection.execute(
        """
        SELECT
            loan_count,
            dpd_ready_count,
            dpd_data_required_count,
            label_review_required_count,
            label_refresh_required_count,
            current_label_ready_count,
            stage_1_count,
            stage_2_count,
            stage_3_count,
            default_count,
            write_off_supported_count,
            cash_recovery_observed_count,
            cured_count,
            quantitative_ecl_ready,
            ecl_amount,
            ecl_calculation_enabled,
            account_1190_posting_enabled,
            automatic_source_posting
        FROM accounting.ecl_credit_risk_label_summary
        """
    ).fetchone()
    if summary is None:
        raise SystemExit("ECL credit-risk label verification failed: summary is missing")
    if bool(summary[13]) or summary[14] is not None or any(bool(v) for v in summary[15:]):
        raise SystemExit(
            "ECL credit-risk label verification failed: quantitative ECL or posting was unexpectedly enabled"
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify protected SPINA V1 ECL credit-risk label controls plus strict cash-recovery chronology on the approved live database."
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
    missing = [str(path) for path in MIGRATIONS if not path.is_file()]
    if missing:
        raise SystemExit(
            "ECL credit-risk label migration file was not found: " + ", ".join(missing)
        )

    with psycopg.connect(database_url, autocommit=True) as connection:
        prerequisites = connection.execute(
            """
            SELECT
                to_regclass('accounting.ecl_methodology_policy_v1'),
                to_regclass('accounting.loan_contract_dpd_assessment')
            """
        ).fetchone()
        if any(item is None for item in prerequisites):
            raise SystemExit(
                "ECL credit-risk label migration refused: 0069 methodology policy and contract-driven DPD foundation must be installed"
            )

        before = _history_counts(connection)
        for migration in MIGRATIONS:
            connection.execute(migration.read_text(encoding="utf-8"))
        summary = _verify(connection)
        after = _history_counts(connection)
        if after != before:
            raise SystemExit(
                f"ECL credit-risk label verification failed: protected history changed from {before} to {after}"
            )

    print(
        "ECL credit-risk label live summary: "
        f"loans={summary[0]}, dpd_ready={summary[1]}, dpd_blocked={summary[2]}, "
        f"review_required={summary[3]}, refresh_required={summary[4]}, "
        f"current_labels={summary[5]}, stage1={summary[6]}, stage2={summary[7]}, "
        f"stage3={summary[8]}, defaults={summary[9]}, writeoff_supported={summary[10]}, "
        f"cash_recovery={summary[11]}, cured={summary[12]}, history_unchanged=True, "
        "strict_cash_recovery_chronology=True, explicit_management_review=True, "
        "automatic_staging_enabled=False, automatic_default_enabled=False, "
        "automatic_write_off_enabled=False, automatic_recovery_enabled=False, "
        "quantitative_ecl_ready=False, ecl_calculation_enabled=False, "
        "account_1190_posting_enabled=False, automatic_source_posting=False."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
