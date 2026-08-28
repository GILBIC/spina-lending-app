from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.seven_by_seven_collection_posting import (
    SEVEN_BY_SEVEN_MOBILE_SETTING,
    SevenBySevenAwarePerLoanContractCollectionPostingBridge,
)
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)
from psycopg.types.json import Jsonb
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    CollectionStatus,
    PastDueFollowupInput,
    PastDueReasonCode,
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
            posting_bridge=SevenBySevenAwarePerLoanContractCollectionPostingBridge(),
        )
    )


def _setup_case(*, enabled: bool = True, principal: str = "5000.00") -> Case:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:12]
    release_date = date(2097, 8, 1)
    payment_start = release_date + timedelta(days=1)
    installation_id = f"x7-mobile-installation-{suffix}"
    settings = {
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
        SEVEN_BY_SEVEN_MOBILE_SETTING: enabled,
    }

    with psycopg.connect(DATABASE_URL) as connection:
        collector_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s, %s, 'active') returning id
            """,
            (f"x7-mobile-{suffix}", f"7x7 Mobile Collector {suffix}"),
        ).fetchone()[0]
        device_record_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', 'x7-b5-test', 'active')
            returning id
            """,
            (collector_id, f"hash-{suffix}"),
        ).fetchone()[0]
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s, %s, 'B.5 disposable 7x7 mobile acceptance', 120,
                      'seven_by_seven', 7.00, %s, true)
            returning id
            """,
            (f"X7M-{suffix}", f"7x7 Mobile {suffix}", Jsonb(settings)),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients (
                client_code, full_name, area, status
            ) values (%s, %s, 'Cardona', 'active') returning id
            """,
            (f"X7MC-{suffix}", f"7x7 Mobile Client {suffix}"),
        ).fetchone()[0]
        loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (%s, %s, %s, %s, 35.00, %s, %s, 'active', %s)
            returning id
            """,
            (
                f"X7ML-{suffix}",
                client_id,
                loan_type_id,
                principal,
                release_date,
                release_date + timedelta(days=120),
                collector_id,
            ),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_collection_state (
                loan_id, remaining_balance, is_reconciled, state_version
            ) values (%s, %s, true, 0)
            on conflict (loan_id) do update
            set remaining_balance = excluded.remaining_balance,
                is_reconciled = true,
                state_version = 0,
                pass_count = 0,
                last_payment_date = null,
                advance_until = null,
                note = ''
            """,
            (loan_id, principal),
        )
        connection.execute(
            """
            insert into lending.collector_area_assignments (
                collector_user_id, area, sort_order, is_active
            ) values (%s, 'Cardona', 0, true)
            """,
            (collector_id,),
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
    key: UUID | None = None,
    collection_date: date | None = None,
    entry_type: CollectionEntryType = CollectionEntryType.PAYMENT,
    amount: str | None = "200.00",
    device_sequence: int = 1,
    route_version: int = 0,
    covered_dates: tuple[date, ...] = (),
    note: str = "",
    past_due_followup: PastDueFollowupInput | None = None,
    payment_allocation_intent: PaymentAllocationIntent = PaymentAllocationIntent.SCHEDULED,
) -> CollectionCommand:
    actual_key = key or uuid4()
    actual_date = collection_date or case.payment_start
    selected = tuple(sorted(covered_dates))
    return CollectionCommand(
        idempotency_key=actual_key,
        route_entry_id=str(case.loan_id),
        client_id=str(case.client_id),
        loan_id=str(case.loan_id),
        collection_date=actual_date,
        entry_type=entry_type,
        amount=Decimal(amount) if amount is not None else None,
        advance_from=(
            selected[0] if entry_type is CollectionEntryType.ADVANCE else None
        ),
        advance_until=(
            selected[-1] if entry_type is CollectionEntryType.ADVANCE else None
        ),
        covered_dates=selected,
        recorded_at=datetime.combine(
            actual_date, datetime.min.time(), tzinfo=timezone.utc
        ),
        device_id=case.installation_id,
        device_sequence=device_sequence,
        note=note,
        route_revision=f"loan:{case.loan_id}:v{route_version}",
        past_due_followup=past_due_followup,
        payment_allocation_intent=payment_allocation_intent,
    )


