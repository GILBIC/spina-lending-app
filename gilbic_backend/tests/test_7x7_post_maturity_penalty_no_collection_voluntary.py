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

from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.management_no_collection_repository import (
    NoCollectionSelection,
    PostgresManagementNoCollectionRepository,
)
from gilbic_backend.seven_by_seven_collection_posting import (
    SEVEN_BY_SEVEN_MOBILE_SETTING,
)
from gilbic_backend.seven_by_seven_multi_receipt_posting import (
    MultiReceiptSevenBySevenCollectionPostingBridge,
)
from gilbic_backend.seven_by_seven_penalty_coordinator import (
    project_verified_seven_by_seven_penalty_state,
)
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

RELEASE_DATE = date(2097, 11, 1)
PAYMENT_START = RELEASE_DATE + timedelta(days=1)


@dataclass(frozen=True, slots=True)
class Case:
    collector_id: UUID
    device_record_id: UUID
    installation_id: str
    client_id: UUID
    loan_id: UUID
    contractual_maturity: date

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
            posting_bridge=MultiReceiptSevenBySevenCollectionPostingBridge(),
        )
    )


def _setup_case() -> Case:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:12]
    installation_id = f"x7-ncv-penalty-installation-{suffix}"
    loan_type_settings = {
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
        SEVEN_BY_SEVEN_MOBILE_SETTING: True,
    }

    schedule_rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("3000.00"),
        agreed_daily_payment=Decimal("50.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=PAYMENT_START,
    )
    contractual_maturity = max(row.due_date for row in schedule_rows)

    with psycopg.connect(DATABASE_URL) as connection:
        collector_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s, %s, 'active') returning id
            """,
            (f"x7-ncv-pen-{suffix}", f"7x7 NC Penalty Collector {suffix}"),
        ).fetchone()[0]
        device_record_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'p6-task6b-red', 'active')
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
                %s, %s, 'Priority 6 Task 6B NC voluntary penalty', 60,
                'seven_by_seven', 7.00, %s, true
            ) returning id
            """,
            (
                f"X7NCVP-{suffix}",
                f"7x7 NC Voluntary Penalty {suffix}",
                Jsonb(loan_type_settings),
            ),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients (client_code, full_name, area, status)
            values (%s, %s, 'Cardona', 'active') returning id
            """,
            (f"X7NCVPC-{suffix}", f"7x7 NC Penalty Client {suffix}"),
        ).fetchone()[0]
        loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (
                %s, %s, %s, 3000.00, 50.00,
                %s, %s, 'active', %s
            ) returning id
            """,
            (
                f"X7NCVPL-{suffix}",
                client_id,
                loan_type_id,
                RELEASE_DATE,
                contractual_maturity,
                collector_id,
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_collection_state (
                loan_id, remaining_balance, is_reconciled, state_version
            ) values (%s, 3000.00, true, 0)
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
                5000.00, 0.00
            ) returning id
            """,
            (
                loan_id,
                fingerprint,
                f"P6-T6B-PENALTY-{suffix}",
                "Exact signed penalty authority for NC voluntary path RED coverage.",
                collector_id,
            ),
        ).fetchone()[0]
        schedule_settings = {
            "seven_by_seven_penalty_policy": {
                "policy_version": "7x7-penalty-v1",
                "review_id": int(review_id),
                "terms_fingerprint": fingerprint,
                "contractual_monthly_rate": "0.030000",
                "proration_days": 30,
                "legal_rate_ceiling": "0.030000",
                "lifetime_nonprincipal_cost_ceiling": "5000.00",
                "counted_nonprincipal_cost_at_contract_lock": "0.00",
            }
        }
        with connection.cursor() as cursor:
            register_verified_contract_schedule(
                cursor,
                loan_id=loan_id,
                payment_frequency="daily",
                contract_reference=f"SIGNED-X7-NCV-PEN-{suffix}",
                contract_signed_date=RELEASE_DATE,
                effective_from=RELEASE_DATE,
                grace_days=0,
                installments=schedule_rows,
                evidence_basis="signed_contract",
                evidence_reference=f"SIGNED-X7-NCV-PEN-DOC-{suffix}",
                verification_note=(
                    "Borrower accepted the exact immutable 7x7 schedule and "
                    "post-maturity penalty disclosure."
                ),
                verified_by_user_id=collector_id,
                agreed_daily_payment=Decimal("50.00"),
                schedule_settings=schedule_settings,
                confirmed=True,
            )

    return Case(
        collector_id=collector_id,
        device_record_id=device_record_id,
        installation_id=installation_id,
        client_id=client_id,
        loan_id=loan_id,
        contractual_maturity=contractual_maturity,
    )


def _operational_version(case: Case) -> int:
    with _connection_factory() as connection:
        row = connection.execute(
            """
            select coalesce(state.operational_version, 0)
            from lending.loan_contract_schedules schedule
            left join lending.loan_schedule_operational_state state
              on state.schedule_id = schedule.id
            where schedule.loan_id = %s
              and schedule.status = 'active'
            order by schedule.schedule_version desc
            limit 1
            """,
            (case.loan_id,),
        ).fetchone()
    assert row is not None
    return int(row[0])


def _declare_no_collection(case: Case, no_collection_date: date) -> None:
    version = _operational_version(case)
    records = PostgresManagementNoCollectionRepository().declare_many(
        actor_user_id=case.collector_id,
        selections=(
            NoCollectionSelection(
                loan_id=case.loan_id,
                expected_operational_version=version,
            ),
        ),
        no_collection_date=no_collection_date,
        reason="Priority 6 Task 6B protected post-maturity NC test.",
    )
    assert len(records) == 1
    assert records[0].adjustment_type == "no_collection"


def _route_revision(case: Case) -> str:
    with _connection_factory() as connection:
        version = connection.execute(
            """
            select state_version
            from lending.loan_collection_state
            where loan_id = %s
            """,
            (case.loan_id,),
        ).fetchone()[0]
    return f"loan:{case.loan_id}:v{int(version)}"


def _project_penalty(case: Case, *, as_of_date: date):
    with _connection_factory() as connection:
        with connection.cursor() as cursor:
            return project_verified_seven_by_seven_penalty_state(
                cursor,
                loan_id=case.loan_id,
                as_of_date=as_of_date,
            )


def _command(
    case: Case,
    *,
    amount: str,
    collection_date: date,
    device_sequence: int = 1,
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
        recorded_at=datetime.combine(
            collection_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ),
        device_id=case.installation_id,
        device_sequence=device_sequence,
        note="Priority 6 post-maturity NC voluntary penalty test",
        route_revision=_route_revision(case),
        payment_allocation_intent=PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY,
    )


def _submit(case: Case, command: CollectionCommand):
    headers = SubmissionHeaders(
        idempotency_key=command.idempotency_key,
        client_transaction_id=command.idempotency_key,
        device_id=case.installation_id,
        contract_version=CONTRACT_VERSION,
    )
    return _service().submit(actor=case.actor, headers=headers, command=command)


def test_post_maturity_nc_voluntary_receipt_freezes_only_shared_coordinator_penalty() -> None:
    """NC voluntary cash must not bypass or locally recompute post-maturity penalty.

    The first NC shifts the exact signed-maturity row into the first penalty day.
    The second NC protects that shifted row again on the first penalty day. Other
    overdue contractual amounts remain unprotected and penalty-bearing. The
    receipt therefore must freeze exactly the coordinator's pre-receipt projection:
    protected cash stays excluded, unprotected overdue cash still accrues, and the
    same-day payment cannot retroactively lower or increase that day's penalty.
    """

    case = _setup_case()
    first_penalty_day = case.contractual_maturity + timedelta(days=1)

    _declare_no_collection(case, case.contractual_maturity)
    _declare_no_collection(case, first_penalty_day)

    before = _project_penalty(case, as_of_date=first_penalty_day)
    assert before.status == "projected"
    assert before.projected_penalty > Decimal("0.00")
    assert before.penalty_base > Decimal("0.00")

    outcome = _submit(
        case,
        _command(
            case,
            amount="20.00",
            collection_date=first_penalty_day,
        ),
    )
    assert outcome.status is CollectionStatus.ACCEPTED
    assert outcome.posted is not None

    after = _project_penalty(case, as_of_date=first_penalty_day)
    with _connection_factory() as connection:
        assessed = Decimal(
            connection.execute(
                """
                select coalesce(sum(assessed_penalty_amount), 0)
                from lending.seven_by_seven_penalty_assessments
                where loan_id = %s
                """,
                (case.loan_id,),
            ).fetchone()[0]
        )
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

    assert assessed == before.projected_penalty
    assert after.projected_penalty == Decimal("0.00")
    assert after.assessed_penalty_balance == before.projected_penalty
    assert details == (
        str(before.projected_penalty),
        "0.00",
        str(before.projected_penalty),
    )
