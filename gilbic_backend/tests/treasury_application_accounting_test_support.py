"""Current signed-schedule, protected Treasury application and EIR test source."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)
from gilbic_backend.treasury_claims import claim_action
from gilbic_backend.treasury_models import AllocationPreview, ReceiptApply
from gilbic_backend.treasury_repository import TreasuryService
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from test_treasury_receipt_accounting_postgres import mapping, post, prepare
from treasury_test_support import grant_live

from gilbic_backend import treasury_collection_posting as allocation


def create_application_source(f, monkeypatch, *, collection_delay=0):
    conn, actor = f["conn"], f["actor"]
    release = f["day"] - timedelta(days=1)
    collection_day = f["day"] + timedelta(days=collection_delay)
    signed = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("3000.00"),
        agreed_daily_payment=Decimal("50.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=f["day"],
    )
    settings = {
        "contractual_interest_payment_frequency": "daily",
        "contractual_principal_due": "on_or_before_maturity",
        "principal_prepayment_allowed": True,
        "principal_prepayment_changes_daily_interest": False,
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
        "mobile_seven_by_seven_enabled": True,
    }
    loan_type = conn.execute(
        "INSERT INTO lending.loan_types(code,name,term_days,calculation_mode,daily_interest_per_1000,settings) VALUES(%s,'Synthetic signed 7x7',%s,'seven_by_seven',7,%s) RETURNING id",
        (uuid4().hex, len(signed), Jsonb(settings)),
    ).fetchone()["id"]
    loan = conn.execute(
        "INSERT INTO lending.loans(loan_number,client_id,loan_type_id,principal,daily_amount,date_released,due_date,status,created_by_user_id) VALUES(%s,%s,%s,3000,50,%s,%s,'active',%s) RETURNING id",
        (
            uuid4().hex,
            f["client"],
            loan_type,
            release,
            signed[-1].due_date,
            actor.user_id,
        ),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO lending.loan_collection_state(loan_id,remaining_balance,is_reconciled,state_version) VALUES(%s,3000,true,0)",
        (loan,),
    )
    with conn.cursor(row_factory=tuple_row) as cursor:
        schedule = register_verified_contract_schedule(
            cursor,
            loan_id=loan,
            payment_frequency="daily",
            contract_reference="test:7x7-signed",
            contract_signed_date=release,
            effective_from=release,
            grace_days=0,
            installments=signed,
            evidence_basis="signed_contract",
            evidence_reference="test:7x7-exact-signed-document",
            verification_note="Synthetic borrower confirmed the exact signed amortizing schedule.",
            verified_by_user_id=actor.user_id,
            agreed_daily_payment=Decimal("50.00"),
            confirmed=True,
        )
    conn.execute(
        "INSERT INTO lending.loan_schedule_operational_state(schedule_id,operational_version,updated_by_user_id) VALUES(%s,0,%s) ON CONFLICT DO NOTHING",
        (schedule, actor.user_id),
    )
    token = conn.execute(
        "SELECT accounting.seven_by_seven_policy_review_token(%s) AS token", (loan,)
    ).fetchone()["token"]
    assert token, "Current signed 7x7 policy token is unavailable"
    conn.execute(
        """SELECT accounting.record_seven_by_seven_policy_decision(%s,%s,'held_to_collect','passes','amortised_cost',
        'verified_no_prepayment_schedule_is_expected_cash_flow_estimate','contractual_term',%s,
        'Synthetic documented amortised-cost policy',%s,%s,'Synthetic explicit classification and expected-life assessment.',
        'test:classification-evidence',%s)""",
        (
            loan,
            token,
            len(signed),
            Jsonb(
                {
                    "business_model_basis": "Synthetic held to collect",
                    "sppi_review": "Synthetic signed terms assessed",
                }
            ),
            Jsonb(
                {"prepayment_feature_reviewed": True, "expected_life_days": len(signed)}
            ),
            actor.user_id,
        ),
    )
    anchor_token = conn.execute(
        "SELECT accounting.seven_by_seven_eir_anchor_review_token(%s) AS token", (loan,)
    ).fetchone()["token"]
    anchor = conn.execute(
        """SELECT accounting.record_seven_by_seven_eir_initial_carrying_anchor(%s,%s,3000,
        'management_evidence_backed_ifrs9_initial_measurement',%s,'test:initial-measurement',
        'Synthetic initial fair value and costs reviewed explicitly.',%s) AS id""",
        (
            loan,
            anchor_token,
            Jsonb(
                {
                    "fair_value_basis": "Synthetic 3000",
                    "transaction_costs_assessment": "Synthetic zero",
                    "integral_fees_assessment": "Synthetic zero",
                    "source_documents": ["test:initial"],
                }
            ),
            actor.user_id,
        ),
    ).fetchone()["id"]
    lines = [
        {
            "account_code": "1110",
            "debit": "3000.00",
            "credit": "0",
            "client_id": str(f["client"]),
            "loan_id": str(loan),
        },
        {"account_code": "3000", "debit": "0", "credit": "3000.00"},
    ]
    opening = conn.execute(
        "SELECT accounting.create_manual_journal_draft(%s,'Synthetic reviewed initial carrying value',%s,%s) AS id",
        (release, actor.user_id, Jsonb(lines)),
    ).fetchone()["id"]
    # The legacy manual constructor does not accept loan attribution. This
    # synthetic reviewed opening adds it while the journal remains a draft;
    # the protected posting path then freezes the exact attributed evidence.
    conn.execute(
        "UPDATE accounting.journal_lines SET client_id=%s,loan_id=%s WHERE journal_entry_id=%s AND account_id=(SELECT id FROM accounting.accounts WHERE code='1110')",
        (f["client"], loan, opening),
    )
    conn.execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)", (opening, actor.user_id)
    )
    assert conn.execute(
        "SELECT sum(l.debit-l.credit) AS amount FROM accounting.journal_lines l JOIN accounting.journal_entries j ON j.id=l.journal_entry_id WHERE j.id=%s AND j.status='posted' AND l.loan_id=%s",
        (opening, loan),
    ).fetchone()["amount"] == Decimal("3000.00")
    receipt_preparation = prepare(f, mapping(f))
    receipt_journal = post(f, receipt_preparation)
    grant_live(conn, actor.user_id, "treasury.payment.apply")
    conn.execute(
        "UPDATE treasury.account_access SET permissions=array_append(permissions,'treasury.payment.apply') WHERE account_id=%s AND user_id=%s",
        (f["wallet"], actor.user_id),
    )
    actor = replace(actor, permissions=("treasury.payment.apply",))
    monkeypatch.setattr(
        allocation.combined, "_current_business_date", lambda: collection_day
    )
    receipt = conn.execute(
        "SELECT * FROM treasury.receipts WHERE id=%s", (f["receipt"],)
    ).fetchone()
    inputs = {
        "mode": "single",
        "total_amount": "50.00",
        "loans": [{"loan_id": loan, "expected_version": 0}],
        "effective_date": collection_day,
        "expected_version": 1,
    }
    preview = allocation.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    assert preview["can_apply"], preview
    command = ReceiptApply(
        **inputs,
        action="receipt_apply",
        request_id=uuid4(),
        account_id=f["wallet"],
        receipt_id=f["receipt"],
        digest=preview["digest"],
    )
    account = conn.execute(
        "SELECT * FROM treasury.accounts WHERE id=%s", (f["wallet"],)
    ).fetchone()
    _, _, payload, _ = claim_action(TreasuryService(), conn, actor, account, command)
    application = UUID(payload["application_id"])
    transaction = UUID(payload["application"]["transaction_ids"][0])
    measurement = conn.execute(
        "SELECT * FROM accounting.preview_seven_by_seven_source_event_accounting(%s) WHERE transaction_id=%s",
        (loan, transaction),
    ).fetchone()
    assert measurement is not None and measurement["event_preview_ready"], (
        "Current EIR authority must be ready before adapter assertions"
    )
    return f | {
        "day": collection_day,
        "loan": loan,
        "schedule": schedule,
        "anchor": anchor,
        "opening": opening,
        "application": application,
        "transaction": transaction,
        "measurement": measurement,
        "receipt_journal": receipt_journal,
    }


def application_coordinates(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.treasury_application_coordinates(%s) AS source",
            (f["application"],),
        )
        .fetchone()["source"]
    )


def application_prepare(f, *, request=None, digest=None):
    digest = digest or application_coordinates(f)["source_digest"]
    result = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_treasury_application(%s,%s,%s,%s) AS id",
            (f["application"], digest, request or uuid4(), f["actor"].user_id),
        )
        .fetchone()["id"]
    )
    return (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_application_preparations WHERE id=%s",
            (result,),
        )
        .fetchone()
    )


def application_post(f, preparation, *, digest=None, token=None):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.post_treasury_application(%s,%s,%s,%s) AS id",
            (
                preparation["id"],
                digest or preparation["source_digest"],
                token or preparation["confirmation_token"],
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )


def additional_loan_gl(f, *, code="1110", amount="1.00", loan=True):
    conn = f["conn"]
    entry = conn.execute(
        "SELECT accounting.create_manual_journal_draft(%s,'Synthetic additional reviewed carrying adjustment',%s,%s) AS id",
        (
            f["day"],
            f["actor"].user_id,
            Jsonb(
                [
                    {"account_code": code, "debit": amount, "credit": "0"},
                    {"account_code": "3000", "debit": "0", "credit": amount},
                ]
            ),
        ),
    ).fetchone()["id"]
    conn.execute(
        "UPDATE accounting.journal_lines SET client_id=%s,loan_id=%s WHERE journal_entry_id=%s AND account_id=(SELECT id FROM accounting.accounts WHERE code=%s)",
        (f["client"], f["loan"] if loan else None, entry, code),
    )
    conn.execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)",
        (entry, f["actor"].user_id),
    )
    return entry


def late_prior_collection(f):
    """Retained real-money-shaped source, appended after the original GL post."""
    return (
        f["conn"]
        .execute(
            """INSERT INTO lending.collection_transactions(idempotency_key,loan_id,client_id,collector_user_id,
        registered_device_id,route_entry_id,collection_date,entry_type,amount,applied_amount,unallocated_amount,
        recorded_at,device_sequence,previous_balance,official_balance,pass_count_after,receipt_number)
        VALUES(%s,%s,%s,%s,%s,%s,%s,'payment',1,1,0,now(),923,3000,2999,0,%s) RETURNING id""",
            (
                uuid4(),
                f["loan"],
                f["client"],
                f["actor"].user_id,
                f["actor"].registered_device_id,
                f["loan"],
                f["day"] - timedelta(days=1),
                uuid4().hex,
            ),
        )
        .fetchone()["id"]
    )