def _register_verified_schedule(case: Case) -> None:
    rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("5000.00"),
        agreed_daily_payment=Decimal("50.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=case.payment_start,
    )
    with _connection_factory() as connection, connection.cursor() as cursor:
        register_verified_contract_schedule(
            cursor,
            loan_id=case.loan_id,
            payment_frequency="daily",
            contract_reference=f"SIGNED-X7-EXTRA-{case.loan_id}",
            contract_signed_date=case.payment_start - timedelta(days=1),
            effective_from=case.payment_start - timedelta(days=1),
            grace_days=0,
            installments=rows,
            evidence_basis="signed_contract",
            evidence_reference=f"SIGNED-X7-EXTRA-DOC-{case.loan_id}",
            verification_note="Borrower accepted the signed 50 peso daily payment.",
            verified_by_user_id=case.collector_id,
            confirmed=True,
        )


def _headers(case: Case, command: CollectionCommand) -> SubmissionHeaders:
    return SubmissionHeaders(
        idempotency_key=command.idempotency_key,
        client_transaction_id=command.idempotency_key,
        device_id=case.installation_id,
        contract_version=CONTRACT_VERSION,
    )


def _submit(case: Case, command: CollectionCommand):
    return _service().submit(
        actor=case.actor,
        headers=_headers(case, command),
        command=command,
    )


def test_mobile_payment_uses_fixed_interest_first_allocator_and_exact_receipt_balance() -> (
    None
):
    case = _setup_case()
    command = _command(case, amount="200.00")

    outcome = _submit(case, command)

    assert outcome.status is CollectionStatus.ACCEPTED
    assert outcome.posted is not None
    assert outcome.posted.official_balance == Decimal("4835.00")
    assert outcome.posted.receipt_number.startswith("GBC-20970802-")
    assert outcome.posted.route_revision == f"loan:{case.loan_id}:v1"

    with _connection_factory() as connection:
        row = connection.execute(
            """
            select amount, previous_balance, official_balance,
                   details->>'seven_by_seven_policy',
                   details->>'seven_by_seven_fixed_daily_interest',
                   details->>'seven_by_seven_interest_paid',
                   details->>'seven_by_seven_principal_paid',
                   details->>'seven_by_seven_closing_interest_arrears'
            from lending.collection_transactions
            where id = %s
            """,
            (UUID(outcome.posted.server_transaction_id),),
        ).fetchone()
        state = connection.execute(
            """
            select remaining_balance, state_version, pass_count, last_payment_date
            from lending.loan_collection_state where loan_id = %s
            """,
            (case.loan_id,),
        ).fetchone()

    assert row == (
        Decimal("200.00"),
        Decimal("5000.00"),
        Decimal("4835.00"),
        "seven_by_seven_operational_allocator_v2",
        "35.00",
        "35.00",
        "165.00",
        "0.00",
    )
    assert state == (Decimal("4835.00"), 1, 0, case.payment_start)


def test_exact_retry_is_duplicate_and_stale_route_requires_refresh_before_next_payment() -> (
    None
):
    case = _setup_case()
    first = _command(case, amount="200.00")

    accepted = _submit(case, first)
    duplicate = _submit(case, first)
    stale = _submit(
        case,
        _command(
            case,
            collection_date=case.payment_start + timedelta(days=1),
            amount="35.00",
            device_sequence=2,
            route_version=0,
        ),
    )
    refreshed = _submit(
        case,
        _command(
            case,
            collection_date=case.payment_start + timedelta(days=1),
            amount="35.00",
            device_sequence=2,
            route_version=1,
        ),
    )

    assert accepted.status is CollectionStatus.ACCEPTED
    assert duplicate.status is CollectionStatus.DUPLICATE
    assert duplicate.posted is not None and accepted.posted is not None
    assert (
        duplicate.posted.server_transaction_id == accepted.posted.server_transaction_id
    )
    assert stale.status is CollectionStatus.CONFLICT
    assert stale.code == "route_revision_changed"
    assert refreshed.status is CollectionStatus.ACCEPTED
    assert refreshed.posted is not None
    assert refreshed.posted.official_balance == Decimal("4835.00")
    assert refreshed.posted.route_revision == f"loan:{case.loan_id}:v2"

    with _connection_factory() as connection:
        count = connection.execute(
            "select count(*) from lending.collection_transactions where loan_id = %s",
            (case.loan_id,),
        ).fetchone()[0]
    assert count == 2


