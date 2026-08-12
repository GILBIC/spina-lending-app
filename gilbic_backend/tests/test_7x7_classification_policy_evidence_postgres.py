from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_0062 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0062_add_7x7_classification_policy_evidence.sql"
).read_text(encoding="utf-8")


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _actor(connection, suffix: str, *, management: bool):
    actor_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"x7policy-{suffix}", f"7x7 Policy {suffix}"),
    ).fetchone()[0]
    if management:
        connection.execute(
            """
            insert into core.user_roles (user_id, role_id)
            select %s, id from core.roles where code = 'management'
            """,
            (actor_id,),
        )
    return actor_id


def _loan_type(connection, suffix: str):
    return connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode,
            daily_interest_per_1000, settings
        ) values (
            %s, %s, 120, 'seven_by_seven', 7.00,
            jsonb_build_object(
                'contractual_interest_payment_frequency', 'daily',
                'contractual_principal_due', 'on_or_before_maturity',
                'principal_prepayment_allowed', true,
                'principal_prepayment_changes_daily_interest', false,
                'mobile_collections_enabled', false
            )
        ) returning id
        """,
        (f"X7POL-{suffix}", f"7x7 Policy {suffix}"),
    ).fetchone()[0]


def _loan(connection, *, suffix: str, actor_id, loan_type_id, release_date: date):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"X7POL-C-{suffix}", f"7x7 Policy Client {suffix}"),
    ).fetchone()[0]
    return connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status, created_by_user_id
        ) values (
            %s, %s, %s, 3000.00, 21.00,
            %s, %s, 'active', %s
        ) returning id
        """,
        (
            f"X7POL-L-{suffix}",
            client_id,
            loan_type_id,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]


def _verified_schedule(connection, *, loan_id, actor_id, release_date: date, suffix: str):
    schedule_id = connection.execute(
        """
        insert into lending.loan_contract_schedules (
            loan_id, schedule_version, status, payment_frequency,
            contract_reference, contract_signed_date, effective_from,
            grace_days, settings, created_by_user_id
        ) values (
            %s, 1, 'active', 'daily', %s, %s, %s,
            0, '{}'::jsonb, %s
        ) returning id
        """,
        (
            loan_id,
            f"X7POL-CONTRACT-{suffix}",
            release_date,
            release_date,
            actor_id,
        ),
    ).fetchone()[0]
    connection.execute(
        """
        insert into lending.loan_contract_installments (
            schedule_id, installment_number, due_date, contractual_amount,
            principal_component, interest_component
        )
        select
            %s,
            day_number,
            %s::date + day_number,
            case when day_number = 120 then 3021.00::numeric else 21.00::numeric end,
            case when day_number = 120 then 3000.00::numeric else 0.00::numeric end,
            21.00::numeric
        from generate_series(1, 120) day_number
        """,
        (schedule_id, release_date),
    )
    connection.execute(
        """
        insert into lending.loan_contract_schedule_registrations (
            schedule_id, evidence_basis, evidence_reference,
            verification_note, verified_by_user_id
        ) values (%s, 'signed_contract', %s, %s, %s)
        """,
        (
            schedule_id,
            f"X7POL-EVIDENCE-{suffix}",
            "Verified exact 7x7 signed-contract schedule for classification policy proof",
            actor_id,
        ),
    )
    return schedule_id


def _record(
    connection,
    *,
    loan_id,
    review_token: str,
    actor_id,
    expected_cash_flow_policy: str,
    business_model: str = "held_to_collect",
    sppi: str = "passes",
    measurement_category: str = "amortised_cost",
    expected_life_policy: str = "contractual_term",
    expected_life_days: int = 120,
):
    return connection.execute(
        """
        select accounting.record_seven_by_seven_policy_decision(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
        """,
        (
            loan_id,
            review_token,
            business_model,
            sppi,
            measurement_category,
            expected_cash_flow_policy,
            expected_life_policy,
            expected_life_days,
            "IFRS 9 classification and EIR policy review",
            Jsonb(
                {
                    "business_model_basis": "documented lending portfolio management objective",
                    "sppi_review": "explicit contract-level assessment; no inference from rate equality",
                }
            ),
            Jsonb(
                {
                    "prepayment_feature_reviewed": True,
                    "expected_cash_flow_basis": expected_cash_flow_policy,
                    "expected_life_days": expected_life_days,
                }
            ),
            "Management reviewed the classification and expected-cash-flow evidence explicitly.",
            "X7POL-SUPPORTING-EVIDENCE",
            actor_id,
        ),
    ).fetchone()[0]


def _setup_case(connection, suffix: str, release_date: date):
    management_actor = _actor(connection, suffix + "-mgmt", management=True)
    non_management_actor = _actor(connection, suffix + "-staff", management=False)
    loan_type_id = _loan_type(connection, suffix)
    loan_id = _loan(
        connection,
        suffix=suffix,
        actor_id=management_actor,
        loan_type_id=loan_type_id,
        release_date=release_date,
    )
    _verified_schedule(
        connection,
        loan_id=loan_id,
        actor_id=management_actor,
        release_date=release_date,
        suffix=suffix,
    )
    token = connection.execute(
        "select accounting.seven_by_seven_policy_review_token(%s)",
        (loan_id,),
    ).fetchone()[0]
    assert token is not None and len(token) == 64
    return management_actor, non_management_actor, loan_id, token


