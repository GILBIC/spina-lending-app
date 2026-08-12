from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _fixture(connection, *, suffix: str):
    actor_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"rtd-{suffix}", f"Renewal Treatment {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        )
        values (%s, %s, 120, 'fixed_daily', 0)
        returning id
        """,
        (f"RTD-{suffix}", f"Renewal Treatment {suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"RTD-C-{suffix}", f"Treatment Client {suffix}"),
    ).fetchone()[0]
    max_end = connection.execute(
        "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
    ).fetchone()[0]
    renewal_date = max_end + timedelta(days=30)
    old_release = renewal_date - timedelta(days=60)
    old_loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status
        )
        values (%s, %s, %s, 5000.00, 50.00, %s, %s, 'active')
        returning id
        """,
        (
            f"RTD-OLD-{suffix}",
            client_id,
            loan_type_id,
            old_release,
            old_release + timedelta(days=120),
        ),
    ).fetchone()[0]
    new_loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status
        )
        values (%s, %s, %s, 6000.00, 60.00, %s, %s, 'active')
        returning id
        """,
        (
            f"RTD-NEW-{suffix}",
            client_id,
            loan_type_id,
            renewal_date,
            renewal_date + timedelta(days=120),
        ),
    ).fetchone()[0]

    connection.execute(
        "select set_config('lending.loan_disbursement_evidence_insert_allowed', 'on', true)"
    )
    disbursement_event_id = connection.execute(
        """
        insert into lending.loan_disbursement_events (
            loan_id, client_id, event_kind, business_date, disbursed_at,
            cash_disbursed_amount, settlement_amount, other_deduction_amount,
            funding_account_system_key, external_reference, evidence_note,
            principal_snapshot, date_released_snapshot, loan_status_snapshot,
            recorded_by_user_id
        )
        values (
            %s, %s, 'renewal_release', %s,
            (%s::date + time '09:00') at time zone 'Asia/Manila',
            3000.00, 3000.00, 0.00,
            'cash_bank', %s, '', 6000.00, %s, 'active', %s
        )
        returning id
        """,
        (
            new_loan_id,
            client_id,
            renewal_date,
            renewal_date,
            f"RTD-DISB-{suffix}",
            renewal_date,
            actor_id,
        ),
    ).fetchone()[0]

    connection.execute(
        "select set_config('lending.loan_renewal_execution_insert_allowed', 'on', true)"
    )
    execution_id = connection.execute(
        """
        insert into lending.loan_renewal_execution_events (
            old_loan_id, new_loan_id, disbursement_event_id, client_id,
            business_date, executed_at, old_loan_settlement_amount,
            external_reference, evidence_note,
            old_loan_principal_snapshot, old_loan_date_released_snapshot,
            old_loan_status_snapshot, new_loan_principal_snapshot,
            new_loan_date_released_snapshot, new_loan_status_snapshot,
            recorded_by_user_id
        )
        values (
            %s, %s, %s, %s, %s,
            (%s::date + time '09:05') at time zone 'Asia/Manila',
            3000.00, %s, '', 5000.00, %s, 'active',
            6000.00, %s, 'active', %s
        )
        returning id
        """,
        (
            old_loan_id,
            new_loan_id,
            disbursement_event_id,
            client_id,
            renewal_date,
            renewal_date,
            f"RTD-EXEC-{suffix}",
            old_release,
            renewal_date,
            actor_id,
        ),
    ).fetchone()[0]

    schedule_id = connection.execute(
        """
        insert into lending.loan_contract_schedules (
            loan_id, schedule_version, status, payment_frequency,
            contract_reference, contract_signed_date, effective_from,
            created_by_user_id
        )
        values (%s, 1, 'active', 'daily', %s, %s, %s, %s)
        returning id
        """,
        (
            new_loan_id,
            f"RTD-CONTRACT-{suffix}",
            renewal_date,
            renewal_date,
            actor_id,
        ),
    ).fetchone()[0]
    installment_amounts = (Decimal("1600.00"),) * 4
    for number, amount in enumerate(installment_amounts, start=1):
        connection.execute(
            """
            insert into lending.loan_contract_installments (
                schedule_id, installment_number, due_date, contractual_amount
            )
            values (%s, %s, %s, %s)
            """,
            (
                schedule_id,
                number,
                renewal_date + timedelta(days=30 * number),
                amount,
            ),
        )
    connection.execute(
        """
        insert into lending.loan_contract_schedule_registrations (
            schedule_id, evidence_basis, evidence_reference,
            verification_note, verified_by_user_id
        )
        values (%s, 'signed_renewal_contract', %s, %s, %s)
        """,
        (
            schedule_id,
            f"RTD-CONTRACT-EVIDENCE-{suffix}",
            "Verified signed renewal agreement for disposable accounting proof.",
            actor_id,
        ),
    )
    return {
        "actor_id": actor_id,
        "client_id": client_id,
        "old_loan_id": old_loan_id,
        "new_loan_id": new_loan_id,
        "execution_id": execution_id,
        "schedule_id": schedule_id,
        "renewal_date": renewal_date,
        "contract_reference": f"RTD-CONTRACT-{suffix}",
        "contract_evidence_reference": f"RTD-CONTRACT-EVIDENCE-{suffix}",
        "contractual_total": Decimal("6400.00"),
    }


def _record(
    connection,
    fixture,
    *,
    token: str,
    decision: str = "modification_no_derecognition",
    rationale: str = "Reviewed qualitative evidence supports continuation of the existing financial asset.",
):
    return connection.execute(
        """
        select accounting.record_renewal_treatment_decision(
            %s, %s, %s, %s, %s,
            %s, 'renewal_accounting_treatment_readiness_v1',
            %s, 'renewal_treatment_decision_evidence_v1',
            %s, %s::jsonb, %s, %s,
            2000.00, 0.001000000000, 3000.00, 3000.00, 0.00,
            %s, 1, %s, %s, 4, %s,
            2227.92, 227.92, 11.396000, %s
        )
        """,
        (
            fixture["execution_id"],
            fixture["old_loan_id"],
            fixture["new_loan_id"],
            fixture["client_id"],
            fixture["renewal_date"],
            token,
            decision,
            "PFRS 9 renewal accounting policy v1",
            Jsonb(
                {
                    "legal_terms_reviewed": True,
                    "borrower_identity_continues": True,
                    "qualitative_conclusion": "same financial asset continues",
                }
            ),
            rationale,
            "RTD-ACCOUNTING-REVIEW-001",
            fixture["schedule_id"],
            fixture["contract_reference"],
            fixture["contract_evidence_reference"],
            fixture["contractual_total"],
            fixture["actor_id"],
        ),
    ).fetchone()[0]


def test_decision_evidence_is_immutable_idempotent_and_requires_explicit_void_for_correction():
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        fixture = _fixture(connection, suffix=suffix)
        token = "a" * 64
        decision_id = _record(connection, fixture, token=token)
        repeated_id = _record(connection, fixture, token=token)
        assert repeated_id == decision_id

        status = connection.execute(
            """
            select decision, readiness_review_token, is_active,
                   automatic_classification_enabled,
                   quantitative_threshold_decisive,
                   journal_lines_enabled, automatic_source_posting
            from accounting.renewal_treatment_decision_status
            where decision_id = %s
            """,
            (decision_id,),
        ).fetchone()
        assert status == (
            "modification_no_derecognition",
            token,
            True,
            False,
            False,
            False,
            False,
        )

        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "update accounting.renewal_treatment_decisions set decision = 'derecognition' where id = %s",
                    (decision_id,),
                )
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "delete from accounting.renewal_treatment_decisions where id = %s",
                    (decision_id,),
                )
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    """
                    insert into accounting.renewal_treatment_decision_voids (
                        decision_id, renewal_execution_event_id, void_reason, voided_by_user_id
                    ) values (%s, %s, 'direct insert forbidden', %s)
                    """,
                    (decision_id, fixture["execution_id"], fixture["actor_id"]),
                )
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                _record(
                    connection,
                    fixture,
                    token="b" * 64,
                    decision="derecognition",
                    rationale="Different reviewed evidence concludes that derecognition is required for this renewal.",
                )

        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(
                    "select set_config('lending.loan_renewal_execution_void_allowed', 'on', true)"
                )
                connection.execute(
                    """
                    update lending.loan_renewal_execution_events
                    set is_voided = true,
                        voided_by_user_id = %s,
                        voided_at = now(),
                        void_reason = 'blocked while decision active'
                    where id = %s
                    """,
                    (fixture["actor_id"], fixture["execution_id"]),
                )

        void_id = connection.execute(
            "select accounting.void_renewal_treatment_decision(%s, %s, %s)",
            (decision_id, fixture["actor_id"], "correct reviewed treatment evidence"),
        ).fetchone()[0]
        repeated_void_id = connection.execute(
            "select accounting.void_renewal_treatment_decision(%s, %s, %s)",
            (decision_id, fixture["actor_id"], "correct reviewed treatment evidence"),
        ).fetchone()[0]
        assert repeated_void_id == void_id
        assert connection.execute(
            "select is_active from accounting.renewal_treatment_decision_status where decision_id = %s",
            (decision_id,),
        ).fetchone()[0] is False
        original = connection.execute(
            "select decision, readiness_review_token from accounting.renewal_treatment_decisions where id = %s",
            (decision_id,),
        ).fetchone()
        assert original == ("modification_no_derecognition", token)

        corrected_id = _record(
            connection,
            fixture,
            token="b" * 64,
            decision="derecognition",
            rationale="Corrected Management qualitative review concludes that the original financial asset is derecognized.",
        )
        assert corrected_id != decision_id
        assert connection.execute(
            "select count(*) from accounting.renewal_treatment_decisions where renewal_execution_event_id = %s",
            (fixture["execution_id"],),
        ).fetchone()[0] == 2
        assert connection.execute(
            "select count(*) from accounting.renewal_treatment_decision_voids where renewal_execution_event_id = %s",
            (fixture["execution_id"],),
        ).fetchone()[0] == 1


def test_decision_insert_rolls_back_if_immutable_audit_write_fails():
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        fixture = _fixture(connection, suffix=suffix)
        trigger_suffix = suffix.replace("-", "")
        function_name = f"test_fail_rtd_audit_{trigger_suffix}"
        trigger_name = f"zz_test_fail_rtd_audit_{trigger_suffix}"
        connection.execute(
            f"""
            create function core.{function_name}()
            returns trigger language plpgsql as $$
            begin
                if NEW.action = 'accounting.renewal_treatment_decision.recorded' then
                    raise exception 'forced renewal treatment decision audit failure';
                end if;
                return NEW;
            end;
            $$
            """
        )
        connection.execute(
            f"""
            create trigger {trigger_name}
            before insert on core.audit_logs
            for each row execute function core.{function_name}()
            """
        )
        connection.commit()

        with pytest.raises(psycopg.Error):
            with connection.transaction():
                _record(connection, fixture, token="c" * 64)

        assert connection.execute(
            "select count(*) from accounting.renewal_treatment_decisions where renewal_execution_event_id = %s",
            (fixture["execution_id"],),
        ).fetchone()[0] == 0
        connection.execute(f"drop trigger {trigger_name} on core.audit_logs")
        connection.execute(f"drop function core.{function_name}()")
