"""Real Regular Treasury applications consume retained funds after fiscal prefixes."""

from contextlib import nullcontext
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.contract_collection_activation_repository import (
    PostgresContractCollectionActivationRepository,
)
from gilbic_backend.contract_collection_posting import CONTRACT_ALLOCATION_SETTING
from gilbic_backend.eir_cash_allocation import (
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
    money,
)
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from gilbic_backend.treasury_claims import claim_action, put_evidence
from gilbic_backend.treasury_models import (
    AllocationPreview,
    ReceiptApply,
    ReceiptVerify,
)
from gilbic_backend.treasury_repository import TreasuryService
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from test_elapsed_period_assessment_postgres import (
    _collection,
    _seed,
)
from test_elapsed_period_assessment_postgres import (
    _post as post_prefix,
)
from test_elapsed_period_assessment_postgres import (
    _prepare as prepare_prefix,
)
from test_source_close_guard_postgres import _connect
from test_treasury_receipt_accounting_postgres import mapping, post, prepare
from treasury_test_support import PDF, grant_live

from gilbic_backend import contract_collection_activation_repository as activation
from gilbic_backend import treasury_collection_posting as allocation

POLICY = "treasury_regular_original_first_cash_v1"
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0158_add_regular_treasury_applications.sql"
)


def _prefix(f):
    """Recognize day2; a day4 cash boundary must still use original raw carrying."""
    conn = f["conn"]
    first = f | {"cutoff": f["release_day"] + timedelta(days=2)}
    conn.execute(
        "UPDATE accounting.fiscal_periods SET end_date=%s WHERE id=%s",
        (first["cutoff"], first["period"]),
    )
    first["evidence"] = conn.execute(
        "SELECT accounting.record_ecl_forward_looking_evidence("
        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL)",
        (
            "regular-prefix-" + f["suffix"],
            "Synthetic earlier published economic evidence",
            "Earlier publication " + f["suffix"],
            first["cutoff"] - timedelta(days=30),
            first["cutoff"] - timedelta(days=1),
            first["cutoff"],
            f["cutoff"] + timedelta(days=180),
            datetime.combine(first["cutoff"], time(10), tzinfo=timezone.utc),
            first["cutoff"],
            "Original publication existed at the historical prefix cutoff.",
            f["actor"],
        ),
    ).fetchone()[0]
    prepared, digest = prepare_prefix(first)
    audit = post_prefix(first, prepared, digest)
    f["period"] = conn.execute(
        "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) "
        "VALUES(%s,%s,%s,'open') RETURNING id",
        (
            "Regular cash boundary " + f["suffix"],
            first["cutoff"] + timedelta(days=1),
            f["cutoff"],
        ),
    ).fetchone()[0]
    row = conn.execute(
        "SELECT source_snapshot#>>'{eir,cumulative_interest}', "
        "measurement_snapshot->>'ecl_amount' "
        "FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (prepared,),
    ).fetchone()
    return {
        "prefix_period": first["period"],
        "prefix_cutoff": first["cutoff"],
        "prefix_preparation": prepared,
        "prefix_posting": audit,
        "prior_interest": Decimal(row[0]),
        "prior_allowance": Decimal(row[1]),
    }


