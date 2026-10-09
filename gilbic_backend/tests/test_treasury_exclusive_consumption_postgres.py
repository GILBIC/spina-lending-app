"""Exclusive actual movement use, exercised through real Treasury transactions."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.treasury_authorization import TreasuryConflict
from gilbic_backend.treasury_models import (
    AccountConfigure,
    DisbursementRecord,
    MovementCorrect,
    TransferRecord,
)
from test_treasury_postgres import receipt
from test_treasury_reconciliation_postgres import T1, movement, opening
from treasury_test_support import actor, connect, evidence, version

pytest_plugins = ["treasury_test_support"]


def approved_employee_source(f, kind):
    from test_employee_operations_postgres import Case

    with connect() as conn:
        employee = actor(conn, "collector")
        case = Case(conn, {"owner": f["owner"], "manager": f["owner"], "one": employee})
        case.call(
            "owner",
            "profile_save",
            id=employee.user_id,
            employee_id=employee.user_id,
            hire_date="2024-01-01",
            effective_from="2024-01-01",
            daily_rate="800.00",
            payout_method="gcash",
            staff_manager=False,
            active=True,
            premium_pay_covered=True,
            holiday_pay_covered=True,
            tax_exempt=True,
            gp_partial_day_policy="prorated",
            classification_basis="Synthetic reviewed compensation",
        )
        if kind == "payroll":
            case.call(
                "owner",
                "schedule_save",
                employee_id=employee.user_id,
                effective_from="2024-01-01",
                work_days=[1, 2, 3, 4, 5, 6],
                start_time="06:00",
                end_time="15:00",
                meal_minutes=60,
                reason="Synthetic reviewed schedule",
            )
            case.week()
            source = case.payroll()
            approved = case.call(
                "owner",
                "payroll_approve",
                id=source["id"],
                employee_id=employee.user_id,
                expected_version=1,
                decision="approved",
                reason="Synthetic approved payroll",
            )
        else:
            source = case.call(
                "one",
                "advance_request",
                employee_id=employee.user_id,
                amount="100.00",
                reason="Synthetic agreed advance",
                installments=[{"due_date": "2026-10-10", "amount": "100.00"}],
                employee_acknowledgment="Agreed terms",
                payroll_authorization="Actual authorization",
            )
            approved = case.call(
                "owner",
                "advance_decide",
                id=source["id"],
                employee_id=employee.user_id,
                expected_version=1,
                decision="approved",
                reason="Synthetic approved advance",
            )
    return {
        "purpose": kind,
        "source_id": source["id"],
        "source_version": approved["version"],
        "payee_id": employee.user_id,
        "destination_confirmed": True,
        "destination_evidence_id": evidence(f),
        "payee_acknowledgment": "Employee received principal",
    }


def debit(f, reference, **fields):
    return DisbursementRecord(
        action="disbursement_record",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        amount="100.00",
        provider="gcash",
        reference=reference,
        effective_at=T1,
        evidence_id=evidence(f),
        recipient_attestation="Synthetic independently verified actual debit",
        reason="Synthetic exact debit consumption",
        **fields,
    )


def money_state(f):
    with connect() as conn:
        return {
            name: conn.execute(query, (f["account_id"],)).fetchall()
            for name, query in {
                "events": "select * from treasury.events where account_id=%s order by id",
                "lines": "select * from treasury.movement_lines where account_id=%s order by id",
                "links": "select l.* from treasury.source_links l join treasury.events e on e.id=l.event_id where e.account_id=%s order by l.id",
                "receipts": "select * from treasury.receipts where account_id=%s order by id",
                "transfers": "select * from treasury.transfers where source_account_id=%s order by id",
                "revisions": "select r.* from treasury.event_revisions r join treasury.events e on e.id=r.event_id where e.account_id=%s order by r.id",
                "account": "select version,movement_watermark from treasury.accounts where id=%s",
            }.items()
        }


@pytest.mark.parametrize("kind", ["payroll", "salary_advance"])
@pytest.mark.parametrize("first", ["source", "refund"])
def test_refund_and_employee_source_cannot_consume_same_debit(treasury, kind, first):
    f = treasury
    source_fields = approved_employee_source(f, kind)
    received = f["service"].execute(f["owner"], receipt(f))
    commands = {
        "source": source_fields,
        "refund": {"purpose": "refund", "receipt_id": received["target_id"]},
    }
    reference = "exclusive-" + uuid4().hex
    command = debit(f, reference, **commands[first])
    saved = f["service"].execute(f["owner"], command)
    assert saved["result"]["source_link"]["status"] in {
        "completed",
        "actual_refund_recorded",
    }, saved
    assert f["service"].execute(f["owner"], command) == saved
    before = money_state(f)
    rejected_command = debit(
        f, reference, **commands["refund" if first == "source" else "source"]
    )
    rejected = f["service"].execute(f["owner"], rejected_command)
    assert rejected["result"]["source_link"]["status"] == "blocked", rejected
    assert rejected["result"]["new_movement"] is False
    assert f["service"].execute(f["owner"], rejected_command) == rejected
    assert money_state(f) == before
    with connect() as conn:
        assert conn.execute(
            "select count(*) as n from core.employee_payments where employee_id=%s",
            (source_fields["payee_id"],),
        ).fetchone()["n"] == (first == "source")


def other_account(f):
    other = dict(f, account_id=uuid4())
    f["service"].execute(
        f["owner"],
        AccountConfigure(
            action="account_configure",
            request_id=uuid4(),
            account_id=other["account_id"],
            expected_version=0,
            ledger_context_id=f["context_id"],
            context="synthetic",
            kind="gcash",
            alias="Synthetic other wallet",
            ownership="synthetic",
            custodian_user_id=f["owner"].user_id,
            designated_receiving=True,
            payment_instructions="Synthetic recipient only",
        ),
    )
    return other


def transfer_command(f, other, transfer_id, leg, reference):
    return TransferRecord(
        action="transfer_record",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        transfer_id=transfer_id,
        leg=leg,
        other_account_id=other["account_id"],
        other_account_version=version(other),
        amount="100.00",
        provider="gcash",
        reference=reference,
        effective_at=T1,
        evidence_id=evidence(f),
        recipient_attestation="Synthetic actual transfer independently verified",
        reason="Synthetic correlated transfer",
    )


@pytest.mark.parametrize("first", ["transfer", "refund"])
def test_transfer_source_and_refund_are_exclusive(treasury, first):
    f = treasury
    other = other_account(f)
    received = f["service"].execute(f["owner"], receipt(f))
    reference = "transfer-refund-" + uuid4().hex
    transfer_id = uuid4()
    if first == "transfer":
        command = transfer_command(f, other, transfer_id, "source", reference)
        saved = f["service"].execute(f["owner"], command)
        before = money_state(f)
        result = f["service"].execute(
            f["owner"],
            debit(f, reference, purpose="refund", receipt_id=received["target_id"]),
        )
        assert result["result"]["source_link"]["status"] == "blocked", result
    else:
        command = debit(
            f, reference, purpose="refund", receipt_id=received["target_id"]
        )
        saved = f["service"].execute(f["owner"], command)
        before = money_state(f)
        with pytest.raises(TreasuryConflict):
            f["service"].execute(
                f["owner"], transfer_command(f, other, transfer_id, "source", reference)
            )
    assert f["service"].execute(f["owner"], command) == saved
    assert money_state(f) == before


@pytest.mark.parametrize("leg", ["source", "destination"])
@pytest.mark.parametrize("complete", [False, True])
def test_correlated_transfer_leg_correction_rejected_without_writes(
    treasury, leg, complete
):
    f = treasury
    other = other_account(f)
    transfer_id = uuid4()
    command = transfer_command(f, other, transfer_id, leg, "bound-" + uuid4().hex)
    saved = f["service"].execute(f["owner"], command)
    if complete:
        f["service"].execute(
            f["owner"],
            transfer_command(
                other,
                f,
                transfer_id,
                "destination" if leg == "source" else "source",
                "opposite-" + uuid4().hex,
            ),
        )
    correction = MovementCorrect(
        action="movement_correct",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        event_id=saved["result"]["event"]["id"],
        event_version=1,
        evidence_id=evidence(f, "correction"),
        correction="false_observation",
        reason="Synthetic erroneous observation",
    )
    before, other_before = money_state(f), money_state(other)
    with pytest.raises(TreasuryConflict, match="transfer"):
        f["service"].execute(f["owner"], correction)
    assert money_state(f) == before
    assert money_state(other) == other_before
    with connect() as conn:
        assert (
            conn.execute(
                "select 1 from treasury.outcomes where request_id=%s",
                (correction.request_id,),
            ).fetchone()
            is None
        )


def test_unlinked_observation_correction_and_exact_replay_still_work(treasury):
    f = treasury
    opening(f)
    saved = movement(f, "unlinked-" + uuid4().hex, "100.00")
    command = MovementCorrect(
        action="movement_correct",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        event_id=saved["target_id"],
        event_version=1,
        evidence_id=evidence(f, "correction"),
        correction="false_observation",
        reason="Synthetic proved false observation",
    )
    result = f["service"].execute(f["owner"], command)
    assert result["result"]["event"]["corrected"] is True
    assert f["service"].execute(f["owner"], command) == result
    with connect() as conn:
        assert conn.execute(
            "select sum(signed_amount) as amount from treasury.movement_lines where event_id=%s",
            (saved["target_id"],),
        ).fetchone()["amount"] == Decimal("0.00")


def test_concurrent_refunds_for_different_receipts_claim_debit_once(treasury):
    f = treasury
    receipts = [
        f["service"].execute(
            f["owner"], receipt(f, reference="received-" + uuid4().hex)
        )
        for _ in range(2)
    ]
    reference = "race-refund-" + uuid4().hex
    f["service"].execute(f["owner"], debit(f, reference, purpose="unclassified"))
    commands = [
        debit(f, reference, purpose="refund", receipt_id=row["target_id"])
        for row in receipts
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda command: f["service"].execute(f["owner"], command), commands
            )
        )
    assert sorted(result["result"]["source_link"]["status"] for result in results) == [
        "actual_refund_recorded",
        "blocked",
    ]
    with connect() as conn:
        assert conn.execute(
            "select sum(refunded_amount) as amount from treasury.receipts where account_id=%s",
            (f["account_id"],),
        ).fetchone()["amount"] == Decimal("100.00")
        assert (
            conn.execute(
                "select count(*) as n from treasury.source_links l join treasury.events e on e.id=l.event_id where e.account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )


def test_refund_exact_source_relink_after_full_capacity_consumption(treasury):
    f = treasury
    received = f["service"].execute(f["owner"], receipt(f, amount="100.00"))
    reference = "full-refund-" + uuid4().hex
    command = debit(f, reference, purpose="refund", receipt_id=received["target_id"])
    saved = f["service"].execute(f["owner"], command)
    before = money_state(f)
    relink = f["service"].execute(
        f["owner"],
        command.model_copy(
            update={"request_id": uuid4(), "expected_version": version(f)}
        ),
    )
    assert relink["result"]["source_link"]["status"] == "actual_refund_recorded"
    assert relink["result"]["new_movement"] is False
    assert f["service"].execute(f["owner"], command) == saved
    assert money_state(f) == before


@pytest.mark.parametrize("first", ["transfer", "receipt"])
def test_transfer_destination_and_borrower_receipt_are_exclusive(treasury, first):
    f = treasury
    other = other_account(f)
    reference = "destination-receipt-" + uuid4().hex
    transfer_id = uuid4()
    if first == "transfer":
        f["service"].execute(
            f["owner"],
            transfer_command(f, other, transfer_id, "destination", reference),
        )
        rejected = receipt(f, reference=reference, amount="100.00", effective_at=T1)
    else:
        f["service"].execute(
            f["owner"],
            receipt(f, reference=reference, amount="100.00", effective_at=T1),
        )
        rejected = transfer_command(f, other, transfer_id, "destination", reference)
    before, other_before = money_state(f), money_state(other)
    with pytest.raises(TreasuryConflict):
        f["service"].execute(f["owner"], rejected)
    assert money_state(f) == before
    assert money_state(other) == other_before


def test_same_transfer_event_cannot_bind_another_correlation(treasury):
    f = treasury
    other = other_account(f)
    reference = "one-transfer-" + uuid4().hex
    command = transfer_command(f, other, uuid4(), "source", reference)
    saved = f["service"].execute(f["owner"], command)
    before = money_state(f)
    relink = f["service"].execute(
        f["owner"], transfer_command(f, other, command.transfer_id, "source", reference)
    )
    assert relink["result"]["event"]["id"] == saved["result"]["event"]["id"]
    with pytest.raises(TreasuryConflict):
        f["service"].execute(
            f["owner"], transfer_command(f, other, uuid4(), "source", reference)
        )
    # The legitimate relink retains existing transfer version semantics.
    after = money_state(f)
    assert after["transfers"][0]["version"] == before["transfers"][0]["version"] + 1
    after["transfers"][0]["version"] = before["transfers"][0]["version"]
    assert after == before


def test_concurrent_payroll_and_refund_claim_existing_debit_once(treasury):
    f = treasury
    source_fields = approved_employee_source(f, "payroll")
    received = f["service"].execute(f["owner"], receipt(f))
    reference = "race-payroll-" + uuid4().hex
    f["service"].execute(f["owner"], debit(f, reference, purpose="unclassified"))
    commands = [
        debit(f, reference, **source_fields),
        debit(f, reference, purpose="refund", receipt_id=received["target_id"]),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda command: f["service"].execute(f["owner"], command), commands
            )
        )
    statuses = [result["result"]["source_link"]["status"] for result in results]
    assert statuses.count("blocked") == 1
    assert statuses.count("completed") + statuses.count("actual_refund_recorded") == 1
    with connect() as conn:
        links = conn.execute(
            "select l.* from treasury.source_links l join treasury.events e on e.id=l.event_id where e.account_id=%s",
            (f["account_id"],),
        ).fetchall()
        assert len(links) == 1
        payments = conn.execute(
            "select count(*) as n from core.employee_payments where employee_id=%s",
            (source_fields["payee_id"],),
        ).fetchone()["n"]
        refunded = conn.execute(
            "select refunded_amount from treasury.receipts where id=%s",
            (received["target_id"],),
        ).fetchone()["refunded_amount"]
        assert (payments, refunded) in {(1, Decimal("0.00")), (0, Decimal("100.00"))}
