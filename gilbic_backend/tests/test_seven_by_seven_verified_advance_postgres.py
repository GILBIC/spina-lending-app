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


def _schema_supports_verified_advance() -> bool:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute(
            """
            select pg_get_constraintdef(oid)
            from pg_constraint
            where conrelid = 'lending.loan_installment_payment_allocations'::regclass
              and conname = 'loan_installment_payment_allocations_allocation_basis_check'
            """
        ).fetchone()
    return row is not None and "future_advance_oldest_first" in str(row[0])


def _setup_case() -> Case:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:12]
    release_date = date(2097, 9, 1)
    payment_start = release_date + timedelta(days=1)
    installation_id = f"x7-verified-advance-installation-{suffix}"
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
            (f"x7-va-{suffix}", f"7x7 Verified Advance Collector {suffix}"),
        ).fetchone()[0]
        device_record_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'x7-verified-advance-test', 'active')
            returning id
            """,
            (collector_id, f"hash-{suffix}"),
        ).fetchone()[0]
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s, %s, 'Verified future Advance disposable test', 120,
                      'seven_by_seven', 7.00, %s, true)
            returning id
            """,
            (f"X7VA-{suffix}", f"7x7 Verified Advance {suffix}", Jsonb(settings)),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients (client_code, full_name, area, status)
            values (%s, %s, 'Cardona', 'active') returning id
            """,
            (f"X7VAC-{suffix}", f"7x7 Verified Advance Client {suffix}"),
        ).fetchone()[0]
        loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (%s, %s, %s, 3000.00, 21.00, %s, %s, 'active', %s)
            returning id
            """,
            (
                f"X7VAL-{suffix}",
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
                contract_reference=f"SIGNED-X7-VA-{suffix}",
                contract_signed_date=release_date,
                effective_from=release_date,
                grace_days=0,
                installments=schedule_rows,
                evidence_basis="signed_contract",
                evidence_reference=f"SIGNED-X7-VA-DOC-{suffix}",
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


def _command(
    case: Case,
    *,
    entry_type: CollectionEntryType,
    amount: str,
    device_sequence: int,
    route_version: int,
    collection_date: date | None = None,
    covered_dates: tuple[date, ...] = (),
) -> CollectionCommand:
    actual_date = collection_date or case.payment_start
    selected = tuple(sorted(covered_dates))
    key = uuid4()
    return CollectionCommand(
        idempotency_key=key,
        route_entry_id=str(case.loan_id),
        client_id=str(case.client_id),
        loan_id=str(case.loan_id),
        collection_date=actual_date,
        entry_type=entry_type,
        amount=Decimal(amount),
        advance_from=(selected[0] if entry_type is CollectionEntryType.ADVANCE else None),
        advance_until=(selected[-1] if entry_type is CollectionEntryType.ADVANCE else None),
        covered_dates=selected,
        recorded_at=datetime.combine(actual_date, datetime.min.time(), tzinfo=timezone.utc),
        device_id=case.installation_id,
        device_sequence=device_sequence,
        note="",
        route_revision=f"loan:{case.loan_id}:v{route_version}",
        past_due_followup=None,
    )


def _submit(case: Case, command: CollectionCommand):
    headers = SubmissionHeaders(
        idempotency_key=command.idempotency_key,
        client_transaction_id=command.idempotency_key,
        device_id=case.installation_id,
        contract_version=CONTRACT_VERSION,
    )
    return _service().submit(actor=case.actor, headers=headers, command=command)


def test_verified_advance_is_future_row_evidence_without_receipt_date_financial_effect() -> None:
    if not _schema_supports_verified_advance():
        pytest.skip("Migration 0104 future Advance allocation basis is not installed")

    case = _setup_case()
    first_payment = _submit(
        case,
        _command(
            case,
            entry_type=CollectionEntryType.PAYMENT,
            amount="50.00",
            device_sequence=1,
            route_version=0,
        ),
    )
    assert first_payment.status is CollectionStatus.ACCEPTED
    assert first_payment.posted is not None
    assert first_payment.posted.official_balance == Decimal("2971.00")

    row2 = case.payment_start + timedelta(days=1)
    row3 = case.payment_start + timedelta(days=2)
    row4 = case.payment_start + timedelta(days=3)

    first_advance = _submit(
        case,
        _command(
            case,
            entry_type=CollectionEntryType.ADVANCE,
            amount="120.00",
            device_sequence=2,
            route_version=1,
            covered_dates=(row2, row3, row4),
        ),
    )
    assert first_advance.status is CollectionStatus.ACCEPTED
    assert first_advance.posted is not None
    assert first_advance.posted.official_balance == Decimal("2971.00")

    second_advance = _submit(
        case,
        _command(
            case,
            entry_type=CollectionEntryType.ADVANCE,
            amount="30.00",
            device_sequence=3,
            route_version=2,
            covered_dates=(row4,),
        ),
    )
    assert second_advance.status is CollectionStatus.ACCEPTED
    assert second_advance.posted is not None
    assert second_advance.posted.official_balance == Decimal("2971.00")

    with _connection_factory() as connection:
        state = connection.execute(
            """
            select remaining_balance, state_version, advance_until, last_payment_date
            from lending.loan_collection_state
            where loan_id = %s
            """,
            (case.loan_id,),
        ).fetchone()
        advance_rows = connection.execute(
            """
            select
                installment.installment_number,
                installment.effective_due_date,
                allocation.amount_applied,
                allocation.allocation_basis,
                transaction.id,
                transaction.previous_balance,
                transaction.official_balance,
                transaction.details->>'seven_by_seven_advance_financial_state'
            from lending.loan_installment_payment_allocations allocation
            join lending.loan_contract_installments_operational installment
              on installment.id = allocation.installment_id
            join lending.collection_transactions transaction
              on transaction.id = allocation.transaction_id
            where transaction.loan_id = %s
              and allocation.allocation_basis = 'future_advance_oldest_first'
            order by transaction.accepted_at, installment.installment_number
            """,
            (case.loan_id,),
        ).fetchall()

    assert state == (
        Decimal("2971.00"),
        3,
        row4,
        case.payment_start,
    )
    assert [
        (row[0], row[1], row[2], row[3], row[5], row[6], row[7])
        for row in advance_rows
    ] == [
        (2, row2, Decimal("50.00"), "future_advance_oldest_first", Decimal("2971.00"), Decimal("2971.00"), "deferred_until_effective_due_date"),
        (3, row3, Decimal("50.00"), "future_advance_oldest_first", Decimal("2971.00"), Decimal("2971.00"), "deferred_until_effective_due_date"),
        (4, row4, Decimal("20.00"), "future_advance_oldest_first", Decimal("2971.00"), Decimal("2971.00"), "deferred_until_effective_due_date"),
        (4, row4, Decimal("30.00"), "future_advance_oldest_first", Decimal("2971.00"), Decimal("2971.00"), "deferred_until_effective_due_date"),
    ]
