from contextlib import nullcontext
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from gilbic_backend.collection_posting import PostgresCollectionPostingBridge
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from gilbic_backend.seven_by_seven_collection_posting import (
    SevenBySevenAwarePerLoanContractCollectionPostingBridge,
)
from gilbic_backend.seven_by_seven_no_collection_voluntary_posting import (
    NoCollectionVoluntarySevenBySevenCollectionPostingBridge,
)
from spina_mobile_collections.contracts import CollectionStatus, PaymentAllocationIntent
from spina_mobile_collections.postgres import PostgresCollectionExecutor
from spina_mobile_collections.service import (
    CONTRACT_VERSION,
    CollectionSubmissionService,
    SubmissionHeaders,
)
from test_collection_posting import FakeCursor, actor, command, loan_row

from gilbic_backend import collection_posting, combined_collection_api


class SubmissionCursor(FakeCursor):
    """Synthetic SQL boundary; the service/executor/posting methods remain real."""

    def __init__(self, loan):
        super().__init__(loan)
        self.saved = None

    def execute(self, statement, parameters=None):
        super().execute(statement, parameters)
        sql = " ".join(statement.lower().split())
        if "from mobile.gilbic_collection_idempotency" in sql:
            self._next = self.saved
        elif "select state.state_version" in sql:
            self._next = {"state_version": self.loan["state_version"]}
        elif "coalesce(sum(applied_amount)" in sql and "as remaining_balance" in sql:
            self._next = {
                "applied_amount": self.same_day_applied_amount,
                "remaining_balance": self.loan["remaining_balance"],
            }
        elif "from lending.loans loan" in sql:
            self._next = dict(
                self.loan,
                activation_action="",
                activation_is_active=False,
                contract_allocation_enabled=False,
            )
        elif "update lending.loan_collection_state" in sql:
            self.loan.update(
                remaining_balance=parameters[0],
                pass_count=parameters[1],
                last_payment_date=parameters[2],
                state_version=parameters[5],
            )
        elif "insert into lending.collection_transactions" in sql:
            self.same_day_applied_amount = parameters[10]
        elif "insert into mobile.gilbic_collection_idempotency" in sql:
            self.saved = {
                "collector_account_id": parameters[1],
                "registered_device_id": parameters[2],
                "canonical_request_hash": parameters[3],
                "server_transaction_id": parameters[5],
                "receipt_number": parameters[6],
                "official_balance": parameters[7],
                "accepted_at": parameters[8],
                "route_revision": parameters[9],
                "result_payload": parameters[10].obj,
            }
        return self

    def fetchall(self):
        return []


class SubmissionConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def transaction(self):
        return nullcontext()

    def cursor(self, **kwargs):
        return self.cursor_instance


def freeze_clock(monkeypatch, instant):
    class ServerClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz)

    monkeypatch.setattr(collection_posting, "datetime", ServerClock)


def service_for(cursor, bridge=None):
    connection = SubmissionConnection(cursor)
    return CollectionSubmissionService(
        PostgresCollectionExecutor(
            connection_factory=lambda: connection,
            posting_bridge=bridge or ConcurrentReceiptSafeCollectionPostingBridge(),
        )
    )


def submit(service, value):
    return service.submit(
        actor=actor(),
        headers=SubmissionHeaders(
            idempotency_key=value.idempotency_key,
            client_transaction_id=value.idempotency_key,
            device_id=value.device_id,
            contract_version=CONTRACT_VERSION,
        ),
        command=value,
    )


def assert_no_date_side_effects(cursor):
    sql = "\n".join(statement.lower() for statement, _ in cursor.executions)
    assert "client_area_pending_transfers" not in sql
    assert "nextval" not in sql
    assert not any(
        statement.lstrip().lower().startswith(("insert", "update", "delete"))
        for statement, _ in cursor.executions
    )


@pytest.mark.parametrize(
    "bridge_type",
    [
        PostgresCollectionPostingBridge,
        ConcurrentReceiptSafeCollectionPostingBridge,
    ],
)
def test_future_collection_rejected_before_transfer_financial_or_sequence_effects(
    monkeypatch,
    bridge_type,
):
    freeze_clock(monkeypatch, datetime(2026, 10, 6, 4, tzinfo=timezone.utc))
    cursor = SubmissionCursor(loan_row())
    value = replace(
        command(),
        collection_date=date(2099, 1, 1),
        recorded_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )

    result = submit(service_for(cursor, bridge_type()), value)

    assert result.status is CollectionStatus.REJECTED
    assert result.code == "collection_date_in_future"
    assert cursor.loan["remaining_balance"] == Decimal("1000.00")
    assert cursor.loan["last_payment_date"] == date(2026, 7, 31)
    assert cursor.saved is None
    assert_no_date_side_effects(cursor)


