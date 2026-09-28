from __future__ import annotations

import importlib.util
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from spina_mobile_collections.contracts import (
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

_source = Path(__file__).with_name(
    "test_combined_collection_renewal_workflow_postgres.py"
)
_spec = importlib.util.spec_from_file_location("regular_advance_cases", _source)
assert _spec is not None and _spec.loader is not None
cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cases)


def test_verified_regular_advance_allocates_selected_dates_through_runtime_bridge() -> (
    None
):
    """A new non-voided ADV must reach the tuple-based allocator with row values."""
    assert DATABASE_URL is not None
    case = cases._setup_combined_case(verified_regular_schedule=True)
    selected = (date(2097, 8, 2), date(2097, 8, 3))
    key = uuid4()
    command = CollectionCommand(
        idempotency_key=key,
        route_entry_id=str(case.regular_loan_id),
        client_id=str(case.client_id),
        loan_id=str(case.regular_loan_id),
        collection_date=selected[0],
        entry_type=CollectionEntryType.ADVANCE,
        amount=Decimal("100.00"),
        advance_from=selected[0],
        advance_until=selected[-1],
        covered_dates=selected,
        recorded_at=datetime(2097, 8, 2, 1, tzinfo=UTC),
        device_id=case.installation_id,
        device_sequence=1,
        route_revision=f"loan:{case.regular_loan_id}:v0",
    )
    headers = SubmissionHeaders(
        idempotency_key=key,
        client_transaction_id=key,
        device_id=case.installation_id,
        contract_version=CONTRACT_VERSION,
    )
    service = CollectionSubmissionService(
        PostgresCollectionExecutor(
            connection_factory=lambda: psycopg.connect(DATABASE_URL),
            posting_bridge=ConcurrentReceiptSafeCollectionPostingBridge(),
        )
    )

    result = service.submit(actor=case.actor, headers=headers, command=command)

    assert result.status is CollectionStatus.ACCEPTED, result
    assert result.posted is not None
    transaction_id = UUID(result.posted.server_transaction_id)
    assert result.posted.official_balance == Decimal("4900.00")
    repeated = service.submit(actor=case.actor, headers=headers, command=command)
    assert repeated.status is CollectionStatus.DUPLICATE
    assert repeated.posted is not None
    assert repeated.posted.server_transaction_id == result.posted.server_transaction_id
    assert repeated.posted.receipt_number == result.posted.receipt_number
    assert repeated.posted.official_balance == result.posted.official_balance
    assert repeated.posted.accepted_at == result.posted.accepted_at
    assert repeated.posted.route_revision == result.posted.route_revision
    assert repeated.posted.result_metadata == result.posted.result_metadata

    with psycopg.connect(DATABASE_URL) as connection:
        receipt = connection.execute(
            """SELECT id,amount,applied_amount,unallocated_amount,is_voided
               FROM lending.collection_transactions WHERE loan_id=%s""",
            (case.regular_loan_id,),
        ).fetchall()
        assert receipt == [
            (
                transaction_id,
                Decimal("100.00"),
                Decimal("100.00"),
                Decimal("0.00"),
                False,
            )
        ]
        allocations = connection.execute(
            """SELECT i.installment_number,i.due_date,a.amount_applied,a.allocation_basis
               FROM lending.loan_installment_payment_allocations a
               JOIN lending.loan_contract_installments i ON i.id=a.installment_id
               WHERE a.transaction_id=%s ORDER BY i.installment_number""",
            (transaction_id,),
        ).fetchall()
        assert allocations == [
            (1, selected[0], Decimal("50.00"), "exact_covered_date"),
            (2, selected[1], Decimal("50.00"), "exact_covered_date"),
        ]
        covered = connection.execute(
            """SELECT covered_date FROM lending.collection_covered_dates
               WHERE transaction_id=%s ORDER BY covered_date""",
            (transaction_id,),
        ).fetchall()
        assert covered == [(selected[0],), (selected[1],)]
        state = connection.execute(
            """SELECT remaining_balance,state_version,advance_until
               FROM lending.loan_collection_state WHERE loan_id=%s""",
            (case.regular_loan_id,),
        ).fetchone()
        assert state == (Decimal("4900.00"), 1, selected[1])
