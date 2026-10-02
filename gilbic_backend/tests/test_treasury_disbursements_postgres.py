from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.treasury_authorization import TreasuryConflict
from gilbic_backend.treasury_models import (
    AccountConfigure,
    DisbursementRecord,
    MovementClassify,
    MovementCorrect,
    TransferRecord,
)
from gilbic_backend.treasury_repository import account_snapshot
from test_treasury_reconciliation_postgres import T1, movement, opening
from treasury_test_support import actor, connect, evidence, version


def test_unapproved_actual_debit_remains_exception_not_paid_and_fee_once(treasury):
    f = treasury
    opening(f)
    command = DisbursementRecord(
        action="disbursement_record",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        amount="2000.00",
        fee="15.00",
        provider="gcash",
        reference="unapproved-001",
        effective_at=T1,
        evidence_id=evidence(f),
        recipient_attestation="Actually debited in the recipient history",
        purpose="loan_release",
        source_id=uuid4(),
        source_version=1,
        payee_id=f["client_id"],
        reason="Investigate unmatched real debit",
    )
    result = f["service"].execute(f["owner"], command)
    assert result["result"]["source_link"]["status"] == "blocked"
    assert result["result"]["event"]["status"] == "debited_destination_unconfirmed"
    assert f["service"].execute(f["owner"], command) == result
    with connect() as conn:
        assert (
            account_snapshot(conn, f["account_id"], T1)["expected_balance"] == "7985.00"
        )
        assert (
            conn.execute(
                "select count(*) as n from treasury.source_links where event_id=%s",
                (result["target_id"],),
            ).fetchone()["n"]
            == 0
        )


def test_actual_refund_consumes_capacity_once_without_loan_void(treasury):
    from test_treasury_postgres import receipt

    f = treasury
    opening(f)
    received = f["service"].execute(f["owner"], receipt(f))
    command = DisbursementRecord(
        action="disbursement_record",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        amount="200.00",
        provider="gcash",
        reference="refund-001",
        effective_at=T1,
        evidence_id=evidence(f),
        recipient_attestation="Actual refund debit independently verified",
        purpose="refund",
        receipt_id=received["target_id"],
        reason="Actual provider refund, not loan void",
    )
    result = f["service"].execute(f["owner"], command)
    assert f["service"].execute(f["owner"], command) == result
    with connect() as conn:
        stored = conn.execute(
            "select * from treasury.receipts where id=%s", (received["target_id"],)
        ).fetchone()
        assert (
            stored["refunded_amount"] == Decimal("200.00")
            and stored["applied_amount"] == 0
        )
        assert (
            account_snapshot(conn, f["account_id"], T1)["expected_balance"]
            == "10800.00"
        )


def test_transfer_two_real_times_not_income_and_source_in_transit(treasury):
    f = treasury
    opening(f)
    other_id = uuid4()
    f["service"].execute(
        f["owner"],
        AccountConfigure(
            action="account_configure",
            request_id=uuid4(),
            account_id=other_id,
            expected_version=0,
            ledger_context_id=f["context_id"],
            context="synthetic",
            kind="bank",
            alias="Synthetic second account",
            ownership="synthetic",
            custodian_user_id=f["owner"].user_id,
        ),
    )
    transfer_id = uuid4()
    first = f["service"].execute(
        f["owner"],
        TransferRecord(
            action="transfer_record",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            transfer_id=transfer_id,
            leg="source",
            other_account_id=other_id,
            other_account_version=1,
            amount="1000.00",
            provider="gcash",
            reference="source001",
            effective_at=T1,
            evidence_id=evidence(f),
            recipient_attestation="Source debit verified",
            reason="Own tracked transfer",
        ),
    )
    assert first["result"]["transfer"]["transit_amount"] == "1000.00"
    from gilbic_backend.treasury_claims import upload_evidence
    from treasury_test_support import PDF

    other_evidence = upload_evidence(
        f["service"], f["owner"], uuid4(), other_id, "recipient", PDF, "application/pdf"
    )["target_id"]
    second = f["service"].execute(
        f["owner"],
        TransferRecord(
            action="transfer_record",
            request_id=uuid4(),
            account_id=other_id,
            expected_version=1,
            transfer_id=transfer_id,
            leg="destination",
            other_account_id=f["account_id"],
            other_account_version=version(f),
            amount="1000.00",
            provider="bank",
            reference="destination002",
            effective_at=datetime(2026, 10, 2, 1, tzinfo=timezone.utc),
            evidence_id=other_evidence,
            recipient_attestation="Destination credit independently verified",
            reason="Own tracked transfer received",
        ),
    )
    assert (
        second["result"]["transfer"]["status"] == "completed"
        and second["result"]["transfer"]["transit_amount"] == "0.00"
    )
    with connect() as conn:
        assert (
            account_snapshot(conn, f["account_id"], T1)["expected_balance"] == "9000.00"
        )
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=any(%s)",
                ([f["account_id"], other_id],),
            ).fetchone()["n"]
            == 2
        )


