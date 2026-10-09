"""Management reports actual applied receipts against the registered contract."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
import treasury_test_support
from gilbic_backend.contract_schedule_engine import ContractInstallment
from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.contract_schedule_service import store_contract_schedule
from gilbic_backend.management_loan_api import _loan_payload
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)
from psycopg.rows import tuple_row
from treasury_test_support import connect

from gilbic_backend import management_loan_repository as management

treasury = treasury_test_support.treasury


def register(f, *, seven=False, total="6000.00", supersede=False):
    rows = (
        generate_signed_seven_by_seven_schedule(
            original_principal="3000.00",
            agreed_daily_payment="121.00",
            daily_interest_per_1000="7.00",
            first_due_date=date(2026, 10, 2),
        )
        if seven
        else (ContractInstallment(1, date(2026, 10, 2), Decimal(total)),)
    )
    with connect() as conn:
        return register_verified_contract_schedule(
            conn.cursor(row_factory=tuple_row),
            loan_id=f["loan_id"],
            payment_frequency="daily" if seven else "custom",
            contract_reference=uuid4().hex,
            contract_signed_date=date(2026, 10, 1),
            effective_from=date(2026, 10, 1),
            grace_days=0,
            installments=rows,
            evidence_basis="signed_contract",
            evidence_reference="Synthetic registered contractual amount",
            verification_note="Isolated paid projection regression",
            verified_by_user_id=f["owner"].user_id,
            agreed_daily_payment=Decimal("121.00") if seven else None,
            confirmed=True,
            supersede_active=supersede,
        )


def receipt(f, *, amount, applied, voided=False, entry_type="payment"):
    with connect() as conn:
        conn.execute(
            """insert into lending.collection_transactions(
            idempotency_key,loan_id,client_id,collector_user_id,registered_device_id,
            route_entry_id,collection_date,entry_type,amount,applied_amount,unallocated_amount,allocation_state,recorded_at,
            device_sequence,previous_balance,official_balance,pass_count_after,
            receipt_number,advance_from,advance_until,is_voided,voided_at,voided_by_user_id,void_reason)
            values(%s,%s,%s,%s,%s,%s,'2026-10-02',%s,%s,%s,%s,%s,now(),1,6000,5900,0,%s,%s,%s,%s,
                case when %s then now() else null end,%s,%s)""",
            (
                uuid4(),
                f["loan_id"],
                f["client_id"],
                f["owner"].user_id,
                f["owner"].registered_device_id,
                f["loan_id"],
                entry_type,
                Decimal(amount),
                Decimal(applied),
                Decimal(amount) - Decimal(applied),
                "not_applicable"
                if entry_type == "pass"
                else "unallocated"
                if Decimal(applied) == 0
                else "partially_allocated"
                if Decimal(amount) > Decimal(applied)
                else "fully_allocated",
                uuid4().hex,
                date(2026, 10, 3) if entry_type == "advance" else None,
                date(2026, 10, 4) if entry_type == "advance" else None,
                voided,
                voided,
                f["owner"].user_id if voided else None,
                "Synthetic reversed receipt" if voided else None,
            ),
        )


@pytest.mark.parametrize(
    "mode,applied,remaining,registered,voided,entry_type,want_paid,want_percent",
    [
        ("fixed_daily", "100.00", "5900.00", True, False, "payment", "100.00", "1.7"),
        ("fixed_daily", "0.00", "6000.00", True, False, "payment", "0.00", "0.0"),
        ("fixed_daily", "0.00", "6000.00", True, False, "pass", "0.00", "0.0"),
        ("fixed_daily", "100.00", "6000.00", True, True, "payment", "0.00", "0.0"),
        ("fixed_daily", "75.00", "5925.00", True, False, "payment", "75.00", "1.2"),
        ("fixed_daily", "100.00", "5900.00", True, False, "advance", "100.00", "1.7"),
        ("fixed_daily", "100.00", "5900.00", False, False, "payment", "100.00", None),
        (
            "seven_by_seven",
            "121.00",
            "2900.00",
            True,
            False,
            "payment",
            "121.00",
            "3.3",
        ),
        ("seven_by_seven", "21.00", "3000.00", True, False, "payment", "21.00", "0.6"),
        ("seven_by_seven", "0.00", "3000.00", True, False, "payment", "0.00", "0.0"),
    ],
)
def test_management_paid_projection_uses_applied_receipts(
    treasury,
    monkeypatch,
    mode,
    applied,
    remaining,
    registered,
    voided,
    entry_type,
    want_paid,
    want_percent,
):
    f = treasury
    seven = mode == "seven_by_seven"
    with connect() as conn:
        type_id = conn.execute(
            "insert into lending.loan_types(code,name,term_days,calculation_mode) values(%s,'Synthetic paid projection',60,%s) returning id",
            (uuid4().hex, mode),
        ).fetchone()["id"]
        conn.execute(
            "update lending.loans set loan_type_id=%s,principal=%s where id=%s",
            (type_id, Decimal("3000.00" if seven else "5000.00"), f["loan_id"]),
        )
        conn.execute(
            "insert into lending.loan_collection_state(loan_id,remaining_balance) values(%s,%s)",
            (f["loan_id"], Decimal(remaining)),
        )
    if registered:
        register(f, seven=seven)
    # Cash tendered may exceed applied amount. Voided and zero receipts never
    # become invented paid cash, even when contractual state has another basis.
    receipt(
        f,
        amount="0.00" if entry_type == "pass" else "150.00",
        applied=applied,
        voided=voided,
        entry_type=entry_type,
    )
    monkeypatch.setattr(management, "open_connection", connect)
    result = management.PostgresManagementLoanRepository().list_portfolio(
        query=f["loan_id"].hex, status="all", limit=50, offset=0
    )
    assert len(result.loans) == 1
    payload = _loan_payload(result.loans[0])
    assert payload["paid_amount"] == want_paid
    assert payload["paid_percent"] == want_percent


def test_only_active_registered_contract_supplies_management_denominator(
    treasury, monkeypatch
):
    f = treasury
    register(f, total="1000.00")
    register(f, total="6000.00", supersede=True)
    receipt(f, amount="100.00", applied="100.00")
    monkeypatch.setattr(management, "open_connection", connect)
    result = management.PostgresManagementLoanRepository().list_portfolio(
        query=f["loan_id"].hex, status="all", limit=50, offset=0
    )
    assert _loan_payload(result.loans[0])["paid_percent"] == "1.7"


def test_unverified_schedule_does_not_supply_management_percentage(
    treasury, monkeypatch
):
    f = treasury
    with connect() as conn:
        store_contract_schedule(
            conn.cursor(row_factory=tuple_row),
            loan_id=f["loan_id"],
            payment_frequency="custom",
            contract_reference=uuid4().hex,
            contract_signed_date=date(2026, 10, 1),
            effective_from=date(2026, 10, 1),
            grace_days=0,
            installments=(
                ContractInstallment(1, date(2026, 10, 2), Decimal("6000.00")),
            ),
            created_by_user_id=f["owner"].user_id,
        )
    receipt(f, amount="100.00", applied="100.00")
    monkeypatch.setattr(management, "open_connection", connect)
    result = management.PostgresManagementLoanRepository().list_portfolio(
        query=f["loan_id"].hex, status="all", limit=50, offset=0
    )
    assert _loan_payload(result.loans[0])["paid_amount"] == "100.00"
    assert _loan_payload(result.loans[0])["paid_percent"] is None
