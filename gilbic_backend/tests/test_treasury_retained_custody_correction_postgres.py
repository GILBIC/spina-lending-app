"""Actual Collector custody is retained even after partial/full protected returns."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import test_collector_surplus_postgres
import treasury_test_support
from gilbic_backend.collector_surplus import load
from gilbic_backend.treasury_authorization import TreasuryConflict
from gilbic_backend.treasury_models import MovementCorrect
from test_collector_surplus_postgres import cash_delta, command, count
from test_treasury_reconciliation_postgres import movement
from treasury_test_support import connect, evidence, version

treasury = treasury_test_support.treasury
surplus = test_collector_surplus_postgres.surplus


def correction(f, event_id):
    return MovementCorrect(
        action="movement_correct",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        event_id=event_id,
        event_version=1,
        evidence_id=evidence(f, "correction"),
        correction="false_observation",
        reason="Review actual observation with protected custody retained",
    )


def retained_cash(f):
    counted = count(f, "9900.00")
    return command(
        f,
        "collector_custody_exception_record",
        count_id=counted["id"],
        count_version=counted["version"],
        source_digest=counted["source_digest"],
        retained_amount="9900.00",
        retained_at=datetime.now(UTC),
        evidence_id=f["evidence_id"],
        holder_attestation="Cash retained pending disputed handover",
        reason="Real holder retains counted short cash",
    )["result"]["exception"]


def return_cash(f, held, amount):
    action = command(
        f,
        "collector_custody_exception_return_prepare",
        exception_id=held["id"],
        exception_version=held["version"],
        amount=amount,
        evidence_id=f["evidence_id"],
        reason="Return disputed cash through protected custody",
    )["result"]["action_record"]
    debit = command(
        f,
        "disbursement_record",
        purpose="collector_custody_exception_return",
        source_id=action["id"],
        source_version=action["version"],
        payee_id=f["collector"].user_id,
        amount=amount,
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=datetime.now(UTC),
        evidence_id=f["evidence_id"],
        recipient_attestation="Actual cash returned to original Collector",
        reason="Protected cash handover",
    )["result"]
    action, event = debit["source_link"]["action_record"], debit["event"]
    with connect() as conn:
        held = load(conn, "exceptions", UUID(held["id"]))
    ack = command(
        f,
        "collector_custody_exception_return_acknowledge",
        actor=f["collector"],
        exception_id=held["id"],
        exception_version=held["version"],
        action_id=action["id"],
        action_version=action["version"],
        event_id=event["id"],
        event_version=1,
        reviewed_amount=amount,
        confirmation="received",
        acknowledged_at=datetime.now(UTC),
        reason="Collector confirms actual cash receipt",
    )["result"]["acknowledgment"]
    return command(
        f,
        "collector_surplus_return_record",
        action_id=action["id"],
        action_version=action["version"],
        event_id=event["id"],
        event_version=1,
        acknowledgment_id=ack["id"],
        acknowledgment_version=ack["version"],
        reason="Retain independently confirmed actual return",
    )["result"]["exception"]


@pytest.mark.parametrize("returned", ["0.00", "40.00", "9900.00"])
def test_generic_correction_cannot_erase_retained_custody_history(surplus, returned):
    f = surplus
    held = retained_cash(f)
    if returned != "0.00":
        held = return_cash(f, held, returned)
    expected = Decimal("9900.00") - Decimal(returned)
    assert cash_delta(f) == expected
    with pytest.raises(TreasuryConflict, match="Collector"):
        f["service"].execute(f["owner"], correction(f, held["event_id"]))
    assert cash_delta(f) == expected
    with connect() as conn:
        after = load(conn, "exceptions", UUID(held["id"]))
        assert after["remaining_held_amount"] == str(expected)
        assert (
            conn.execute(
                "select count(*) n from treasury.event_revisions where event_id=%s and action='correct'",
                (held["event_id"],),
            ).fetchone()["n"]
            == 0
        )


def test_unbound_correction_and_exact_replay_remain_supported(treasury):
    f = treasury
    event = movement(f, "unbound-observation", "100.00", "credit")
    model = correction(f, event["target_id"])
    result = f["service"].execute(f["owner"], model)
    assert result["status"] == "saved"
    assert f["service"].execute(f["owner"], model) == result
    assert cash_delta(f) == Decimal("0.00")
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) n from treasury.event_revisions where event_id=%s and action='correct'",
                (event["target_id"],),
            ).fetchone()["n"]
            == 1
        )
