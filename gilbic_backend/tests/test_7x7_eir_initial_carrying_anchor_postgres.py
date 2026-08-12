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

SQL_0063 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0063_add_7x7_eir_initial_carrying_anchor.sql"
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
        (f"x7anchor-{suffix}", f"7x7 Anchor {suffix}"),
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
        (f"X7ANCH-{suffix}", f"7x7 Anchor {suffix}"),
    ).fetchone()[0]


def _loan(connection, *, suffix: str, actor_id, loan_type_id, release_date: date):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"X7ANCH-C-{suffix}", f"7x7 Anchor Client {suffix}"),
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
            f"X7ANCH-L-{suffix}",
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
            f"X7ANCH-CONTRACT-{suffix}",
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
            f"X7ANCH-EVIDENCE-{suffix}",
            "Verified exact 7x7 signed-contract schedule for EIR anchor proof",
            actor_id,
        ),
    )
    return schedule_id


def _record_policy(connection, *, loan_id, token: str, actor_id):
    return connection.execute(
        """
        select accounting.record_seven_by_seven_policy_decision(
            %s, %s,
            'held_to_collect', 'passes', 'amortised_cost',
            'verified_no_prepayment_schedule_is_expected_cash_flow_estimate',
            'contractual_term', 120,
            %s, %s, %s, %s, %s, %s
        )
        """,
        (
            loan_id,
            token,
            "IFRS 9 classification and expected-cash-flow policy review",
            Jsonb(
                {
                    "business_model_basis": "documented objective is collection of contractual cash flows",
                    "sppi_review": "explicit contract assessment supports principal and interest cash flows",
                }
            ),
            Jsonb(
                {
                    "prepayment_feature_reviewed": True,
                    "expected_cash_flow_basis": "verified signed-contract no-prepayment schedule",
                    "expected_life_days": 120,
                }
            ),
            "Management explicitly approved amortised-cost classification and the expected-cash-flow basis.",
            "X7ANCH-POLICY-SUPPORT",
            actor_id,
        ),
    ).fetchone()[0]


