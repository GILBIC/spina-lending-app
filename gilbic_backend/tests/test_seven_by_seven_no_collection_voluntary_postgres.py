from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

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
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)
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


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


class Case:
    def __init__(
        self,
        *,
        collector_id: UUID,
        device_record_id: UUID,
        installation_id: str,
        client_id: UUID,
        loan_id: UUID,
        payment_start: date,
    ) -> None:
        self.collector_id = collector_id
        self.device_record_id = device_record_id
        self.installation_id = installation_id
        self.client_id = client_id
        self.loan_id = loan_id
        self.payment_start = payment_start

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
    release_date = date(2097, 10, 1)
    payment_start = release_date + timedelta(days=1)
    installation_id = f"x7-nc-voluntary-installation-{suffix}"
    settings = {
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
            (f"x7-ncv-{suffix}", f"7x7 NC Voluntary Collector {suffix}"),
        ).fetchone()[0]
        device_record_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'x7-nc-voluntary-test', 'active')
            returning id
            """,
            (collector_id, f"hash-{suffix}"),
        ).fetchone()[0]
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s, %s, 'Atomic NC voluntary disposable test', 120,
                      'seven_by_seven', 7.00, %s, true)
            returning id
            """,
            (f"X7NCV-{suffix}", f"7x7 NC Voluntary {suffix}", Jsonb(settings)),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients (client_code, full_name, area, status)
            values (%s, %s, 'Cardona', 'active') returning id
            """,
            (f"X7NCVC-{suffix}", f"7x7 NC Voluntary Client {suffix}"),
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
                f"X7NCVL-{suffix}",
                client_id,
                loan_type_id,
                release_date,
                release_date + timedelta(days=120),
                collector_id,
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_collection_state (
                loan_id, remaining_balance, is_reconciled, state_version
            ) values (%s, 3000.00, true, 0)
            on conflict (loan_id) do update
            set remaining_balance = excluded.remaining_balance,
                is_reconciled = true,
                state_version = 0,
                pass_count = 0,
                last_payment_date = null,
                advance_until = null,
                note = ''
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

        schedule_rows = generate_signed_seven_by_seven_schedule(
            original_principal=Decimal("3000.00"),
            agreed_daily_payment=Decimal("50.00"),
            daily_interest_per_1000=Decimal("7.00"),
            first_due_date=payment_start,
        )
        with connection.cursor() as cursor:
            register_verified_contract_schedule(
                cursor,
                loan_id=loan_id,
                payment_frequency="daily",
                contract_reference=f"SIGNED-X7-NCV-{suffix}",
                contract_signed_date=release_date,
                effective_from=release_date,
                grace_days=0,
                installments=schedule_rows,
                evidence_basis="signed_contract",
                evidence_reference=f"SIGNED-X7-NCV-DOC-{suffix}",
                verification_note="Borrower accepted the signed 50 peso daily payment.",
                verified_by_user_id=collector_id,
                confirmed=True,
            )

    return Case(
        collector_id=collector_id,
        device_record_id=device_record_id,
        installation_id=installation_id,
        client_id=client_id,
        loan_id=loan_id,
        payment_start=payment_start,
    )


def _declare_no_collection(case: Case) -> UUID:
    records = PostgresManagementNoCollectionRepository().declare_many(
        actor_user_id=case.collector_id,
        selections=(
            NoCollectionSelection(
                loan_id=case.loan_id,
                expected_operational_version=0,
            ),
        ),
        no_collection_date=case.payment_start,
        reason="Disposable test No Collection day.",
    )
    assert len(records) == 1
    record = records[0]
    assert record.adjustment_type == "no_collection"
    affected = [
        shift
        for shift in record.shifts
        if shift.prior_effective_due_date == case.payment_start
    ]
    assert len(affected) == 1
    assert affected[0].new_effective_due_date > case.payment_start
    return record.adjustment_id


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


def _command(
    case: Case,
    *,
    amount: str,
    device_sequence: int,
    route_revision: str,
    key: UUID | None = None,
) -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=key or uuid4(),
        route_entry_id=str(case.loan_id),
        client_id=str(case.client_id),
        loan_id=str(case.loan_id),
        collection_date=case.payment_start,
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal(amount),
        recorded_at=datetime.combine(
            case.payment_start,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ),
        device_id=case.installation_id,
        device_sequence=device_sequence,
        route_revision=route_revision,
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


def test_partial_then_same_day_full_nc_voluntary_completion_is_atomic_and_idempotent() -> None:
    case = _setup_case()
    source_adjustment_id = _declare_no_collection(case)
    assert _route_revision(case) == f"loan:{case.loan_id}:v1"

    partial_command = _command(
        case,
        amount="20.00",
        device_sequence=1,
        route_revision=_route_revision(case),
    )
    partial = _submit(case, partial_command)
    assert partial.status is CollectionStatus.ACCEPTED
    assert partial.posted is not None
    assert partial.posted.official_balance == Decimal("3000.00")
    assert partial.posted.route_revision == f"loan:{case.loan_id}:v2"

    with _connection_factory() as connection:
        partial_allocation = connection.execute(
            """
            select
                allocation.installment_id,
                allocation.amount_applied,
                allocation.allocation_basis
            from lending.loan_installment_payment_allocations allocation
            where allocation.transaction_id = %s
            """,
            (UUID(partial.posted.server_transaction_id),),
        ).fetchone()
        completion_count = connection.execute(
            """
            select count(*)
            from lending.loan_no_collection_voluntary_completions
            where no_collection_adjustment_id = %s
            """,
            (source_adjustment_id,),
        ).fetchone()[0]
        partial_receipt = connection.execute(
            """
            select
                previous_balance,
                official_balance,
                details->>'seven_by_seven_no_collection_plan_status',
                details->>'seven_by_seven_no_collection_keep_interest_holiday'
            from lending.collection_transactions
            where id = %s
            """,
            (UUID(partial.posted.server_transaction_id),),
        ).fetchone()

    assert partial_allocation is not None
    affected_installment_id = int(partial_allocation[0])
    assert partial_allocation[1:] == (
        Decimal("20.00"),
        "future_advance_oldest_first",
    )
    assert completion_count == 0
    assert partial_receipt == (
        Decimal("3000.00"),
        Decimal("3000.00"),
        "partial_shifted_prepayment",
        "true",
    )

    full_key = uuid4()
    full_command = _command(
        case,
        amount="30.00",
        device_sequence=2,
        route_revision=partial.posted.route_revision,
        key=full_key,
    )
    full = _submit(case, full_command)
    assert full.status is CollectionStatus.ACCEPTED
    assert full.posted is not None
    assert full.posted.official_balance == Decimal("2971.00")
    assert full.posted.route_revision == f"loan:{case.loan_id}:v3"

    retry = _submit(case, full_command)
    assert retry.status is CollectionStatus.DUPLICATE
    assert retry.posted is not None
    assert retry.posted.server_transaction_id == full.posted.server_transaction_id
    assert retry.posted.receipt_number == full.posted.receipt_number
    assert retry.posted.official_balance == Decimal("2971.00")

    with _connection_factory() as connection:
        completion = connection.execute(
            """
            select
                completion.adjustment_id,
                completion.no_collection_adjustment_id,
                completion.transaction_id,
                completion.affected_installment_id,
                completion.current_receipt_completion_amount,
                completion.prior_advance_activation_amount,
                adjustment.adjustment_type,
                adjustment.no_collection_date
            from lending.loan_no_collection_voluntary_completions completion
            join lending.loan_schedule_adjustments adjustment
              on adjustment.id = completion.adjustment_id
            where completion.no_collection_adjustment_id = %s
            """,
            (source_adjustment_id,),
        ).fetchone()
        full_allocation = connection.execute(
            """
            select installment_id, amount_applied, allocation_basis
            from lending.loan_installment_payment_allocations
            where transaction_id = %s
            """,
            (UUID(full.posted.server_transaction_id),),
        ).fetchone()
        full_receipt = connection.execute(
            """
            select
                previous_balance,
                official_balance,
                (details->>'seven_by_seven_interest_paid')::numeric,
                (details->>'seven_by_seven_principal_paid')::numeric,
                details->>'seven_by_seven_no_collection_plan_status',
                details->>'seven_by_seven_no_collection_keep_interest_holiday'
            from lending.collection_transactions
            where id = %s
            """,
            (UUID(full.posted.server_transaction_id),),
        ).fetchone()
        state = connection.execute(
            """
            select remaining_balance, state_version, last_payment_date
            from lending.loan_collection_state
            where loan_id = %s
            """,
            (case.loan_id,),
        ).fetchone()
        operational = connection.execute(
            """
            select operational_state.operational_version,
                   installment.effective_due_date
            from lending.loan_no_collection_voluntary_completions completion
            join lending.loan_schedule_adjustments adjustment
              on adjustment.id = completion.adjustment_id
            join lending.loan_schedule_operational_state operational_state
              on operational_state.schedule_id = adjustment.schedule_id
            join lending.loan_contract_installments_operational installment
              on installment.id = completion.affected_installment_id
            where completion.no_collection_adjustment_id = %s
            """,
            (source_adjustment_id,),
        ).fetchone()
        source_history = connection.execute(
            """
            select
                source.adjustment_type,
                source.no_collection_date,
                count(reversal.id)
            from lending.loan_schedule_adjustments source
            left join lending.loan_schedule_adjustments reversal
              on reversal.reverses_adjustment_id = source.id
             and reversal.adjustment_type = 'reversal'
            where source.id = %s
            group by source.id, source.adjustment_type, source.no_collection_date
            """,
            (source_adjustment_id,),
        ).fetchone()
        transaction_count = connection.execute(
            """
            select count(*)
            from lending.collection_transactions
            where loan_id = %s
              and collection_date = %s
              and is_voided = false
            """,
            (case.loan_id, case.payment_start),
        ).fetchone()[0]
        idempotency_count = connection.execute(
            """
            select count(*)
            from mobile.gilbic_collection_idempotency
            where idempotency_key = %s
            """,
            (full_key,),
        ).fetchone()[0]

    assert completion is not None
    assert completion[1] == source_adjustment_id
    assert completion[2] == UUID(full.posted.server_transaction_id)
    assert int(completion[3]) == affected_installment_id
    assert completion[4] == Decimal("30.00")
    assert completion[5] == Decimal("20.00")
    assert completion[6:] == ("voluntary_completion", case.payment_start)
    assert full_allocation == (
        affected_installment_id,
        Decimal("30.00"),
        "oldest_due_first",
    )
    assert full_receipt == (
        Decimal("3000.00"),
        Decimal("2971.00"),
        Decimal("21.00"),
        Decimal("29.00"),
        "full_voluntary_completion",
        "false",
    )
    assert state == (Decimal("2971.00"), 3, case.payment_start)
    assert operational == (2, case.payment_start)
    assert source_history == ("no_collection", case.payment_start, 0)
    assert transaction_count == 2
    assert idempotency_count == 1
