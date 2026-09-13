from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0096 = (SQL_ROOT / "0096_separate_collection_receipt_cash_from_loan_application.sql").read_text(
    encoding="utf-8"
)
SQL_0117 = (SQL_ROOT / "0117_add_7x7_pricing_compliance_readiness.sql").read_text(
    encoding="utf-8"
)
SQL_0118 = (SQL_ROOT / "0118_add_7x7_post_maturity_penalty_authority.sql").read_text(
    encoding="utf-8"
)


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _create_payment(
    connection,
    *,
    suffix: str,
    loan_id,
    client_id,
    actor_id,
    device_id,
    collection_date: date,
    sequence: int,
    amount: str,
):
    return connection.execute(
        """
        insert into lending.collection_transactions (
            idempotency_key,
            loan_id,
            client_id,
            collector_user_id,
            registered_device_id,
            route_entry_id,
            collection_date,
            entry_type,
            amount,
            applied_amount,
            unallocated_amount,
            allocation_state,
            recorded_at,
            device_sequence,
            note,
            previous_balance,
            official_balance,
            pass_count_after,
            advance_until_after,
            receipt_number,
            details
        ) values (
            %s, %s, %s, %s, %s, %s, %s, 'payment',
            %s, %s, 0.00, 'fully_allocated', now(), %s, '',
            3000.00, 3000.00, 0, null, %s, '{}'::jsonb
        )
        returning id
        """,
        (
            uuid4(),
            loan_id,
            client_id,
            actor_id,
            device_id,
            loan_id,
            collection_date,
            amount,
            amount,
            sequence,
            f"X7-PEN-R-{suffix}-{sequence}",
        ),
    ).fetchone()[0]


def _create_assessment(
    connection,
    *,
    loan_id,
    schedule_id,
    review_id,
    fingerprint: str,
    source_transaction_id,
    assessment_date: date,
    amount: str,
):
    return connection.execute(
        """
        insert into lending.seven_by_seven_penalty_assessments (
            loan_id,
            schedule_id,
            pricing_compliance_review_id,
            terms_fingerprint,
            assessment_start_date,
            assessed_through_date,
            opening_penalty_base,
            calculation_evidence,
            contractual_monthly_rate,
            legal_rate_ceiling,
            effective_monthly_rate,
            penalty_proration_days,
            theoretical_penalty_exact,
            opening_cost_headroom,
            assessed_penalty_amount,
            source_transaction_id
        ) values (
            %s, %s, %s, %s, %s, %s,
            1000.00, '{"proof":"task1"}'::jsonb,
            0.030000, 0.050000, 0.030000, 30,
            %s, 1000.00, %s, %s
        )
        returning id
        """,
        (
            loan_id,
            schedule_id,
            review_id,
            fingerprint,
            assessment_date,
            assessment_date,
            amount,
            amount,
            source_transaction_id,
        ),
    ).fetchone()[0]


