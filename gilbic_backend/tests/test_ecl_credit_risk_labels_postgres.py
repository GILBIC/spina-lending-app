from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0070_add_ecl_credit_risk_labels.sql"
).read_text(encoding="utf-8")


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _create_reviewable_loan(
    connection: psycopg.Connection,
    *,
    suffix: str,
    actor_user_id,
    dpd_days: int,
):
    loan_type_id = connection.execute(
        """
        INSERT INTO lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        )
        VALUES (%s, %s, 120, 'custom', 0)
        RETURNING id
        """,
        (f"ECLLBL-{suffix}", f"ECL Label Test {suffix}"),
    ).fetchone()[0]

    client_id = connection.execute(
        """
        INSERT INTO lending.clients (client_code, full_name, status)
        VALUES (%s, %s, 'active')
        RETURNING id
        """,
        (f"ECLLBL-C-{suffix}", f"ECL Label Client {suffix}"),
    ).fetchone()[0]

    loan_id = connection.execute(
        """
        INSERT INTO lending.loans (
            loan_number,
            client_id,
            loan_type_id,
            principal,
            daily_amount,
            date_released,
            due_date,
            status,
            created_by_user_id
        )
        VALUES (
            %s, %s, %s, 1000.00, 0.00,
            current_date - 120, current_date + 30, 'active', %s
        )
        RETURNING id
        """,
        (f"ECLLBL-L-{suffix}", client_id, loan_type_id, actor_user_id),
    ).fetchone()[0]

    schedule_id = connection.execute(
        """
        INSERT INTO lending.loan_contract_schedules (
            loan_id,
            schedule_version,
            payment_frequency,
            contract_reference,
            contract_signed_date,
            effective_from,
            grace_days,
            created_by_user_id
        )
        VALUES (
            %s, 1, 'custom', %s,
            current_date - 120, current_date - 120, 0, %s
        )
        RETURNING id
        """,
        (loan_id, f"ECLLBL-CONTRACT-{suffix}", actor_user_id),
    ).fetchone()[0]

    connection.execute(
        """
        INSERT INTO lending.loan_contract_installments (
            schedule_id,
            installment_number,
            due_date,
            contractual_amount
        )
        VALUES (%s, 1, current_date - %s, 1000.00)
        """,
        (schedule_id, dpd_days),
    )
    return loan_id