def actual_regular_source(conn, monkeypatch, tmp_path, *, with_prefix=False):
    # Use the current schema without silently reinstalling153 over154 hooks.
    assert conn.execute(
        "SELECT to_regprocedure('accounting.post_elapsed_loan_period_assessment(uuid,uuid,text)')"
    ).fetchone()[0], "Run this fixture against the current through154 schema"
    if MIGRATION.exists():
        source = MIGRATION.read_text(encoding="utf-8").strip()
        assert source.startswith("BEGIN;") and source.endswith("COMMIT;")
        conn.execute(source[len("BEGIN;") : -len("COMMIT;")])
    monkeypatch.setenv("SPINA_ELAPSED_ASSESSMENT_BASELINE", "1")
    f = _seed(conn, elapsed_days=4)
    conn.execute(
        "UPDATE lending.loan_types SET settings=settings || %s "
        "WHERE id=(SELECT loan_type_id FROM lending.loans WHERE id=%s)",
        (
            Jsonb(
                {
                    "mobile_collections_enabled": True,
                    "mobile_balance_mode": "direct_remaining_balance",
                    CONTRACT_ALLOCATION_SETTING: True,
                }
            ),
            f["loan"],
        ),
    )
    conn.execute(
        "INSERT INTO lending.loan_collection_state(loan_id,remaining_balance,is_reconciled,state_version) "
        "VALUES(%s,6000,true,0)",
        (f["loan"],),
    )
    conn.execute(
        "INSERT INTO lending.loan_schedule_operational_state(schedule_id,operational_version,updated_by_user_id) "
        "SELECT id,0,%s FROM lending.loan_contract_schedules WHERE loan_id=%s",
        (f["actor"], f["loan"]),
    )
    # Use the real Management activation readiness/locking/writer while keeping
    # this fixture's entire operational source inside its rollback transaction.
    monkeypatch.setattr(activation, "open_connection", lambda: nullcontext(conn))
    activated = PostgresContractCollectionActivationRepository().activate(
        loan_id=f["loan"],
        acted_by_user_id=f["actor"],
        activation_note="Synthetic original Regular signed schedule reconciled and activated.",
    )
    assert activated.active_for_current_schedule and activated.balance_reconciled
    prefix = (
        _prefix(f)
        if with_prefix
        else {
            "prior_interest": Decimal("0.00"),
            "prior_allowance": Decimal("0.00"),
        }
    )
    actor_id, device = f["actor"], uuid4()
    conn.execute(
        "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) "
        "VALUES(%s,%s,%s,'web','active')",
        (device, actor_id, device.hex),
    )
    permissions = (
        "treasury.view",
        "treasury.account.manage",
        "treasury.receipt.verify",
        "treasury.payment.apply",
        "accounting.journal.manage",
    )
    grant_live(conn, actor_id, *permissions)
    actor = AccountContext(
        actor_id,
        actor_id,
        "synthetic",
        None,
        "Synthetic original Regular manager",
        "active",
        ("management",),
        permissions,
        True,
        device,
    )
    conn.row_factory = dict_row
    context, wallet = uuid4(), uuid4()
    conn.execute(
        "INSERT INTO treasury.contexts(id,kind,created_by) VALUES(%s,'synthetic',%s)",
        (context, actor_id),
    )
    conn.execute(
        "INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) "
        "VALUES(%s,%s,'gcash','Synthetic original Regular wallet','synthetic',%s)",
        (wallet, context, actor_id),
    )
    conn.execute(
        "INSERT INTO treasury.account_access(account_id,user_id,permissions,private_history,granted_by) "
        "VALUES(%s,%s,%s,true,%s)",
        (wallet, actor_id, list(permissions[:4]), actor_id),
    )
    service = TreasuryService(store=PrivateEvidenceStore(tmp_path / "regular-private"))
    account = conn.execute(
        "SELECT * FROM treasury.accounts WHERE id=%s", (wallet,)
    ).fetchone()
    evidence = put_evidence(
        service, conn, actor, account, uuid4(), "recipient", PDF, "application/pdf"
    )
    receipt_command = ReceiptVerify(
        action="receipt_verify",
        request_id=uuid4(),
        account_id=wallet,
        expected_version=account["version"],
        client_id=f["client"],
        amount="250.00",
        provider="gcash",
        reference=uuid4().hex,
        effective_at=datetime.combine(
            f["cutoff"], time(9), tzinfo=timezone(timedelta(hours=8))
        ),
        evidence_id=evidence["id"],
        recipient_attestation="Synthetic recipient verified this actual wallet credit.",
    )
    receipt, _, verified, _ = claim_action(
        service, conn, actor, account, receipt_command
    )
    assert verified["new_movement"] is True
    f = (
        f
        | prefix
        | {
            "actor_id": actor_id,
            "actor": actor,
            "wallet": wallet,
            "context": context,
            "receipt": receipt,
            "event": UUID(verified["receipt"]["event_id"]),
            "evidence": evidence["id"],
            "day": f["cutoff"],
        }
    )
    f["receipt_journal"] = post(f, prepare(f, mapping(f)))
    monkeypatch.setattr(allocation.combined, "_current_business_date", lambda: f["day"])
    receipt_row = conn.execute(
        "SELECT * FROM treasury.receipts WHERE id=%s", (receipt,)
    ).fetchone()
    inputs = {
        "mode": "single",
        "total_amount": "200.00",
        "loans": [{"loan_id": f["loan"], "expected_version": 0}],
        "effective_date": f["day"],
        "expected_version": receipt_row["version"],
    }
    preview = allocation.preview_allocation(
        conn, actor, receipt_row, AllocationPreview(**inputs)
    )
    assert preview["can_apply"], preview
    application_command = ReceiptApply(
        **inputs,
        action="receipt_apply",
        request_id=uuid4(),
        account_id=wallet,
        receipt_id=receipt,
        digest=preview["digest"],
    )
    account = conn.execute(
        "SELECT * FROM treasury.accounts WHERE id=%s", (wallet,)
    ).fetchone()
    _, _, applied, _ = claim_action(service, conn, actor, account, application_command)
    f["application"] = UUID(applied["application_id"])
    transactions = applied["application"]["transaction_ids"]
    assert len(transactions) == 1, "Fixture must use one real protected collection"
    f["transaction"] = UUID(transactions[0])
    transaction = conn.execute(
        "SELECT * FROM lending.collection_transactions WHERE id=%s",
        (f["transaction"],),
    ).fetchone()
    assert transaction["funding_source"] == "treasury_receipt"
    assert transaction["applied_amount"] == transaction["amount"] == Decimal("200.00")
    assert transaction["unallocated_amount"] == 0
    with localcontext() as context:
        context.prec = 50
        result = allocate_event_date_eir_cash(
            EirCutoverState(
                loan_id=f["loan"],
                calculation_mode="fixed_daily",
                cutover_date=f["release_day"],
                due_date=f["release_day"] + timedelta(days=120),
                measurement_status="measured",
                daily_eir=f["rate"],
                loan_component=Decimal("5000.00"),
                accrued_interest_component=Decimal("0.00"),
                gross_carrying_amount=Decimal("5000.00"),
            ),
            (
                EirCashSourceEvent(
                    transaction_id=f["transaction"],
                    collection_date=f["day"],
                    accepted_at=transaction["accepted_at"],
                    entry_type=transaction["entry_type"],
                    amount=transaction["amount"],
                    funding_source=transaction["funding_source"],
                ),
            ),
        )
    assert result.status == "allocation_reference_ready"
    f["expected"] = result.allocations[0]
    assert f["expected"].effective_interest_accrued_since_prior_event == Decimal(
        "62.58"
    )
    return f