def test_exact_term_pricing_compliance_review_is_append_only_and_fail_closed() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    ready_fingerprint = "a" * 64
    changed_fingerprint = "b" * 64
    penalty_fingerprint = "c" * 64

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0096))
            connection.execute(_transaction_body(SQL_0117))
            connection.execute(_transaction_body(SQL_0118))

            actor_id = connection.execute(
                """
                insert into core.users (username, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"x7-ready-{suffix}", f"7x7 Readiness Reviewer {suffix}"),
            ).fetchone()[0]
            device_id = connection.execute(
                """
                insert into core.devices (
                    user_id, device_identifier_hash, platform, status
                ) values (%s, %s, 'desktop', 'active')
                returning id
                """,
                (actor_id, f"x7-ready-device-{suffix}"),
            ).fetchone()[0]
            client_id = connection.execute(
                """
                insert into lending.clients (client_code, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"X7-RDY-C-{suffix}", f"7x7 Readiness Client {suffix}"),
            ).fetchone()[0]
            loan_type_id = connection.execute(
                """
                insert into lending.loan_types (
                    code, name, term_days, calculation_mode,
                    daily_interest_per_1000, settings
                ) values (%s, %s, 60, 'seven_by_seven', 7.00, '{}'::jsonb)
                returning id
                """,
                (f"X7-RDY-{suffix}", f"7x7 Readiness {suffix}"),
            ).fetchone()[0]
            loan_id = connection.execute(
                """
                insert into lending.loans (
                    loan_number, client_id, loan_type_id, principal, daily_amount,
                    date_released, due_date, status, created_by_user_id
                ) values (%s, %s, %s, 3000.00, 50.00, %s, %s, 'active', %s)
                returning id
                """,
                (
                    f"X7-RDY-L-{suffix}",
                    client_id,
                    loan_type_id,
                    date(2093, 1, 1),
                    date(2093, 4, 15),
                    actor_id,
                ),
            ).fetchone()[0]

            first_review_id = connection.execute(
                """
                insert into lending.seven_by_seven_pricing_compliance_reviews (
                    loan_id, terms_fingerprint,
                    applicability_review_ready, pricing_cap_review_ready,
                    disclosure_ready, total_cost_cap_review_ready,
                    evidence_reference, review_note, reviewed_by_user_id
                ) values (%s, %s, true, true, true, true, %s, %s, %s)
                returning id
                """,
                (
                    loan_id,
                    ready_fingerprint,
                    f"X7-RDY-EVIDENCE-{suffix}",
                    "Exact proposed terms reviewed and all readiness evidence is complete.",
                    actor_id,
                ),
            ).fetchone()[0]

            legacy_penalty_authority = connection.execute(
                """
                select
                    penalty_policy_version,
                    penalty_monthly_rate,
                    penalty_proration_days,
                    penalty_rate_ceiling,
                    lifetime_nonprincipal_cost_ceiling,
                    counted_nonprincipal_cost_at_contract_lock
                from lending.seven_by_seven_pricing_compliance_reviews
                where id = %s
                """,
                (first_review_id,),
            ).fetchone()
            assert legacy_penalty_authority == (None, None, None, None, None, None)

            connection.execute("savepoint immutable_review")
            with pytest.raises(psycopg.Error):
                connection.execute(
                    """
                    update lending.seven_by_seven_pricing_compliance_reviews
                    set disclosure_ready = false
                    where id = %s
                    """,
                    (first_review_id,),
                )
            connection.execute("rollback to savepoint immutable_review")

            connection.execute(
                """
                insert into lending.seven_by_seven_pricing_compliance_reviews (
                    loan_id, terms_fingerprint,
                    applicability_review_ready, pricing_cap_review_ready,
                    disclosure_ready, total_cost_cap_review_ready,
                    evidence_reference, review_note, reviewed_by_user_id
                ) values (%s, %s, true, true, false, true, %s, %s, %s)
                """,
                (
                    loan_id,
                    ready_fingerprint,
                    f"X7-RDY-REVIEW-{suffix}",
                    "A newer exact-term review marks disclosure readiness unresolved.",
                    actor_id,
                ),
            )
            connection.execute(
                """
                insert into lending.seven_by_seven_pricing_compliance_reviews (
                    loan_id, terms_fingerprint,
                    applicability_review_ready, pricing_cap_review_ready,
                    disclosure_ready, total_cost_cap_review_ready,
                    evidence_reference, review_note, reviewed_by_user_id
                ) values (%s, %s, true, true, true, true, %s, %s, %s)
                """,
                (
                    loan_id,
                    changed_fingerprint,
                    f"X7-RDY-CHANGED-{suffix}",
                    "Different proposed terms require and receive their own exact-term review.",
                    actor_id,
                ),
            )

            connection.execute("savepoint incomplete_penalty_authority")
            with pytest.raises(psycopg.Error):
                connection.execute(
                    """
                    insert into lending.seven_by_seven_pricing_compliance_reviews (
                        loan_id, terms_fingerprint,
                        applicability_review_ready, pricing_cap_review_ready,
                        disclosure_ready, total_cost_cap_review_ready,
                        evidence_reference, review_note, reviewed_by_user_id,
                        penalty_policy_version
                    ) values (
                        %s, %s, true, true, true, true, %s, %s, %s, 'v1'
                    )
                    """,
                    (
                        loan_id,
                        penalty_fingerprint,
                        f"X7-PEN-INCOMPLETE-{suffix}",
                        "Incomplete penalty authority must fail the all-or-complete constraint.",
                        actor_id,
                    ),
                )
            connection.execute("rollback to savepoint incomplete_penalty_authority")

            penalty_review_id = connection.execute(
                """
                insert into lending.seven_by_seven_pricing_compliance_reviews (
                    loan_id, terms_fingerprint,
                    applicability_review_ready, pricing_cap_review_ready,
                    disclosure_ready, total_cost_cap_review_ready,
                    evidence_reference, review_note, reviewed_by_user_id,
                    penalty_policy_version, penalty_monthly_rate,
                    penalty_proration_days, penalty_rate_ceiling,
                    lifetime_nonprincipal_cost_ceiling,
                    counted_nonprincipal_cost_at_contract_lock
                ) values (
                    %s, %s, true, true, true, true, %s, %s, %s,
                    '7x7-penalty-v1', 0.030000, 30, 0.050000,
                    3000.00, 1260.00
                )
                returning id
                """,
                (
                    loan_id,
                    penalty_fingerprint,
                    f"X7-PEN-AUTH-{suffix}",
                    "Exact signed penalty policy and legal cap authority are evidenced.",
                    actor_id,
                ),
            ).fetchone()[0]

            latest_same_terms = connection.execute(
                """
                select applicability_review_ready, pricing_cap_review_ready,
                       disclosure_ready, total_cost_cap_review_ready
                from lending.seven_by_seven_pricing_compliance_reviews
                where loan_id = %s and terms_fingerprint = %s
                order by reviewed_at desc, id desc
                limit 1
                """,
                (loan_id, ready_fingerprint),
            ).fetchone()
            assert latest_same_terms == (True, True, False, True)

            different_terms_count = connection.execute(
                """
                select count(*)
                from lending.seven_by_seven_pricing_compliance_reviews
                where loan_id = %s and terms_fingerprint = %s
                """,
                (loan_id, changed_fingerprint),
            ).fetchone()[0]
            assert different_terms_count == 1

            schedule_id = connection.execute(
                """
                insert into lending.loan_contract_schedules (
                    loan_id, schedule_version, status, payment_frequency,
                    contract_reference, contract_signed_date, effective_from,
                    grace_days, created_by_user_id
                ) values (
                    %s, 1, 'active', 'daily', %s, %s, %s, 0, %s
                )
                returning id
                """,
                (
                    loan_id,
                    f"X7-PEN-CONTRACT-{suffix}",
                    date(2093, 1, 1),
                    date(2093, 1, 2),
                    actor_id,
                ),
            ).fetchone()[0]
            installment_id = connection.execute(
                """
                insert into lending.loan_contract_installments (
                    schedule_id, installment_number, due_date,
                    contractual_amount, principal_component, interest_component
                ) values (%s, 1, %s, 50.00, 29.00, 21.00)
                returning id
                """,
                (schedule_id, date(2093, 1, 2)),
            ).fetchone()[0]

            paid_transaction = _create_payment(
                connection,
                suffix=suffix,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                collection_date=date(2093, 4, 16),
                sequence=1,
                amount="60.00",
            )
            first_assessment_id = _create_assessment(
                connection,
                loan_id=loan_id,
                schedule_id=schedule_id,
                review_id=penalty_review_id,
                fingerprint=penalty_fingerprint,
                source_transaction_id=paid_transaction,
                assessment_date=date(2093, 4, 16),
                amount="1.00",
            )
            connection.execute(
                """
                insert into lending.seven_by_seven_penalty_payment_allocations (
                    loan_id, transaction_id, amount_applied
                ) values (%s, %s, 1.00)
                """,
                (loan_id, paid_transaction),
            )

            evidence = connection.execute(
                """
                select assessed_penalty, penalty_paid, penalty_outstanding, ready_to_post
                from accounting.seven_by_seven_penalty_evidence
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert evidence == (1, 1, 0, False)

            connection.execute("savepoint immutable_assessment")
            with pytest.raises(psycopg.Error):
                connection.execute(
                    """
                    update lending.seven_by_seven_penalty_assessments
                    set opening_penalty_base = 999.00
                    where id = %s
                    """,
                    (first_assessment_id,),
                )
            connection.execute("rollback to savepoint immutable_assessment")

            installment_first_transaction = _create_payment(
                connection,
                suffix=suffix,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                collection_date=date(2093, 4, 17),
                sequence=2,
                amount="50.00",
            )
            connection.execute(
                """
                insert into lending.loan_installment_payment_allocations (
                    installment_id, transaction_id, amount_applied,
                    allocation_basis, allocation_reference
                ) values (%s, %s, 45.00, 'manual_review', 'task1-installment-first')
                """,
                (installment_id, installment_first_transaction),
            )
            _create_assessment(
                connection,
                loan_id=loan_id,
                schedule_id=schedule_id,
                review_id=penalty_review_id,
                fingerprint=penalty_fingerprint,
                source_transaction_id=installment_first_transaction,
                assessment_date=date(2093, 4, 17),
                amount="10.00",
            )
            connection.execute("savepoint installment_first_guard")
            with pytest.raises(psycopg.Error):
                connection.execute(
                    """
                    insert into lending.seven_by_seven_penalty_payment_allocations (
                        loan_id, transaction_id, amount_applied
                    ) values (%s, %s, 10.00)
                    """,
                    (loan_id, installment_first_transaction),
                )
            connection.execute("rollback to savepoint installment_first_guard")

            penalty_first_transaction = _create_payment(
                connection,
                suffix=suffix,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
                collection_date=date(2093, 4, 18),
                sequence=3,
                amount="50.00",
            )
            _create_assessment(
                connection,
                loan_id=loan_id,
                schedule_id=schedule_id,
                review_id=penalty_review_id,
                fingerprint=penalty_fingerprint,
                source_transaction_id=penalty_first_transaction,
                assessment_date=date(2093, 4, 18),
                amount="10.00",
            )
            connection.execute(
                """
                insert into lending.seven_by_seven_penalty_payment_allocations (
                    loan_id, transaction_id, amount_applied
                ) values (%s, %s, 10.00)
                """,
                (loan_id, penalty_first_transaction),
            )
            connection.execute("savepoint penalty_first_guard")
            with pytest.raises(psycopg.Error):
                connection.execute(
                    """
                    insert into lending.loan_installment_payment_allocations (
                        installment_id, transaction_id, amount_applied,
                        allocation_basis, allocation_reference
                    ) values (%s, %s, 45.00, 'manual_review', 'task1-penalty-first')
                    """,
                    (installment_id, penalty_first_transaction),
                )
            connection.execute("rollback to savepoint penalty_first_guard")
        finally:
            connection.rollback()
