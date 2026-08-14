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
    SQL_ROOT / "0075_add_read_only_quantitative_ecl_measurement.sql",
    SQL_ROOT / "0076_harden_read_only_quantitative_ecl_measurement.sql",
    SQL_ROOT / "0077_add_protected_ecl_allowance_posting.sql",
    SQL_ROOT / "0078_harden_ecl_allowance_posting_queue.sql",
    SQL_ROOT / "0079_add_ecl_remeasurement_writeoff_recovery.sql",
    SQL_ROOT / "0080_harden_ecl_post_writeoff_boundaries.sql",
)

_HISTORY_RELATIONS = (
    "accounting.ecl_credit_risk_label_reviews",
    "accounting.ecl_forward_looking_evidence",
    "accounting.ecl_forward_looking_evidence_revocations",
    "accounting.ecl_quantitative_measurements",
    "accounting.ecl_allowance_draft_preparations",
    "accounting.ecl_allowance_postings",
    "accounting.ecl_allowance_posting_lines",
    "accounting.ecl_allowance_remeasurements",
    "accounting.ecl_accounting_writeoffs",
    "accounting.ecl_post_writeoff_recoveries",
    "accounting.ecl_post_writeoff_recovery_review_provenance",
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
    if relation not in _HISTORY_RELATIONS:
        raise ValueError(f"Unsupported relation count: {relation}")
    exists = connection.execute("SELECT to_regclass(%s)", (relation,)).fetchone()[0]
    if exists is None:
        return 0
    return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])


def _history_counts(connection: psycopg.Connection) -> tuple[int, ...]:
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
        *(_relation_count(connection, relation) for relation in _HISTORY_RELATIONS),
    )