@pytest.fixture
def regular_application(request, monkeypatch, tmp_path):
    with _connect() as conn:
        try:
            yield actual_regular_source(
                conn,
                monkeypatch,
                tmp_path,
                with_prefix=getattr(request, "param", False),
            )
        finally:
            conn.rollback()


def coordinates(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.treasury_application_coordinates(%s) AS source",
            (f["application"],),
        )
        .fetchone()["source"]
    )


def retained(f):
    source = coordinates(f)
    preparation = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_treasury_application(%s,%s,%s,%s) AS id",
            (f["application"], source["source_digest"], uuid4(), f["actor_id"]),
        )
        .fetchone()["id"]
    )
    return (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_application_preparations WHERE id=%s",
            (preparation,),
        )
        .fetchone()
    )


def posted(f, preparation):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.post_treasury_application(%s,%s,%s,%s) AS id",
            (
                preparation["id"],
                preparation["source_digest"],
                preparation["confirmation_token"],
                f["actor_id"],
            ),
        )
        .fetchone()["id"]
    )


def loan_balances(f):
    return {
        row["code"]: row["amount"]
        for row in f["conn"]
        .execute(
            "SELECT a.code,sum(l.debit-l.credit) amount FROM accounting.journal_lines l "
            "JOIN accounting.journal_entries j ON j.id=l.journal_entry_id "
            "JOIN accounting.accounts a ON a.id=l.account_id "
            "WHERE j.status='posted' AND l.loan_id=%s GROUP BY a.code",
            (f["loan"],),
        )
        .fetchall()
    }


def test_first_regular_application_exposes_its_own_retained_product_policy(
    regular_application,
):
    f = regular_application
    source = coordinates(f)
    assert source["product_model"] == "fixed_daily"
    assert source["accounting_policy_version"] == POLICY
    assert source["amount"] == "200.00"
    assert {line["account_code"] for line in source["lines"]} == {
        "2200",
        "1100",
        "1120",
        "4000",
    }
    assert source["measurement"]["cumulative_interest"] == "62.58"
    assert source["measurement"]["prior_recognized_interest"] == "0.00"


