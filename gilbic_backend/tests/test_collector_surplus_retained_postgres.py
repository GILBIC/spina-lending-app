"""Full remittance acceptance includes actual held cash without another inflow."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import test_collector_surplus_postgres as surplus_support
import treasury_test_support
from gilbic_backend.collector_settlement import preview
from gilbic_backend.collector_surplus import load
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from gilbic_backend.treasury_models import COMMAND_ADAPTER, SettlementPreview
from test_collector_surplus_postgres import accept, cash_delta, command, count
from treasury_test_support import connect, version

surplus = surplus_support.surplus
treasury = treasury_test_support.treasury


def retained(t):
    c = count(t, "9900.00")
    return command(
        t,
        "collector_custody_exception_record",
        count_id=c["id"],
        count_version=c["version"],
        source_digest=c["source_digest"],
        retained_amount="9900.00",
        retained_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        holder_attestation="Actually retained synthetic cash",
        reason="Short handover disputed",
    )["result"]["exception"]


def held_preview(t, e):
    with connect() as conn:
        return preview(
            t["service"],
            conn,
            t["owner"],
            t["remittance_id"],
            SettlementPreview(
                account_id=t["account_id"],
                expected_version=version(t),
                retained_exception_id=e["id"],
                retained_exception_version=e["version"],
            ),
        )


def additional_count(t, e, amount="100.00"):
    p = held_preview(t, e)
    return command(
        t,
        "collector_count_record",
        remittance_id=t["remittance_id"],
        source_digest=p["source_digest"],
        counted_amount=amount,
        counted_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="New cash counted separately from the retained cash",
        review_acknowledged=True,
        retained_exception_id=e["id"],
        retained_exception_version=e["version"],
    )["result"]["count"]


@pytest.mark.parametrize(
    "new_cash,expected_total,excess",
    [
        ("100.00", "10000.00", None),
        ("200.00", "10100.00", "100.00"),
    ],
)
def test_full_acceptance_links_held_cash_without_double_receipt(
    surplus, new_cash, expected_total, excess
):
    t = surplus
    e = retained(t)
    p = held_preview(t, e)
    assert p["can_count"] is True
    assert p["retained_cash_amount"] == "9900.00"
    assert p["physical_cash_required"] == "100.00"
    c = additional_count(t, e, new_cash)
    request = COMMAND_ADAPTER.validate_python(
        {
            "action": "collector_count_accept",
            "request_id": uuid4(),
            "account_id": t["account_id"],
            "expected_version": version(t),
            "count_id": c["id"],
            "count_version": c["version"],
            "source_digest": c["source_digest"],
            "physical_receipt_acknowledged": True,
        }
    )
    result = t["service"].execute(t["owner"], request)
    assert t["service"].execute(t["owner"], request) == result
    assert cash_delta(t) == Decimal(expected_total)
    settlement = result["result"]["settlement"]
    assert settlement["physical_amount"] == new_cash
    assert settlement["retained_cash_amount"] == "9900.00"
    assert settlement["retained_exception_id"] == e["id"]
    assert (
        result["result"]["case"]["received_excess_amount"]
        if excess
        else result["result"]["case"]
    ) == excess
    with connect() as conn:
        current = load(conn, "exceptions", UUID(e["id"]))
        assert current["remaining_held_amount"] == "0.00"
        assert current["included_amount"] == "9900.00"
        assert current["status"] == "included_in_settlement"
        assert (
            conn.execute(
                "select status from lending.collection_remittances where id=%s",
                (t["remittance_id"],),
            ).fetchone()["status"]
            == "received"
        )
        links = conn.execute(
            "select event_id,linked_amount from treasury.source_links where source_kind='collector_remittance_physical' and source_id=%s order by linked_amount",
            (t["remittance_id"],),
        ).fetchall()
        assert [r["linked_amount"] for r in links] == [
            Decimal("100.00"),
            Decimal("9900.00"),
        ]
        assert str(links[1]["event_id"]) == e["event_id"]
    with pytest.raises(TreasuryConflict):
        accept(t, c)
    assert cash_delta(t) == Decimal(expected_total)


def test_short_additional_count_cannot_accept_or_retain_the_old_cash_again(surplus):
    t = surplus
    e = retained(t)
    c = additional_count(t, e, "99.00")
    assert c["disposition"] == "counted_short_rejected"
    with pytest.raises(TreasuryConflict):
        accept(t, c)
    with pytest.raises(TreasuryConflict):
        command(
            t,
            "collector_custody_exception_record",
            count_id=c["id"],
            count_version=c["version"],
            source_digest=c["source_digest"],
            retained_amount="99.00",
            retained_at=datetime.now(UTC),
            evidence_id=t["evidence_id"],
            holder_attestation="Another offered short amount",
            reason="Must not duplicate held cash",
        )
    assert cash_delta(t) == Decimal("9900.00")


def test_return_reservation_invalidates_count_and_blocks_inclusion(surplus):
    t = surplus
    e = retained(t)
    c = additional_count(t, e)
    command(
        t,
        "collector_custody_exception_return_prepare",
        exception_id=e["id"],
        exception_version=e["version"],
        amount="100.00",
        evidence_id=t["evidence_id"],
        reason="Reserve an actual return",
    )
    with pytest.raises(TreasuryConflict):
        accept(t, c)
    with connect() as conn:
        current = load(conn, "exceptions", UUID(e["id"]))
    with pytest.raises(TreasuryConflict):
        held_preview(t, current)
    assert cash_delta(t) == Decimal("9900.00")


def test_selected_exception_must_belong_to_exact_remittance_and_account(surplus):
    t = surplus
    e = retained(t)
    with pytest.raises(TreasuryConflict):
        held_preview(t, {**e, "version": e["version"] + 1})
    other = {**t, "remittance_id": uuid4()}
    with pytest.raises(TreasuryDenied):
        held_preview(other, e)
    with pytest.raises(TreasuryDenied):
        held_preview({**t, "account_id": t["wallet_id"]}, e)


def test_acceptance_failure_rolls_back_inclusion_new_cash_and_custody(
    surplus, monkeypatch
):
    import gilbic_backend.collector_settlement as settlement

    t = surplus
    e = retained(t)
    c = additional_count(t, e)
    original = settlement.save

    def fail_settlement(conn, kind, *args, **kwargs):
        if kind == "settlements":
            raise RuntimeError("Synthetic failure after money and custody writes")
        return original(conn, kind, *args, **kwargs)

    monkeypatch.setattr(settlement, "save", fail_settlement)
    with pytest.raises(RuntimeError, match="Synthetic failure"):
        accept(t, c)
    assert cash_delta(t) == Decimal("9900.00")
    with connect() as conn:
        current = load(conn, "exceptions", UUID(e["id"]))
        assert current["version"] == e["version"]
        assert current["remaining_held_amount"] == "9900.00"
        assert (
            conn.execute(
                "select status from lending.collection_remittances where id=%s",
                (t["remittance_id"],),
            ).fetchone()["status"]
            == "submitted"
        )
        assert (
            conn.execute(
                "select count(*) as n from treasury.source_links where event_id=%s",
                (UUID(e["event_id"]),),
            ).fetchone()["n"]
            == 0
        )


def test_additional_count_cannot_predate_the_held_receipt(surplus):
    t = surplus
    e = retained(t)
    p = held_preview(t, e)
    with pytest.raises(TreasuryConflict):
        command(
            t,
            "collector_count_record",
            remittance_id=t["remittance_id"],
            source_digest=p["source_digest"],
            counted_amount="100.00",
            counted_at=datetime.now(UTC) - timedelta(days=1),
            evidence_id=t["evidence_id"],
            recipient_attestation="Backdated new count",
            review_acknowledged=True,
            retained_exception_id=e["id"],
            retained_exception_version=e["version"],
        )


def test_concurrent_acceptances_receive_new_and_held_cash_only_once(surplus):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    t = surplus
    e = retained(t)
    c = additional_count(t, e)
    barrier = Barrier(2)
    commands = [
        COMMAND_ADAPTER.validate_python(
            {
                "action": "collector_count_accept",
                "request_id": uuid4(),
                "account_id": t["account_id"],
                "expected_version": version(t),
                "count_id": c["id"],
                "count_version": c["version"],
                "source_digest": c["source_digest"],
                "physical_receipt_acknowledged": True,
            }
        )
        for _ in range(2)
    ]

    def attempt(body):
        barrier.wait(timeout=10)
        try:
            return t["service"].execute(t["owner"], body)["status"]
        except TreasuryConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, commands)) == ["conflict", "saved"]
    assert cash_delta(t) == Decimal("10000.00")


def test_original_retained_proof_is_required_to_recover_the_additional_count(surplus):
    from treasury_test_support import evidence

    t = surplus
    e = retained(t)
    old_evidence_id = t["evidence_id"]
    t["evidence_id"] = evidence(t)
    p = held_preview(t, e)
    body = COMMAND_ADAPTER.validate_python(
        {
            "action": "collector_count_record",
            "request_id": uuid4(),
            "account_id": t["account_id"],
            "expected_version": version(t),
            "remittance_id": t["remittance_id"],
            "source_digest": p["source_digest"],
            "counted_amount": "100.00",
            "counted_at": datetime.now(UTC),
            "evidence_id": t["evidence_id"],
            "recipient_attestation": "Separate new count evidence",
            "review_acknowledged": True,
            "retained_exception_id": e["id"],
            "retained_exception_version": e["version"],
        }
    )
    t["service"].execute(t["owner"], body)
    from gilbic_backend.office_review_evidence_storage import EvidenceFileError

    t["service"].store._path(UUID(str(old_evidence_id))).write_bytes(
        b"corrupt synthetic retained proof"
    )
    with pytest.raises(EvidenceFileError):
        t["service"].request_result(t["owner"], body.request_id)