def _verify_required_objects(connection: psycopg.Connection) -> None:
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
            to_regclass('accounting.ecl_quantitative_measurements'),
            to_regclass('accounting.ecl_quantitative_measurement_queue'),
            to_regclass('accounting.ecl_quantitative_measurement_summary'),
            to_regclass('accounting.ecl_allowance_draft_preparations'),
            to_regclass('accounting.ecl_allowance_postings'),
            to_regclass('accounting.ecl_allowance_posting_lines'),
            to_regclass('accounting.ecl_allowance_posting_queue'),
            to_regclass('accounting.ecl_allowance_posting_summary'),
            to_regclass('accounting.ecl_allowance_remeasurements'),
            to_regclass('accounting.ecl_accounting_writeoffs'),
            to_regclass('accounting.ecl_post_writeoff_recoveries'),
            to_regclass('accounting.ecl_post_writeoff_recovery_review_provenance'),
            to_regclass('accounting.ecl_a5_action_queue'),
            to_regclass('accounting.ecl_a5_summary'),
            to_regprocedure(
                'accounting.review_ecl_credit_risk_labels(uuid,text,boolean,text,text,text,text,text,boolean,boolean,text,text,text,text,uuid,uuid)'
            ),
            to_regprocedure('accounting.guard_ecl_cash_recovery_chronology()'),
            to_regprocedure(
                'accounting.record_ecl_forward_looking_evidence(text,text,text,date,date,date,date,timestamp with time zone,date,text,uuid,uuid)'
            ),
            to_regprocedure('accounting.revoke_ecl_forward_looking_evidence(uuid,text,uuid)'),
            to_regprocedure(
                'accounting.record_read_only_quantitative_ecl_measurement(uuid,date,jsonb,text,uuid)'
            ),
            to_regprocedure(
                'accounting.prepare_initial_ecl_allowance_journal(uuid,uuid,text,text,numeric,date,uuid,uuid,uuid,numeric,text)'
            ),
            to_regprocedure(
                'accounting.post_initial_ecl_allowance_journal(uuid,uuid,text,uuid,text,uuid,text,text,date,uuid,uuid,uuid,numeric,numeric,text)'
            ),
            to_regprocedure('accounting.ecl_loan_allowance_balance(uuid)'),
            to_regprocedure(
                'accounting.post_ecl_allowance_remeasurement(uuid,uuid,text,text,numeric,numeric,date,uuid,uuid,uuid,text)'
            ),
            to_regprocedure(
                'accounting.post_ecl_full_writeoff(uuid,uuid,text,bigint,uuid,text,numeric,numeric,numeric,numeric,uuid,uuid,uuid,date,uuid,text)'
            ),
            to_regprocedure(
                'accounting.review_ecl_post_writeoff_recovery(uuid,uuid,text,uuid,numeric,text,text,text)'
            ),
            to_regprocedure(
                'accounting.post_ecl_post_writeoff_recovery(bigint,uuid,text,uuid,numeric,date,uuid,uuid,uuid,text)'
            ),
            to_regprocedure('accounting.guard_ecl_post_writeoff_loan_insert()'),
            to_regprocedure('accounting.guard_ecl_post_writeoff_collection_accounting()')
        """
    ).fetchone()
    if any(item is None for item in objects):
        raise SystemExit(
            "ECL verification failed: required A1-A5 protected label/readiness/measurement/allowance/write-off/recovery objects are missing"
        )


def _verify_triggers(connection: psycopg.Connection) -> None:
    required = {
        ("ecl_credit_risk_label_reviews", "ecl_cash_recovery_chronology_guard"),
        ("ecl_quantitative_measurements", "accounting_ecl_post_writeoff_measurement_guard"),
        ("ecl_allowance_draft_preparations", "accounting_ecl_post_writeoff_allowance_preparation_guard"),
        ("ecl_allowance_postings", "accounting_ecl_post_writeoff_allowance_posting_guard"),
        ("ecl_allowance_remeasurements", "accounting_ecl_post_writeoff_remeasurement_guard"),
        ("regular_journal_posting_entries", "accounting_ecl_post_writeoff_regular_collection_guard"),
        ("seven_by_seven_journal_postings", "accounting_ecl_post_writeoff_7x7_collection_guard"),
        (
            "ecl_post_writeoff_recovery_review_provenance",
            "accounting_ecl_post_writeoff_recovery_review_audit_guard",
        ),
    }
    found = set(
        connection.execute(
            """
            SELECT relation.relname, trigger.tgname
            FROM pg_trigger trigger
            JOIN pg_class relation ON relation.oid = trigger.tgrelid
            JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'accounting'
              AND NOT trigger.tgisinternal
            """
        ).fetchall()
    )
    missing = sorted(required - found)
    if missing:
        raise SystemExit(f"ECL verification failed: required protected triggers are missing {missing!r}")


def _verify_permissions(connection: psycopg.Connection) -> None:
    expected = {
        "accounting.ecl.credit_risk_label.review",
        "accounting.ecl.forward_looking_evidence.manage",
        "accounting.ecl.measurement.review",
        "accounting.ecl.allowance.prepare",
        "accounting.ecl.allowance.post",
        "accounting.ecl.remeasurement.post",
        "accounting.ecl.writeoff.post",
        "accounting.ecl.recovery.review",
        "accounting.ecl.recovery.post",
    }
    rows = connection.execute(
        """
        SELECT permission_code
        FROM core.role_permissions role_permission
        JOIN core.roles role ON role.id = role_permission.role_id
        WHERE role.code = 'management'
          AND permission_code = ANY(%s)
        """,
        (list(expected),),
    ).fetchall()
    actual = {row[0] for row in rows}
    if actual != expected:
        raise SystemExit(
            f"ECL verification failed: required Management permissions are missing {sorted(expected - actual)!r}"
        )


def _verify_accounts(connection: psycopg.Connection) -> None:
    rows = connection.execute(
        """
        SELECT code, system_key, account_type, normal_balance, is_posting, is_active
        FROM accounting.accounts
        WHERE system_key IN (
            'cash_collector_custody',
            'credit_loss_expense',
            'allowance_expected_credit_loss'
        )
        ORDER BY system_key
        """
    ).fetchall()
    expected = [
        ("1190", "allowance_expected_credit_loss", "asset", "credit", True, True),
        ("1020", "cash_collector_custody", "asset", "debit", True, True),
        ("5000", "credit_loss_expense", "expense", "debit", True, True),
    ]
    if rows != expected:
        raise SystemExit(f"A5 accounting refused: protected 1020/1190/5000 identities are invalid {rows!r}")


def _verify_existing_recovery_chronology(connection: psycopg.Connection) -> None:
    invalid = connection.execute(
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
    if int(invalid) != 0:
        raise SystemExit(
            "ECL verification failed: existing cash-recovery evidence violates strict accepted_at chronology"
        )


def _verify(connection: psycopg.Connection) -> tuple[tuple, tuple, tuple, tuple, tuple, tuple]:
    _verify_required_objects(connection)
    _verify_triggers(connection)
    _verify_permissions(connection)
    _verify_accounts(connection)
    _verify_existing_recovery_chronology(connection)

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
    if policy is None or policy[:8] != expected_prefix or any(bool(value) for value in policy[8:]):
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
    if label_summary is None or bool(label_summary[13]) or label_summary[14] is not None or any(
        bool(value) for value in label_summary[15:]
    ):
        raise SystemExit("ECL label verification unexpectedly enabled automatic quantitative ECL/posting")

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
    if forward_summary is None or any(bool(value) for value in forward_summary[7:]):
        raise SystemExit(
            "ECL forward-looking verification unexpectedly defaulted numeric assumptions or enabled posting"
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
    if readiness_summary is None or int(readiness_summary[0]) != int(label_summary[0]):
        raise SystemExit("ECL quantitative input-readiness summary is missing or population mismatched")
    if bool(readiness_summary[9]) or readiness_summary[10] is not None or any(
        bool(value) for value in readiness_summary[11:]
    ):
        raise SystemExit("A1/A2 readiness unexpectedly enabled allowance posting")

    measurement_summary = connection.execute(
        """
        SELECT
            loan_count, input_ready_count, input_blocked_count,
            measurement_required_count, new_measurement_required_count,
            measured_count, authoritative_ecl_total,
            read_only_ecl_calculation_enabled,
            account_1190_posting_enabled, automatic_source_posting
        FROM accounting.ecl_quantitative_measurement_summary
        """
    ).fetchone()
    if measurement_summary is None or int(measurement_summary[0]) != int(readiness_summary[0]):
        raise SystemExit("A3 measurement queue population does not match A1/A2 readiness")
    if not bool(measurement_summary[7]) or bool(measurement_summary[8]) or bool(measurement_summary[9]):
        raise SystemExit("A3 measurement safety flags are invalid")

    allowance_summary = connection.execute(
        """
        SELECT
            loan_count, measurement_not_authoritative_count,
            no_allowance_required_count, preparation_required_count,
            posting_ready_count, posted_current_count,
            a5_remeasurement_required_count, posting_audit_incomplete_count,
            preparation_blocked_count, protected_allowance_balance_total,
            account_1190_posting_enabled, automatic_source_posting
        FROM accounting.ecl_allowance_posting_summary
        """
    ).fetchone()
    if allowance_summary is None or int(allowance_summary[0]) != int(measurement_summary[0]):
        raise SystemExit("A4 allowance queue population does not match A3 measurement queue")
    if not bool(allowance_summary[10]) or bool(allowance_summary[11]):
        raise SystemExit("A4 allowance posting safety flags are invalid")

    a5_summary = connection.execute(
        """
        SELECT
            loan_count, remeasurement_required_count, allowance_current_count,
            writeoff_ready_count, written_off_count, recovery_ready_count,
            blocked_count, remeasurement_posting_count, writeoff_posting_count,
            post_writeoff_recovery_count, protected_a5_accounting_enabled,
            automatic_source_posting
        FROM accounting.ecl_a5_summary
        """
    ).fetchone()
    if a5_summary is None or not bool(a5_summary[10]) or bool(a5_summary[11]):
        raise SystemExit("A5 protected accounting safety flags are invalid")
    if int(a5_summary[0]) != int(label_summary[0]):
        raise SystemExit("A5 action queue population does not match the protected loan population")

    measurement_count = _relation_count(connection, "accounting.ecl_quantitative_measurements")
    if measurement_count == 0:
        if int(measurement_summary[5]) != 0 or measurement_summary[6] != 0:
            raise SystemExit("A3 installation fabricated an authoritative ECL amount")
        if int(measurement_summary[2]) + int(measurement_summary[3]) != int(measurement_summary[0]):
            raise SystemExit("Every unmeasured loan must remain input-blocked or measurement-required")

    evidence_count = _relation_count(connection, "accounting.ecl_forward_looking_evidence")
    if evidence_count == 0:
        if bool(forward_summary[6]) or int(forward_summary[0]) != 0:
            raise SystemExit("Forward-looking readiness became true without approved evidence")
        if int(readiness_summary[8]) != int(readiness_summary[0]):
            raise SystemExit("Every current loan must retain the forward-looking blocker without evidence")

    return (
        label_summary,
        readiness_summary,
        forward_summary,
        measurement_summary,
        allowance_summary,
        a5_summary,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify protected SPINA V1 ECL controls through A5 controlled "
            "remeasurement, full write-off and exact post-write-off recovery."
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
                "ECL migration refused: protected methodology, DPD, EIR/carrying, posting and reversal foundations must be installed"
            )

        before = _history_counts(connection)
        for migration in MIGRATIONS:
            connection.execute(migration.read_text(encoding="utf-8"))
        (
            label_summary,
            readiness_summary,
            forward_summary,
            measurement_summary,
            allowance_summary,
            a5_summary,
        ) = _verify(connection)
        after = _history_counts(connection)
        if after != before:
            raise SystemExit(
                "ECL installation verification failed: schema/control installation changed protected financial/evidence history "
                f"from {before} to {after}"
            )

    print(
        "ECL label/readiness/measurement/allowance/A5 live summary: "
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
        f"measurement_input_blocked={measurement_summary[2]}, measurement_required={measurement_summary[3]}, "
        f"measurement_refresh_required={measurement_summary[4]}, measured={measurement_summary[5]}, "
        f"authoritative_ecl_total={measurement_summary[6]}, "
        f"allowance_preparation_required={allowance_summary[3]}, allowance_posting_ready={allowance_summary[4]}, "
        f"allowance_posted_current={allowance_summary[5]}, allowance_a5_required={allowance_summary[6]}, "
        f"allowance_total={allowance_summary[9]}, a5_remeasurement_required={a5_summary[1]}, "
        f"a5_allowance_current={a5_summary[2]}, a5_writeoff_ready={a5_summary[3]}, "
        f"a5_written_off={a5_summary[4]}, a5_recovery_ready={a5_summary[5]}, "
        f"a5_remeasurement_postings={a5_summary[7]}, a5_writeoffs={a5_summary[8]}, "
        f"a5_recoveries={a5_summary[9]}, history_unchanged=True, "
        "strict_cash_recovery_chronology=True, deterministic_input_blockers=True, "
        "forward_looking_governance_installed=True, read_only_ecl_calculation_enabled=True, "
        "protected_account_1190_posting_enabled=True, protected_a5_accounting_enabled=True, "
        "automatic_source_posting=False."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
