from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_seven_by_seven_extra_principal_persistence_postgres import (
    _record_adjustment,
    _setup_case,
)

import gilbic_backend.collection_void_repository as void_repository_module
import gilbic_backend.refund_due_repository as refund_repository_module
from gilbic_backend.collection_void_repository import (
    CollectionVoidRecord,
    PostgresCollectionVoidRepository,
)
from gilbic_backend.refund_due_repository import PostgresRefundDueRepository
from gilbic_backend.seven_by_seven_extra_principal_reversal import (
    ExtraPrincipalReversalIdempotencyMismatch,
    ExtraPrincipalReversalRequestResult,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


@contextmanager
def _test_connection():
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        yield connection


def _require_0108_schema() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        relation = connection.execute(
            "select to_regclass("
            "'lending.seven_by_seven_extra_principal_reversal_requests'"
            ")"
        ).fetchone()[0]
    if relation is None:
        pytest.skip(
            "Migration 0108 is not installed; disposable bridge validation owns "
            "this test."
        )


def _seed_extra_principal_case() -> tuple[UUID, UUID, UUID]:
    assert DATABASE_URL is not None
    loan_id, client_id, collector_id, device_id, installment_id = _setup_case()
    unique_area = f"Reversal-{uuid4().hex[:12]}"
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "update lending.clients set area = %s where id = %s",
            (unique_area, client_id),
        )
        connection.execute(
            """
            insert into lending.collector_area_assignments (
                collector_user_id, area, sort_order, is_active
            ) values (%s, %s, 0, true)
            """,
            (collector_id, unique_area),
        )
        adjustment_id = _record_adjustment(
            connection,
            loan_id=loan_id,
            client_id=client_id,
            collector_id=collector_id,
            device_id=device_id,
            installment_id=installment_id,
            sequence=2,
            expected_version=0,
            prior_future_principal="3000.00",
            reduction="20.00",
            prior_principal="29.00",
            prior_amount="50.00",
            new_principal="9.00",
            new_amount="30.00",
            advance_before="35.00",
            advance_retained="30.00",
            refund_due="5.00",
        )
        transaction_id = connection.execute(
            """
            select transaction_id
            from lending.seven_by_seven_extra_principal_adjustments
            where id = %s
            """,
            (adjustment_id,),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_collection_state (
                loan_id, remaining_balance, is_reconciled, state_version
            ) values (%s, 3000.00, true, 1)
            on conflict (loan_id) do update
            set remaining_balance = excluded.remaining_balance,
                is_reconciled = true,
                state_version = excluded.state_version
            """,
            (loan_id,),
        )
        connection.execute(
            """
            update lending.collection_transactions
            set details = coalesce(details, '{}'::jsonb) || %s
            where id = %s
            """,
            (Jsonb({"state_version_after": 1}), transaction_id),
        )
    return adjustment_id, transaction_id, collector_id


def test_completed_extra_principal_void_request_replays_exact_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    _require_0108_schema()
    adjustment_id, transaction_id, actor_id = _seed_extra_principal_case()
    monkeypatch.setattr(void_repository_module, "open_connection", _test_connection)
    repository = PostgresCollectionVoidRepository()
    request_key = uuid4()

    first = repository.void_unremitted(
        actor_user_id=actor_id,
        transaction_id=transaction_id,
        reason="Wrong receipt",
        idempotency_key=request_key,
    )
    duplicate = repository.void_unremitted(
        actor_user_id=actor_id,
        transaction_id=transaction_id,
        reason="Wrong receipt",
        idempotency_key=request_key,
    )

    assert isinstance(first, CollectionVoidRecord)
    assert isinstance(duplicate, ExtraPrincipalReversalRequestResult)
    assert duplicate.outcome == "completed"
    assert duplicate.adjustment_id == adjustment_id
    assert duplicate.collection_void == first
    with psycopg.connect(DATABASE_URL) as connection:
        state = connection.execute(
            """
            select
                transaction.is_voided,
                (select count(*)
                   from lending.seven_by_seven_extra_principal_reversal_requests request
                  where request.idempotency_key = %s)
            from lending.collection_transactions transaction
            where transaction.id = %s
            """,
            (request_key, transaction_id),
        ).fetchone()
    assert state == (True, 1)


def test_released_refund_creates_durable_blocked_reversal_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    _require_0108_schema()
    adjustment_id, transaction_id, actor_id = _seed_extra_principal_case()
    monkeypatch.setattr(void_repository_module, "open_connection", _test_connection)
    monkeypatch.setattr(refund_repository_module, "open_connection", _test_connection)
    refunds = PostgresRefundDueRepository()
    approval = refunds.approve(
        idempotency_key=uuid4(),
        actor_user_id=actor_id,
        adjustment_id=adjustment_id,
        approved_amount=Decimal("5.00"),
        reason="Borrower requested physical return",
        authority_reference="MGT-REVERSAL-BLOCK-0001",
    )
    refunds.release(
        idempotency_key=uuid4(),
        actor_user_id=actor_id,
        approval_id=approval.approval_id,
        released_amount=Decimal("5.00"),
        released_at=datetime(2099, 1, 1, 9, tzinfo=UTC),
        evidence_reference="SIGNED-REFUND-REVERSAL-BLOCK-0001",
        evidence_digest="b" * 64,
    )
    repository = PostgresCollectionVoidRepository()
    request_key = uuid4()

    first = repository.void_unremitted(
        actor_user_id=actor_id,
        transaction_id=transaction_id,
        reason="Wrong receipt",
        idempotency_key=request_key,
    )
    duplicate = repository.void_unremitted(
        actor_user_id=actor_id,
        transaction_id=transaction_id,
        reason="Wrong receipt",
        idempotency_key=request_key,
    )

    assert isinstance(first, ExtraPrincipalReversalRequestResult)
    assert first == duplicate
    assert first.outcome == "blocked_refund_released"
    assert first.released_refund_amount == Decimal("5.00")
    with pytest.raises(ExtraPrincipalReversalIdempotencyMismatch):
        repository.void_unremitted(
            actor_user_id=actor_id,
            transaction_id=transaction_id,
            reason="Different reason",
            idempotency_key=request_key,
        )

    with psycopg.connect(DATABASE_URL) as connection:
        state = connection.execute(
            """
            select
                transaction.is_voided,
                (select count(*)
                   from lending.seven_by_seven_extra_principal_reversal_requests request
                  where request.idempotency_key = %s),
                (select outcome
                   from lending.seven_by_seven_extra_principal_reversal_requests request
                  where request.idempotency_key = %s)
            from lending.collection_transactions transaction
            where transaction.id = %s
            """,
            (request_key, request_key, transaction_id),
        ).fetchone()
    assert state == (False, 1, "blocked_refund_released")
