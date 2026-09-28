from __future__ import annotations

import importlib.util
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from gilbic_backend.collector_schedule_repository import (
    PostgresCollectorScheduleRepository,
)
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from gilbic_backend.contract_collection_posting import CONTRACT_ALLOCATION_SETTING
from spina_mobile_collections.contracts import (
    CollectionCommand,
    CollectionEntryType,
    CollectionStatus,
    PastDueFollowupInput,
    PastDueReasonCode,
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
_spec = importlib.util.spec_from_file_location("regular_followup_cases", _source)
assert _spec is not None and _spec.loader is not None
cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cases)


@pytest.mark.parametrize(
    ("activated", "entry_type", "cash", "unpaid"),
    [
        pytest.param(
            True, CollectionEntryType.PAYMENT, "20.00", "30.00", id="activated-payment"
        ),
        pytest.param(
            True, CollectionEntryType.PASS, None, "50.00", id="activated-pass"
        ),
        pytest.param(
            False, CollectionEntryType.PAYMENT, "20.00", "30.00", id="legacy-payment"
        ),
    ],
)
def test_regular_followup_matches_the_posted_receipts_contract_mode(
    activated: bool, entry_type: CollectionEntryType, cash: str | None, unpaid: str
) -> None:
    """Per-loan activation must bind follow-up to its actual unpaid installment."""
    assert DATABASE_URL is not None
    case = cases._setup_combined_case(verified_regular_schedule=activated)
    with psycopg.connect(DATABASE_URL) as connection:
        # The live switch is immutable per-loan activation, not the retired
        # loan-type rollout flag. Keep that flag absent just like current API use.
        connection.execute(
            """UPDATE lending.loan_types SET settings=settings-%s
               WHERE id=(SELECT loan_type_id FROM lending.loans WHERE id=%s)""",
            (CONTRACT_ALLOCATION_SETTING, case.regular_loan_id),
        )
        first_installment = connection.execute(
            """SELECT i.id FROM lending.loan_contract_installments i
               JOIN lending.loan_contract_schedules s ON s.id=i.schedule_id
               WHERE s.loan_id=%s AND s.status='active' AND i.installment_number=1""",
            (case.regular_loan_id,),
        ).fetchone()
    key = uuid4()
    day, promise_day = date(2097, 8, 2), date(2097, 8, 3)
    command = CollectionCommand(
        idempotency_key=key,
        route_entry_id=str(case.regular_loan_id),
        client_id=str(case.client_id),
        loan_id=str(case.regular_loan_id),
        collection_date=day,
        entry_type=entry_type,
        amount=Decimal(cash) if cash is not None else None,
        recorded_at=datetime(2097, 8, 2, 1, tzinfo=UTC),
        device_id=case.installation_id,
        device_sequence=1,
        route_revision=f"loan:{case.regular_loan_id}:v0",
        past_due_followup=PastDueFollowupInput(
            reason_code=PastDueReasonCode.PROMISED_TO_PAY_LATER,
            note="Synthetic promise for the unpaid installment remainder.",
            promised_payment_date=promise_day,
            promised_amount=Decimal(unpaid),
        ),
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
    assert result.posted.official_balance == Decimal("5000.00") - Decimal(cash or "0")
    duplicate = service.submit(actor=case.actor, headers=headers, command=command)
    assert duplicate.status is CollectionStatus.DUPLICATE
    assert duplicate.posted is not None
    assert duplicate.posted.server_transaction_id == str(transaction_id)

    with psycopg.connect(DATABASE_URL) as connection:
        obligations = connection.execute(
            """SELECT installment_id,original_past_due_amount,remaining_past_due_amount,
                      current_reason_code,source_transaction_id
               FROM lending.past_due_obligations WHERE loan_id=%s""",
            (case.regular_loan_id,),
        ).fetchall()
        assert obligations == [
            (
                first_installment[0] if activated else None,
                Decimal(unpaid),
                Decimal(unpaid),
                "promised_to_pay_later",
                transaction_id,
            )
        ]
        promises = connection.execute(
            """SELECT p.promised_for_date,p.remaining_promised_amount,p.status,
                      link.target_amount,o.installment_id
               FROM lending.payment_promises p
               JOIN lending.payment_promise_obligations link ON link.promise_id=p.id
               JOIN lending.past_due_obligations o ON o.id=link.past_due_obligation_id
               WHERE p.loan_id=%s""",
            (case.regular_loan_id,),
        ).fetchall()
        assert promises == [
            (
                promise_day,
                Decimal(unpaid),
                "pending",
                Decimal(unpaid),
                first_installment[0] if activated else None,
            )
        ]
        receipt_count = connection.execute(
            "SELECT count(*) FROM lending.collection_transactions WHERE loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone()[0]
        assert receipt_count == 1

    if activated:
        schedule = PostgresCollectorScheduleRepository().get_schedule(
            collector_user_id=case.collector_id,
            loan_id=case.regular_loan_id,
            as_of_date=day,
        )
        first = next(row for row in schedule.rows if row.installment_number == 1)
        assert first.remaining_amount == Decimal(unpaid)
        assert first.past_due_reason_code == "promised_to_pay_later"
        assert first.promised_for_date == promise_day
        assert first.promise_remaining_amount == Decimal(unpaid)
        assert first.promise_status == "pending"
