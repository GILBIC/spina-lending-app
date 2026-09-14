from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    CollectionStatus,
    PaymentAllocationIntent,
)
from spina_mobile_collections.postgres import PostgresCollectionExecutor
from spina_mobile_collections.service import (
    CONTRACT_VERSION,
    CollectionSubmissionService,
    SubmissionHeaders,
)

from gilbic_backend.seven_by_seven_collection_posting import (
    SEVEN_BY_SEVEN_MOBILE_SETTING,
    SevenBySevenAwarePerLoanContractCollectionPostingBridge,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

RELEASE_DATE = date(2097, 8, 1)
FIRST_DUE_DATE = RELEASE_DATE + timedelta(days=1)
CONTRACTUAL_MATURITY = FIRST_DUE_DATE + timedelta(days=1)
FIRST_PENALTY_DAY = CONTRACTUAL_MATURITY + timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Case:
    collector_id: UUID
    device_record_id: UUID
    installation_id: str
    client_id: UUID
    loan_id: UUID

    @property
    def actor(self) -> ActorContext:
        return ActorContext(
            account_id=str(self.collector_id),
            device_id=self.installation_id,
            registered_device_id=str(self.device_record_id),
            permissions=frozenset({"collection.create"}),
        )


def _connection_factory() -> psycopg.Connection:
    assert DATABASE_URL is not None
    return psycopg.connect(DATABASE_URL)


def _service() -> CollectionSubmissionService:
    return CollectionSubmissionService(
        PostgresCollectionExecutor(
            connection_factory=_connection_factory,
            posting_bridge=SevenBySevenAwarePerLoanContractCollectionPostingBridge(),
        )
    )


def _setup_case(*, penalty_authority: bool = True) -> Case:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:12]
    installation_id = f"x7-penalty-installation-{suffix}"
    loan_type_settings = {
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
        SEVEN_BY_SEVEN_MOBILE_SETTING: True,
    }

    with psycopg.connect(DATABASE_URL) as connection:
        collector_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s, %s, 'active') returning id
            """,
            (f"x7-pen-col-{suffix}", f"7x7 Penalty Collector {suffix}"),
        ).fetchone()[0]
        device_record_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'p6-task5-test', 'active')
            returning id
            """,
            (collector_id, f"hash-{suffix}"),
        ).fetchone()[0]
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (
                %s, %s, 'Priority 6 Task 5 protected payoff', 60,
                'seven_by_seven', 7.00, %s, true
            ) returning id
            """,
            (
                f"X7PEN-{suffix}",
                f"7x7 Penalty {suffix}",
                Jsonb(loan_type_settings),
            ),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients (client_code, full_name, area, status)
            values (%s, %s, 'Cardona', 'active') returning id
            """,
            (f"X7PC-{suffix}", f"7x7 Penalty Client {suffix}"),
        ).fetchone()[0]
        loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (
                %s, %s, %s, 1000.00, 507.00,
                %s, %s, 'active', %s
            ) returning id
            """,
            (
                f"X7PL-{suffix}",
                client_id,
                loan_type_id,
                RELEASE_DATE,
                CONTRACTUAL_MATURITY,
                collector_id,
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_collection_state (
                loan_id, remaining_balance, is_reconciled, state_version
            ) values (%s, 1000.00, true, 0)
            """,
            (loan_id,),
        )
        connection.execute(
            """
            insert into lending.collector_area_assignments (
                collector_user_id, area, sort_order, is_active
            ) values (%s, 'Cardona', 0, true)
            """,
            (collector_id,),
        )

        fingerprint = (suffix + "a" * 64)[:64]
        review_id: int | None = None
        if penalty_authority:
            review_id = connection.execute(
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
                    '7x7-penalty-v1', 0.030000, 30, 0.030000,
                    1000.00, 14.00
                ) returning id
                """,
                (
                    loan_id,
                    fingerprint,
                    f"P6-T5-PENALTY-{suffix}",
                    "Exact signed penalty policy and legal cap authority for Task 5.",
                    collector_id,
                ),
            ).fetchone()[0]

        schedule_settings: dict[str, object] = {}
        if review_id is not None:
            schedule_settings = {
                "seven_by_seven_penalty_policy": {
                    "policy_version": "7x7-penalty-v1",
                    "review_id": review_id,
                    "terms_fingerprint": fingerprint,
                    "contractual_monthly_rate": "0.030000",
                    "proration_days": 30,
                    "legal_rate_ceiling": "0.030000",
                    "lifetime_nonprincipal_cost_ceiling": "1000.00",
                    "counted_nonprincipal_cost_at_contract_lock": "14.00",
                }
            }

        schedule_id = connection.execute(
            """
            insert into lending.loan_contract_schedules (
                loan_id, schedule_version, status, payment_frequency,
                contract_reference, contract_signed_date, effective_from,
                grace_days, settings, created_by_user_id
            ) values (
                %s, 1, 'active', 'daily', %s, %s, %s,
                0, %s, %s
            ) returning id
            """,
            (
                loan_id,
                f"P6-T5-CONTRACT-{suffix}",
                RELEASE_DATE,
                RELEASE_DATE,
                Jsonb(schedule_settings),
                collector_id,
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_contract_installments (
                schedule_id, installment_number, due_date,
                contractual_amount, principal_component, interest_component
            ) values
                (%s, 1, %s, 507.00, 500.00, 7.00),
                (%s, 2, %s, 507.00, 500.00, 7.00)
            """,
            (schedule_id, FIRST_DUE_DATE, schedule_id, CONTRACTUAL_MATURITY),
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
                f"P6-T5-SIGNED-{suffix}",
                "Borrower accepted the exact two-row signed 7x7 schedule and disclosure.",
                collector_id,
            ),
        )

    return Case(
        collector_id=collector_id,
        device_record_id=device_record_id,
        installation_id=installation_id,
        client_id=client_id,
        loan_id=loan_id,
    )


