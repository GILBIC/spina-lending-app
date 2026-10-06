"""A void must restore proven state, including legacy opening route data."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.collection_correction_repository import (
    PostgresCollectionCorrectionRepository,
)
from gilbic_backend.collection_void_repository import (
    CollectionVoidConflict,
    PostgresCollectionVoidRepository,
)
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from psycopg.types.json import Jsonb
from spina_mobile_collections.contracts import (
    CollectionCommand,
    CollectionEntryType,
    PastDueFollowupInput,
    PastDueReasonCode,
)
from test_collector_payment_undo_postgres import DAY, _connect, _paid_case
from test_combined_collection_renewal_workflow_postgres import (
    DATABASE_URL,
    _setup_combined_case,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL required"
)


def _void(case, receipt, caller, version=1, business_date=DAY):
    options = {}
    if caller == "collector":
        options = {
            "collector_expected_route_revision": f"loan:{case.regular_loan_id}:v{version}",
            "collector_business_date": business_date,
        }
    return PostgresCollectionVoidRepository().void_unremitted(
        actor_user_id=case.collector_id,
        transaction_id=receipt,
        reason="Correct mistaken legacy receipt",
        **options,
    )


def _snapshot(case, receipt):
    with _connect() as conn:
        return {
            "state": conn.execute(
                "select to_jsonb(s) from lending.loan_collection_state s where loan_id=%s",
                (case.regular_loan_id,),
            ).fetchone()[0],
            "receipt": conn.execute(
                "select to_jsonb(t) from lending.collection_transactions t where id=%s",
                (receipt,),
            ).fetchone()[0],
            "covered": conn.execute(
                "select covered_date from lending.collection_covered_dates where transaction_id=%s order by covered_date",
                (receipt,),
            ).fetchall(),
            "voids": conn.execute(
                "select id from lending.collection_transaction_voids where transaction_id=%s",
                (receipt,),
            ).fetchall(),
            "loan": conn.execute(
                "select status from lending.loans where id=%s", (case.regular_loan_id,)
            ).fetchone(),
            "audit_count": conn.execute(
                "select count(*) from core.audit_logs where actor_user_id=%s",
                (case.collector_id,),
            ).fetchone()[0],
        }


@pytest.mark.parametrize("caller", ["management", "collector"])
def test_missing_first_receipt_state_rejects_without_mutation(monkeypatch, caller):
    case, receipt = _paid_case(monkeypatch, contract=False, prior_count=5)
    with _connect() as conn:
        conn.execute(
            "update lending.collection_transactions set details=details-'collection_state_before' where id=%s",
            (receipt,),
        )
    before = _snapshot(case, receipt)
    with pytest.raises(CollectionVoidConflict, match="prior state"):
        _void(case, receipt, caller)
    assert _snapshot(case, receipt) == before


@pytest.mark.parametrize("caller", ["management", "collector"])
def test_saved_state_restores_opening_missed_count_and_note(monkeypatch, caller):
    case, receipt = _paid_case(monkeypatch, contract=False, prior_count=5)
    _void(case, receipt, caller)
    with _connect() as conn:
        assert conn.execute(
            "select remaining_balance,pass_count,note,state_version from lending.loan_collection_state where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal("5000.00"), 5, "Opening route note", 2)


@pytest.mark.parametrize("caller", ["management", "collector"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("pass_count", True),
        ("pass_count", 5.75),
        ("state_version", False),
        ("state_version", 0.75),
    ],
)
def test_saved_state_rejects_noninteger_count_or_version(
    monkeypatch, caller, field, value
):
    case, receipt = _paid_case(monkeypatch, contract=False, prior_count=5)
    with _connect() as conn:
        conn.execute(
            "update lending.collection_transactions set details=jsonb_set(details,%s,%s) where id=%s",
            (["collection_state_before", field], Jsonb(value), receipt),
        )
    before = _snapshot(case, receipt)
    with pytest.raises(CollectionVoidConflict, match="prior state"):
        _void(case, receipt, caller)
    assert _snapshot(case, receipt) == before


def _legacy_receipt_pair(
    *, previous_pass=False, previous_snapshot=True, previous_note="Prior route note"
):
    case = _setup_combined_case(verified_regular_schedule=False)
    prior_day = DAY - timedelta(days=1)
    with _connect() as conn:
        conn.execute(
            """update lending.loan_collection_state
               set pass_count=5,note='Opening route note',last_payment_date=%s
               where loan_id=%s""",
            (DAY - timedelta(days=5), case.regular_loan_id),
        )
        receipts = []
        for sequence, day in enumerate((prior_day, DAY), start=1):
            is_pass = sequence == 1 and previous_pass
            result = ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
                conn,
                case.actor,
                CollectionCommand(
                    idempotency_key=uuid4(),
                    route_entry_id=str(case.regular_loan_id),
                    client_id=str(case.client_id),
                    loan_id=str(case.regular_loan_id),
                    collection_date=day,
                    entry_type=CollectionEntryType.PASS
                    if is_pass
                    else CollectionEntryType.PAYMENT,
                    amount=None if is_pass else Decimal("50.00"),
                    recorded_at=datetime(day.year, day.month, day.day, 1, tzinfo=UTC),
                    device_id=case.installation_id,
                    device_sequence=sequence,
                    route_revision=f"loan:{case.regular_loan_id}:v{sequence - 1}",
                    note=previous_note if sequence == 1 else "Mistaken payment",
                    past_due_followup=PastDueFollowupInput(
                        reason_code=PastDueReasonCode.NO_CASH, note="No cash today"
                    )
                    if is_pass
                    else None,
                ),
            )
            receipts.append(result.server_transaction_id)
        conn.execute(
            "update lending.collection_transactions set details=details-'collection_state_before' where id=%s",
            (receipts[1],),
        )
        if not previous_snapshot:
            conn.execute(
                "update lending.collection_transactions set details=details-'collection_state_before' where id=%s",
                (receipts[0],),
            )
    return case, receipts[0], receipts[1]


@pytest.mark.parametrize("caller", ["management", "collector"])
@pytest.mark.parametrize("previous_pass", [False, True])
@pytest.mark.parametrize("previous_note", ["Prior route note", ""])
def test_verified_previous_receipt_restores_exact_route_state(
    caller, previous_pass, previous_note
):
    case, _, receipt = _legacy_receipt_pair(
        previous_pass=previous_pass, previous_note=previous_note
    )
    _void(case, receipt, caller, version=2)
    with _connect() as conn:
        assert conn.execute(
            """select remaining_balance,pass_count,note,last_payment_date,state_version
               from lending.loan_collection_state where loan_id=%s""",
            (case.regular_loan_id,),
        ).fetchone() == (
            Decimal("5000.00") if previous_pass else Decimal("4950.00"),
            6 if previous_pass else 0,
            previous_note or "Opening route note",
            DAY - timedelta(days=5 if previous_pass else 1),
            3,
        )


@pytest.mark.parametrize("caller", ["management", "collector"])
@pytest.mark.parametrize(
    "problem",
    [
        "version_gap",
        "balance_mismatch",
        "pass_without_snapshot",
        "inherited_note_without_snapshot",
    ],
)
def test_unverified_previous_receipt_cannot_supply_prior_state(caller, problem):
    case, previous, receipt = _legacy_receipt_pair(
        previous_pass=problem == "pass_without_snapshot",
        previous_snapshot=False,
        previous_note=""
        if problem == "inherited_note_without_snapshot"
        else "Prior route note",
    )
    with _connect() as conn:
        if problem == "version_gap":
            conn.execute(
                "update lending.collection_transactions set details=details || %s where id=%s",
                (Jsonb({"state_version_after": 0}), previous),
            )
        elif problem == "balance_mismatch":
            conn.execute(
                "update lending.collection_transactions set official_balance=4900 where id=%s",
                (previous,),
            )
    before = _snapshot(case, receipt)
    with pytest.raises(CollectionVoidConflict, match="prior state"):
        _void(case, receipt, caller, version=2)
    assert _snapshot(case, receipt) == before


@pytest.mark.parametrize("caller", ["management", "collector"])
def test_previous_correction_that_cleared_note_stays_cleared(monkeypatch, caller):
    case, previous = _paid_case(monkeypatch, contract=False, prior_count=5)
    PostgresCollectionCorrectionRepository().correct_own_unremitted(
        actor_user_id=case.collector_id,
        transaction_id=previous,
        entry_type="payment",
        amount=Decimal("50.00"),
        covered_dates=(DAY,),
        note="",
        reason="Clear outdated route note",
        expected_route_revision=f"loan:{case.regular_loan_id}:v1",
    )
    next_day = DAY + timedelta(days=1)
    with _connect() as conn:
        result = ConcurrentReceiptSafeCollectionPostingBridge().post_collection(
            conn,
            case.actor,
            CollectionCommand(
                idempotency_key=uuid4(),
                route_entry_id=str(case.regular_loan_id),
                client_id=str(case.client_id),
                loan_id=str(case.regular_loan_id),
                collection_date=next_day,
                entry_type=CollectionEntryType.PAYMENT,
                amount=Decimal("50.00"),
                recorded_at=datetime(
                    next_day.year, next_day.month, next_day.day, 1, tzinfo=UTC
                ),
                device_id=case.installation_id,
                device_sequence=9,
                route_revision=f"loan:{case.regular_loan_id}:v2",
                note="Mistaken payment",
            ),
        )
        receipt = result.server_transaction_id
        conn.execute(
            "update lending.collection_transactions set details=details-'collection_state_before' where id=%s",
            (receipt,),
        )
    _void(case, receipt, caller, version=3, business_date=next_day)
    with _connect() as conn:
        assert conn.execute(
            "select remaining_balance,note,last_payment_date from lending.loan_collection_state where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal("4950.00"), "", DAY)
