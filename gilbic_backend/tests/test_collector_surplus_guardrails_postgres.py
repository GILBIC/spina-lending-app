"""Independent boundary checks against the disposable Collector workflow."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
import test_collector_surplus_postgres as surplus_support
import treasury_test_support
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from gilbic_backend.treasury_models import (
    COMMAND_ADAPTER,
    AccountConfigure,
    AccountGrant,
    TransferRecord,
)
from test_collector_surplus_postgres import accept, cash_delta, command, count, credit
from treasury_test_support import actor, connect, evidence, grant_live, version

surplus = surplus_support.surplus
treasury = treasury_test_support.treasury


def observe_return(t, action_row):
    return command(
        t,
        "disbursement_record",
        purpose="collector_surplus_return",
        source_id=action_row["id"],
        source_version=action_row["version"],
        payee_id=t["collector"].user_id,
        amount="40.00",
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="Synthetic actual debit already observed",
        reason="Synthetic independent outgoing cash evidence",
    )["result"]


def test_frozen_credit_retains_observation_without_advancing_return(surplus):
    from gilbic_backend.treasury_disbursements import source_choices

    t = surplus
    action_row, credit_row = surplus_support.prepared(t)
    command(
        t,
        "collector_surplus_resolve_source",
        credit_id=credit_row["id"],
        credit_version=credit_row["version"],
        source_id=t["remittance_id"],
        source_digest="a" * 64,
        amount="40.00",
        evidence_id=t["evidence_id"],
        reason="Synthetic source conflict requires recovery before payment",
    )
    with connect() as conn:
        before_choices = source_choices(conn, t["owner"])
    assert not any(row["id"] == action_row["id"] for row in before_choices)
    observed = observe_return(t, action_row)
    assert observed["source_link"]["status"] == "blocked"
    assert observed["source_link"]["action_record"]["status"] == "reserved"
    assert cash_delta(t) == Decimal("10060.00")
    with connect() as conn:
        current = conn.execute(
            "select payload from treasury.collector_credits where id=%s",
            (credit_row["id"],),
        ).fetchone()["payload"]
        choices = source_choices(conn, t["owner"])
    assert current["frozen"] is True
    assert current["outstanding_amount"] == "100.00"
    assert current["reserved_amount"] == "40.00"
    assert not any(row["id"] == action_row["id"] for row in choices)


@pytest.mark.parametrize("initial", ["not_received", "received"])
def test_current_acknowledgment_resolves_delayed_receipt_without_new_debit(
    surplus, initial
):
    t = surplus
    action_row, credit_row = surplus_support.prepared(t)
    observed = observe_return(t, action_row)
    action_row = observed["source_link"]["action_record"]
    event = observed["event"]

    def acknowledge(confirmation):
        return command(
            t,
            "collector_surplus_return_acknowledge",
            actor=t["collector"],
            credit_id=credit_row["id"],
            credit_version=credit_row["version"],
            action_id=action_row["id"],
            action_version=action_row["version"],
            event_id=event["id"],
            event_version=event["version"],
            reviewed_amount="40.00",
            confirmation=confirmation,
            acknowledged_at=datetime.now(UTC),
            reason="Synthetic updated actual receipt statement",
        )["result"]["acknowledgment"]

    def settle(ack):
        return command(
            t,
            "collector_surplus_return_record",
            action_id=action_row["id"],
            action_version=action_row["version"],
            event_id=event["id"],
            event_version=event["version"],
            acknowledgment_id=ack["id"],
            acknowledgment_version=ack["version"],
            reason="Synthetic independent review of latest actual receipt",
        )

    first = acknowledge(initial)
    if initial == "received":
        acknowledge("not_received")
        with pytest.raises(TreasuryConflict):
            settle(first)
    current = acknowledge("received")
    result = settle(current)
    assert result["result"]["disposition"] == "paid"
    assert result["result"]["credit"]["outstanding_amount"] == "60.00"
    assert result["result"]["credit"]["reserved_amount"] == "0.00"
    assert cash_delta(t) == Decimal("10060.00")
    with connect() as conn:
        facts = conn.execute(
            "select payload from treasury.collector_acknowledgments where action_id=%s",
            (action_row["id"],),
        ).fetchall()
    assert len(facts) == (3 if initial == "received" else 2)
    assert {row["payload"]["confirmation"] for row in facts} == {
        "received",
        "not_received",
    }


def test_unpaid_cancellation_releases_reservation_without_cash(surplus):
    t = surplus
    action_row, credit_row = surplus_support.prepared(t)
    before = cash_delta(t)
    result = command(
        t,
        "collector_surplus_action_cancel",
        action_id=action_row["id"],
        action_version=action_row["version"],
        evidence_id=t["evidence_id"],
        reason="Synthetic approved return cancelled before any actual debit",
    )
    assert result["status"] == "saved"
    assert result["result"]["disposition"] == "cancelled"
    assert result["result"]["action_record"]["event_id"] is None
    with connect() as conn:
        current = conn.execute(
            "select payload from treasury.collector_credits where id=%s",
            (credit_row["id"],),
        ).fetchone()["payload"]
    assert current["reserved_amount"] == "0.00"
    assert current["available_amount"] == current["outstanding_amount"] == "100.00"
    assert cash_delta(t) == before


def own_request(credit_row, request_id=None):
    return COMMAND_ADAPTER.validate_python(
        {
            "action": "collector_surplus_return_request",
            "request_id": request_id or uuid4(),
            "credit_id": credit_row["id"],
            "credit_version": credit_row["version"],
            "amount": "40.00",
            "destination": {
                "kind": "physical_cash",
                "recipient_reference": None,
            },
            "reason": "Synthetic own credit return request",
        }
    )


def test_foreign_collector_cannot_request_another_collectors_credit(surplus):
    t = surplus
    current_credit = credit(t)
    with connect() as conn:
        other = actor(conn, "collector")
    with pytest.raises(TreasuryDenied):
        t["service"].execute(other, own_request(current_credit))
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.collector_requests where credit_id=%s",
                (UUID(current_credit["id"]),),
            ).fetchone()["n"]
            == 0
        )


def test_own_request_replay_is_bound_to_payload_and_current_collector_role(surplus):
    t = surplus
    current_credit = credit(t)
    submitted = own_request(current_credit)
    saved = t["service"].execute(t["collector"], submitted)
    assert saved["result"]["disposition"] == "requested"
    assert t["service"].request_result(t["collector"], submitted.request_id) == saved
    changed = COMMAND_ADAPTER.validate_python(
        dict(submitted.model_dump(mode="json"), amount="41.00")
    )
    with pytest.raises(TreasuryConflict):
        t["service"].execute(t["collector"], changed)
    with connect() as conn:
        conn.execute(
            """delete from core.user_roles
            where user_id=%s and role_id in
            (select id from core.roles where code='collector')""",
            (t["collector"].user_id,),
        )
    with pytest.raises(TreasuryDenied):
        t["service"].request_result(t["collector"], submitted.request_id)


def test_acceptance_rolls_back_cash_custody_and_case_if_outcome_save_fails(
    surplus, monkeypatch
):
    t = surplus
    recorded_count = count(t)

    def reject_outcome(*args, **kwargs):
        raise RuntimeError("Synthetic audit/outcome failure")

    monkeypatch.setattr(t["service"], "save_result", reject_outcome)
    with pytest.raises(RuntimeError, match="Synthetic audit/outcome failure"):
        accept(t, recorded_count)
    with connect() as conn:
        remittance = conn.execute(
            """select status,custody_transferred_at from lending.collection_remittances
            where id=%s""",
            (t["remittance_id"],),
        ).fetchone()
        assert remittance["status"] == "submitted"
        assert remittance["custody_transferred_at"] is None
        assert conn.execute(
            "select coalesce(sum(signed_amount),0) as amount from treasury.movement_lines where account_id=%s",
            (t["account_id"],),
        ).fetchone()["amount"] == Decimal("0.00")
        for table in ("collector_settlements", "collector_cases", "collector_credits"):
            query = psycopg.sql.SQL(
                "select count(*) as n from treasury.{} where account_id=%s"
            ).format(psycopg.sql.Identifier(table))
            assert conn.execute(query, (t["account_id"],)).fetchone()["n"] == 0
        assert (
            conn.execute(
                "select count(*) as n from treasury.collector_counts where account_id=%s",
                (t["account_id"],),
            ).fetchone()["n"]
            == 1
        )


def test_staff_count_recovery_fails_if_private_evidence_is_missing(
    surplus, monkeypatch
):
    t = surplus
    recorded_count = count(t)
    with connect() as conn:
        request_id = conn.execute(
            "select request_id from treasury.outcomes where action='collector_count_record' and result->>'target_id'=%s",
            (recorded_count["id"],),
        ).fetchone()["request_id"]

    def missing_file(*args, **kwargs):
        raise FileNotFoundError("Synthetic private evidence is unavailable")

    monkeypatch.setattr(t["service"].store, "read", missing_file)
    with pytest.raises((FileNotFoundError, TreasuryDenied)):
        t["service"].request_result(t["owner"], request_id)


def test_database_cannot_drop_required_credit_capacity_value(surplus):
    t = surplus
    current_credit = credit(t)
    with pytest.raises(psycopg.Error), connect() as conn:
        conn.execute(
            """update treasury.collector_credits
            set payload=payload-'available_amount',version=version+1 where id=%s""",
            (UUID(current_credit["id"]),),
        )
    with connect() as conn:
        row = conn.execute(
            "select payload,version from treasury.collector_credits where id=%s",
            (UUID(current_credit["id"]),),
        ).fetchone()
        assert row["payload"]["available_amount"] == "100.00"
        assert row["version"] == current_credit["version"]


def test_two_prior_counts_cannot_receive_the_same_disputed_cash_twice(surplus):
    t = surplus
    first = count(t, "9900.00")
    second = count(t, "9900.00")

    def retain(recorded_count):
        return command(
            t,
            "collector_custody_exception_record",
            count_id=recorded_count["id"],
            count_version=recorded_count["version"],
            source_digest=recorded_count["source_digest"],
            retained_amount="9900.00",
            retained_at=datetime.now(UTC),
            evidence_id=t["evidence_id"],
            holder_attestation="Synthetic actual retained short cash",
            reason="Synthetic disputed handover",
        )

    retained = retain(first)
    assert retained["result"]["disposition"] == "custody_exception_recorded"
    with pytest.raises(TreasuryConflict):
        retain(second)
    assert cash_delta(t) == Decimal("9900.00")
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.collector_exceptions where account_id=%s",
                (t["account_id"],),
            ).fetchone()["n"]
            == 1
        )


def test_fully_granted_collector_still_cannot_recognize_their_own_credit(surplus):
    t = surplus
    received = accept(t, count(t))
    case = received["result"]["case"]
    permission = "treasury.collector_surplus.resolve"
    with connect() as conn:
        grant_live(conn, t["collector"].user_id, permission)
    t["service"].execute(
        t["owner"],
        AccountGrant(
            action="account_grant",
            request_id=uuid4(),
            account_id=t["account_id"],
            expected_version=version(t),
            user_id=t["collector"].user_id,
            permissions=[permission],
            private_history=False,
        ),
    )
    with pytest.raises(TreasuryDenied, match="independent"):
        command(
            t,
            "collector_surplus_recognize",
            actor=t["collector"],
            case_id=case["id"],
            case_version=case["version"],
            source_digest=case["source_digest"],
            source_review_acknowledged=True,
            amount="100.00",
            evidence_id=t["evidence_id"],
            reason="Synthetic forbidden self recognition despite live grants",
        )
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.collector_credits where account_id=%s",
                (t["account_id"],),
            ).fetchone()["n"]
            == 0
        )


def test_same_opening_cash_cannot_anchor_two_collectors_beyond_its_capacity(surplus):
    t = surplus
    opening_evidence = evidence(t, "opening")
    prepared = command(
        t,
        "opening_prepare",
        cutoff=datetime(2026, 10, 1, tzinfo=UTC),
        amount="100.00",
        evidence_id=opening_evidence,
        reason="Synthetic existing cash includes Collector liabilities",
        personal_amount="0.00",
        third_party_amount="100.00",
        transit_amount="0.00",
    )
    activated = command(
        t,
        "opening_activate",
        opening_id=prepared["target_id"],
        opening_version=prepared["version"],
        confirmed=True,
        reason="Synthetic opening reviewed",
    )
    with connect() as conn:
        other_collector = actor(conn, "collector")

    def anchor(collector_user_id):
        return command(
            t,
            "collector_surplus_opening_prepare",
            collector_user_id=collector_user_id,
            opening_id=activated["target_id"],
            opening_version=activated["version"],
            amount="80.00",
            evidence_id=opening_evidence,
            overlap_review_acknowledged=True,
            reason="Synthetic existing liability anchor",
        )

    first = anchor(t["collector"].user_id)
    assert first["result"]["disposition"] == "opening_prepared"
    with pytest.raises(TreasuryConflict):
        anchor(other_collector.user_id)
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.collector_openings where account_id=%s",
                (t["account_id"],),
            ).fetchone()["n"]
            == 1
        )


def test_existing_transfer_keeps_commanded_source_when_other_uuid_sorts_last(treasury):
    t = dict(treasury)
    source_id, destination_id = sorted([uuid4(), uuid4()], key=str)
    t["account_id"] = source_id
    for account_id in (source_id, destination_id):
        t["service"].execute(
            t["owner"],
            AccountConfigure(
                action="account_configure",
                request_id=uuid4(),
                account_id=account_id,
                expected_version=0,
                ledger_context_id=t["context_id"],
                context="synthetic",
                kind="gcash",
                alias="Synthetic sorted transfer account",
                ownership="synthetic",
                custodian_user_id=t["owner"].user_id,
            ),
        )
    result = t["service"].execute(
        t["owner"],
        TransferRecord(
            action="transfer_record",
            request_id=uuid4(),
            account_id=source_id,
            expected_version=version(t),
            transfer_id=uuid4(),
            leg="source",
            other_account_id=destination_id,
            other_account_version=1,
            amount="10.00",
            provider="gcash",
            reference=uuid4().hex,
            effective_at=datetime.now(UTC),
            evidence_id=evidence(t),
            recipient_attestation="Synthetic independently observed source debit",
            reason="Source identity must not depend on lock sort order",
        ),
    )
    assert result["result"]["account_id"] == str(source_id)
    assert result["result"]["event"]["account_id"] == str(source_id)
    assert result["result"]["transfer"]["transit_amount"] == "10.00"
    assert cash_delta(t) == Decimal("-10.00")
    with connect() as conn:
        assert conn.execute(
            "select coalesce(sum(signed_amount),0) as amount from treasury.movement_lines where account_id=%s",
            (destination_id,),
        ).fetchone()["amount"] == Decimal("0.00")