def _command(
    case: Case,
    *,
    amount: str,
    collection_date: date = FIRST_PENALTY_DAY,
    device_sequence: int = 1,
    route_version: int = 0,
) -> CollectionCommand:
    key = uuid4()
    return CollectionCommand(
        idempotency_key=key,
        route_entry_id=str(case.loan_id),
        client_id=str(case.client_id),
        loan_id=str(case.loan_id),
        collection_date=collection_date,
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal(amount),
        advance_from=None,
        advance_until=None,
        covered_dates=(),
        recorded_at=datetime.combine(
            collection_date, datetime.min.time(), tzinfo=timezone.utc
        ),
        device_id=case.installation_id,
        device_sequence=device_sequence,
        note="Priority 6 post-maturity penalty collection test",
        route_revision=f"loan:{case.loan_id}:v{route_version}",
        past_due_followup=None,
        payment_allocation_intent=PaymentAllocationIntent.SCHEDULED,
    )


def _submit(case: Case, command: CollectionCommand):
    headers = SubmissionHeaders(
        idempotency_key=command.idempotency_key,
        client_transaction_id=command.idempotency_key,
        device_id=case.installation_id,
        contract_version=CONTRACT_VERSION,
    )
    return _service().submit(actor=case.actor, headers=headers, command=command)


