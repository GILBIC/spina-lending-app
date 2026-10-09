"""Financial audit regressions against a disposable database and real owners."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import test_treasury_collection_posting_postgres as treasury_cases
from gilbic_backend.collection_correction_repository import (
    CollectionCorrectionInvalid,
    PostgresCollectionCorrectionRepository,
)
from gilbic_backend.collection_void_repository import (
    CollectionVoidConflict,
    CollectionVoidInvalid,
    PostgresCollectionVoidRepository,
)
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from gilbic_backend.past_due_promise_progress import PastDuePromiseProgress
from gilbic_backend.treasury_models import AllocationPreview, ReceiptApply
from spina_mobile_collections.contracts import (
    CollectionCommand,
    CollectionEntryType,
    PastDueFollowupInput,
    PastDueReasonCode,
)
from test_collection_void_prior_state_postgres import _snapshot
from test_collector_payment_undo_postgres import DAY, _connect, _paid_case
from test_combined_collection_renewal_workflow_postgres import (
    DATABASE_URL,
    _setup_combined_case,
)
from test_treasury_collection_posting_postgres import _input, adapter

from gilbic_backend import collection_posting

receipt_case = treasury_cases.receipt_case

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL required"
)


def _payment(conn, case, *, amount, sequence, followup=None, day=DAY, bridge=None):
    version = conn.execute(
        "select state_version from lending.loan_collection_state where loan_id=%s",
        (case.regular_loan_id,),
    ).fetchone()[0]
    return (bridge or ConcurrentReceiptSafeCollectionPostingBridge()).post_collection(
        conn,
        case.actor,
        CollectionCommand(
            idempotency_key=uuid4(),
            route_entry_id=str(case.regular_loan_id),
            client_id=str(case.client_id),
            loan_id=str(case.regular_loan_id),
            collection_date=day,
            entry_type=CollectionEntryType.PAYMENT,
            amount=Decimal(amount),
            recorded_at=datetime.combine(day, datetime.min.time(), UTC),
            device_id=case.installation_id,
            device_sequence=sequence,
            route_revision=f"loan:{case.regular_loan_id}:v{version}",
            past_due_followup=followup,
        ),
    )


def _promise():
    return PastDueFollowupInput(
        reason_code=PastDueReasonCode.PROMISED_TO_PAY_LATER,
        promised_payment_date=DAY,
        promised_amount=Decimal("25.00"),
    )


def _correct(case, receipt, amount, version=1):
    return PostgresCollectionCorrectionRepository().correct_own_unremitted(
        actor_user_id=case.collector_id,
        transaction_id=receipt,
        entry_type="payment",
        amount=Decimal(amount),
        covered_dates=(DAY,),
        note="Corrected receipt",
        reason="Correct actual cash received",
        expected_route_revision=f"loan:{case.regular_loan_id}:v{version}",
    )


def test_reduced_legacy_correction_requires_complete_past_due_replacement(monkeypatch):
    case, receipt = _paid_case(monkeypatch, contract=False)
    before = _snapshot(case, receipt)
    with pytest.raises(CollectionCorrectionInvalid, match="Past Due"):
        _correct(case, receipt, "25.00")
    assert _snapshot(case, receipt) == before
    # The error's recovery route is executable, including the required reason.
    PostgresCollectionVoidRepository().void_unremitted(
        actor_user_id=case.collector_id,
        transaction_id=receipt,
        reason="Replace incorrect cash amount",
        collector_business_date=DAY,
        collector_expected_route_revision=f"loan:{case.regular_loan_id}:v1",
    )
    with _connect() as conn:
        replacement = _payment(
            conn, case, amount="25.00", sequence=10, followup=_promise()
        )
        assert replacement.official_balance == Decimal("4975.00")
        assert conn.execute(
            "select remaining_past_due_amount from lending.past_due_obligations where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone()[0] == Decimal("25.00")


def test_full_legacy_correction_preserves_coverage(monkeypatch):
    case, receipt = _paid_case(monkeypatch, contract=False)
    assert _correct(case, receipt, "50.00").covered_dates == (DAY,)


def test_legacy_correction_counts_other_same_day_applied_receipts(monkeypatch):
    monkeypatch.setattr(
        collection_posting, "current_collection_business_date", lambda: DAY
    )
    case = _setup_combined_case(verified_regular_schedule=False)
    # Older legacy receipts predate follow-up capture; use their original owner.
    with _connect() as conn:
        bridge = collection_posting.PostgresCollectionPostingBridge()
        _payment(conn, case, amount="20.00", sequence=1, bridge=bridge)
        second = _payment(conn, case, amount="30.00", sequence=2, bridge=bridge)
    receipt = UUID(second.server_transaction_id)
    assert _correct(case, receipt, "30.00", version=2).covered_dates == (DAY,)
    before = _snapshot(case, receipt)
    with pytest.raises(CollectionCorrectionInvalid, match="Past Due"):
        _correct(case, receipt, "29.99", version=3)
    assert _snapshot(case, receipt) == before


@pytest.mark.parametrize(
    "second_amount,remaining,status",
    [
        ("25.00", "0.00", "kept"),
        ("10.00", "15.00", "pending"),
    ],
)
def test_legacy_same_day_receipts_reduce_linked_promise(
    monkeypatch, second_amount, remaining, status
):
    monkeypatch.setattr(
        collection_posting, "current_collection_business_date", lambda: DAY
    )
    case = _setup_combined_case(verified_regular_schedule=False)
    with _connect() as conn:
        _payment(conn, case, amount="25.00", sequence=1, followup=_promise())
        paid = _payment(conn, case, amount=second_amount, sequence=2)
        # Reconciliation is based on protected applied totals, so repeated progress
        # must not spend the same receipt twice.
        PastDuePromiseProgress().apply(
            conn, transaction_id=UUID(paid.server_transaction_id), collection_date=DAY
        )
        assert conn.execute(
            "select remaining_past_due_amount,status from lending.past_due_obligations where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal(remaining), "paid" if remaining == "0.00" else "open")
        assert conn.execute(
            "select remaining_promised_amount,status from lending.payment_promises where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal(remaining), status)
        PastDuePromiseProgress().apply(
            conn,
            transaction_id=UUID(paid.server_transaction_id),
            collection_date=DAY + timedelta(days=1),
        )
        assert conn.execute(
            "select status from lending.payment_promises where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone()[0] == ("kept" if status == "kept" else "partially_kept")


@pytest.mark.parametrize("activated", [False, True])
def test_management_void_rejects_linked_paid_progress_without_mutation(
    monkeypatch, activated
):
    monkeypatch.setattr(
        collection_posting, "current_collection_business_date", lambda: DAY
    )
    case = _setup_combined_case(verified_regular_schedule=activated)
    with _connect() as conn:
        _payment(conn, case, amount="25.00", sequence=1, followup=_promise())
        paid = _payment(conn, case, amount="25.00", sequence=2)
        assert conn.execute(
            "select remaining_promised_amount,status from lending.payment_promises where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal("0.00"), "kept")
    receipt = UUID(paid.server_transaction_id)
    before = _snapshot(case, receipt)
    with pytest.raises(CollectionVoidInvalid, match="linked|Past Due"):
        PostgresCollectionVoidRepository().void_unremitted(
            actor_user_id=case.collector_id,
            transaction_id=receipt,
            reason="Correct mistaken repayment",
        )
    assert _snapshot(case, receipt) == before


@pytest.mark.parametrize("stale", [None, "seven", "regular"])
def test_treasury_three_component_reversal_retains_version_conflict_protection(
    receipt_case, stale
):
    conn, case, actor, receipt = receipt_case
    balances_before = conn.execute(
        "select loan_id, remaining_balance from lending.loan_collection_state where loan_id=any(%s) order by loan_id",
        ([case.regular_loan_id, case.seven_loan_id],),
    ).fetchall()
    inputs = _input(
        conn, case, total_amount="109.00", extra_choice="seven_by_seven_advance"
    )
    preview = adapter.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    assert preview["can_apply"], preview
    result = adapter.apply_receipt(
        conn,
        actor,
        receipt,
        ReceiptApply(
            **inputs,
            action="receipt_apply",
            request_id=uuid4(),
            account_id=receipt["account_id"],
            receipt_id=receipt["id"],
            digest=preview["digest"],
        ),
    )
    assert len(result["transaction_ids"]) == 3
    if stale:
        conn.execute(
            "update lending.loan_collection_state set state_version=state_version+1 where loan_id=%s",
            (case.seven_loan_id if stale == "seven" else case.regular_loan_id,),
        )

    def reverse():
        with conn.transaction():
            return adapter.reverse_application(
                conn,
                actor,
                receipt,
                {"id": uuid4(), "source_result": result},
                SimpleNamespace(
                    request_id=uuid4(), reason="Correct three component allocation"
                ),
            )

    if stale:
        with pytest.raises(CollectionVoidConflict, match="changed|latest"):
            reverse()
    else:
        assert reverse()["status"] == "reversed"
    assert conn.execute(
        "select count(*) n from lending.collection_transactions where funding_receipt_id=%s and is_voided",
        (receipt["id"],),
    ).fetchone()["n"] == (0 if stale else 3)
    if not stale:
        assert (
            conn.execute(
                "select loan_id, remaining_balance from lending.loan_collection_state where loan_id=any(%s) order by loan_id",
                ([case.regular_loan_id, case.seven_loan_id],),
            ).fetchall()
            == balances_before
        )
        assert conn.execute(
            "select amount,refunded_amount from treasury.receipts where id=%s",
            (receipt["id"],),
        ).fetchone() == {
            "amount": Decimal("2000.00"),
            "refunded_amount": Decimal("0.00"),
        }


def test_legacy_progress_does_not_assign_next_day_payment_to_old_promise(monkeypatch):
    monkeypatch.setattr(
        collection_posting,
        "current_collection_business_date",
        lambda: DAY + timedelta(days=1),
    )
    case = _setup_combined_case(verified_regular_schedule=False)
    with _connect() as conn:
        _payment(conn, case, amount="25.00", sequence=1, followup=_promise())
        _payment(conn, case, amount="50.00", sequence=2, day=DAY + timedelta(days=1))
        assert conn.execute(
            "select remaining_past_due_amount,status from lending.past_due_obligations where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal("25.00"), "open")
        assert conn.execute(
            "select remaining_promised_amount,status from lending.payment_promises where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal("25.00"), "not_kept")


def test_legacy_final_balance_caps_past_due_and_clears_promise_on_payoff(monkeypatch):
    monkeypatch.setattr(
        collection_posting, "current_collection_business_date", lambda: DAY
    )
    case = _setup_combined_case(verified_regular_schedule=False)
    with _connect() as conn:
        conn.execute(
            "update lending.loan_collection_state set remaining_balance=35 where loan_id=%s",
            (case.regular_loan_id,),
        )
        _payment(
            conn,
            case,
            amount="25.00",
            sequence=1,
            followup=PastDueFollowupInput(
                reason_code=PastDueReasonCode.PROMISED_TO_PAY_LATER,
                promised_payment_date=DAY,
                promised_amount=Decimal("10.00"),
            ),
        )
        assert conn.execute(
            "select original_past_due_amount,remaining_past_due_amount from lending.past_due_obligations where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == (Decimal("10.00"), Decimal("10.00"))
        paid = _payment(conn, case, amount="10.00", sequence=2)
        assert paid.official_balance == Decimal("0.00")
        assert conn.execute(
            "select status,remaining_past_due_amount from lending.past_due_obligations where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == ("paid", Decimal("0.00"))
        assert conn.execute(
            "select status,remaining_promised_amount from lending.payment_promises where loan_id=%s",
            (case.regular_loan_id,),
        ).fetchone() == ("kept", Decimal("0.00"))


@pytest.mark.parametrize(
    "invalid_proof", ["other_loan", "other_application", "changed_state"]
)
def test_treasury_reversal_continuation_rejects_unrelated_or_stale_void(
    receipt_case, invalid_proof
):
    conn, case, actor, receipt = receipt_case
    inputs = _input(
        conn, case, total_amount="109.00", extra_choice="seven_by_seven_advance"
    )
    preview = adapter.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    posted = adapter.apply_receipt(
        conn,
        actor,
        receipt,
        ReceiptApply(
            **inputs,
            action="receipt_apply",
            request_id=uuid4(),
            account_id=receipt["account_id"],
            receipt_id=receipt["id"],
            digest=preview["digest"],
        ),
    )
    first_seven, regular, extra = [UUID(value) for value in posted["transaction_ids"]]
    repo = PostgresCollectionVoidRepository()

    def void(tx, previous=None):
        conn.execute(
            "select set_config('spina.treasury_application_reversal','on',true)"
        )
        return repo.void_unremitted(
            connection=conn,
            actor_user_id=actor.user_id,
            transaction_id=tx,
            reason="Verify protected reversal continuation",
            treasury_previous_void_transaction_id=previous,
        )

    if invalid_proof != "other_application":
        void(extra)
    previous = extra
    if invalid_proof == "other_loan":
        void(regular)
        previous = regular
    elif invalid_proof == "changed_state":
        conn.execute(
            "update lending.loan_collection_state set state_version=state_version+1 where loan_id=%s",
            (case.seven_loan_id,),
        )
    else:
        # Another successful application of the same wallet receipt may be
        # reversed, but is not the predecessor of this application's first leg.
        other_inputs = _input(
            conn,
            case,
            mode="single",
            loans=[
                {
                    "loan_id": case.seven_loan_id,
                    "expected_version": 2,
                }
            ],
            total_amount="21.00",
            intent="extra_as_advance",
        )
        other_preview = adapter.preview_allocation(
            conn, actor, receipt, AllocationPreview(**other_inputs)
        )
        assert other_preview["can_apply"], other_preview
        other = adapter.apply_receipt(
            conn,
            actor,
            receipt,
            ReceiptApply(
                **other_inputs,
                action="receipt_apply",
                request_id=uuid4(),
                account_id=receipt["account_id"],
                receipt_id=receipt["id"],
                digest=other_preview["digest"],
            ),
        )
        assert len(other["transaction_ids"]) == 1
        previous = UUID(other["transaction_ids"][0])
        void(previous)
    before = conn.execute(
        "select to_jsonb(s) state from lending.loan_collection_state s where loan_id=%s",
        (case.seven_loan_id,),
    ).fetchone()["state"]
    with pytest.raises(CollectionVoidConflict, match="changed|latest"):
        void(first_seven, previous)
    assert (
        conn.execute(
            "select to_jsonb(s) state from lending.loan_collection_state s where loan_id=%s",
            (case.seven_loan_id,),
        ).fetchone()["state"]
        == before
    )
    assert not conn.execute(
        "select is_voided from lending.collection_transactions where id=%s",
        (first_seven,),
    ).fetchone()["is_voided"]
