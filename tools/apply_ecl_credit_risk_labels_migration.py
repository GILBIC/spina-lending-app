from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATIONS = (
    SQL_ROOT / "0070_add_ecl_credit_risk_labels.sql",
    SQL_ROOT / "0071_harden_ecl_cash_recovery_chronology.sql",
    SQL_ROOT / "0072_add_ecl_quantitative_input_readiness.sql",
    SQL_ROOT / "0073_add_ecl_forward_looking_evidence_governance.sql",
    SQL_ROOT / "0074_integrate_ecl_forward_looking_readiness.sql",
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
    supported = {
        "accounting.ecl_credit_risk_label_reviews",
        "accounting.ecl_forward_looking_evidence",
        "accounting.ecl_forward_looking_evidence_revocations",
    }
    if relation in supported:
        return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])
    raise ValueError(f"Unsupported relation count: {relation}")


def _history_counts(connection: psycopg.Connection) -> tuple[int, int, int, int, int, int]:
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
        _relation_count(connection, "accounting.ecl_forward_looking_evidence"),
        _relation_count(connection, "accounting.ecl_forward_looking_evidence_revocations"),
    )


def _verify(connection: psycopg.Connection) -> tuple[tuple, tuple, tuple]:
    objects = connection.execute(
        """
        SELECT
            to_regclass('accounting.ecl_credit_risk_label_reviews'),
            to_regclass('accounting.ecl_credit_risk_label_policy_v1'),
            to_regclass('accounting.ecl_credit_risk_label_queue'),
            to_regclass('accounting.ecl_credit_risk_label_summary'),
            to_regclass('accounting.ecl_quantitative_input_readiness_a1_base'),
            to_regclass('accounting.ecl_quantitative_input_readiness'),
            to_regclass('accounting.ecl_quantitative_input_readiness_summary'),
            to_regclass('accounting.ecl_forward_looking_evidence'),
            to_regclass('accounting.ecl_forward_looking_evidence_revocations'),
            to_regclass('accounting.ecl_forward_looking_evidence_status'),
            to_regclass('accounting.ecl_forward_looking_evidence_readiness'),
            to_regprocedure(
                'accounting.review_ecl_credit_risk_labels(uuid,text,boolean,text,text,text,text,text,boolean,boolean,text,text,text,text,uuid,uuid)'
            ),
            to_regprocedure('accounting.guard_ecl_cash_recovery_chronology()'),
            to_regprocedure(
                'accounting.record_ecl_forward_looking_evidence(text,text,text,date,date,date,date,timestamp with time zone,date,text,uuid,uuid)'
            ),
            to_regprocedure(
                'accounting.revoke_ecl_forward_looking_evidence(uuid,text,uuid)'
            )
        """
    ).fetchone()
    if any(item is None for item in objects):
        raise SystemExit(
            "ECL verification failed: required protected label/readiness/forward-looking objects are missing"
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
            "ECL credit-risk label verification failed: existing cash-recovery evidence does not match strict accepted_at chronology"
        )

    permissions = connection.execute(
        """
        SELECT permission_code
        FROM core.role_permissions role_permission
        JOIN core.roles role ON role.id = role_permission.role_id
        WHERE role.code = 'management'
          AND permission_code IN (
              'accounting.ecl.credit_risk_label.review',
              'accounting.ecl.forward_looking_evidence.manage'
          )
        ORDER BY permission_code
        """
    ).fetchall()
    if {row[0] for row in permissions} != {
        "accounting.ecl.credit_risk_label.review",
        "accounting.ecl.forward_looking_evidence.manage",
    }:
        raise SystemExit("ECL verification failed: required Management permissions are missing")

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
        raise SystemExit(f"ECL credit-risk label verification failed: policy mismatch {policy!r}")

    label_summary = connection.execute(
        """
        SELECT
            loan_count, dpd_ready_count, dpd_data_required_count,
            label_review_required_count, label_refresh_required_count,
            current_label_ready_count, stage_1_count, stage_2_count,
            stage_3_count, default_count, write_off_supported_count,
            cash_recovery_observed_count, cured_count, quantitative_ecl_ready,
            ecl_amount, ecl_calculation_enabled, account_1190_posting_enabled,
            automatic_source_posting
        FROM accounting.ecl_credit_risk_label_summary
        """
    ).fetchone()
    if label_summary is None:
        raise SystemExit("ECL credit-risk label verification failed: label summary is missing")
    if bool(label_summary[13]) or label_summary[14] is not None or any(
        bool(value) for value in label_summary[15:]
    ):
        raise SystemExit("ECL verification failed: quantitative ECL or posting was unexpectedly enabled")

    forward_summary = connection.execute(
        """
        SELECT
            current_evidence_count, stale_count, superseded_count, revoked_count,
            not_yet_effective_count, current_status_count,
            approved_forward_looking_evidence_ready,
            scenario_probability_defaulted, multiplier_defaulted,
            management_overlay_defaulted, ecl_calculation_enabled,
            account_1190_posting_enabled, automatic_source_posting
        FROM accounting.ecl_forward_looking_evidence_readiness
        """
    ).fetchone()
    if forward_summary is None:
        raise SystemExit("ECL forward-looking evidence verification failed: readiness summary missing")
    if any(bool(value) for value in forward_summary[7:]):
        raise SystemExit(
            "ECL forward-looking evidence verification failed: numeric defaults/calculation/posting unexpectedly enabled"
        )

    readiness_summary = connection.execute(
        """
        SELECT
            loan_count, quantitative_input_ready_count,
            contractual_schedule_dpd_blocked_count,
            credit_risk_label_blocked_count,
            original_eir_initial_carrying_blocked_count,
            protected_history_blocked_count, current_carrying_blocked_count,
            outcome_evidence_blocked_count, forward_looking_evidence_blocked_count,
            quantitative_ecl_ready, ecl_amount, ecl_calculation_enabled,
            account_1190_posting_enabled, automatic_source_posting
        FROM accounting.ecl_quantitative_input_readiness_summary
        """
    ).fetchone()
    if readiness_summary is None:
        raise SystemExit("ECL quantitative input-readiness summary is missing")
    if int(readiness_summary[0]) != int(label_summary[0]):
        raise SystemExit("ECL input-readiness loan population does not match label queue")
    if bool(readiness_summary[9]) or readiness_summary[10] is not None or any(
        bool(value) for value in readiness_summary[11:]
    ):
        raise SystemExit("ECL input-readiness unexpectedly enabled calculation or posting")

    # Installation is evidence-free: it must not fabricate a forecast just to
    # make readiness pass. Existing approved evidence, if any, is preserved.
    evidence_count = _relation_count(connection, "accounting.ecl_forward_looking_evidence")
    if evidence_count == 0:
        if bool(forward_summary[6]) or int(forward_summary[0]) != 0:
            raise SystemExit("ECL forward-looking readiness became true without approved evidence")
        if int(readiness_summary[8]) != int(readiness_summary[0]):
            raise SystemExit(
                "Every current loan must retain the forward-looking blocker while no evidence exists"
            )

    return label_summary, readiness_summary, forward_summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify protected SPINA V1 ECL labels, strict recovery chronology, "
            "per-loan quantitative-input readiness, and forward-looking evidence governance."
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
        raise SystemExit("ECL migration file was not found: " + ", ".join(missing))

    with psycopg.connect(database_url, autocommit=True) as connection:
        prerequisites = connection.execute(
            """
            SELECT
                to_regclass('accounting.ecl_methodology_policy_v1'),
                to_regclass('accounting.loan_contract_dpd_assessment'),
                to_regclass('accounting.greenfield_regular_eir_anchor_readiness'),
                to_regclass('accounting.seven_by_seven_eir_initial_carrying_readiness'),
                to_regclass('accounting.regular_journal_posting_entries'),
                to_regclass('accounting.regular_journal_reversal_sets'),
                to_regclass('accounting.seven_by_seven_journal_postings'),
                to_regclass('accounting.seven_by_seven_journal_reversals')
            """
        ).fetchone()
        if any(item is None for item in prerequisites):
            raise SystemExit(
                "ECL readiness migration refused: protected methodology, DPD, EIR/carrying, posting and reversal foundations must be installed"
            )

        before = _history_counts(connection)
        for migration in MIGRATIONS:
            connection.execute(migration.read_text(encoding="utf-8"))
        label_summary, readiness_summary, forward_summary = _verify(connection)
        after = _history_counts(connection)
        if after != before:
            raise SystemExit(
                f"ECL verification failed: protected/evidence history changed from {before} to {after}"
            )

    print(
        "ECL credit-risk label/readiness live summary: "
        f"loans={label_summary[0]}, dpd_ready={label_summary[1]}, dpd_blocked={label_summary[2]}, "
        f"review_required={label_summary[3]}, refresh_required={label_summary[4]}, "
        f"current_labels={label_summary[5]}, stage1={label_summary[6]}, stage2={label_summary[7]}, "
        f"stage3={label_summary[8]}, defaults={label_summary[9]}, writeoff_supported={label_summary[10]}, "
        f"cash_recovery={label_summary[11]}, cured={label_summary[12]}, "
        f"input_ready={readiness_summary[1]}, schedule_dpd_blocked={readiness_summary[2]}, "
        f"label_blocked={readiness_summary[3]}, eir_anchor_blocked={readiness_summary[4]}, "
        f"protected_history_blocked={readiness_summary[5]}, current_carrying_blocked={readiness_summary[6]}, "
        f"outcome_blocked={readiness_summary[7]}, forward_looking_blocked={readiness_summary[8]}, "
        f"forward_current={forward_summary[0]}, forward_stale={forward_summary[1]}, "
        f"forward_superseded={forward_summary[2]}, forward_revoked={forward_summary[3]}, "
        "history_unchanged=True, strict_cash_recovery_chronology=True, "
        "deterministic_input_blockers=True, forward_looking_governance_installed=True, "
        "quantitative_ecl_ready=False, ecl_calculation_enabled=False, "
        "account_1190_posting_enabled=False, automatic_source_posting=False."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
