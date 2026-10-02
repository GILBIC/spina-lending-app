"""Synthetic real PostgreSQL acceptance, capacity, authority and rollback proof."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import treasury_test_support
from gilbic_backend.collector_settlement import preview
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from gilbic_backend.treasury_models import (
    COMMAND_ADAPTER,
    AccountConfigure,
    SettlementPreview,
)
from treasury_test_support import actor, connect, evidence, version

treasury = treasury_test_support.treasury


@pytest.fixture
def surplus(treasury, monkeypatch):
    t = treasury
    monkeypatch.setenv("SPINA_COLLECTOR_SURPLUS_ENABLED", "true")
    with connect() as conn:
        collector = actor(conn, "collector")
    t["collector"] = collector
    t["wallet_id"] = t["account_id"]
    t["account_id"] = uuid4()
    t["service"].execute(
        t["owner"],
        AccountConfigure(
            action="account_configure",
            request_id=uuid4(),
            account_id=t["account_id"],
            expected_version=0,
            ledger_context_id=t["context_id"],
            context="synthetic",
            kind="physical_cash",
            alias="Synthetic counter",
            ownership="synthetic",
            custodian_user_id=t["owner"].user_id,
        ),
    )
    t["evidence_id"] = evidence(t)
    rid, tid = uuid4(), uuid4()
    t["remittance_id"] = rid
    t["transaction_id"] = tid
    with connect() as conn:
        conn.execute(
            """insert into lending.collection_transactions(id,idempotency_key,loan_id,client_id,collector_user_id,registered_device_id,route_entry_id,collection_date,entry_type,amount,recorded_at,device_sequence,note,previous_balance,official_balance,pass_count_after,receipt_number,details)
  values(%s,%s,%s,%s,%s,%s,%s,'2026-10-01','payment',10000,now(),1,'Synthetic counted source',10000,0,0,%s,'{}')""",
            (
                tid,
                uuid4(),
                t["loan_id"],
                t["client_id"],
                collector.user_id,
                collector.registered_device_id,
                t["loan_id"],
                tid.hex,
            ),
        )
        conn.execute(
            """insert into lending.collection_remittances(id,remittance_number,collector_user_id,recipient_user_id,collection_date,status,transaction_count,payment_count,unable_to_pay_count,covered_payment_count,client_count,total_amount,note,submitted_at) values(%s,%s,%s,%s,'2026-10-01','submitted',1,1,0,0,1,10000,'Synthetic handover',now())""",
            (rid, rid.hex, collector.user_id, t["owner"].user_id),
        )
        conn.execute(
            "insert into lending.collection_remittance_items(remittance_id,transaction_id,client_id,loan_id,collection_date,entry_type,amount,receipt_number,transaction_snapshot) values(%s,%s,%s,%s,'2026-10-01','payment',10000,%s,'{}')",
            (rid, tid, t["client_id"], t["loan_id"], tid.hex),
        )
        conn.execute(
            "update lending.collection_transactions set remittance_id=%s,is_locked=true,locked_at=now(),locked_by_user_id=%s where id=%s",
            (rid, collector.user_id, tid),
        )
    return t


def command(t, action, actor=None, **fields):
    own = action in {
        "collector_surplus_return_request",
        "collector_surplus_application_request",
        "collector_surplus_return_acknowledge",
        "collector_custody_exception_return_acknowledge",
    }
    common = (
        {} if own else {"account_id": t["account_id"], "expected_version": version(t)}
    )
    model = COMMAND_ADAPTER.validate_python(
        dict(action=action, request_id=uuid4(), **common, **fields)
    )
    return t["service"].execute(actor or t["owner"], model)


def snapshot(t):
    with connect() as conn:
        return preview(
            t["service"],
            conn,
            t["owner"],
            t["remittance_id"],
            SettlementPreview(account_id=t["account_id"], expected_version=version(t)),
        )


def count(t, amount="10100.00", counted_at=None):
    p = snapshot(t)
    return command(
        t,
        "collector_count_record",
        remittance_id=t["remittance_id"],
        source_digest=p["source_digest"],
        counted_amount=amount,
        counted_at=counted_at or datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="Synthetic physically counted cash",
        review_acknowledged=True,
    )["result"]["count"]


def accept(t, c):
    return command(
        t,
        "collector_count_accept",
        count_id=c["id"],
        count_version=c["version"],
        source_digest=c["source_digest"],
        physical_receipt_acknowledged=True,
    )


def credit(t):
    accepted = accept(t, count(t))
    case = accepted["result"]["case"]
    return command(
        t,
        "collector_surplus_recognize",
        case_id=case["id"],
        case_version=case["version"],
        source_digest=case["source_digest"],
        source_review_acknowledged=True,
        amount="100.00",
        evidence_id=t["evidence_id"],
        reason="Independent source review identifies genuine Collector overpayment",
    )["result"]["credit"]


def cash_delta(t):
    with connect() as conn:
        return conn.execute(
            "select coalesce(sum(signed_amount),0) as total from treasury.movement_lines where account_id=%s",
            (t["account_id"],),
        ).fetchone()["total"]


def test_exact_count_accepts_once(surplus):
    t = surplus
    c = count(t, "10000.00")
    r = accept(t, c)
    assert r["result"]["disposition"] == "accepted_exact"
    assert cash_delta(t) == Decimal("10000.00")
    assert r["result"]["case"] is None
    with pytest.raises(TreasuryConflict):
        accept(t, c)
    assert cash_delta(t) == Decimal("10000.00")


def test_short_count_is_not_received(surplus):
    t = surplus
    c = count(t, "9900.00")
    assert c["disposition"] == "counted_short_rejected" and c["difference"] == "-100.00"
    with pytest.raises(TreasuryConflict):
        accept(t, c)
    assert cash_delta(t) == 0
    with connect() as conn:
        assert (
            conn.execute(
                "select status from lending.collection_remittances where id=%s",
                (t["remittance_id"],),
            ).fetchone()["status"]
            == "submitted"
        )


def test_overage_is_unidentified_until_independent_recognition(surplus):
    t = surplus
    c = credit(t)
    assert c["outstanding_amount"] == "100.00"
    assert cash_delta(t) == Decimal("10100.00")
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.collector_credits where account_id=%s",
                (t["account_id"],),
            ).fetchone()["n"]
            == 1
        )


def test_changed_source_digest_rejects_acceptance(surplus):
    t = surplus
    c = count(t)
    with connect() as conn:
        conn.execute(
            "update lending.collection_remittances set note=%s where id=%s",
            ("Changed source evidence", t["remittance_id"]),
        )
    with pytest.raises(TreasuryConflict, match="Source changed"):
        accept(t, c)
    assert cash_delta(t) == 0


def test_legacy_boolean_receive_is_blocked_when_enabled(surplus, monkeypatch):
    from gilbic_backend.remittance_review_repository import (
        PostgresReviewedRemittanceRepository,
    )

    t = surplus
    monkeypatch.setenv(
        "DATABASE_URL", __import__("os").environ["GILBIC_TEST_DATABASE_URL"]
    )
    with pytest.raises(Exception, match="actual physical count"):
        PostgresReviewedRemittanceRepository().confirm_received(
            remittance_id=t["remittance_id"],
            recipient_user_id=t["owner"].user_id,
            review_acknowledged=True,
        )
    assert cash_delta(t) == 0


def test_own_projection_excludes_private_source(surplus):
    from gilbic_backend.collector_surplus_reads import workspace

    t = surplus
    credit(t)
    with connect() as conn:
        w = workspace(t["service"], conn, t["collector"])
    assert (
        w["mode"] == "own"
        and w["accounts"] == []
        and w["totals"]["outstanding_amount"] == "100.00"
    )
    assert "evidence_id" not in str(w) and "source_snapshot" not in str(w)


def test_own_received_history_keeps_safe_facts_without_current_source_claims(surplus):
    from gilbic_backend.collector_surplus_reads import workspace

    t = surplus
    accept(t, count(t))
    with connect() as conn:
        result = workspace(
            t["service"], conn, t["collector"], kind="remittances", mode="own"
        )
    row = result["items"][0]
    assert row["remittance_id"] == str(t["remittance_id"])
    assert row["remittance_number"] and row["total_amount"] == "10000.00"
    assert row["collection_date"] == "2026-10-01" and row["submitted_at"]
    assert (
        row["application_request_supported"] is False and row["source_digest"] is None
    )
    assert "source_snapshot" not in row and "gross_obligation" not in row


def test_explicit_own_mode_denies_staff_without_collector_role(surplus):
    from gilbic_backend.collector_surplus_reads import workspace

    t = surplus
    credit(t)
    with pytest.raises(TreasuryDenied), connect() as conn:
        workspace(t["service"], conn, t["owner"], mode="own", export=True)


def test_owner_with_collector_role_explicit_own_mode_has_no_staff_history(surplus):
    from gilbic_backend.collector_surplus_reads import workspace

    t = surplus
    credit(t)
    with connect() as conn:
        conn.execute(
            "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code='collector' on conflict do nothing",
            (t["owner"].user_id,),
        )
        result = workspace(t["service"], conn, t["owner"], mode="own", export=True)
    assert result["mode"] == "own" and result["accounts"] == []
    assert result["items"] == [] and result["total_count"] == 0


def test_database_rejects_request_linked_to_credit_from_another_account(surplus):
    import psycopg

    t = surplus
    c = credit(t)
    req = command(
        t,
        "collector_surplus_return_request",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        amount="1.00",
        destination={"kind": "physical_cash", "recipient_reference": None},
        reason="Synthetic own request",
    )["result"]["request"]
    with pytest.raises(psycopg.errors.ForeignKeyViolation), connect() as conn:
        conn.execute(
            "insert into treasury.collector_requests(id,account_id,ledger_context_id,collector_user_id,payload) select %s,%s,ledger_context_id,collector_user_id,payload from treasury.collector_requests where id=%s",
            (uuid4(), t["wallet_id"], req["id"]),
        )


def test_concurrent_return_approvals_reserve_capacity_only_once(surplus):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from gilbic_backend.collector_surplus import load

    t = surplus
    c = credit(t)
    req = command(
        t,
        "collector_surplus_return_request",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        amount="70.00",
        destination={"kind": "physical_cash", "recipient_reference": None},
        reason="Exact own requested return",
    )["result"]["request"]
    barrier = Barrier(2)

    def approving(_):
        barrier.wait()
        try:
            return command(
                t,
                "collector_surplus_return_prepare",
                credit_id=c["id"],
                credit_version=c["version"],
                collector_request_id=req["id"],
                collector_request_version=req["version"],
                amount="70.00",
                destination=req["destination"],
                evidence_id=t["evidence_id"],
                reason="Competing independent approvals",
            )
        except TreasuryConflict:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(approving, range(2)))
    assert len([result for result in results if result]) == 1
    with connect() as conn:
        current = load(conn, "credits", c["id"], lock=False)
    assert (
        current["reserved_amount"] == "70.00" and current["available_amount"] == "30.00"
    )
    assert cash_delta(t) == Decimal("10100.00")


def test_recognition_no_self_approval(surplus):
    t = surplus
    r = accept(t, count(t))
    case = r["result"]["case"]
    with pytest.raises(TreasuryDenied):
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
            reason="Forbidden self recognition",
        )


def test_return_reserves_without_movement(surplus):
    t = surplus
    c = credit(t)
    request = command(
        t,
        "collector_surplus_return_request",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        amount="40.00",
        destination={"kind": "physical_cash", "recipient_reference": None},
        reason="Return my own credit",
    )["result"]["request"]
    r = command(
        t,
        "collector_surplus_return_prepare",
        credit_id=c["id"],
        credit_version=c["version"],
        collector_request_id=request["id"],
        collector_request_version=request["version"],
        amount="40.00",
        destination=request["destination"],
        evidence_id=t["evidence_id"],
        reason="Independent return approval",
    )
    assert (
        r["result"]["credit"]["outstanding_amount"] == "100.00"
        and r["result"]["credit"]["available_amount"] == "60.00"
    )
    assert cash_delta(t) == Decimal("10100.00")


def prepared(t, amount="40.00"):
    c = credit(t)
    req = command(
        t,
        "collector_surplus_return_request",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        amount=amount,
        destination={"kind": "physical_cash", "recipient_reference": None},
        reason="Return my own credit",
    )["result"]["request"]
    result = command(
        t,
        "collector_surplus_return_prepare",
        credit_id=c["id"],
        credit_version=c["version"],
        collector_request_id=req["id"],
        collector_request_version=req["version"],
        amount=amount,
        destination=req["destination"],
        evidence_id=t["evidence_id"],
        reason="Independent evidenced approval",
    )
    return result["result"]["action_record"], result["result"]["credit"]


def paid(t):
    a, c = prepared(t)
    debit = command(
        t,
        "disbursement_record",
        purpose="collector_surplus_return",
        source_id=a["id"],
        source_version=a["version"],
        payee_id=t["collector"].user_id,
        amount="40.00",
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="Synthetic actual cash handed out",
        reason="Observed actual return",
    )
    assert cash_delta(t) == Decimal("10060.00")
    a = debit["result"]["source_link"]["action_record"]
    event = debit["result"]["event"]
    ack = command(
        t,
        "collector_surplus_return_acknowledge",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        action_id=a["id"],
        action_version=a["version"],
        event_id=event["id"],
        event_version=1,
        reviewed_amount="40.00",
        confirmation="received",
        acknowledged_at=datetime.now(UTC),
        reason="I independently received this exact cash",
    )["result"]["acknowledgment"]
    result = command(
        t,
        "collector_surplus_return_record",
        action_id=a["id"],
        action_version=a["version"],
        event_id=event["id"],
        event_version=1,
        acknowledgment_id=ack["id"],
        acknowledgment_version=ack["version"],
        reason="Exact Collector receipt verified",
    )
    assert result["result"]["credit"]["outstanding_amount"] == "60.00"
    return result


def test_blocked_actual_debit_retained_once_and_reservation_cannot_be_cancelled(
    surplus,
):
    from gilbic_backend.collector_surplus import load
    from gilbic_backend.treasury_disbursements import source_choices

    t = surplus
    a, c = prepared(t)
    fields = {
        "purpose": "collector_surplus_return",
        "source_id": a["id"],
        "source_version": a["version"] + 1,
        "payee_id": t["collector"].user_id,
        "amount": "40.00",
        "provider": "physical_cash",
        "reference": uuid4().hex,
        "effective_at": datetime.now(UTC),
        "evidence_id": t["evidence_id"],
        "recipient_attestation": "Synthetic independently observed actual cash",
        "reason": "Retain actual debit even when source version conflicts",
    }
    model = COMMAND_ADAPTER.validate_python(
        {
            "action": "disbursement_record",
            "request_id": uuid4(),
            "account_id": t["account_id"],
            "expected_version": version(t),
            **fields,
        }
    )
    result = t["service"].execute(t["owner"], model)
    link = result["result"]["source_link"]
    assert link["status"] == "blocked" and link["source_id"] == a["id"]
    assert (
        link["source_version"] == fields["source_version"]
        and link["action_record"]["status"] == "reserved"
    )
    event = result["result"]["event"]
    assert (
        event["classification"] == "verified_unclassified"
        and link["observed_event_id"] == event["id"]
    )
    assert cash_delta(t) == Decimal("10060.00")
    assert t["service"].execute(t["owner"], model) == result
    with connect() as conn:
        current = load(conn, "credits", c["id"], lock=False)
        assert (
            current["outstanding_amount"] == "100.00"
            and current["reserved_amount"] == "40.00"
        )
        assert all(
            choice["id"] != a["id"] for choice in source_choices(conn, t["owner"])
        )
    with pytest.raises(TreasuryConflict):
        command(
            t,
            "collector_surplus_action_cancel",
            action_id=a["id"],
            action_version=a["version"],
            evidence_id=t["evidence_id"],
            reason="Cannot erase independently observed debit",
        )
    with pytest.raises(TreasuryConflict):
        command(
            t,
            "disbursement_record",
            **{**fields, "source_version": a["version"], "reference": uuid4().hex},
        )
    assert cash_delta(t) == Decimal("10060.00")
    reconciled = command(
        t, "disbursement_record", **{**fields, "source_version": a["version"]}
    )
    assert (
        reconciled["result"]["event"]["id"] == event["id"]
        and not reconciled["result"]["new_movement"]
    )
    assert reconciled["result"]["source_link"]["status"] == "confirmation_pending"
    assert cash_delta(t) == Decimal("10060.00")


def test_actual_return_only_settles_after_own_acknowledgment(surplus):
    result = paid(surplus)
    assert result["result"]["disposition"] == "paid"
    assert result["result"]["credit"]["reserved_amount"] == "0.00"
    assert cash_delta(surplus) == Decimal("10060.00")


def test_real_incoming_reversal_reopens_only_justified_credit(surplus):
    t = surplus
    r = paid(t)
    a = r["result"]["action_record"]
    result = command(
        t,
        "collector_surplus_return_reverse",
        action_id=a["id"],
        action_version=a["version"],
        amount="10.00",
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="Synthetic actual returned payout cash counted",
        reason="Independently verified actual payout returned",
    )
    assert result["result"]["disposition"] == "return_reversed"
    assert result["result"]["credit"]["outstanding_amount"] == "70.00"
    assert cash_delta(t) == Decimal("10070.00")


def test_application_request_has_explicit_blocker_without_capacity_consumption(surplus):
    t = surplus
    c = credit(t)
    target = pass_remittance(t)
    from gilbic_backend.collector_settlement import source_snapshot

    with connect() as conn:
        _source, _snapshot, digest, _gross, _refund = source_snapshot(conn, target)
    req = command(
        t,
        "collector_surplus_application_request",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        remittance_id=target,
        source_digest=digest,
        amount="10.00",
        reason="Explicit own future application request",
    )["result"]["request"]
    result = command(
        t,
        "collector_surplus_application_prepare",
        credit_id=c["id"],
        credit_version=c["version"],
        collector_request_id=req["id"],
        collector_request_version=req["version"],
        remittance_id=target,
        source_digest=digest,
        amount="10.00",
        evidence_id=t["evidence_id"],
        reason="Review future application safe adapter",
    )
    assert (
        result["status"] == "blocked"
        and result["result"]["disposition"] == "blocked_adapter"
    )
    assert result["result"]["credit"]["available_amount"] == "100.00"
    assert cash_delta(t) == Decimal("10100.00")


def test_wallet_return_fee_changes_only_paying_wallet(surplus):
    from gilbic_backend.collector_surplus import load

    t = surplus
    c = paid(t)["result"]["credit"]
    office = t["account_id"]
    request = command(
        t,
        "collector_surplus_return_request",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        amount="60.00",
        destination={
            "kind": "gcash",
            "recipient_reference": "synthetic-own-destination",
        },
        reason="Return remaining own credit",
    )["result"]["request"]
    t["account_id"] = t["wallet_id"]
    t["evidence_id"] = evidence(t)
    reserved = command(
        t,
        "collector_surplus_return_prepare",
        credit_id=c["id"],
        credit_version=c["version"],
        collector_request_id=request["id"],
        collector_request_version=request["version"],
        amount="60.00",
        destination=request["destination"],
        evidence_id=t["evidence_id"],
        reason="Independently approved exact wallet return",
    )["result"]
    a = reserved["action_record"]
    c = reserved["credit"]
    debit = command(
        t,
        "disbursement_record",
        purpose="collector_surplus_return",
        source_id=a["id"],
        source_version=a["version"],
        payee_id=t["collector"].user_id,
        amount="60.00",
        fee="2.00",
        provider="gcash",
        reference=uuid4().hex,
        effective_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="Synthetic actual exact-payee wallet transaction verified",
        reason="Actual second return with separate fee",
    )["result"]
    assert cash_delta(t) == Decimal("-62.00")
    with connect() as conn:
        assert conn.execute(
            "select sum(signed_amount) as amount from treasury.movement_lines where account_id=%s",
            (office,),
        ).fetchone()["amount"] == Decimal("10060.00")
    a = debit["source_link"]["action_record"]
    event = debit["event"]
    ack = command(
        t,
        "collector_surplus_return_acknowledge",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        action_id=a["id"],
        action_version=a["version"],
        event_id=event["id"],
        event_version=1,
        reviewed_amount="60.00",
        confirmation="received",
        acknowledged_at=datetime.now(UTC),
        reason="I independently received my exact wallet principal",
    )["result"]["acknowledgment"]
    settled = command(
        t,
        "collector_surplus_return_record",
        action_id=a["id"],
        action_version=a["version"],
        event_id=event["id"],
        event_version=1,
        acknowledgment_id=ack["id"],
        acknowledgment_version=1,
        reason="Own receipt confirmed exact principal",
    )["result"]
    assert settled["credit"]["outstanding_amount"] == "0.00"
    with connect() as conn:
        assert load(conn, "credits", UUID(c["id"]))["returned_amount"] == "100.00"


def test_held_dispute_return_preserves_original_unaccepted_obligation(surplus):
    t = surplus
    c = count(t, "9900.00")
    retained = command(
        t,
        "collector_custody_exception_record",
        count_id=c["id"],
        count_version=1,
        source_digest=c["source_digest"],
        retained_amount="9900.00",
        retained_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        holder_attestation="Synthetic cash physically retained during dispute",
        reason="Retained cash is not a full receipt",
    )["result"]["exception"]
    assert cash_delta(t) == Decimal("9900.00")
    a = command(
        t,
        "collector_custody_exception_return_prepare",
        exception_id=retained["id"],
        exception_version=retained["version"],
        amount="9900.00",
        evidence_id=t["evidence_id"],
        reason="Return all rejected disputed cash",
    )["result"]["action_record"]
    debit = command(
        t,
        "disbursement_record",
        purpose="collector_custody_exception_return",
        source_id=a["id"],
        source_version=a["version"],
        payee_id=t["collector"].user_id,
        amount="9900.00",
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="Synthetic rejected cash actually returned",
        reason="Return disputed handover",
    )["result"]
    a = debit["source_link"]["action_record"]
    event = debit["event"]
    from gilbic_backend.collector_surplus import load

    with connect() as conn:
        retained = load(conn, "exceptions", UUID(retained["id"]))
    ack = command(
        t,
        "collector_custody_exception_return_acknowledge",
        actor=t["collector"],
        exception_id=retained["id"],
        exception_version=retained["version"],
        action_id=a["id"],
        action_version=a["version"],
        event_id=event["id"],
        event_version=1,
        reviewed_amount="9900.00",
        confirmation="received",
        acknowledged_at=datetime.now(UTC),
        reason="I actually received my rejected cash back",
    )["result"]["acknowledgment"]
    result = command(
        t,
        "collector_surplus_return_record",
        action_id=a["id"],
        action_version=a["version"],
        event_id=event["id"],
        event_version=1,
        acknowledgment_id=ack["id"],
        acknowledgment_version=1,
        reason="Disputed cash independently confirmed returned",
    )["result"]
    assert (
        result["disposition"] == "exception_returned"
        and result["exception"]["remaining_held_amount"] == "0.00"
    )
    assert cash_delta(t) == 0
    with connect() as conn:
        assert (
            conn.execute(
                "select status from lending.collection_remittances where id=%s",
                (t["remittance_id"],),
            ).fetchone()["status"]
            == "submitted"
        )


def test_current_receiving_contract_keeps_feature_off_legacy_explicit(
    surplus, monkeypatch
):
    from gilbic_backend.collector_settlement import receiving_contract

    t = surplus
    monkeypatch.setenv("SPINA_COLLECTOR_SURPLUS_ENABLED", "false")
    with connect() as conn:
        p = receiving_contract(t["service"], conn, t["owner"], t["remittance_id"])
    assert p["legacy_receive_allowed"] and not p["count_required"]
    monkeypatch.setenv("SPINA_COLLECTOR_SURPLUS_ENABLED", "true")
    count(t)
    monkeypatch.setenv("SPINA_COLLECTOR_SURPLUS_ENABLED", "false")
    with connect() as conn:
        p = receiving_contract(t["service"], conn, t["owner"], t["remittance_id"])
    assert p["count_required"] and not p["legacy_receive_allowed"]


def test_concurrent_accept_and_recognition_capacity(surplus):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    t = surplus
    c = count(t)
    barrier = Barrier(2)

    def accepting(_):
        barrier.wait()
        try:
            return accept(t, c)
        except TreasuryConflict:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(accepting, range(2)))
    accepted = [row for row in results if row]
    assert len(accepted) == 1 and cash_delta(t) == Decimal("10100.00")
    case = accepted[0]["result"]["case"]
    barrier = Barrier(2)

    def recognizing(_):
        barrier.wait()
        try:
            return command(
                t,
                "collector_surplus_recognize",
                case_id=case["id"],
                case_version=1,
                source_digest=case["source_digest"],
                source_review_acknowledged=True,
                amount="70.00",
                evidence_id=t["evidence_id"],
                reason="Competing independent recognition",
            )
        except TreasuryConflict:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(recognizing, range(2)))
    assert len([row for row in results if row]) == 1
    assert cash_delta(t) == Decimal("10100.00")


def test_reclassification_after_actual_partial_return_freezes_without_negative_credit(
    surplus,
):
    t = surplus
    c = paid(t)["result"]["credit"]
    result = command(
        t,
        "collector_surplus_resolve_source",
        credit_id=c["id"],
        credit_version=c["version"],
        source_id=t["transaction_id"],
        source_digest="a" * 64,
        amount="100.00",
        evidence_id=t["evidence_id"],
        reason="Actual later borrower evidence requires protected historical recovery",
    )["result"]
    assert result["disposition"] == "recovery_required" and result["credit"]["frozen"]
    assert result["credit"]["outstanding_amount"] == "60.00" and cash_delta(
        t
    ) == Decimal("10060.00")


def test_source_recognition_invalidates_close_without_changing_cash_or_snapshot(
    surplus,
):
    from datetime import timedelta

    from gilbic_backend.treasury_reconciliation import preview_reconciliation

    t = surplus
    start = datetime.now(UTC) - timedelta(days=1)
    opening = command(
        t,
        "opening_prepare",
        cutoff=start,
        amount="0.00",
        evidence_id=evidence(t, "opening"),
        reason="Synthetic independently counted opening",
    )
    command(
        t,
        "opening_activate",
        opening_id=opening["target_id"],
        opening_version=opening["version"],
        confirmed=True,
        reason="Synthetic opening authorized",
    )
    accepted = accept(t, count(t))
    case = accepted["result"]["case"]
    with connect() as conn:
        event = conn.execute(
            "select * from treasury.events where id=%s",
            (accepted["result"]["settlement"]["event_id"],),
        ).fetchone()
    observation = uuid4()
    recon = command(
        t,
        "reconciliation_observe",
        reconciliation_id=uuid4(),
        coverage_start=start,
        cutoff=datetime.now(UTC),
        actual_balance="10100.00",
        evidence_id=evidence(t, "statement"),
        complete_history=True,
        rows=[
            {
                "id": observation,
                "provider": "physical_cash",
                "reference": event["reference"],
                "direction": "credit",
                "amount": "10100.00",
                "effective_at": event["effective_at"],
            }
        ],
    )
    matched = command(
        t,
        "reconciliation_match",
        reconciliation_id=recon["target_id"],
        reconciliation_version=recon["version"],
        observation_id=observation,
        event_id=event["id"],
    )
    close = command(
        t,
        "reconciliation_close",
        reconciliation_id=recon["target_id"],
        reconciliation_version=matched["version"],
        opening_id=opening["target_id"],
        movement_watermark=matched["result"]["reconciliation"]["movement_watermark"],
        reason="Cash match complete; identification remains separate",
    )
    original = close["result"]["reconciliation"]["closed_snapshot"]
    assert (
        original["collector_source_status"]["pending_identification_amount"] == "100.00"
    )
    assert not original["collector_source_status"]["gl_posting_available"]
    command(
        t,
        "collector_surplus_recognize",
        case_id=case["id"],
        case_version=case["version"],
        source_digest=case["source_digest"],
        source_review_acknowledged=True,
        amount="100.00",
        evidence_id=t["evidence_id"],
        reason="Later independently reviewed Collector entitlement",
    )
    with connect() as conn:
        row = conn.execute(
            "select * from treasury.reconciliations where id=%s", (recon["target_id"],)
        ).fetchone()
        account = conn.execute(
            "select * from treasury.accounts where id=%s", (t["account_id"],)
        ).fetchone()
        current = preview_reconciliation(conn, account, row)
        assert row["requires_review"] and row["closed_snapshot"] == original
        assert (
            current["collector_source_status"]["pending_identification_amount"]
            == "0.00"
        )
        assert (
            current["collector_source_status"]["collector_outstanding_amount"]
            == "100.00"
        )
    assert cash_delta(t) == Decimal("10100.00")


def test_opening_activation_rechecks_actual_cash_date_even_if_entered_later(surplus):
    from datetime import timedelta

    t = surplus
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    opening = command(
        t,
        "opening_prepare",
        cutoff=cutoff,
        amount="10000.00",
        evidence_id=evidence(t, "opening"),
        reason="Synthetic evidenced opening",
    )
    command(
        t,
        "opening_activate",
        opening_id=opening["target_id"],
        opening_version=opening["version"],
        confirmed=True,
        reason="Synthetic owner confirms opening",
    )
    anchor = command(
        t,
        "collector_surplus_opening_prepare",
        collector_user_id=t["collector"].user_id,
        opening_id=opening["target_id"],
        opening_version=2,
        amount="100.00",
        evidence_id=evidence(t, "opening"),
        overlap_review_acknowledged=True,
        reason="Initial overlap review before late source entry",
    )
    accept(t, count(t, counted_at=cutoff - timedelta(minutes=1)))
    with pytest.raises(TreasuryConflict, match="pre-cutoff"):
        command(
            t,
            "collector_surplus_opening_activate",
            anchor_id=anchor["target_id"],
            anchor_version=anchor["version"],
            reason="Must recheck actual source overlap",
        )


def test_opening_pending_excess_never_assumes_collector_credit(surplus):
    from datetime import timedelta

    t = surplus
    opening = command(
        t,
        "opening_prepare",
        cutoff=datetime.now(UTC) - timedelta(days=1),
        amount="10000.00",
        evidence_id=evidence(t, "opening"),
        reason="Actual synthetic opening",
    )
    command(
        t,
        "opening_activate",
        opening_id=opening["target_id"],
        opening_version=opening["version"],
        confirmed=True,
        reason="Owner confirms synthetic opening",
    )
    anchor = command(
        t,
        "collector_surplus_opening_prepare",
        collector_user_id=t["collector"].user_id,
        opening_id=opening["target_id"],
        opening_version=2,
        anchor_kind="pending_excess",
        amount="100.00",
        evidence_id=evidence(t, "opening"),
        overlap_review_acknowledged=True,
        reason="Included unknown source requires identification",
    )
    activated = command(
        t,
        "collector_surplus_opening_activate",
        anchor_id=anchor["target_id"],
        anchor_version=anchor["version"],
        reason="Retain pending opening excess truthfully",
    )["result"]
    assert (
        activated["case"]["unidentified_amount"] == "100.00"
        and activated["credit"] is None
    )
    assert cash_delta(t) == 0


def pass_remittance(t):
    rid, tid = uuid4(), uuid4()
    with connect() as conn:
        conn.execute(
            """insert into lending.collection_transactions(id,idempotency_key,loan_id,client_id,collector_user_id,registered_device_id,route_entry_id,collection_date,entry_type,amount,recorded_at,device_sequence,note,previous_balance,official_balance,pass_count_after,receipt_number,details)
         values(%s,%s,%s,%s,%s,%s,%s,'2026-10-02','pass',0,now(),2,'Synthetic PASS source',10000,10000,1,%s,'{}')""",
            (
                tid,
                uuid4(),
                t["loan_id"],
                t["client_id"],
                t["collector"].user_id,
                t["collector"].registered_device_id,
                t["loan_id"],
                tid.hex,
            ),
        )
        conn.execute(
            """insert into lending.collection_remittances(id,remittance_number,collector_user_id,recipient_user_id,collection_date,status,transaction_count,payment_count,unable_to_pay_count,covered_payment_count,client_count,total_amount,note,submitted_at) values(%s,%s,%s,%s,'2026-10-02','submitted',1,0,1,0,1,0,'Synthetic zero PASS handover',now())""",
            (rid, rid.hex, t["collector"].user_id, t["owner"].user_id),
        )
        conn.execute(
            "insert into lending.collection_remittance_items(remittance_id,transaction_id,client_id,loan_id,collection_date,entry_type,amount,receipt_number,transaction_snapshot) values(%s,%s,%s,%s,'2026-10-02','pass',0,%s,'{}')",
            (rid, tid, t["client_id"], t["loan_id"], tid.hex),
        )
        conn.execute(
            "update lending.collection_transactions set remittance_id=%s,is_locked=true,locked_at=now(),locked_by_user_id=%s where id=%s",
            (rid, t["collector"].user_id, tid),
        )
    return rid


def test_actual_service_serialized_contract_examples(surplus, monkeypatch):
    import json
    import os
    from datetime import timedelta
    from pathlib import Path

    from gilbic_backend.collector_surplus_reads import workspace
    from gilbic_backend.treasury_repository import json_value

    t = surplus
    examples = []
    original = t["service"].execute

    def recording(actor, model):
        result = original(actor, model)
        examples.append(
            {
                "kind": model.action,
                "actor": {
                    "user_id": str(actor.user_id),
                    "device_id": str(actor.registered_device_id),
                },
                "command": model.model_dump(mode="json"),
                "response": {"success": True, "data": result},
            }
        )
        return result

    monkeypatch.setattr(t["service"], "execute", recording)
    opening = command(
        t,
        "opening_prepare",
        cutoff=datetime.now(UTC) - timedelta(days=1),
        amount="10000.00",
        evidence_id=evidence(t, "opening"),
        reason="Synthetic evidenced physical opening",
    )
    command(
        t,
        "opening_activate",
        opening_id=opening["target_id"],
        opening_version=opening["version"],
        confirmed=True,
        reason="Owner confirms actual synthetic opening",
    )
    p = snapshot(t)
    assert isinstance(p["source_items"], list) and isinstance(
        p["refund_due_releases"], list
    )
    examples.append(
        {
            "kind": "preview",
            "actor": {
                "user_id": str(t["owner"].user_id),
                "device_id": str(t["owner"].registered_device_id),
            },
            "response": {"success": True, "data": p},
        }
    )
    result = paid(t)
    a = result["result"]["action_record"]
    reversed_result = command(
        t,
        "collector_surplus_return_reverse",
        action_id=a["id"],
        action_version=a["version"],
        amount="10.00",
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="Synthetic returned payout physically counted",
        reason="Actual independently observed reversal",
    )
    c = reversed_result["result"]["credit"]
    t["remittance_id"] = pass_remittance(t)
    future = snapshot(t)
    req = command(
        t,
        "collector_surplus_application_request",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        remittance_id=t["remittance_id"],
        source_digest=future["source_digest"],
        amount="10.00",
        reason="Explicit own application intent",
    )["result"]["request"]
    blocked = command(
        t,
        "collector_surplus_application_prepare",
        credit_id=c["id"],
        credit_version=c["version"],
        collector_request_id=req["id"],
        collector_request_version=req["version"],
        remittance_id=t["remittance_id"],
        source_digest=future["source_digest"],
        amount="10.00",
        evidence_id=t["evidence_id"],
        reason="Protected application adapter review",
    )
    assert blocked["result"]["disposition"] == "blocked_adapter"
    zero = accept(t, count(t, "0.00"))
    assert (
        zero["result"]["settlement"]["event_id"] is None
        and zero["result"]["settlement"]["physical_amount"] == "0.00"
    )
    anchor = command(
        t,
        "collector_surplus_opening_prepare",
        collector_user_id=t["collector"].user_id,
        opening_id=opening["target_id"],
        opening_version=2,
        amount="10.00",
        evidence_id=evidence(t, "opening"),
        overlap_review_acknowledged=True,
        reason="Independent evidenced opening liability",
    )
    command(
        t,
        "collector_surplus_opening_activate",
        anchor_id=anchor["target_id"],
        anchor_version=anchor["version"],
        reason="Activate synthetic liability without cash inflow",
    )
    return_request = command(
        t,
        "collector_surplus_return_request",
        actor=t["collector"],
        credit_id=c["id"],
        credit_version=c["version"],
        amount="10.00",
        destination={"kind": "physical_cash", "recipient_reference": None},
        reason="Request own exact partial return",
    )["result"]["request"]
    reserved = command(
        t,
        "collector_surplus_return_prepare",
        credit_id=c["id"],
        credit_version=c["version"],
        collector_request_id=return_request["id"],
        collector_request_version=return_request["version"],
        amount="10.00",
        destination=return_request["destination"],
        evidence_id=t["evidence_id"],
        reason="Independently reviewed reserved return",
    )["result"]["action_record"]
    observed = command(
        t,
        "disbursement_record",
        purpose="collector_surplus_return",
        source_id=reserved["id"],
        source_version=reserved["version"] + 1,
        payee_id=t["collector"].user_id,
        amount="10.00",
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=datetime.now(UTC),
        evidence_id=t["evidence_id"],
        recipient_attestation="Actual synthetic outgoing cash counted",
        reason="Actual debit retains blocked current source version",
    )
    assert observed["result"]["source_link"]["status"] == "blocked"
    with connect() as conn:
        for who, kind in [
            (t["owner"], "credits"),
            (t["owner"], "actions"),
            (t["owner"], "openings"),
            (t["collector"], "credits"),
            (t["collector"], "remittances"),
        ]:
            w = workspace(t["service"], conn, who, kind)
            examples.append(
                {
                    "kind": w["mode"] + "-workspace-" + kind,
                    "actor": {
                        "user_id": str(who.user_id),
                        "device_id": str(who.registered_device_id),
                    },
                    "response": {"success": True, "data": w},
                }
            )
    assert cash_delta(t) == Decimal("10060.00")
    if path := os.getenv("SPINA_SURPLUS_CONTRACT_EXAMPLES_PATH"):
        Path(path).write_text(
            json.dumps(
                json_value(
                    {
                        "synthetic_only": True,
                        "contract_version": 1,
                        "examples": examples,
                    }
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
