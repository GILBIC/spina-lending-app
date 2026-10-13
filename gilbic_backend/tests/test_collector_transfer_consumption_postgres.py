"""Collector custody and transfer attribution must be exclusive in either order."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import test_collector_surplus_postgres as collector_support
from gilbic_backend.treasury_authorization import TreasuryConflict
from gilbic_backend.treasury_models import (
    COMMAND_ADAPTER,
    AccountConfigure,
    TransferRecord,
)
from test_collector_surplus_postgres import count, paid
from test_treasury_exclusive_consumption_postgres import money_state
from test_treasury_postgres import receipt
from treasury_test_support import connect, version

surplus = collector_support.surplus
treasury = collector_support.treasury


def other_cash_account(t):
    other = dict(t, account_id=uuid4())
    t["service"].execute(
        t["owner"],
        AccountConfigure(
            action="account_configure",
            request_id=uuid4(),
            account_id=other["account_id"],
            expected_version=0,
            ledger_context_id=t["context_id"],
            context="synthetic",
            kind="physical_cash",
            alias="Synthetic separate cash custody",
            ownership="synthetic",
            custodian_user_id=t["owner"].user_id,
        ),
    )
    return other


def transfer(t, other, amount, reference, effective_at):
    return TransferRecord(
        action="transfer_record",
        request_id=uuid4(),
        account_id=t["account_id"],
        expected_version=version(t),
        transfer_id=uuid4(),
        leg="destination",
        other_account_id=other["account_id"],
        other_account_version=version(other),
        amount=amount,
        provider="physical_cash",
        reference=reference,
        effective_at=effective_at,
        evidence_id=t["evidence_id"],
        recipient_attestation="Synthetic independently verified actual cash credit",
        reason="Synthetic correlated cash transfer",
    )


def collector_command(t, action, **fields):
    return COMMAND_ADAPTER.validate_python(
        dict(
            action=action,
            request_id=uuid4(),
            account_id=t["account_id"],
            expected_version=version(t),
            **fields,
        )
    )


def custody_state(t, other):
    with connect() as conn:
        state = {
            table: conn.execute(
                f"select * from treasury.collector_{table} where account_id=%s order by id",
                (t["account_id"],),
            ).fetchall()
            for table in (
                "counts",
                "settlements",
                "exceptions",
                "cases",
                "credits",
                "actions",
                "entries",
                "acknowledgments",
            )
        }
        state["remittance"] = conn.execute(
            "select * from lending.collection_remittances where id=%s",
            (t["remittance_id"],),
        ).fetchall()
        state["reviews"] = conn.execute(
            "select * from lending.collection_remittance_reviews where remittance_id=%s",
            (t["remittance_id"],),
        ).fetchall()
    return dict(state, money=money_state(t), other_money=money_state(other))


def assert_second_attribution_rejected(
    t, other, external_first, make_external, make_collector
):
    accepted_command = make_external() if external_first else make_collector()
    saved = t["service"].execute(t["owner"], accepted_command)
    rejected_command = make_collector() if external_first else make_external()
    before = custody_state(t, other)
    with pytest.raises(TreasuryConflict):
        t["service"].execute(t["owner"], rejected_command)
    assert custody_state(t, other) == before
    assert t["service"].execute(t["owner"], accepted_command) == saved
    assert custody_state(t, other) == before
    with connect() as conn:
        assert (
            conn.execute(
                "select 1 from treasury.outcomes where request_id=%s",
                (rejected_command.request_id,),
            ).fetchone()
            is None
        )


@pytest.mark.parametrize("first", ["transfer", "reversal"])
def test_transfer_destination_and_collector_reversal_are_exclusive(surplus, first):
    t = surplus
    paid_action = paid(t)["result"]["action_record"]
    other = other_cash_account(t)
    effective_at = datetime.now(UTC)
    reference = "collector-reversal-" + uuid4().hex
    assert_second_attribution_rejected(
        t,
        other,
        first == "transfer",
        lambda: transfer(t, other, "10.00", reference, effective_at),
        lambda: collector_command(
            t,
            "collector_surplus_return_reverse",
            action_id=paid_action["id"],
            action_version=paid_action["version"],
            amount="10.00",
            provider="physical_cash",
            reference=reference,
            effective_at=effective_at,
            evidence_id=t["evidence_id"],
            recipient_attestation="Synthetic actual payout returned to custody",
            reason="Synthetic verified reversal",
        ),
    )


@pytest.mark.parametrize("first", ["receipt", "reversal"])
def test_borrower_receipt_and_collector_reversal_are_exclusive(surplus, first):
    t = surplus
    paid_action = paid(t)["result"]["action_record"]
    other = other_cash_account(t)
    effective_at = datetime.now(UTC)
    reference = "receipt-reversal-" + uuid4().hex

    def make_receipt():
        return receipt(
            t, reference=reference, amount="10.00", effective_at=effective_at
        ).model_copy(update={"provider": "physical_cash"})

    def make_reversal():
        return collector_command(
            t,
            "collector_surplus_return_reverse",
            action_id=paid_action["id"],
            action_version=paid_action["version"],
            amount="10.00",
            provider="physical_cash",
            reference=reference,
            effective_at=effective_at,
            evidence_id=t["evidence_id"],
            recipient_attestation="Synthetic actual payout returned to custody",
            reason="Synthetic verified reversal",
        )

    assert_second_attribution_rejected(
        t, other, first == "receipt", make_receipt, make_reversal
    )


@pytest.mark.parametrize("first", ["transfer", "exception"])
def test_transfer_destination_and_disputed_custody_are_exclusive(surplus, first):
    t = surplus
    counted = count(t, "9900.00")
    other = other_cash_account(t)
    retained_at = datetime.now(UTC)
    assert_second_attribution_rejected(
        t,
        other,
        first == "transfer",
        lambda: transfer(
            t, other, "9900.00", "collector-dispute:" + counted["id"], retained_at
        ),
        lambda: collector_command(
            t,
            "collector_custody_exception_record",
            count_id=counted["id"],
            count_version=counted["version"],
            source_digest=counted["source_digest"],
            retained_amount="9900.00",
            retained_at=retained_at,
            evidence_id=t["evidence_id"],
            holder_attestation="Synthetic rejected short cash actually retained",
            reason="Synthetic cash custody dispute",
        ),
    )


@pytest.mark.parametrize("first", ["transfer", "acceptance"])
@pytest.mark.parametrize("amount", ["10000.00", "10100.00"])
def test_transfer_destination_and_count_acceptance_are_exclusive(
    surplus, first, amount
):
    t = surplus
    counted_at = datetime.now(UTC)
    counted = count(t, amount, counted_at=counted_at)
    other = other_cash_account(t)
    assert_second_attribution_rejected(
        t,
        other,
        first == "transfer",
        lambda: transfer(
            t,
            other,
            amount,
            "collector-remittance:" + str(t["remittance_id"]),
            counted_at,
        ),
        lambda: collector_command(
            t,
            "collector_count_accept",
            count_id=counted["id"],
            count_version=counted["version"],
            source_digest=counted["source_digest"],
            physical_receipt_acknowledged=True,
        ),
    )


def test_genuine_overage_retains_physical_and_excess_portions_with_exact_replay(
    surplus,
):
    t = surplus
    counted = count(t, "10100.00")
    command = collector_command(
        t,
        "collector_count_accept",
        count_id=counted["id"],
        count_version=counted["version"],
        source_digest=counted["source_digest"],
        physical_receipt_acknowledged=True,
    )
    saved = t["service"].execute(t["owner"], command)
    assert t["service"].execute(t["owner"], command) == saved
    with connect() as conn:
        assert conn.execute(
            "select l.source_kind,l.linked_amount from treasury.source_links l join treasury.events e on e.id=l.event_id where e.account_id=%s order by l.source_kind",
            (t["account_id"],),
        ).fetchall() == [
            {"source_kind": "collector_excess_pending", "linked_amount": 100},
            {"source_kind": "collector_remittance_physical", "linked_amount": 10000},
        ]
        assert (
            conn.execute(
                "select sum(signed_amount) as amount from treasury.movement_lines where account_id=%s",
                (t["account_id"],),
            ).fetchone()["amount"]
            == 10100
        )
