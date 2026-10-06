"""Collector mistake recovery using the real reversal and route repositories."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.collection_correction_repository import (
    PostgresCollectionCorrectionRepository,
)
from gilbic_backend.collection_void_repository import (
    CollectionVoidError,
    PostgresCollectionVoidRepository,
)
from gilbic_backend.collector_route_repository import PostgresCollectorRouteRepository
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from spina_mobile_collections.contracts import (
    CollectionCommand,
    CollectionEntryType,
    PastDueFollowupInput,
    PastDueReasonCode,
)
from test_combined_collection_renewal_workflow_postgres import (
    DATABASE_URL,
    _body,
    _client_for,
    _connect,
    _headers,
    _setup_combined_case,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL required"
)
DAY = date(2097, 8, 2)


def test_penalty_assessment_source_cannot_be_undone_by_collector():
    from psycopg.types.json import Jsonb
    from test_7x7_post_maturity_penalty_postgres import (
        FIRST_PENALTY_DAY,
        _payment,
        _project,
        _seed_case,
        freeze_verified_seven_by_seven_penalty_assessment,
    )

    with _connect() as conn:
        case = _seed_case(conn, suffix=uuid4().hex[:10])
        receipt = _payment(
            conn,
            case=case,
            collection_date=FIRST_PENALTY_DAY,
            amount=Decimal("2.00"),
            sequence=1,
        )
        with conn.cursor() as cursor:
            freeze_verified_seven_by_seven_penalty_assessment(
                cursor,
                loan_id=case["loan_id"],
                through_date=FIRST_PENALTY_DAY,
                source_transaction_id=receipt,
            )
        conn.execute(
            """insert into lending.loan_collection_state
               (loan_id, remaining_balance, state_version, is_reconciled)
               values (%s, 1000, 1, true)""",
            (case["loan_id"],),
        )
        conn.execute(
            "update lending.collection_transactions set details=%s where id=%s",
            (
                Jsonb(
                    {
                        "state_version_before": 0,
                        "state_version_after": 1,
                        "collection_state_before": {
                            "remaining_balance": "1000.00",
                            "pass_count": 0,
                            "last_payment_date": None,
                            "advance_until": None,
                            "note": "",
                            "state_version": 0,
                        },
                    }
                ),
                receipt,
            ),
        )
        area = f"Penalty recovery {uuid4().hex}"
        conn.execute(
            "update lending.clients set area=%s where id=%s", (area, case["client_id"])
        )
        conn.execute(
            "insert into lending.collector_area_assignments(collector_user_id,area,sort_order,is_active) values (%s,%s,0,true)",
            (case["actor_id"], area),
        )
    route = PostgresCollectorRouteRepository().get_today_route(
        collector_user_id=case["actor_id"],
        collector_name="Collector",
        route_date=FIRST_PENALTY_DAY,
    )
    entry = next(row for row in route.entries if row.loan_id == case["loan_id"])
    assert not entry.can_undo_today and not entry.can_edit_today
    with pytest.raises(CollectionVoidError, match="penalty"):
        PostgresCollectionVoidRepository().void_unremitted(
            actor_user_id=case["actor_id"],
            transaction_id=receipt,
            reason="Mistaken Pay",
            collector_business_date=FIRST_PENALTY_DAY,
            collector_expected_route_revision=f"loan:{case['loan_id']}:v1",
        )
    with _connect() as conn:
        assert not conn.execute(
            "select is_voided from lending.collection_transactions where id=%s",
            (receipt,),
        ).fetchone()[0]
        assert (
            _project(conn, case=case, as_of_date=FIRST_PENALTY_DAY).status
            != "management_review_required"
        )


@pytest.mark.parametrize("payoff", [False, True])
def test_other_area_original_recorder_can_find_own_payment_for_undo(
    monkeypatch, payoff
):
    from gilbic_backend import other_area_repository

    case, receipt = _paid_case(monkeypatch, contract=False, payoff=payoff)

    class BusinessClock:
        @staticmethod
        def now(_tz):
            return datetime(2097, 8, 2, tzinfo=UTC)

    monkeypatch.setattr(other_area_repository, "datetime", BusinessClock)
    with _connect() as conn:
        area = f"Cross Area {uuid4().hex}"
        conn.execute(
            "update lending.clients set area=%s where id=%s", (area, case.client_id)
        )
        name = conn.execute(
            "select full_name from lending.clients where id=%s", (case.client_id,)
        ).fetchone()[0]
    rows = other_area_repository.PostgresOtherAreaRepository().search(
        collector_user_id=case.collector_id,
        query=name,
    )
    entry = next(row for row in rows if row.loan_id == case.regular_loan_id)
    assert entry.can_undo_today
    assert entry.today_transaction_id == receipt
    assert not entry.can_enter_payment
    other = other_area_repository.PostgresOtherAreaRepository().search(
        collector_user_id=uuid4(),
        query=name,
    )
    assert not next(
        row for row in other if row.loan_id == case.regular_loan_id
    ).can_undo_today
    # A search result does not grant delegated-work access.
    assert (
        other_area_repository.PostgresOtherAreaRepository().list_work(
            collector_user_id=case.collector_id,
            collection_date=DAY,
        )
        == ()
    )
    _undo(case, receipt)
    refreshed = other_area_repository.PostgresOtherAreaRepository().search(
        collector_user_id=case.collector_id,
        query=name,
    )
    assert not next(
        row for row in refreshed if row.loan_id == case.regular_loan_id
    ).processed_today


def _paid_case(monkeypatch, *, contract=True, payoff=False, prior_count=0):
    from gilbic_backend import combined_collection_api

    monkeypatch.setattr(combined_collection_api, "_current_business_date", lambda: DAY)
    case = _setup_combined_case(verified_regular_schedule=contract)
    if prior_count:
        with _connect() as conn:
            conn.execute(
                "update lending.loan_collection_state set pass_count=%s, note='Opening route note' where loan_id=any(%s)",
                (prior_count, [case.regular_loan_id, case.seven_loan_id]),
            )
    if payoff:
        with _connect() as conn:
            conn.execute(
                "update lending.loan_collection_state set remaining_balance=50 where loan_id=%s",
                (case.regular_loan_id,),
            )
    key, body = _body(case)
    response = _client_for(case).post(
        "/api/v1/collector/collections/combined", headers=_headers(case, key), json=body
    )
    assert response.status_code == 200, response.text
    with _connect() as conn:
        receipt = conn.execute(
            "select id from lending.collection_transactions where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone()[0]
    return case, receipt


def _undo(case, receipt, **changes):
    args = {
        "actor_user_id": case.collector_id,
        "transaction_id": receipt,
        "reason": "Mistaken Pay tap",
        "collector_business_date": DAY,
        "collector_expected_route_revision": f"loan:{case.regular_loan_id}:v1",
    }
    args.update(changes)
    return PostgresCollectionVoidRepository().void_unremitted(**args)


@pytest.mark.parametrize("contract", [False, True])
def test_own_undo_restores_balance_route_and_schedule_once(monkeypatch, contract):
    case, receipt = _paid_case(monkeypatch, contract=contract)
    result = _undo(case, receipt)
    assert result.restored_balance == Decimal("5000.00")
    assert (
        _undo(case, receipt) == result
    )  # Lost response: same receipt, no second reversal.
    with _connect() as conn:
        assert conn.execute(
            "select remaining_balance, pass_count, state_version from lending.loan_collection_state where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal("5000.00"), 0, 2)
        assert (
            conn.execute(
                "select count(*) from lending.collection_transaction_voids where transaction_id=%s",
                (receipt,),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "select count(*) from lending.collection_covered_dates where transaction_id=%s",
                (receipt,),
            ).fetchone()[0]
            == 0
        )
        # Undo one loan must not silently undo the other leg of a combined Pay.
        assert (
            conn.execute(
                "select is_voided from lending.collection_transactions where loan_id=%s",
                (case.seven_loan_id,),
            ).fetchone()[0]
            is False
        )
    route = PostgresCollectorRouteRepository().get_today_route(
        collector_user_id=case.collector_id, collector_name="Collector", route_date=DAY
    )
    entry = next(row for row in route.entries if row.loan_id == case.regular_loan_id)
    assert entry.processed_today is False
    if contract:
        assert entry.contract_today_unpaid_amount == Decimal("50.00")


def test_two_simultaneous_undo_requests_return_one_reversal(monkeypatch):
    case, receipt = _paid_case(monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _undo(case, receipt), range(2)))
    assert results[0] == results[1]
    # A retry after midnight still confirms the same historical undo.
    assert _undo(case, receipt, collector_business_date=date(2097, 8, 3)) == results[0]
    with pytest.raises(CollectionVoidError):
        _undo(case, receipt, reason="Different request")


def test_older_first_receipt_cannot_invent_an_opening_missed_count(monkeypatch):
    case, receipt = _paid_case(monkeypatch, contract=False, prior_count=5)
    with _connect() as conn:
        conn.execute(
            "update lending.collection_transactions set details=details-'collection_state_before' where id=%s",
            (receipt,),
        )
    with pytest.raises(CollectionVoidError, match="prior state"):
        _undo(case, receipt)
    route = PostgresCollectorRouteRepository().get_today_route(
        collector_user_id=case.collector_id, collector_name="Collector", route_date=DAY
    )
    entry = next(row for row in route.entries if row.loan_id == case.regular_loan_id)
    assert not entry.can_undo_today and not entry.can_edit_today


@pytest.mark.parametrize(
    "linked_key", ["past_due_followup", "past_due_promise_progress"]
)
def test_simple_undo_does_not_leave_linked_followup_records_stale(
    monkeypatch, linked_key
):
    case, receipt = _paid_case(monkeypatch)
    from psycopg.types.json import Jsonb

    with _connect() as conn:
        conn.execute(
            "update lending.collection_transactions set details=details || %s where id=%s",
            (Jsonb({linked_key: {"linked_evidence": True}}), receipt),
        )
    with pytest.raises(CollectionVoidError, match="linked records"):
        _undo(case, receipt)
    with _connect() as conn:
        assert (
            conn.execute(
                "select is_voided from lending.collection_transactions where id=%s",
                (receipt,),
            ).fetchone()[0]
            is False
        )


@pytest.mark.parametrize("change", ["actor", "revision", "date", "locked"])
def test_undo_rejects_unauthorized_stale_or_protected_receipts(monkeypatch, change):
    case, receipt = _paid_case(monkeypatch)
    args = {}
    if change == "actor":
        args["actor_user_id"] = uuid4()
    elif change == "revision":
        args["collector_expected_route_revision"] = f"loan:{case.regular_loan_id}:v0"
    elif change == "date":
        args["collector_business_date"] = date(2097, 8, 3)
    else:
        with _connect() as conn:
            recipient = conn.execute(
                "insert into core.users(username, full_name, status) values (%s, 'Recipient', 'active') returning id",
                (str(uuid4()),),
            ).fetchone()[0]
            conn.execute(
                "insert into core.user_roles(user_id, role_id) select %s,id from core.roles where code='employee'",
                (recipient,),
            )
        from gilbic_backend.remittance_repository import PostgresRemittanceRepository

        PostgresRemittanceRepository().submit(
            expected_review_digest=PostgresRemittanceRepository().preview(collector_user_id=case.collector_id, collection_date=DAY).review_digest,
            collector_user_id=case.collector_id,
            recipient_user_id=recipient,
            collection_date=DAY,
            note="Test remittance",
        )
    with pytest.raises(CollectionVoidError):
        _undo(case, receipt, **args)
    with _connect() as conn:
        assert (
            conn.execute(
                "select is_voided from lending.collection_transactions where id=%s",
                (receipt,),
            ).fetchone()[0]
            is False
        )


def test_paid_off_today_remains_visible_for_correction(monkeypatch):
    case, receipt = _paid_case(monkeypatch, contract=False, payoff=True)
    route = PostgresCollectorRouteRepository().get_today_route(
        collector_user_id=case.collector_id, collector_name="Collector", route_date=DAY
    )
    entries = [row for row in route.entries if row.loan_id == case.regular_loan_id]
    assert len(entries) == 1
    assert entries[0].today_transaction_id == receipt
    assert entries[0].can_undo_today is True
    assert entries[0].can_enter_payment is False


def test_legacy_pay_to_not_pay_updates_receipt_application_and_missed_count(
    monkeypatch,
):
    case, receipt = _paid_case(monkeypatch, contract=False, prior_count=5)
    result = PostgresCollectionCorrectionRepository().correct_own_unremitted(
        actor_user_id=case.collector_id,
        transaction_id=receipt,
        entry_type="pass",
        amount=None,
        covered_dates=(),
        note="No cash",
        reason="Mistaken Pay tap",
        expected_route_revision=f"loan:{case.regular_loan_id}:v1",
    )
    assert result.official_balance == Decimal("5000.00")
    assert result.pass_count_after == 6
    with _connect() as conn:
        assert conn.execute(
            "select amount, applied_amount, unallocated_amount, allocation_state from lending.collection_transactions where id=%s",
            (receipt,),
        ).fetchone() == (
            Decimal("0.00"),
            Decimal("0.00"),
            Decimal("0.00"),
            "not_applicable",
        )
    corrected = PostgresCollectionCorrectionRepository().correct_own_unremitted(
        actor_user_id=case.collector_id,
        transaction_id=receipt,
        entry_type="payment",
        amount=Decimal("60.00"),
        covered_dates=(DAY,),
        note="Corrected cash",
        reason="Borrower paid after correction",
        expected_route_revision=f"loan:{case.regular_loan_id}:v2",
    )
    assert corrected.official_balance == Decimal("4940.00")
    with _connect() as conn:
        assert conn.execute(
            "select applied_amount, allocation_state from lending.collection_transactions where id=%s",
            (receipt,),
        ).fetchone() == (Decimal("60.00"), "fully_allocated")


@pytest.mark.parametrize("product", ["regular", "seven"])
def test_undo_preserves_opening_missed_count_before_recording_not_pay(
    monkeypatch, product
):
    case, receipt = _paid_case(monkeypatch, prior_count=5)
    loan = case.regular_loan_id if product == "regular" else case.seven_loan_id
    with _connect() as conn:
        receipt = conn.execute(
            "select id from lending.collection_transactions where loan_id=%s", (loan,)
        ).fetchone()[0]
    _undo(case, receipt, collector_expected_route_revision=f"loan:{loan}:v1")
    with _connect() as conn:
        assert conn.execute(
            "select pass_count, note from lending.loan_collection_state where loan_id=%s",
            (loan,),
        ).fetchone() == (5, "Opening route note")
        posted = ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
            conn,
            case.actor,
            CollectionCommand(
                idempotency_key=uuid4(),
                route_entry_id=str(loan),
                client_id=str(case.client_id),
                loan_id=str(loan),
                collection_date=DAY,
                entry_type=CollectionEntryType.PASS,
                amount=None,
                recorded_at=datetime(2097, 8, 2, 1, tzinfo=UTC),
                device_id=case.installation_id,
                device_sequence=9,
                route_revision=f"loan:{loan}:v2",
                note="Borrower did not pay",
                past_due_followup=PastDueFollowupInput(
                    reason_code=PastDueReasonCode.NO_CASH, note="No cash today"
                ),
            ),
        )
        assert posted.server_transaction_id
        assert (
            conn.execute(
                "select pass_count from lending.loan_collection_state where loan_id=%s",
                (loan,),
            ).fetchone()[0]
            == 6
        )