def test_exact_covered_dates_are_preserved_without_changing_7x7_cash_allocation_basis() -> (
    None
):
    case = _setup_case()
    selected = (
        case.payment_start,
        case.payment_start + timedelta(days=2),
        case.payment_start + timedelta(days=5),
    )
    command = _command(
        case,
        entry_type=CollectionEntryType.ADVANCE,
        amount="210.00",
        covered_dates=selected,
    )

    outcome = _submit(case, command)

    assert outcome.status is CollectionStatus.ACCEPTED
    assert outcome.posted is not None
    assert outcome.posted.official_balance == Decimal("4825.00")
    with _connection_factory() as connection:
        covered = tuple(
            row[0]
            for row in connection.execute(
                """
                select covered_date
                from lending.collection_covered_dates
                where transaction_id = %s
                order by covered_date
                """,
                (UUID(outcome.posted.server_transaction_id),),
            ).fetchall()
        )
        allocation = connection.execute(
            """
            select details->>'seven_by_seven_interest_paid',
                   details->>'seven_by_seven_principal_paid'
            from lending.collection_transactions where id = %s
            """,
            (UUID(outcome.posted.server_transaction_id),),
        ).fetchone()
    assert covered == selected
    assert allocation == ("35.00", "175.00")


def test_unable_to_pay_is_no_cash_and_later_payment_accrues_calendar_gap_interest() -> (
    None
):
    case = _setup_case()
    passed = _submit(
        case,
        _command(
            case,
            entry_type=CollectionEntryType.PASS,
            amount=None,
            past_due_followup=PastDueFollowupInput(
                reason_code=PastDueReasonCode.NO_CASH,
                note="Client had no collection cash today",
            ),
        ),
    )
    paid = _submit(
        case,
        _command(
            case,
            collection_date=case.payment_start + timedelta(days=1),
            amount="70.00",
            device_sequence=2,
            route_version=1,
        ),
    )

    assert passed.status is CollectionStatus.ACCEPTED
    assert passed.posted is not None
    assert passed.posted.official_balance == Decimal("5000.00")
    assert paid.status is CollectionStatus.ACCEPTED
    assert paid.posted is not None
    assert paid.posted.official_balance == Decimal("5000.00")

    with _connection_factory() as connection:
        rows = connection.execute(
            """
            select entry_type, amount, official_balance,
                   details->>'seven_by_seven_interest_due',
                   details->>'seven_by_seven_interest_paid'
            from lending.collection_transactions
            where loan_id = %s
            order by collection_date
            """,
            (case.loan_id,),
        ).fetchall()
    assert rows[0][:3] == ("pass", Decimal("0.00"), Decimal("5000.00"))
    assert rows[1] == (
        "payment",
        Decimal("70.00"),
        Decimal("5000.00"),
        "70.00",
        "70.00",
    )


def test_overpayment_and_unreconciled_history_fail_closed_without_official_write() -> (
    None
):
    overpay = _setup_case()
    rejected = _submit(overpay, _command(overpay, amount="6000.00"))
    assert rejected.status is CollectionStatus.REJECTED
    assert rejected.code == "amount_exceeds_seven_by_seven_payoff"

    mismatch = _setup_case()
    historical = _submit(mismatch, _command(mismatch, amount="200.00"))
    assert historical.status is CollectionStatus.ACCEPTED
    with _connection_factory() as connection:
        connection.execute(
            """
            update lending.loan_collection_state
            set remaining_balance = 5000.00
            where loan_id = %s
            """,
            (mismatch.loan_id,),
        )
    blocked = _submit(
        mismatch,
        _command(
            mismatch,
            collection_date=mismatch.payment_start + timedelta(days=1),
            amount="35.00",
            device_sequence=2,
            route_version=1,
        ),
    )
    assert blocked.status is CollectionStatus.REJECTED
    assert blocked.code == "seven_by_seven_balance_not_reconciled"

    with _connection_factory() as connection:
        overpay_count = connection.execute(
            "select count(*) from lending.collection_transactions where loan_id = %s",
            (overpay.loan_id,),
        ).fetchone()[0]
        mismatch_count = connection.execute(
            "select count(*) from lending.collection_transactions where loan_id = %s",
            (mismatch.loan_id,),
        ).fetchone()[0]
    assert overpay_count == 0
    assert mismatch_count == 1