def _record_anchor(
    connection,
    *,
    loan_id,
    token: str,
    actor_id,
    initial_amount: Decimal = Decimal("2970.00"),
):
    return connection.execute(
        """
        select accounting.record_seven_by_seven_eir_initial_carrying_anchor(
            %s, %s, %s,
            'management_evidence_backed_ifrs9_initial_measurement',
            %s, %s, %s, %s
        )
        """,
        (
            loan_id,
            token,
            initial_amount,
            Jsonb(
                {
                    "fair_value_basis": "Management-reviewed instrument-specific initial fair-value evidence",
                    "transaction_costs_assessment": "Directly attributable transaction costs reviewed in the carrying amount",
                    "integral_fees_assessment": "Integral fees/points reviewed; no amount is inferred from operational pricing",
                    "source_documents": ["X7ANCH-INITIAL-MEASUREMENT-WORKPAPER"],
                }
            ),
            "X7ANCH-INITIAL-MEASUREMENT-EVIDENCE",
            "Management reviewed the exact initial gross carrying amount and approved EIR solving from it.",
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
    policy_token = connection.execute(
        "select accounting.seven_by_seven_policy_review_token(%s)",
        (loan_id,),
    ).fetchone()[0]
    assert policy_token is not None and len(policy_token) == 64
    policy_decision_id = _record_policy(
        connection,
        loan_id=loan_id,
        token=policy_token,
        actor_id=management_actor,
    )
    anchor_token = connection.execute(
        "select accounting.seven_by_seven_eir_anchor_review_token(%s)",
        (loan_id,),
    ).fetchone()[0]
    assert anchor_token is not None and len(anchor_token) == 64
    return management_actor, non_management_actor, loan_id, policy_decision_id, anchor_token


def test_eir_anchor_promotes_from_initial_measurement_not_operational_rate_and_stays_posting_disabled() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0063))
            management_actor, non_management_actor, loan_id, _, token = _setup_case(
                connection,
                suffix,
                date(2094, 1, 1),
            )

            before = connection.execute(
                """
                select eir_initial_carrying_readiness_status,
                       active_anchor_exists,
                       principal_base_daily_eir_preview,
                       eir_policy_ready,
                       initial_carrying_amount_ready,
                       current_carrying_amount_ready,
                       journal_lines_enabled,
                       automatic_source_posting
                from accounting.seven_by_seven_eir_initial_carrying_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert before == (
                "management_initial_measurement_and_eir_anchor_required",
                False,
                Decimal("0.007000000000"),
                False,
                False,
                False,
                False,
                False,
            )

            with pytest.raises(psycopg.Error, match="Management actor"):
                with connection.transaction():
                    _record_anchor(
                        connection,
                        loan_id=loan_id,
                        token=token,
                        actor_id=non_management_actor,
                    )

            with pytest.raises(psycopg.Error, match="fair value"):
                with connection.transaction():
                    connection.execute(
                        """
                        select accounting.record_seven_by_seven_eir_initial_carrying_anchor(
                            %s, %s, 2970.00,
                            'management_evidence_backed_ifrs9_initial_measurement',
                            '{}'::jsonb, %s, %s, %s
                        )
                        """,
                        (
                            loan_id,
                            token,
                            "X7ANCH-BAD-EVIDENCE",
                            "Management rationale that is long enough for the protected boundary.",
                            management_actor,
                        ),
                    )

            anchor_id = _record_anchor(
                connection,
                loan_id=loan_id,
                token=token,
                actor_id=management_actor,
            )
            assert _record_anchor(
                connection,
                loan_id=loan_id,
                token=token,
                actor_id=management_actor,
            ) == anchor_id

            after = connection.execute(
                """
                select
                    active_anchor_exists,
                    active_anchor_is_current,
                    anchor_eir_reconciles,
                    eir_policy_ready,
                    initial_carrying_amount_ready,
                    carrying_policy_ready,
                    principal_base_daily_eir_preview,
                    authoritative_daily_eir,
                    authoritative_initial_gross_carrying_amount,
                    authoritative_current_gross_carrying_amount,
                    current_carrying_amount_ready,
                    carrying_amount_ready,
                    journal_lines_enabled,
                    automatic_source_posting,
                    eir_initial_carrying_readiness_status
                from accounting.seven_by_seven_eir_initial_carrying_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert after is not None
            assert after[:6] == (True, True, True, True, True, True)
            assert after[6] == Decimal("0.007000000000")
            assert after[7] is not None
            assert after[7] > after[6]
            assert after[8] == Decimal("2970.00")
            assert after[9:14] == (None, False, False, False, False)
            assert after[14] == "eir_initial_carrying_anchor_ready_for_7x7_accounting_lifecycle"

            journal_count = connection.execute(
                "select count(*) from accounting.journal_entries where source_reference = %s",
                (str(anchor_id),),
            ).fetchone()[0]
            assert journal_count == 0

            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        """
                        update accounting.seven_by_seven_eir_initial_carrying_anchors
                        set authoritative_initial_gross_carrying_amount = 3000.00
                        where id = %s
                        """,
                        (anchor_id,),
                    )
        finally:
            connection.rollback()


def test_eir_anchor_is_stale_safe_and_requires_void_before_correction() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0063))
            management_actor, _, loan_id, policy_decision_id, token = _setup_case(
                connection,
                suffix,
                date(2094, 6, 1),
            )
            anchor_id = _record_anchor(
                connection,
                loan_id=loan_id,
                token=token,
                actor_id=management_actor,
            )

            with pytest.raises(psycopg.Error, match="Different active"):
                with connection.transaction():
                    _record_anchor(
                        connection,
                        loan_id=loan_id,
                        token=token,
                        actor_id=management_actor,
                        initial_amount=Decimal("2960.00"),
                    )

            connection.execute(
                "select accounting.void_seven_by_seven_policy_decision(%s, %s, %s)",
                (policy_decision_id, management_actor, "Policy evidence superseded for staleness proof"),
            )
            stale = connection.execute(
                """
                select active_anchor_exists,
                       active_anchor_is_current,
                       eir_policy_ready,
                       carrying_policy_ready,
                       eir_initial_carrying_readiness_status,
                       automatic_source_posting
                from accounting.seven_by_seven_eir_initial_carrying_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert stale == (
                True,
                False,
                False,
                False,
                "management_classification_policy_evidence_required",
                False,
            )

            void_id = connection.execute(
                "select accounting.void_seven_by_seven_eir_initial_carrying_anchor(%s, %s, %s)",
                (anchor_id, management_actor, "Anchor superseded after policy review changed"),
            ).fetchone()[0]
            assert void_id is not None
            assert connection.execute(
                "select accounting.void_seven_by_seven_eir_initial_carrying_anchor(%s, %s, %s)",
                (anchor_id, management_actor, "Anchor superseded after policy review changed"),
            ).fetchone()[0] == void_id
        finally:
            connection.rollback()