def _financial_state(case: Case) -> tuple[str, Decimal, Decimal, Decimal]:
    with _connection_factory() as connection:
        loan_status = connection.execute(
            "select status from lending.loans where id = %s",
            (case.loan_id,),
        ).fetchone()[0]
        principal_balance = connection.execute(
            "select remaining_balance from lending.loan_collection_state where loan_id = %s",
            (case.loan_id,),
        ).fetchone()[0]
        assessed = connection.execute(
            """
            select coalesce(sum(assessed_penalty_amount), 0)
            from lending.seven_by_seven_penalty_assessments
            where loan_id = %s
            """,
            (case.loan_id,),
        ).fetchone()[0]
        penalty_paid = connection.execute(
            """
            select coalesce(sum(allocation.amount_applied), 0)
            from lending.seven_by_seven_penalty_payment_allocations allocation
            join lending.collection_transactions transaction
              on transaction.id = allocation.transaction_id
            where allocation.loan_id = %s
              and transaction.is_voided = false
            """,
            (case.loan_id,),
        ).fetchone()[0]
    return (
        str(loan_status),
        Decimal(principal_balance),
        Decimal(assessed),
        Decimal(penalty_paid),
    )


def test_post_maturity_short_cash_remains_contractual_and_never_pays_penalty() -> None:
    case = _setup_case()

    outcome = _submit(case, _command(case, amount="500.00"))

    assert outcome.status is CollectionStatus.ACCEPTED
    assert outcome.posted is not None
    assert outcome.posted.official_balance == Decimal("514.00")
    assert _financial_state(case) == (
        "active",
        Decimal("514.00"),
        Decimal("1.01"),
        Decimal("0.00"),
    )


def test_exact_post_maturity_payoff_settles_interest_principal_then_penalty() -> None:
    case = _setup_case()

    outcome = _submit(case, _command(case, amount="1015.01"))

    assert outcome.status is CollectionStatus.ACCEPTED
    assert outcome.posted is not None
    assert outcome.posted.official_balance == Decimal("0.00")
    assert _financial_state(case) == (
        "paid",
        Decimal("0.00"),
        Decimal("1.01"),
        Decimal("1.01"),
    )

    with _connection_factory() as connection:
        details = connection.execute(
            """
            select
                details->>'seven_by_seven_penalty_assessed',
                details->>'seven_by_seven_penalty_paid',
                details->>'seven_by_seven_penalty_outstanding'
            from lending.collection_transactions
            where id = %s
            """,
            (UUID(outcome.posted.server_transaction_id),),
        ).fetchone()
    assert details == ("1.01", "1.01", "0.00")


def test_contractual_payoff_leaves_penalty_outstanding_and_penalty_only_payment_closes() -> None:
    case = _setup_case()

    contractual_only = _submit(case, _command(case, amount="1014.00"))

    assert contractual_only.status is CollectionStatus.ACCEPTED
    assert contractual_only.posted is not None
    assert contractual_only.posted.official_balance == Decimal("0.00")
    assert _financial_state(case) == (
        "active",
        Decimal("0.00"),
        Decimal("1.01"),
        Decimal("0.00"),
    )

    penalty_only = _submit(
        case,
        _command(
            case,
            amount="1.01",
            collection_date=FIRST_PENALTY_DAY + timedelta(days=1),
            device_sequence=2,
            route_version=1,
        ),
    )

    assert penalty_only.status is CollectionStatus.ACCEPTED
    assert penalty_only.posted is not None
    assert penalty_only.posted.official_balance == Decimal("0.00")
    assert _financial_state(case) == (
        "paid",
        Decimal("0.00"),
        Decimal("1.01"),
        Decimal("1.01"),
    )


def test_cash_above_exact_contractual_plus_penalty_payoff_is_rejected() -> None:
    case = _setup_case()

    outcome = _submit(case, _command(case, amount="1015.02"))

    assert outcome.status is CollectionStatus.REJECTED
    assert outcome.code == "amount_exceeds_seven_by_seven_payoff"
    assert _financial_state(case) == (
        "active",
        Decimal("1000.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    )


def test_missing_signed_penalty_authority_fails_closed_before_posting() -> None:
    case = _setup_case(penalty_authority=False)

    outcome = _submit(case, _command(case, amount="1014.00"))

    assert outcome.status is CollectionStatus.REJECTED
    assert outcome.code == "seven_by_seven_penalty_management_review_required"
    assert _financial_state(case) == (
        "active",
        Decimal("1000.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    )