def test_modern_extra_principal_posts_zero_interest_and_exact_immutable_effects() -> (
    None
):
    case = _setup_case()
    _register_verified_schedule(case)

    scheduled = _submit(case, _command(case, amount="50.00"))
    assert scheduled.status is CollectionStatus.ACCEPTED

    extra_command = _command(
        case,
        amount="100.00",
        device_sequence=2,
        route_version=1,
        payment_allocation_intent=(
            PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION
        ),
    )
    extra = _submit(case, extra_command)
    duplicate = _submit(case, extra_command)

    assert extra.status is CollectionStatus.ACCEPTED
    assert extra.posted is not None
    assert extra.posted.official_balance == Decimal("4885.00")
    assert extra.posted.result_metadata["principal_reduction"] == "100.00"
    assert extra.posted.result_metadata["interest_contribution"] == "0.00"
    assert duplicate.status is CollectionStatus.DUPLICATE
    assert duplicate.posted is not None
    assert duplicate.posted.result_metadata == extra.posted.result_metadata

    with _connection_factory() as connection:
        receipt = connection.execute(
            """
            select
                details->>'payment_allocation_intent',
                details->>'seven_by_seven_interest_paid',
                details->>'seven_by_seven_principal_paid'
            from lending.collection_transactions
            where id = %s
            """,
            (UUID(extra.posted.server_transaction_id),),
        ).fetchone()
        adjustment = connection.execute(
            """
            select principal_reduction, transaction_id
            from lending.seven_by_seven_extra_principal_adjustments
            where transaction_id = %s
            """,
            (UUID(extra.posted.server_transaction_id),),
        ).fetchone()
        signed_mismatch_count = connection.execute(
            """
            select count(*)
            from lending.seven_by_seven_extra_principal_adjustment_items item
            join lending.loan_contract_installments installment
              on installment.id = item.installment_id
            where item.adjustment_id = %s
              and (
                  item.signed_contractual_amount <> installment.contractual_amount
                  or item.signed_principal_component <> installment.principal_component
                  or item.signed_interest_component <> installment.interest_component
              )
            """,
            (UUID(extra.posted.result_metadata["adjustment_id"]),),
        ).fetchone()[0]

    assert receipt == (
        "extra_as_principal_reduction",
        "0.00",
        "100.00",
    )
    assert adjustment == (
        Decimal("100.00"),
        UUID(extra.posted.server_transaction_id),
    )
    assert signed_mismatch_count == 0


def test_legacy_voluntary_extra_cannot_activate_7x7_principal_reduction() -> None:
    case = _setup_case()
    _register_verified_schedule(case)
    scheduled = _submit(case, _command(case, amount="50.00"))
    assert scheduled.status is CollectionStatus.ACCEPTED

    rejected = _submit(
        case,
        _command(
            case,
            amount="100.00",
            device_sequence=2,
            route_version=1,
            payment_allocation_intent=PaymentAllocationIntent.VOLUNTARY_EXTRA,
        ),
    )

    assert rejected.status is CollectionStatus.REJECTED
    assert rejected.code == "seven_by_seven_extra_principal_intent_required"

    with _connection_factory() as connection:
        count = connection.execute(
            """
            select count(*)
            from lending.collection_transactions
            where loan_id = %s
            """,
            (case.loan_id,),
        ).fetchone()[0]
    assert count == 1


def test_dedicated_feature_flag_remains_fail_closed_until_explicitly_enabled() -> None:
    case = _setup_case(enabled=False)
    outcome = _submit(case, _command(case, amount="200.00"))

    assert outcome.status is CollectionStatus.REJECTED
    assert outcome.code == "seven_by_seven_mobile_disabled"
    with _connection_factory() as connection:
        count = connection.execute(
            "select count(*) from lending.collection_transactions where loan_id = %s",
            (case.loan_id,),
        ).fetchone()[0]
    assert count == 0