def test_false_observation_correction_keeps_original_reference_reserved(treasury):
    f = treasury
    opening(f)
    event = movement(f, "mistaken001", "100.00")
    f["service"].execute(
        f["owner"],
        MovementCorrect(
            action="movement_correct",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            event_id=event["target_id"],
            event_version=1,
            evidence_id=evidence(f, "correction"),
            correction="false_observation",
            reason="Evidence proves this was not an actual debit",
        ),
    )
    with connect() as conn:
        assert (
            account_snapshot(conn, f["account_id"], T1)["expected_balance"]
            == "10000.00"
        )
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where id=%s",
                (event["target_id"],),
            ).fetchone()["n"]
            == 1
        )
    with pytest.raises(TreasuryConflict):
        movement(f, "mistaken001", "100.00")


def test_append_only_classification_projects_current_version_without_rewriting_original(
    treasury,
):
    f = treasury
    event = movement(f, "classification001", "100.00")
    f["service"].execute(
        f["owner"],
        MovementClassify(
            action="movement_classify",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            event_id=event["target_id"],
            event_version=1,
            classification="personal",
            reason="Owner reviewed actual personal withdrawal",
        ),
    )
    projected = next(
        row
        for row in f["service"].list_records(f["owner"], f["account_id"], "events")[
            "items"
        ]
        if row["id"] == event["target_id"]
    )
    assert projected["version"] == 2 and projected["classification"] == "personal"
    assert projected["original_classification"] == "unclassified"
    with connect() as conn:
        original = conn.execute(
            "select version,classification from treasury.events where id=%s",
            (event["target_id"],),
        ).fetchone()
        assert original["version"] == 1


def test_missing_external_reference_is_owner_unresolved_without_borrower_receipt(
    treasury,
):
    f = treasury
    command = DisbursementRecord(
        action="disbursement_record",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        amount="100.00",
        provider="gcash",
        reference=None,
        effective_at=T1,
        evidence_id=evidence(f),
        direction="credit",
        recipient_attestation="Owner independently verified actual credit, transaction reference unavailable",
        purpose="unclassified",
        reason="Retain unresolved evidence; no loan credit",
    )
    result = f["service"].execute(f["owner"], command)
    assert result["result"]["event"]["reference"] is None
    assert result["result"]["event"]["status"] == "verified_unresolved_reference"
    assert f["service"].execute(f["owner"], command) == result
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.receipts where event_id=%s",
                (result["target_id"],),
            ).fetchone()["n"]
            == 0
        )
        assert (
            conn.execute(
                "select sum(signed_amount) as total from treasury.movement_lines where event_id=%s",
                (result["target_id"],),
            ).fetchone()["total"]
            == 100
        )


