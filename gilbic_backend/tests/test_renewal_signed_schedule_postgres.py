import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.contract_schedule_engine import ContractInstallment
from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.contract_schedule_service import store_contract_schedule
from gilbic_backend.renewal_repository import (
    PostgresRenewalRepository,
    RenewalLoanNotEligible,
)
from gilbic_backend.renewal_workflow_api import _payload, _renewal_row
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)
from psycopg.rows import dict_row
from test_combined_collection_renewal_workflow_postgres import (
    _connect,
    _setup_renewal_client,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("GILBIC_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL is not configured",
)


def _register(loan_id, actor_id, *, seven=False, supersede=False):
    installments = (
        generate_signed_seven_by_seven_schedule(
            original_principal="3000.00",
            agreed_daily_payment="121.00",
            daily_interest_per_1000="7.00",
            first_due_date=date(2097, 8, 2),
        )
        if seven
        else (
            ContractInstallment(1, date(2097, 8, 2), Decimal("1800.00")),
            ContractInstallment(2, date(2097, 9, 2), Decimal("1800.00")),
        )
    )
    with _connect() as connection:
        return register_verified_contract_schedule(
            connection.cursor(),
            loan_id=loan_id,
            payment_frequency="daily" if seven else "custom",
            contract_reference=f"R2-{uuid4()}",
            contract_signed_date=date(2097, 8, 1),
            effective_from=date(2097, 8, 1),
            grace_days=0,
            installments=installments,
            evidence_basis="signed_contract",
            evidence_reference="R2 disposable signed schedule",
            verification_note="Verified isolated regression fixture",
            verified_by_user_id=actor_id,
            agreed_daily_payment=Decimal("121.00") if seven else None,
            confirmed=True,
            supersede_active=supersede,
        )


def _payment(loan_id, client_id, actor_id, amount, *, voided=False):
    with _connect() as connection:
        device_id = connection.execute(
            "insert into core.devices(user_id, device_identifier_hash, platform, status) values (%s,%s,'desktop','active') returning id",
            (actor_id, uuid4().hex),
        ).fetchone()[0]
        return connection.execute(
            """
            insert into lending.collection_transactions (
                idempotency_key, loan_id, client_id, collector_user_id, registered_device_id,
                route_entry_id, collection_date, entry_type, amount, applied_amount,
                recorded_at, device_sequence, previous_balance, official_balance,
                pass_count_after, receipt_number, is_voided,
                voided_at, voided_by_user_id, void_reason
            ) values (%s,%s,%s,%s,%s,%s,'2097-08-02','payment',%s,%s,now(),1,3600,0,0,%s,%s,
                case when %s then now() else null end, %s, %s)
            returning id
            """,
            (
                uuid4(),
                loan_id,
                client_id,
                actor_id,
                device_id,
                loan_id,
                Decimal(amount),
                Decimal(amount),
                f"R2-{uuid4()}",
                voided,
                voided,
                actor_id if voided else None,
                "Reversed regression fixture" if voided else None,
            ),
        ).fetchone()[0]


def test_custom_signed_total_controls_portal_submission_and_workflow():
    user, actor, client, loan = _setup_renewal_client(mode="fixed_daily")
    _register(loan, actor)
    _payment(loan, client, actor, "1799.99")
    _payment(loan, client, actor, "5000.00", voided=True)
    repository = PostgresRenewalRepository()

    option = repository.portal_for_user(user_id=user).loans[0]
    assert option.contractual_total == Decimal("3600.00")
    assert option.paid_amount == Decimal("1799.99")
    assert option.eligible is False
    with pytest.raises(RenewalLoanNotEligible):
        repository.submit_for_user(
            user_id=user,
            loan_id=loan,
            requested_amount=Decimal("3000.00"),
            client_message="Below threshold",
        )

    _payment(loan, client, actor, "0.01")
    request = repository.submit_for_user(
        user_id=user,
        loan_id=loan,
        requested_amount=Decimal("3000.00"),
        client_message="Exactly half",
    )
    with _connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        result = _payload(cursor, _renewal_row(cursor, request_id=request.request_id))
    assert result["contractual_total"] == "3600.00"
    assert result["paid_cash"] == "1800.00"
    assert result["paid_percent"] == "50.0"
    assert result["regular_50_percent_eligible"] is True

    with _connect() as connection:
        connection.execute(
            "update lending.loan_types set term_days=999 where id=(select loan_type_id from lending.loans where id=%s)",
            (loan,),
        )
    assert repository.portal_for_user(user_id=user).loans[
        0
    ].contractual_total == Decimal("3600.00")


def test_seven_by_seven_uses_agreed_payment_duration_without_new_threshold():
    user, actor, _, loan = _setup_renewal_client(mode="seven_by_seven")
    _register(loan, actor, seven=True)
    repository = PostgresRenewalRepository()
    option = repository.portal_for_user(user_id=user).loans[0]
    # Principal 3000 / daily principal 100 = 30 payments of 121.
    assert option.contractual_total == Decimal("3630.00")
    assert option.paid_percent == Decimal("0.0")
    assert option.eligible is True
    assert (
        repository.submit_for_user(
            user_id=user,
            loan_id=loan,
            requested_amount=Decimal("3000.00"),
            client_message="7x7 consideration",
        ).status
        == "pending"
    )


def test_historical_regular_without_verified_schedule_cannot_invent_eligibility():
    user, actor, client, loan = _setup_renewal_client(mode="fixed_daily")
    _payment(loan, client, actor, "4000.00")
    repository = PostgresRenewalRepository()
    option = repository.portal_for_user(user_id=user).loans[0]
    assert option.contractual_total is None
    assert option.paid_percent is None
    assert option.eligible is False
    with pytest.raises(RenewalLoanNotEligible, match="verified signed schedule"):
        repository.submit_for_user(
            user_id=user,
            loan_id=loan,
            requested_amount=Decimal("3000.00"),
            client_message="Missing evidence",
        )


def test_unverified_and_superseded_schedules_do_not_supply_the_total():
    user, actor, _, loan = _setup_renewal_client(mode="fixed_daily")
    with _connect() as connection:
        old_schedule = store_contract_schedule(
            connection.cursor(),
            loan_id=loan,
            payment_frequency="custom",
            contract_reference=f"LEGACY-{uuid4()}",
            contract_signed_date=date(2097, 8, 1),
            effective_from=date(2097, 8, 1),
            grace_days=0,
            installments=(
                ContractInstallment(1, date(2097, 9, 1), Decimal("9000.00")),
            ),
            created_by_user_id=actor,
        )
    repository = PostgresRenewalRepository()
    assert repository.portal_for_user(user_id=user).loans[0].contractual_total is None

    _register(loan, actor, supersede=True)
    assert repository.portal_for_user(user_id=user).loans[
        0
    ].contractual_total == Decimal("3600.00")
    with _connect() as connection:
        assert (
            connection.execute(
                "select status from lending.loan_contract_schedules where id=%s",
                (old_schedule,),
            ).fetchone()[0]
            == "superseded"
        )
        assert connection.execute(
            "select contractual_amount from lending.loan_contract_installments where schedule_id=%s",
            (old_schedule,),
        ).fetchone()[0] == Decimal("9000.00")


def test_fully_paid_regular_keeps_policy_without_fabricating_missing_schedule():
    user, _, _, loan = _setup_renewal_client(mode="fixed_daily")
    with _connect() as connection:
        connection.execute(
            "update lending.loans set status='paid' where id=%s", (loan,)
        )
    repository = PostgresRenewalRepository()
    option = repository.portal_for_user(user_id=user).loans[0]
    assert option.eligible is True
    assert option.contractual_total is None
    assert option.paid_percent is None
    request = repository.submit_for_user(
        user_id=user,
        loan_id=loan,
        requested_amount=Decimal("3000.00"),
        client_message="Fully paid",
    )
    with _connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        result = _payload(cursor, _renewal_row(cursor, request_id=request.request_id))
    assert result["regular_50_percent_eligible"] is True
    assert result["contractual_total"] is None
    assert result["paid_percent"] is None