@pytest.mark.parametrize(
    "bridge_type, intent",
    [
        (
            SevenBySevenAwarePerLoanContractCollectionPostingBridge,
            PaymentAllocationIntent.SCHEDULED,
        ),
        (
            NoCollectionVoluntarySevenBySevenCollectionPostingBridge,
            PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY,
        ),
        (
            ConcurrentReceiptSafeCollectionPostingBridge,
            PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY,
        ),
    ],
)
def test_seven_by_seven_override_rejects_future_before_posting(
    monkeypatch, bridge_type, intent
):
    freeze_clock(monkeypatch, datetime(2026, 10, 6, 4, tzinfo=timezone.utc))
    cursor = SubmissionCursor(
        loan_row(
            calculation_mode="seven_by_seven",
            settings={
                "mobile_collections_enabled": True,
                "mobile_seven_by_seven_enabled": True,
                "mobile_balance_mode": "direct_remaining_balance",
            },
        )
    )
    # An unavailable device would reject later; the future-date guard must run first.
    cursor.device_exists = False
    value = replace(
        command(), collection_date=date(2099, 1, 1), payment_allocation_intent=intent
    )

    result = submit(
        service_for(cursor, bridge_type()),
        value,
    )

    assert result.status is CollectionStatus.REJECTED
    assert result.code == "collection_date_in_future"
    assert_no_date_side_effects(cursor)


@pytest.mark.parametrize(
    "instant, expected",
    [
        (
            datetime(2026, 10, 6, 15, 59, 59, tzinfo=timezone.utc),
            CollectionStatus.REJECTED,
        ),
        (datetime(2026, 10, 6, 16, 0, tzinfo=timezone.utc), CollectionStatus.ACCEPTED),
    ],
)
def test_collection_admission_changes_at_manila_midnight(
    monkeypatch, instant, expected
):
    freeze_clock(monkeypatch, instant)
    cursor = SubmissionCursor(loan_row())
    value = replace(command(), collection_date=date(2026, 10, 7))

    result = submit(service_for(cursor), value)

    assert result.status is expected
    if expected is CollectionStatus.REJECTED:
        assert result.code == "collection_date_in_future"
        assert_no_date_side_effects(cursor)
    else:
        assert cursor.loan["last_payment_date"] == value.collection_date
        assert result.posted.receipt_number == "GBC-20261007-00000042"


@pytest.mark.parametrize("collection_date", [date(2026, 10, 6), date(2026, 8, 1)])
def test_current_and_valid_historical_collection_still_post(
    monkeypatch, collection_date
):
    freeze_clock(monkeypatch, datetime(2026, 10, 6, 4, tzinfo=timezone.utc))
    cursor = SubmissionCursor(loan_row())

    result = submit(
        service_for(cursor), replace(command(), collection_date=collection_date)
    )

    assert result.status is CollectionStatus.ACCEPTED
    assert cursor.loan["last_payment_date"] == collection_date
    assert cursor.loan["remaining_balance"] == Decimal("800.00")


@pytest.mark.parametrize(
    "replay_instant",
    [
        datetime(2026, 10, 7, 16, tzinfo=timezone.utc),
        datetime(2026, 10, 5, 4, tzinfo=timezone.utc),
    ],
)
def test_exact_committed_replay_survives_changed_business_date(
    monkeypatch, replay_instant
):
    freeze_clock(monkeypatch, datetime(2026, 10, 6, 4, tzinfo=timezone.utc))
    cursor = SubmissionCursor(loan_row())
    service = service_for(cursor)
    value = replace(command(), collection_date=date(2026, 10, 6))
    first = submit(service, value)
    assert first.status is CollectionStatus.ACCEPTED
    cursor.executions.clear()
    freeze_clock(monkeypatch, replay_instant)

    replay = submit(service, value)

    assert replay.status is CollectionStatus.DUPLICATE
    assert replay.posted.server_transaction_id == first.posted.server_transaction_id
    assert replay.posted.receipt_number == first.posted.receipt_number
    assert replay.posted.official_balance == first.posted.official_balance
    assert replay.posted.accepted_at == first.posted.accepted_at
    assert_no_date_side_effects(cursor)


@pytest.mark.parametrize(
    "instant, business_date",
    [
        (datetime(2026, 10, 6, 15, 59, 59, tzinfo=timezone.utc), date(2026, 10, 6)),
        (datetime(2026, 10, 6, 16, tzinfo=timezone.utc), date(2026, 10, 7)),
    ],
)
def test_combined_uses_same_manila_clock_and_retains_current_date_rule(
    monkeypatch,
    instant,
    business_date,
):
    freeze_clock(monkeypatch, instant)
    assert combined_collection_api._current_business_date() == business_date
    combined_collection_api._validate_current_route_date(business_date)
    with pytest.raises(HTTPException) as caught:
        combined_collection_api._validate_current_route_date(date(2026, 8, 1))
    assert caught.value.status_code == 422