def _review(
    connection: psycopg.Connection,
    *,
    loan_id,
    actor_user_id,
    stage: str,
    default_label: bool,
    write_off: str = "none",
    recovery: str = "none",
    basis: str = "contractual_dpd",
    evidence_reference: str = "TEST-EVIDENCE",
    review_note: str = "Evidence-backed test review.",
    sicr_rebutted: bool = False,
    default_rebutted: bool = False,
    rebuttal_reference: str | None = None,
    rebuttal_note: str | None = None,
    write_off_reference: str | None = None,
    write_off_note: str | None = None,
    recovery_transaction_id=None,
):
    return connection.execute(
        """
        SELECT accounting.review_ecl_credit_risk_labels(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            loan_id,
            stage,
            default_label,
            write_off,
            recovery,
            basis,
            evidence_reference,
            review_note,
            sicr_rebutted,
            default_rebutted,
            rebuttal_reference,
            rebuttal_note,
            write_off_reference,
            write_off_note,
            recovery_transaction_id,
            actor_user_id,
        ),
    ).fetchone()[0]


def test_ecl_credit_risk_labels_are_evidence_backed_immutable_and_non_posting() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "SELECT to_regclass('accounting.ecl_methodology_policy_v1')"
        ).fetchone()[0] is None:
            pytest.skip("0069 ECL methodology/source policy is not installed")
        if connection.execute(
            "SELECT to_regclass('accounting.loan_contract_dpd_assessment')"
        ).fetchone()[0] is None:
            pytest.skip("Contract-driven DPD foundation is not installed")

        before_history = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM accounting.journal_entries),
                (SELECT count(*) FROM accounting.journal_lines),
                (SELECT count(*) FROM accounting.ecl_outcome_label_reviews)
            """
        ).fetchone()

        try:
            connection.execute(_transaction_body(SQL))

            actor_user_id = connection.execute(
                """
                INSERT INTO core.users (username, full_name, status)
                VALUES (%s, %s, 'active')
                RETURNING id
                """,
                (f"ecl-label-reviewer-{suffix}", f"ECL Label Reviewer {suffix}"),
            ).fetchone()[0]

            ninety_plus_loan = _create_reviewable_loan(
                connection,
                suffix=f"N-{suffix}",
                actor_user_id=actor_user_id,
                dpd_days=95,
            )
            sub_thirty_loan = _create_reviewable_loan(
                connection,
                suffix=f"S-{suffix}",
                actor_user_id=actor_user_id,
                dpd_days=10,
            )

            dpd = connection.execute(
                """
                SELECT days_past_due, thirty_day_sicr_backstop_reached,
                       ninety_day_default_backstop_reached
                FROM accounting.loan_contract_dpd_assessment
                WHERE loan_id = %s
                """,
                (ninety_plus_loan,),
            ).fetchone()
            assert dpd == (95, True, True)

            with pytest.raises(psycopg.Error, match="90-DPD default backstop"):
                with connection.transaction():
                    _review(
                        connection,
                        loan_id=ninety_plus_loan,
                        actor_user_id=actor_user_id,
                        stage="stage_2_lifetime",
                        default_label=False,
                        basis="verified_source_document",
                    )

            first_review = _review(
                connection,
                loan_id=ninety_plus_loan,
                actor_user_id=actor_user_id,
                stage="stage_2_lifetime",
                default_label=False,
                basis="verified_source_document",
                default_rebutted=True,
                rebuttal_reference="REBUT-90-A",
                rebuttal_note="Separate source evidence supports non-default beyond the backstop.",
            )
            assert first_review > 0

            with pytest.raises(psycopg.Error, match="Write-off support requires explicit"):
                with connection.transaction():
                    _review(
                        connection,
                        loan_id=ninety_plus_loan,
                        actor_user_id=actor_user_id,
                        stage="stage_3_credit_impaired",
                        default_label=True,
                        write_off="supported_no_reasonable_expectation_of_recovery",
                        basis="verified_source_document",
                    )

            write_off_review = _review(
                connection,
                loan_id=ninety_plus_loan,
                actor_user_id=actor_user_id,
                stage="stage_3_credit_impaired",
                default_label=True,
                write_off="supported_no_reasonable_expectation_of_recovery",
                basis="verified_source_document",
                evidence_reference="WRITE-OFF-SUPPORT-A",
                review_note="Management reviewed evidence of no reasonable expectation of recovery.",
                write_off_reference="WRITE-OFF-EVIDENCE-A",
                write_off_note="Support label only; no write-off journal is executed.",
            )
            assert write_off_review > first_review

            cured_review = _review(
                connection,
                loan_id=ninety_plus_loan,
                actor_user_id=actor_user_id,
                stage="stage_2_lifetime",
                default_label=False,
                recovery="cured",
                basis="protected_collection_history",
                evidence_reference="CURE-EVIDENCE-A",
                review_note="Protected evidence supports a reviewed cure; no ECL reversal is posted here.",
                default_rebutted=True,
                rebuttal_reference="REBUT-90-CURE-A",
                rebuttal_note="Separate current evidence rebuts the 90-DPD default backstop.",
            )
            assert cured_review > write_off_review

            with pytest.raises(psycopg.Error, match="before the 30-DPD backstop"):
                with connection.transaction():
                    _review(
                        connection,
                        loan_id=sub_thirty_loan,
                        actor_user_id=actor_user_id,
                        stage="stage_2_lifetime",
                        default_label=False,
                        basis="contractual_dpd",
                    )

            qualitative_review = _review(
                connection,
                loan_id=sub_thirty_loan,
                actor_user_id=actor_user_id,
                stage="stage_2_lifetime",
                default_label=False,
                basis="verified_qualitative_credit_event",
                evidence_reference="QUAL-EVENT-B",
                review_note="Verified qualitative event supports lifetime-ECL staging before 30 DPD.",
            )
            assert qualitative_review > 0

            queue_rows = connection.execute(
                """
                SELECT loan_id, current_dpd_risk_band, stage_label, default_label,
                       recovery_label, current_label_ready, label_review_status,
                       quantitative_ecl_ready, ecl_calculation_enabled,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_credit_risk_label_queue
                WHERE loan_id IN (%s, %s)
                ORDER BY loan_id
                """,
                (ninety_plus_loan, sub_thirty_loan),
            ).fetchall()
            assert len(queue_rows) == 2
            assert all(row[5] is True and row[6] == "label_reviewed" for row in queue_rows)
            assert all(row[7:] == (False, False, False, False) for row in queue_rows)

            latest_ninety = connection.execute(
                """
                SELECT review_version, stage_label, default_label, write_off_label,
                       recovery_label, supersedes_review_id
                FROM accounting.ecl_credit_risk_label_reviews
                WHERE loan_id = %s
                ORDER BY review_version DESC
                LIMIT 1
                """,
                (ninety_plus_loan,),
            ).fetchone()
            assert latest_ninety[:5] == (
                3,
                "stage_2_lifetime",
                False,
                "none",
                "cured",
            )
            assert latest_ninety[5] == write_off_review

            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE accounting.ecl_credit_risk_label_reviews SET review_note = 'tamper' WHERE id = %s",
                        (first_review,),
                    )

            policy = connection.execute(
                """
                SELECT automatic_staging_enabled, automatic_default_enabled,
                       automatic_write_off_enabled, automatic_recovery_enabled,
                       quantitative_ecl_ready, ecl_calculation_enabled,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_credit_risk_label_policy_v1
                """
            ).fetchone()
            assert policy == (False, False, False, False, False, False, False, False)

            after_history = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.journal_lines),
                    (SELECT count(*) FROM accounting.ecl_outcome_label_reviews)
                """
            ).fetchone()
            assert after_history == before_history
        finally:
            connection.rollback()
