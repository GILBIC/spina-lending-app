from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
BASE_TEST_PATH = TEST_DIR / "test_ecl_credit_risk_labels_postgres.py"
_spec = importlib.util.spec_from_file_location("ecl_label_helpers", BASE_TEST_PATH)
assert _spec is not None and _spec.loader is not None
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0070 = (SQL_ROOT / "0070_add_ecl_credit_risk_labels.sql").read_text(
    encoding="utf-8"
)
SQL_0071 = (SQL_ROOT / "0071_harden_ecl_cash_recovery_chronology.sql").read_text(
    encoding="utf-8"
)


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _device(connection: psycopg.Connection, actor_user_id, suffix: str):
    return connection.execute(
        """
        INSERT INTO core.devices (
            user_id, device_identifier_hash, platform, app_version, status
        )
        VALUES (%s, %s, 'android', 'ecl-recovery-chronology-test', 'active')
        RETURNING id
        """,
        (actor_user_id, f"ecl-recovery-device-{suffix}"),
    ).fetchone()[0]


def _collection(
    connection: psycopg.Connection,
    *,
    loan_id,
    actor_user_id,
    device_id,
    suffix: str,
    device_sequence: int,
    accepted_at,
):
    client_id = connection.execute(
        "SELECT client_id FROM lending.loans WHERE id = %s",
        (loan_id,),
    ).fetchone()[0]
    transaction_id = uuid4()
    connection.execute(
        """
        INSERT INTO lending.collection_transactions (
            id,
            idempotency_key,
            loan_id,
            client_id,
            collector_user_id,
            registered_device_id,
            route_entry_id,
            collection_date,
            entry_type,
            amount,
            recorded_at,
            accepted_at,
            device_sequence,
            note,
            previous_balance,
            official_balance,
            pass_count_after,
            receipt_number
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, 'payment', 10.00, %s, %s, %s,
            %s, 1000.00, 990.00, 0, %s
        )
        """,
        (
            transaction_id,
            uuid4(),
            loan_id,
            client_id,
            actor_user_id,
            device_id,
            loan_id,
            accepted_at.date(),
            accepted_at - timedelta(seconds=1),
            accepted_at,
            device_sequence,
            f"ECL recovery chronology fixture {suffix}",
            f"ECLREC-{suffix}-{device_sequence}",
        ),
    )
    return transaction_id


def _insert_recovery_review(
    connection: psycopg.Connection,
    *,
    prior_review_id: int,
    recovery_transaction_id,
    actor_user_id,
    evidence_reference: str,
    review_note: str,
):
    return connection.execute(
        """
        INSERT INTO accounting.ecl_credit_risk_label_reviews (
            loan_id,
            review_version,
            stage_label,
            default_label,
            write_off_label,
            recovery_label,
            primary_evidence_basis,
            evidence_reference,
            review_note,
            snapshot_schedule_id,
            snapshot_schedule_version,
            snapshot_days_past_due,
            snapshot_due_unpaid_amount,
            snapshot_thirty_day_backstop,
            snapshot_ninety_day_backstop,
            snapshot_dpd_risk_band,
            sicr_backstop_rebutted,
            default_backstop_rebutted,
            rebuttal_evidence_reference,
            rebuttal_note,
            write_off_evidence_reference,
            write_off_note,
            recovery_transaction_id,
            reviewer_user_id,
            supersedes_review_id
        )
        SELECT
            prior.loan_id,
            prior.review_version + 1,
            prior.stage_label,
            prior.default_label,
            'none',
            'cash_recovery_observed',
            'protected_collection_history',
            %s,
            %s,
            prior.snapshot_schedule_id,
            prior.snapshot_schedule_version,
            prior.snapshot_days_past_due,
            prior.snapshot_due_unpaid_amount,
            prior.snapshot_thirty_day_backstop,
            prior.snapshot_ninety_day_backstop,
            prior.snapshot_dpd_risk_band,
            prior.sicr_backstop_rebutted,
            prior.default_backstop_rebutted,
            prior.rebuttal_evidence_reference,
            prior.rebuttal_note,
            NULL,
            NULL,
            %s,
            %s,
            prior.id
        FROM accounting.ecl_credit_risk_label_reviews prior
        WHERE prior.id = %s
        RETURNING id
        """,
        (
            evidence_reference,
            review_note,
            recovery_transaction_id,
            actor_user_id,
            prior_review_id,
        ),
    ).fetchone()[0]