def test_management_policy_evidence_is_immutable_stale_safe_and_does_not_enable_eir() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0062))
            management_actor, non_management_actor, loan_id, token = _setup_case(
                connection,
                suffix,
                date(2093, 1, 1),
            )

            before = connection.execute(
                """
                select classification_policy_readiness_status,
                       active_policy_decision_exists,
                       authoritative_daily_eir,
                       eir_policy_ready,
                       carrying_amount_ready,
                       journal_lines_enabled,
                       automatic_source_posting
                from accounting.seven_by_seven_classification_policy_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert before == (
                "management_classification_policy_evidence_required",
                False,
                None,
                False,
                False,
                False,
                False,
            )

            with pytest.raises(psycopg.Error, match="Management actor"):
                with connection.transaction():
                    _record(
                        connection,
                        loan_id=loan_id,
                        review_token=token,
                        actor_id=non_management_actor,
                        expected_cash_flow_policy=(
                            "verified_no_prepayment_schedule_is_expected_cash_flow_estimate"
                        ),
                    )

            with pytest.raises(psycopg.Error, match="Measurement category is inconsistent"):
                with connection.transaction():
                    _record(
                        connection,
                        loan_id=loan_id,
                        review_token=token,
                        actor_id=management_actor,
                        expected_cash_flow_policy=(
                            "verified_no_prepayment_schedule_is_expected_cash_flow_estimate"
                        ),
                        measurement_category="fvpl",
                    )

            decision_id = _record(
                connection,
                loan_id=loan_id,
                review_token=token,
                actor_id=management_actor,
                expected_cash_flow_policy=(
                    "verified_no_prepayment_schedule_is_expected_cash_flow_estimate"
                ),
            )
            assert _record(
                connection,
                loan_id=loan_id,
                review_token=token,
                actor_id=management_actor,
                expected_cash_flow_policy=(
                    "verified_no_prepayment_schedule_is_expected_cash_flow_estimate"
                ),
            ) == decision_id

            after = connection.execute(
                """
                select
                    active_policy_decision_exists,
                    active_policy_decision_is_current,
                    business_model_classification_concluded,
                    sppi_classification_concluded,
                    expected_cash_flow_policy_approved,
                    amortised_cost_path_supported,
                    classification_policy_evidence_ready_for_eir_promotion,
                    base_no_prepayment_daily_eir_preview,
                    authoritative_daily_eir,
                    authoritative_initial_gross_carrying_amount,
                    authoritative_current_gross_carrying_amount,
                    eir_policy_ready,
                    carrying_amount_ready,
                    journal_lines_enabled,
                    automatic_source_posting,
                    classification_policy_readiness_status
                from accounting.seven_by_seven_classification_policy_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert after is not None
            assert after[:7] == (True, True, True, True, True, True, True)
            assert after[7] == Decimal("0.007000000000")
            assert after[8:11] == (None, None, None)
            assert after[11:15] == (False, False, False, False)
            assert after[15] == "classification_policy_evidence_ready_for_eir_promotion_review"

            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "update accounting.seven_by_seven_policy_decisions set decision_rationale = 'tamper' where id = %s",
                        (decision_id,),
                    )

            void_id = connection.execute(
                "select accounting.void_seven_by_seven_policy_decision(%s, %s, %s)",
                (decision_id, management_actor, "Superseded by a later supported review"),
            ).fetchone()[0]
            assert void_id is not None

            post_void = connection.execute(
                """
                select active_policy_decision_exists,
                       classification_policy_readiness_status,
                       authoritative_daily_eir,
                       automatic_source_posting
                from accounting.seven_by_seven_classification_policy_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert post_void == (
                False,
                "management_classification_policy_evidence_required",
                None,
                False,
            )
        finally:
            connection.rollback()


def test_explicit_prepayment_cash_flow_requirement_stays_fail_closed() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0062))
            management_actor, _, loan_id, token = _setup_case(
                connection,
                suffix,
                date(2093, 6, 1),
            )

            _record(
                connection,
                loan_id=loan_id,
                review_token=token,
                actor_id=management_actor,
                expected_cash_flow_policy=(
                    "separate_expected_prepayment_cash_flow_evidence_required"
                ),
            )

            readiness = connection.execute(
                """
                select expected_cash_flow_policy_approved,
                       amortised_cost_path_supported,
                       classification_policy_evidence_ready_for_eir_promotion,
                       classification_policy_readiness_status,
                       authoritative_daily_eir,
                       eir_policy_ready,
                       carrying_amount_ready,
                       journal_lines_enabled,
                       automatic_source_posting
                from accounting.seven_by_seven_classification_policy_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert readiness == (
                True,
                True,
                False,
                "expected_prepayment_cash_flow_evidence_required",
                None,
                False,
                False,
                False,
                False,
            )
        finally:
            connection.rollback()