@pytest.mark.parametrize("regular_application", [False, True], indirect=True)
def test_actual_regular_application_consumes_liability_and_posts_cash_only_once(
    regular_application,
):
    f = regular_application
    before = (
        f["conn"]
        .execute(
            "SELECT count(*) count,sum(signed_amount) amount FROM treasury.movement_lines WHERE account_id=%s",
            (f["wallet"],),
        )
        .fetchone()
    )
    prep = retained(f)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) n FROM accounting.journal_entries WHERE source_reference=%s",
            (str(f["application"]),),
        )
        .fetchone()["n"]
        == 0
    )
    entry = posted(f, prep)
    assert posted(f, prep) == entry
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) count,sum(signed_amount) amount FROM treasury.movement_lines WHERE account_id=%s",
            (f["wallet"],),
        )
        .fetchone()
        == before
        == {"count": 1, "amount": Decimal("250.00")}
    )
    assert f["conn"].execute(
        "SELECT sum(l.debit-l.credit) amount FROM accounting.journal_lines l "
        "JOIN accounting.journal_entries j ON j.id=l.journal_entry_id "
        "JOIN accounting.accounts a ON a.id=l.account_id "
        "WHERE j.status='posted' AND a.code='1030' AND l.client_id=%s",
        (f["client"],),
    ).fetchone()["amount"] == Decimal("250.00")
    assert f["conn"].execute(
        "SELECT sum(l.credit-l.debit) amount FROM accounting.journal_lines l "
        "JOIN accounting.journal_entries j ON j.id=l.journal_entry_id "
        "JOIN accounting.accounts a ON a.id=l.account_id "
        "WHERE j.status='posted' AND a.code='2200' AND l.client_id=%s",
        (f["client"],),
    ).fetchone()["amount"] == Decimal("50.00")
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) n FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id "
            "WHERE l.journal_entry_id=%s AND a.code IN('1010','1020','1030','1110','4010')",
            (entry,),
        )
        .fetchone()["n"]
        == 0
    )
    balances = loan_balances(f)
    assert balances["1100"] == f["expected"].loan_component_after == Decimal("4862.58")
    assert balances["1120"] == f["expected"].accrued_interest_after == 0
    assert balances["4000"] == Decimal("-62.58")
    assert balances.get("1190", Decimal(0)) == -f["prior_allowance"]
    proof = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.treasury_application_posting_status WHERE application_id=%s",
            (f["application"],),
        )
        .fetchone()
    )
    assert proof == {"exact_posted": True, "correction_pending": False}
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize("regular_application", [True], indirect=True)
def test_regular_cash_boundary_subtracts_fiscal_claim_without_rounding_reset(
    regular_application,
):
    f = regular_application
    with localcontext() as context:
        context.prec = 50
        original = money(Decimal(5000) * ((1 + f["rate"]) ** 4 - 1))
        rounded_reset = money(
            (Decimal(5000) + f["prior_interest"]) * (1 + f["rate"]) ** 2 - 5000
        )
    assert original == Decimal("62.58") and rounded_reset == Decimal("62.57")
    source = coordinates(f)
    measured = source["measurement"]
    assert Decimal(measured["cumulative_interest"]) == original
    assert Decimal(measured["prior_recognized_interest"]) == f["prior_interest"]
    assert Decimal(measured["incremental_interest"]) == original - f["prior_interest"]
    assert [UUID(row["posting_id"]) for row in source["prefix_claims"]] == [
        f["prefix_posting"]
    ]
    posted(f, retained(f))
    assert (
        f["conn"]
        .execute(
            "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) exact",
            (f["prefix_period"], f["loan"]),
        )
        .fetchone()["exact"]
        is True
    )


def test_first_regular_adapter_cannot_absorb_an_unposted_prior_collection(
    regular_application,
):
    f = regular_application
    f["conn"].row_factory = tuple_row
    try:
        _collection(f | {"actor": f["actor_id"]}, f["release_day"] + timedelta(days=1))
    finally:
        f["conn"].row_factory = dict_row
    with pytest.raises(psycopg.Error, match="prior.*cash|first.*cash|source history"):
        coordinates(f)


@pytest.mark.parametrize("regular_application", [True], indirect=True)
def test_prepared_regular_application_cannot_ignore_changed_prefix_evidence(
    regular_application,
):
    f = regular_application
    prep = retained(f)
    f["conn"].execute(
        "UPDATE accounting.accounts SET normal_balance='debit' WHERE code='4000'"
    )
    with pytest.raises(
        psycopg.Error, match="source changed|prefix|definition|semantic"
    ):
        posted(f, prep)