def test_cash_recovery_requires_server_acceptance_after_prior_review_even_same_day() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0070))
            connection.execute(_transaction_body(SQL_0071))

            actor_user_id = connection.execute(
                """
                INSERT INTO core.users (username, full_name, status)
                VALUES (%s, %s, 'active')
                RETURNING id
                """,
                (f"ecl-recovery-reviewer-{suffix}", f"ECL Recovery Reviewer {suffix}"),
            ).fetchone()[0]
            loan_id = helpers._create_reviewable_loan(
                connection,
                suffix=f"R-{suffix}",
                actor_user_id=actor_user_id,
                dpd_days=95,
            )
            device_id = _device(connection, actor_user_id, suffix)

            # Establish the reviewed deteriorated state through the ordinary
            # protected review function while the contractual DPD fixture is
            # untouched and known-ready.
            deteriorated_review_id = helpers._review(
                connection,
                loan_id=loan_id,
                actor_user_id=actor_user_id,
                stage="stage_3_credit_impaired",
                default_label=True,
                basis="verified_source_document",
                evidence_reference="DEFAULT-EVIDENCE-A",
                review_note="Protected evidence supports a reviewed deteriorated state.",
            )
            deteriorated_created_at = connection.execute(
                """
                SELECT created_at
                FROM accounting.ecl_credit_risk_label_reviews
                WHERE id = %s
                """,
                (deteriorated_review_id,),
            ).fetchone()[0]

            # Reproduce the exact 0070 weakness without changing the DPD
            # prerequisite: the transaction is inserted after the review, but
            # its immutable accepted_at says it was accepted earlier on the
            # same calendar day. The 0071 table trigger is the final fail-closed
            # boundary even if any caller reaches INSERT with stale chronology.
            before_review_accepted_at = deteriorated_created_at.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            before_review_tx = _collection(
                connection,
                loan_id=loan_id,
                actor_user_id=actor_user_id,
                device_id=device_id,
                suffix=suffix,
                device_sequence=1,
                accepted_at=before_review_accepted_at,
            )
            assert before_review_accepted_at.date() == deteriorated_created_at.date()
            assert before_review_accepted_at <= deteriorated_created_at

            with pytest.raises(psycopg.Error, match="accepted after the prior deteriorated review"):
                with connection.transaction():
                    _insert_recovery_review(
                        connection,
                        prior_review_id=deteriorated_review_id,
                        recovery_transaction_id=before_review_tx,
                        actor_user_id=actor_user_id,
                        evidence_reference="RECOVERY-BEFORE-REVIEW",
                        review_note="This same-day payment predates the reviewed deterioration and must fail.",
                    )

            # A same-day protected payment with accepted_at strictly after the
            # deteriorated review must pass the same database boundary.
            after_review_accepted_at = deteriorated_created_at + timedelta(seconds=1)
            after_review_tx = _collection(
                connection,
                loan_id=loan_id,
                actor_user_id=actor_user_id,
                device_id=device_id,
                suffix=suffix,
                device_sequence=2,
                accepted_at=after_review_accepted_at,
            )
            recovery_review_id = _insert_recovery_review(
                connection,
                prior_review_id=deteriorated_review_id,
                recovery_transaction_id=after_review_tx,
                actor_user_id=actor_user_id,
                evidence_reference="RECOVERY-AFTER-REVIEW",
                review_note="Exact protected payment was accepted after the reviewed deterioration.",
            )
            assert recovery_review_id > deteriorated_review_id

            latest = connection.execute(
                """
                SELECT review_version, recovery_label, recovery_transaction_id
                FROM accounting.ecl_credit_risk_label_reviews
                WHERE loan_id = %s
                ORDER BY review_version DESC
                LIMIT 1
                """,
                (loan_id,),
            ).fetchone()
            assert latest == (2, "cash_recovery_observed", after_review_tx)

            chronology_objects = connection.execute(
                """
                SELECT
                    to_regprocedure('accounting.guard_ecl_cash_recovery_chronology()'),
                    count(*) FILTER (
                        WHERE trigger.tgname = 'ecl_cash_recovery_chronology_guard'
                          AND NOT trigger.tgisinternal
                    )
                FROM pg_trigger trigger
                """
            ).fetchone()
            assert chronology_objects[0] is not None
            assert chronology_objects[1] == 1
        finally:
            connection.rollback()