def test_actual_approved_advance_uses_protected_payout_once_and_relinks_truthfully(
    treasury,
):
    from gilbic_backend.employee_operations_models import ACTION_ADAPTER
    from gilbic_backend.employee_operations_repository import (
        PostgresEmployeeOperationsRepository,
    )

    f = treasury
    with connect() as conn:
        employee = actor(conn, "collector")

    def call(who, action, **fields):
        command = ACTION_ADAPTER.validate_python(
            {
                "request_id": uuid4(),
                "id": uuid4(),
                "expected_version": 0,
                "employee_id": employee.user_id,
                "action": action,
            }
            | fields
        )
        with connect() as conn:
            return PostgresEmployeeOperationsRepository.execute_in_transaction(
                conn.cursor(), actor=who, command=command
            )

    call(
        f["owner"],
        "profile_save",
        id=employee.user_id,
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
        classification_basis="Reviewed synthetic staff",
    )
    requested = call(
        employee,
        "advance_request",
        amount="100.00",
        reason="Synthetic agreed principal",
        installments=[{"due_date": "2026-10-10", "amount": "100.00"}],
        employee_acknowledgment="Agreed terms",
        payroll_authorization="Actual authorization",
    )
    # Exact explicit command defaults must be overridable by reviewed source IDs.
    approved_command = ACTION_ADAPTER.validate_python(
        {
            "action": "advance_decide",
            "request_id": uuid4(),
            "id": requested["id"],
            "expected_version": 1,
            "employee_id": employee.user_id,
            "decision": "approved",
            "reason": "Owner approves synthetic principal",
        }
    )
    with connect() as conn:
        approved = PostgresEmployeeOperationsRepository.execute_in_transaction(
            conn.cursor(), actor=f["owner"], command=approved_command
        )
    command = DisbursementRecord(
        action="disbursement_record",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        amount="100.00",
        provider="gcash",
        reference="advance001",
        effective_at=T1,
        evidence_id=evidence(f),
        recipient_attestation="Actual owner debit verified",
        purpose="salary_advance",
        source_id=requested["id"],
        source_version=approved["version"],
        payee_id=employee.user_id,
        destination_confirmed=True,
        destination_evidence_id=evidence(f),
        payee_acknowledgment="Employee actually received principal",
        reason="Execute exact approved advance",
    )
    result = f["service"].execute(f["owner"], command)
    assert result["result"]["source_link"]["status"] == "completed", result
    duplicate = f["service"].execute(
        f["owner"],
        command.model_copy(
            update={"request_id": uuid4(), "expected_version": version(f)}
        ),
    )
    assert duplicate["result"]["source_link"]["status"] == "completed", duplicate
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from core.employee_payments where payload->>'advance_id'=%s",
                (requested["id"],),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )


pytest_plugins = ["treasury_test_support"]


def test_reviewed_payroll_partial_wallet_execution_uses_current_protected_snapshot(
    treasury,
):
    from test_employee_operations_postgres import Case

    f = treasury
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
        payroll = case.payroll()
        approved = case.call(
            "owner",
            "payroll_approve",
            id=payroll["id"],
            employee_id=employee.user_id,
            expected_version=1,
            decision="approved",
            reason="Reviewed current exact payroll snapshot",
        )
        conn.commit()
    command = DisbursementRecord(
        action="disbursement_record",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        amount="1000.00",
        provider="gcash",
        reference="actual-payroll001",
        effective_at=T1,
        evidence_id=evidence(f),
        recipient_attestation="Actual owner debit verified",
        purpose="payroll",
        source_id=payroll["id"],
        source_version=approved["version"],
        payee_id=employee.user_id,
        destination_confirmed=True,
        destination_evidence_id=evidence(f),
        reason="Execute exact approved partial payroll",
    )
    result = f["service"].execute(f["owner"], command)
    assert result["result"]["source_link"]["status"] == "completed", result
    assert f["service"].execute(f["owner"], command) == result
    with connect() as conn:
        row = conn.execute(
            "select * from core.employee_payroll where id=%s", (payroll["id"],)
        ).fetchone()
        assert row["status"] == "partially_paid"
        assert row["payload"]["paid_amount"] == "1000.00"
        assert (
            conn.execute(
                "select count(*) as n from core.employee_payments where employee_id=%s",
                (employee.user_id,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "select sum(signed_amount) as amount from treasury.movement_lines where account_id=%s",
                (f["account_id"],),
            ).fetchone()["amount"]
            == -1000
        )
