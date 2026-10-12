"""Current-day funded renewal from genuine preserved original evidence."""

import hashlib
import json
import os
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import test_treasury_loan_payout_postgres as payouts
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.client_account_repository import PostgresClientAccountRepository
from gilbic_backend.contract_schedule_engine import ContractInstallment
from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.elapsed_period_assessment_repository import (
    PostgresElapsedPeriodAssessmentRepository,
)
from gilbic_backend.first_loan_credential_service import (
    FirstLoanCredentialService,
    PostgresFirstLoanCredentialRepository,
)
from gilbic_backend.loan_payout_accounting_repository import (
    PostgresLoanPayoutAccountingRepository,
)
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from gilbic_backend.treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
)
from gilbic_backend.treasury_claims import put_evidence
from gilbic_backend.treasury_models import COMMAND_ADAPTER
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from test_first_loan_credentials import Auth, Mailer
from test_native_current_schema_cycle_postgres import (
    assess_current_cash_cutoff,
    close_period,
    post_application,
    report,
    retain_application_tax,
    retain_native_dst,
    retained_cash_policy,
)
from test_native_regular_historical_postgres import (
    actual_first_application,
    post_prefix,
)
from test_native_renewal_api import body as review_body
from test_native_renewal_measurement_postgres import dated_native as _renewal_native
from test_native_renewal_measurement_postgres import native_source  # noqa: F401
from test_treasury_receipt_accounting_postgres import install
from treasury_test_support import PDF, grant_live

from gilbic_backend import (
    client_account_repository,
    elapsed_period_assessment_repository,
    first_loan_credential_service,
)

native_measurement_source = _renewal_native


@pytest.fixture
def dated_native(native_measurement_source):
    for filename in (
        "0167_add_regular_payoff_accounting.sql",
        "0168_add_native_credit_risk_assessments.sql",
        "0169_add_native_impaired_cash_reviews.sql",
        "0170_add_reporting_source_proof.sql",
        "0171_add_current_credit_risk_review.sql",
    ):
        install(
            native_measurement_source["conn"],
            Path(__file__).resolve().parents[1] / "sql" / filename,
        )
    return native_measurement_source


def private_copy(tmp_path):
    manifest_path = Path(os.environ["SPINA_NATIVE_HISTORY_MANIFEST"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    store = PrivateEvidenceStore(tmp_path / "renewal-private")
    for relative, expected in manifest["private_files"].items():
        if Path(relative).suffix != ".bin":
            continue
        candidates = (
            manifest_path.parent / "private" / relative,
            manifest_path.parent / relative,
        )
        source = next(path for path in candidates if path.is_file())
        data = source.read_bytes()
        assert (
            len(data) == expected["bytes"]
            and hashlib.sha256(data).hexdigest() == expected["sha256"]
        )
        destination = store.root / source.name
        if destination.exists():
            assert destination.read_bytes() == data
        else:
            destination.write_bytes(data)
    return store


def provision_current_borrower(f, monkeypatch):
    """Resume the retained release intent using real local account writes."""
    conn = f["conn"]

    @contextmanager
    def connection():
        previous = conn.row_factory
        conn.row_factory = tuple_row
        try:
            yield conn
        finally:
            conn.row_factory = previous

    monkeypatch.setattr(client_account_repository, "open_connection", connection)
    monkeypatch.setattr(first_loan_credential_service, "open_connection", connection)
    grant_live(conn, f["actor_id"], "client.credential.manage")

    # Identity-provider and delivery boundaries are local fakes. The release
    # intent, actor/device checks, profile/link writes and audit are real SQL.
    class LocalAuth(Auth):
        def create_user(self, **kwargs):
            identity = super().create_user(**kwargs)
            conn.execute("INSERT INTO auth.users(id) VALUES(%s)", (identity,))
            return identity

    auth, mailer = LocalAuth(), Mailer()
    accounts = PostgresClientAccountRepository()
    profile_errors = []
    create_profile = accounts.create_client_account_profile

    def profile(**kwargs):
        try:
            return create_profile(**kwargs)
        except Exception as error:
            profile_errors.append(repr(error))
            raise

    monkeypatch.setattr(accounts, "create_client_account_profile", profile)
    service = FirstLoanCredentialService(
        intents=PostgresFirstLoanCredentialRepository(),
        accounts=accounts,
        auth_admin=auth,
        mailer=mailer,
    )
    arguments = {
        "loan_id": f["loan_id"],
        "actor_user_id": f["actor_id"],
        "registered_device_id": f["device_id"],
    }
    result = service.provision(**arguments)
    assert result["status"] == "completed", profile_errors
    retry = service.provision(**arguments)
    assert retry["user_id"] == result["user_id"] and "credentials" not in retry
    assert auth.creates == mailer.calls == 1
    return UUID(result["user_id"])


def completed_native_renewal(
    f,
    monkeypatch,
    tmp_path,
    *,
    treatment="modification_no_derecognition",
    close_prefix=False,
    prefix_forecast_multiplier=Decimal(1),
    post_completion=True,
    predecessor_credit_impaired=False,
    predecessor_stage=None,
):
    conn, old, new, request = f["conn"], f["loan_id"], uuid4(), uuid4()
    store = private_copy(tmp_path)
    monkeypatch.setenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", str(store.root))
    borrower_id = provision_current_borrower(f, monkeypatch)
    conn.execute(
        "UPDATE lending.loan_types SET settings=settings||%s WHERE id=(SELECT loan_type_id FROM lending.loans WHERE id=%s)",
        (
            Jsonb(
                {
                    "mobile_collections_enabled": True,
                    "mobile_balance_mode": "direct_remaining_balance",
                    "mobile_contract_schedule_allocation_enabled": True,
                }
            ),
            old,
        ),
    )
    # Forecast variation is explicit review input; the signed cash flows and
    # actual source dates remain the immutable captured contract.
    prefix = f | {
        "installments": [
            item
            | {
                "contractual_amount": (
                    item["contractual_amount"] * prefix_forecast_multiplier
                ).quantize(Decimal("0.01"))
            }
            for item in f["installments"]
        ]
    }
    post_prefix(prefix)
    if close_prefix:
        retain_native_dst(f)
        retained_cash_policy(f, f["period_id"])
        close_period(f, f["period_id"])
    period = conn.execute(
        "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) VALUES(%s,%s,%s,'open') RETURNING id",
        ("Native renewal " + uuid4().hex, f["cutoff"] + timedelta(days=1), f["today"]),
    ).fetchone()["id"]
    applied = actual_first_application(f, monkeypatch, tmp_path)
    post_application(f, applied["application_id"])
    impaired_review = None
    if predecessor_credit_impaired or predecessor_stage:
        from test_native_credit_risk_assessment_postgres import reviewed_stage

        # This is an actual current risk decision, before the actual renewal.
        # It is not a backdated fiscal assessment or an elapsed-interest claim.
        impaired_review = reviewed_stage(
            f, predecessor_stage or "stage_3_credit_impaired"
        )
    remaining = conn.execute(
        "SELECT remaining_balance FROM lending.loan_collection_state WHERE loan_id=%s",
        (old,),
    ).fetchone()["remaining_balance"]
    principal = remaining + Decimal(1000)
    device = uuid4()
    conn.execute(
        "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) VALUES(%s,%s,%s,'web','active')",
        (device, borrower_id, device.hex),
    )
    borrower = AccountContext(
        borrower_id,
        borrower_id,
        "synthetic",
        None,
        "Synthetic signed borrower",
        "active",
        ("client",),
        (),
        True,
        device,
    )
    # Approved operational execution is setup evidence. It creates no GL money;
    # the actual current Treasury workflow below supplies the debit and receipt.
    conn.execute(
        "INSERT INTO lending.loans(id,loan_number,client_id,loan_type_id,principal,daily_amount,interest_rate,date_released,due_date,status,created_by_user_id) "
        "SELECT %s,%s,client_id,loan_type_id,%s,%s,interest_rate,%s,%s,'active',%s FROM lending.loans WHERE id=%s",
        (
            new,
            "NATIVE-RENEWAL-" + uuid4().hex,
            principal,
            principal * Decimal("1.2") / 30,
            f["today"],
            f["today"] + timedelta(days=30),
            f["actor_id"],
            old,
        ),
    )
    conn.execute(
        "INSERT INTO lending.loan_collection_state(loan_id,remaining_balance,is_reconciled) VALUES(%s,%s,true)",
        (new, principal * Decimal("1.2")),
    )
    conn.execute("UPDATE lending.loans SET status='paid' WHERE id=%s", (old,))
    conn.execute(
        "UPDATE lending.loan_collection_state SET remaining_balance=0,state_version=state_version+1 WHERE loan_id=%s",
        (old,),
    )
    conn.execute(
        "INSERT INTO lending.client_renewal_requests(id,client_id,loan_id,requested_by_user_id,requested_amount,status,approved_principal,client_decision,client_decided_at,signer_readiness_status,reviewed_by_user_id,reviewed_at,submitted_at) "
        "VALUES(%s,%s,%s,%s,%s,'approved',%s,'accepted',clock_timestamp(),'ready',%s,clock_timestamp(),clock_timestamp())",
        (
            request,
            f["client_id"],
            old,
            borrower_id,
            principal,
            principal,
            f["actor_id"],
        ),
    )
    conn.execute(
        "INSERT INTO lending.renewal_required_signers(renewal_request_id,party_role,full_name,user_id,government_id_verified_at,selfie_verified_at,signed_at) "
        "VALUES(%s,'borrower','Synthetic signed borrower',%s,clock_timestamp(),clock_timestamp(),clock_timestamp())",
        (request, borrower_id),
    )
    disbursement = conn.execute(
        "SELECT accounting.record_loan_disbursement_evidence(%s,%s,'renewal_release',%s,clock_timestamp(),1000,%s,0,'cash_bank_gcash',%s,%s) AS id",
        (
            new,
            f["actor_id"],
            f["today"],
            remaining,
            uuid4().hex,
            "Explicit current synthetic signed renewal execution",
        ),
    ).fetchone()["id"]
    execution = conn.execute(
        "SELECT accounting.record_loan_renewal_execution_evidence(%s,%s,%s,%s,%s,clock_timestamp(),%s,%s,%s,%s) AS id",
        (
            old,
            new,
            disbursement,
            f["actor_id"],
            f["today"],
            remaining,
            uuid4().hex,
            "Explicit current synthetic signed renewal execution",
            request,
        ),
    ).fetchone()["id"]
    installments = tuple(
        ContractInstallment(
            i, f["today"] + timedelta(days=15 * i), principal * Decimal("0.6")
        )
        for i in (1, 2)
    )
    with conn.cursor(row_factory=tuple_row) as cursor:
        schedule = register_verified_contract_schedule(
            cursor,
            loan_id=new,
            payment_frequency="custom",
            contract_reference="SYNTHETIC-RENEWAL-" + request.hex,
            contract_signed_date=f["today"],
            effective_from=f["today"],
            grace_days=0,
            installments=installments,
            evidence_basis="signed_renewal_contract",
            evidence_reference="test:explicit-new-signed-contract",
            verification_note="Explicit current signed synthetic cash flows independently reviewed.",
            verified_by_user_id=f["actor_id"],
            confirmed=True,
        )
    permissions = tuple(
        row["code"]
        for row in conn.execute(
            "SELECT code FROM core.permissions WHERE code LIKE 'treasury.%' OR code IN('renewal.manage','accounting.journal.manage','accounting.renewal_treatment_decision.manage')"
        )
    )
    grant_live(conn, f["actor_id"], *permissions)
    actor = replace(applied["actor"], permissions=permissions)
    wallet, service = applied["wallet_id"], applied["service"]
    for path in service.store.root.glob("*.bin"):
        (store.root / path.name).write_bytes(path.read_bytes())
    service._store = store
    monkeypatch.setattr(service, "connect", lambda: nullcontext(conn))
    monkeypatch.setenv("SPINA_TREASURY_ENABLED", "true")
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(f["actor_id"]))
    conn.execute(
        "UPDATE treasury.account_access SET permissions=%s WHERE account_id=%s AND user_id=%s",
        (list(permissions), wallet, f["actor_id"]),
    )

    def evidence(_case=None):
        account = conn.execute(
            "SELECT * FROM treasury.accounts WHERE id=%s", (wallet,)
        ).fetchone()
        return put_evidence(
            service, conn, actor, account, uuid4(), "recipient", PDF, "application/pdf"
        )["id"]

    def version(_case=None):
        return conn.execute(
            "SELECT version FROM treasury.accounts WHERE id=%s", (wallet,)
        ).fetchone()["version"]

    monkeypatch.setattr(payouts, "evidence", evidence)
    monkeypatch.setattr(payouts, "version", version)
    setup = f | {
        "owner": actor,
        "account_id": wallet,
        "service": service,
        "renewal_id": request,
        "borrower": borrower,
        "release": {"authorization_id": None, "contract_evidence_reference": None},
        "approved": {"packet_hash": None},
    }
    prepared = payouts.prepare_renewal(setup, "borrower")
    payout = UUID(prepared["target_id"])
    payouts.debit(setup, prepared, purpose="renewal")
    payouts.confirm(setup, payout)
    payouts.own_ack(setup, prepared, borrower, "borrower", 3)
    service.execute(
        actor,
        COMMAND_ADAPTER.validate_python(
            {
                "action": "loan_payout_renewal_complete",
                "request_id": uuid4(),
                "account_id": wallet,
                "expected_version": version(),
                "payout_id": payout,
                "payout_version": 4,
                "evidence_id": evidence(),
                "reviewed_amount": "1000.00",
                "proof_review_confirmed": True,
                "reason": "Management reviewed the signed renewal and independent actual borrower receipt.",
            }
        ),
    )
    repository = PostgresLoanPayoutAccountingRepository(
        connection_factory=lambda: nullcontext(conn),
        evidence_store=store,
        office_evidence_store=store,
    )
    debit = repository.review(actor, payout_id=payout, stage="debit")
    prepared = repository.prepare(
        actor,
        payout_id=payout,
        stage="debit",
        source_digest=debit["source_digest"],
        request_id=uuid4(),
    )["preparation"]
    repository.post(
        actor,
        preparation_id=UUID(prepared["id"]),
        source_digest=prepared["source_digest"],
        confirmation_token=prepared["confirmation_token"],
    )
    candidate = repository.renewal_measurement_review(actor, payout_id=payout)
    if predecessor_credit_impaired:
        assert candidate.get("predecessor_credit_impaired") is True
        assert (
            candidate.get("derecognition_blocker")
            == "successor_credit_adjusted_eir_policy_required"
        )
    review = review_body()["review"]
    review.update(
        decision=treatment,
        settlement_consideration=str(remaining),
        settlement_rebate="0.00",
    )
    if treatment == "derecognition":
        review.update(
            new_initial_fair_value=str(principal),
            fair_value_effective_date=f["today"].isoformat(),
            fair_value_basis="Explicit signed fair value independently reviewed at the synthetic renewal date.",
            day_one_difference_rationale="Explicit fair value equals signed settlement plus actual fresh funding.",
        )
    bundle = evidence()
    args = {
        "payout_id": payout,
        "source_digest": candidate["source_digest"],
        "request_id": uuid4(),
        "evidence_id": bundle,
        "review": review,
    }
    retained = repository.retain_renewal_measurement(actor, **args)
    assert repository.retain_renewal_measurement(actor, **args) == retained
    retention_args = args.copy()
    completion = repository.review(actor, payout_id=payout, stage="completion")
    prepared = repository.prepare(
        actor,
        payout_id=payout,
        stage="completion",
        source_digest=completion["source_digest"],
        request_id=uuid4(),
    )["preparation"]
    args = {
        "preparation_id": UUID(prepared["id"]),
        "source_digest": prepared["source_digest"],
        "confirmation_token": prepared["confirmation_token"],
    }
    posted = repository.post(actor, **args) if post_completion else None
    if post_completion:
        assert repository.post(actor, **args) == posted
    return f | {
        "loan_id": new,
        "old_loan_id": old,
        "payout_id": payout,
        "execution_id": execution,
        "disbursement_event_id": disbursement,
        "principal": principal,
        "old_application_id": applied["application_id"],
        "receipt_amount": applied["receipt_amount"],
        "application_period_id": period,
        "actor": actor,
        "wallet_id": wallet,
        "service": service,
        "private_store": store,
        "repository": repository,
        "candidate": candidate,
        "completion": completion,
        "renewal_review": retained,
        "predecessor_risk_review_id": impaired_review,
        "retention_args": retention_args,
        "posting_args": args,
        "posted": posted,
        "measurement_bundle_id": bundle,
        "journal_id": UUID(posted["journal_entry_id"]) if posted else None,
        "release_day": f["today"],
        "schedule_id": schedule,
        "installments": [
            {"due_date": i.due_date, "contractual_amount": i.contractual_amount}
            for i in installments
        ],
    }


@pytest.mark.parametrize(
    "treatment", ["modification_no_derecognition", "derecognition"]
)
def test_current_native_renewal_posts_one_funded_lineage(
    dated_native, monkeypatch, tmp_path, treatment
):
    f = completed_native_renewal(
        dated_native, monkeypatch, tmp_path, treatment=treatment
    )
    conn = f["conn"]
    assert f["completion"]["accounting_asset_id"] == str(
        f["old_loan_id"]
        if treatment == "modification_no_derecognition"
        else f["loan_id"]
    )
    assert conn.execute(
        "SELECT accounting.native_renewal_structural_exact(%s) AS exact",
        (f["journal_id"],),
    ).fetchone()["exact"]
    caller_timezone = conn.execute("SHOW timezone").fetchone()["TimeZone"]
    origin_digests = set()
    try:
        for timezone in ("UTC", "Asia/Manila", "America/New_York"):
            conn.execute("SELECT set_config('timezone',%s,true)", (timezone,))
            origin_digests.add(
                conn.execute(
                    "SELECT encode(sha256(convert_to(accounting.loan_payout_accounting_origin(%s,'completion')::text,'UTF8')),'hex') AS digest",
                    (f["payout_id"],),
                ).fetchone()["digest"]
            )
            assert conn.execute(
                "SELECT exact_posted AND NOT correction_pending AS exact "
                "FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=%s",
                (f["journal_id"],),
            ).fetchone()["exact"]
    finally:
        conn.execute("SELECT set_config('timezone',%s,true)", (caller_timezone,))
    assert len(origin_digests) == 1
    assert not conn.execute(
        "SELECT accounting.native_renewal_prefix_admitted(%s) AS admitted",
        (f["journal_id"],),
    ).fetchone()["admitted"]
    assert (
        conn.execute(
            "SELECT accounting.journal_disclosure_source_status(%s) AS status",
            (f["journal_id"],),
        ).fetchone()["status"]
        == "current"
    )
    assert (
        conn.execute(
            "SELECT coalesce(sum(l.debit-l.credit),0) AS balance FROM accounting.journal_lines l JOIN accounting.journal_entries j ON j.id=l.journal_entry_id "
            "JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' AND l.loan_id=%s AND a.code IN('1100','1120','1190')",
            (f["old_loan_id"],),
        ).fetchone()["balance"]
        == 0
    )
    segment = conn.execute(
        "SELECT accounting.native_regular_segment_origin(%s,%s) AS source",
        (f["loan_id"], f["today"]),
    ).fetchone()["source"]
    assert segment["ready"]
    rate = Decimal(str(segment["anchor"]["daily_eir"]))
    measured_pv = sum(
        item["contractual_amount"] / (1 + rate) ** (item["due_date"] - f["today"]).days
        for item in f["installments"]
    )
    assert abs(
        measured_pv - Decimal(str(segment["anchor"]["initial_gross_carrying_amount"]))
    ) < Decimal("0.01")
    if treatment == "modification_no_derecognition":
        assert rate == Decimal(f["candidate"]["original_daily_eir"])
    with pytest.raises(RuntimeError), conn.transaction():
        decision = conn.execute(
            "SELECT decision_id FROM accounting.native_renewal_measurement_reviews WHERE id=%s",
            (f["renewal_review"]["id"],),
        ).fetchone()["decision_id"]
        conn.execute(
            "SELECT accounting.void_renewal_treatment_decision(%s,%s,%s)",
            (
                decision,
                f["actor_id"],
                "Synthetic source proof revocation must invalidate renewal disclosure",
            ),
        )
        assert (
            conn.execute(
                "SELECT accounting.journal_disclosure_source_status(%s) AS status",
                (f["journal_id"],),
            ).fetchone()["status"]
            != "current"
        )
        raise RuntimeError("Rollback the synthetic treatment revocation")
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    public_directory = os.getenv("SPINA_NATIVE_RENEWAL_PUBLIC_FIXTURE_DIR")
    if public_directory:
        destination = Path(public_directory)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"native-renewal-{treatment}.json").write_text(
            json.dumps(
                {"candidate": f["candidate"], "completion": f["completion"]}, indent=2
            ),
            encoding="utf-8",
        )


def test_completed_renewal_recovery_keeps_actor_and_immutable_request_checks(
    dated_native, monkeypatch, tmp_path
):
    f = completed_native_renewal(dated_native, monkeypatch, tmp_path)
    conn, repository, actor = f["conn"], f["repository"], f["actor"]
    path = f["private_store"].root / f"{UUID(str(f['measurement_bundle_id'])).hex}.bin"
    original = path.read_bytes()
    try:
        path.write_bytes(b"Synthetic private bundle corruption")
        assert (
            repository.retain_renewal_measurement(actor, **f["retention_args"])
            == f["renewal_review"]
        )
        assert repository.post(actor, **f["posting_args"]) == f["posted"]
        with pytest.raises(TreasuryUnavailable), conn.transaction():
            repository.renewal_measurement_review(actor, payout_id=f["payout_id"])
        with pytest.raises(TreasuryUnavailable), conn.transaction():
            repository.retain_renewal_measurement(
                actor, **(f["retention_args"] | {"request_id": uuid4()})
            )
        with pytest.raises(TreasuryConflict), conn.transaction():
            repository.retain_renewal_measurement(
                actor, **(f["retention_args"] | {"source_digest": "0" * 64})
            )
    finally:
        path.write_bytes(original)
    with pytest.raises(TreasuryDenied), conn.transaction():
        conn.execute(
            "DELETE FROM core.role_permissions rp USING core.user_roles ur "
            "WHERE ur.role_id=rp.role_id AND ur.user_id=%s "
            "AND rp.permission_code='accounting.renewal_treatment_decision.manage'",
            (f["actor_id"],),
        )
        repository.retain_renewal_measurement(actor, **f["retention_args"])
    assert (
        conn.execute(
            "SELECT count(*) AS count FROM accounting.native_regular_asset_lineage WHERE payout_id=%s",
            (f["payout_id"],),
        ).fetchone()["count"]
        == 1
    )
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_renewal_private_barrier_and_post_rollback_preserve_exact_preparation(
    dated_native, monkeypatch, tmp_path
):
    f = completed_native_renewal(
        dated_native, monkeypatch, tmp_path, post_completion=False
    )
    conn, repository, actor = f["conn"], f["repository"], f["actor"]

    def retained_counts():
        return conn.execute(
            "SELECT (SELECT count(*) FROM accounting.native_regular_asset_lineage WHERE payout_id=%s) AS lineage,"
            "(SELECT count(*) FROM accounting.loan_payout_accounting_postings WHERE payout_id=%s AND stage='completion') AS audit,"
            "(SELECT count(*) FROM accounting.journal_entries WHERE source_event_key=%s) AS journal",
            (
                f["payout_id"],
                f["payout_id"],
                f"treasury_loan_payout:{f['payout_id']}:completion",
            ),
        ).fetchone()

    empty = {"lineage": 0, "audit": 0, "journal": 0}
    assert retained_counts() == empty
    path = f["private_store"].root / f"{UUID(str(f['measurement_bundle_id'])).hex}.bin"
    original = path.read_bytes()
    try:
        path.write_bytes(b"A changed signed measurement bundle cannot fund a renewal")
        with pytest.raises(TreasuryUnavailable):
            repository.post(actor, **f["posting_args"])
    finally:
        path.write_bytes(original)
    assert retained_counts() == empty
    with (
        pytest.raises(RuntimeError, match="synthetic transaction rollback"),
        conn.transaction(),
    ):
        posted = repository.post(actor, **f["posting_args"])
        assert posted["journal_entry_id"]
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        assert retained_counts() == {"lineage": 1, "audit": 1, "journal": 1}
        raise RuntimeError("synthetic transaction rollback")
    assert retained_counts() == empty
    posted = repository.post(actor, **f["posting_args"])
    assert repository.post(actor, **f["posting_args"]) == posted
    assert retained_counts() == {"lineage": 1, "audit": 1, "journal": 1}
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize(
    "treatment", ["modification_no_derecognition", "derecognition"]
)
def test_renewal_transfers_or_releases_exact_prior_allowance(
    dated_native, monkeypatch, tmp_path, treatment
):
    f = completed_native_renewal(
        dated_native,
        monkeypatch,
        tmp_path,
        treatment=treatment,
        prefix_forecast_multiplier=Decimal("0.9"),
    )
    conn = f["conn"]
    allowance = Decimal(f["candidate"]["old_allowance"])
    assert allowance > 0
    balances = {
        row["loan_id"]: row["allowance"]
        for row in conn.execute(
            "SELECT l.loan_id,sum(l.credit-l.debit) AS allowance FROM accounting.journal_lines l "
            "JOIN accounting.journal_entries j ON j.id=l.journal_entry_id "
            "JOIN accounting.accounts a ON a.id=l.account_id "
            "WHERE j.status='posted' AND a.code='1190' AND l.loan_id=ANY(%s) GROUP BY l.loan_id",
            ([f["old_loan_id"], f["loan_id"]],),
        )
    }
    assert balances[f["old_loan_id"]] == 0
    assert balances.get(f["loan_id"], Decimal(0)) == (
        allowance if treatment == "modification_no_derecognition" else Decimal(0)
    )
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_native_renewal_closes_both_operational_assets_and_preserves_prior_close(
    dated_native, monkeypatch, tmp_path
):
    f = completed_native_renewal(dated_native, monkeypatch, tmp_path, close_prefix=True)
    close_completed_native_renewal(f, monkeypatch)


@pytest.mark.parametrize("successor_stage", ["stage_2_lifetime", "stage_1_12_month"])
def test_current_stage_two_modification_requires_explicit_successor_risk(
    dated_native, monkeypatch, tmp_path, successor_stage
):
    from test_current_credit_risk_review_postgres import REVIEW
    from test_native_credit_risk_assessment_postgres import (
        lifetime_scenarios,
        reviewed_stage,
    )

    f = completed_native_renewal(
        dated_native,
        monkeypatch,
        tmp_path,
        predecessor_stage="stage_2_lifetime",
    )
    conn = f["conn"]
    # The successor's fresh schedule must not turn the continuing Stage 2 asset
    # into generic Stage 1, even though its current contractual DPD is zero.
    with pytest.raises(psycopg.Error) as denied, conn.transaction():
        assess_current_cash_cutoff(f, f["application_period_id"])
    assert denied.value.sqlstate == "23514"
    with conn.cursor() as cursor:
        assert elapsed_period_assessment_repository._has_native_credit_risk_history(
            cursor, f["loan_id"], f["today"]
        )
    lineage = conn.execute(
        "SELECT * FROM accounting.native_regular_asset_lineage WHERE operational_loan_id=%s",
        (f["loan_id"],),
    ).fetchone()
    assert lineage["accounting_asset_id"] == f["old_loan_id"]
    assert "impairment_opening" not in lineage["anchor"]
    assert not f["candidate"]["predecessor_credit_impaired"]
    assert (
        lineage["anchor"]["credit_risk_opening"]["credit_risk_review"]["id"]
        == f["predecessor_risk_review_id"]
    )
    assert Decimal(str(lineage["anchor"]["daily_eir"])) == Decimal(
        str(f["candidate"]["original_daily_eir"])
    )
    # A later old-loan review is not the continuing asset's inherited decision.
    reviewed_stage(f | {"loan_id": f["old_loan_id"]}, "stage_1_12_month")
    context = conn.execute(
        "SELECT accounting.current_credit_risk_review_context(%s,%s) AS value",
        (f["application_period_id"], f["loan_id"]),
    ).fetchone()["value"]
    assert context["ready"], context["blockers"]
    assert context["prior_review"] is None
    assert context["inherited_review"]["stage_label"] == "stage_2_lifetime"
    assert context["inherited_review"]["id"] == f["predecessor_risk_review_id"]
    assert context["inherited_review"]["loan_id"] == str(f["old_loan_id"])
    public_directory = os.getenv("SPINA_NATIVE_RENEWAL_PUBLIC_FIXTURE_DIR")
    if public_directory:
        from gilbic_backend.current_credit_risk_review_repository import public_context

        (
            Path(public_directory) / "native-renewal-inherited-stage-two-context.json"
        ).write_text(
            json.dumps(public_context(context), indent=2, default=str), encoding="utf-8"
        )
    explicit = REVIEW | {
        "stage_label": successor_stage,
        "default_label": False,
        "recovery_label": "none",
        "review_note": "Actual current borrower evidence supports this explicit reviewed continuing-asset risk decision.",
    }
    args = (
        f["application_period_id"],
        f["loan_id"],
        UUID(f["candidate"]["book_id"]),
        context["source_digest"],
        Jsonb(explicit),
        f["actor_id"],
    )
    command = (
        "SELECT accounting.retain_current_credit_risk_review(%s,%s,%s,%s,%s,%s) AS id"
    )
    risk_id = conn.execute(command, args).fetchone()["id"]
    assert conn.execute(command, args).fetchone()["id"] == risk_id
    retained = conn.execute(
        "SELECT * FROM accounting.ecl_credit_risk_label_reviews WHERE id=%s", (risk_id,)
    ).fetchone()
    assert retained["supersedes_review_id"] == f["predecessor_risk_review_id"]
    assert retained["loan_id"] == f["loan_id"] and retained["review_version"] == 1
    source = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
        (f["application_period_id"], f["loan_id"]),
    ).fetchone()["value"]
    assert source["ready"], source["blockers"]
    prepared = conn.execute(
        "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
        (
            f["application_period_id"],
            f["loan_id"],
            f["actor_id"],
            source["source_digest"],
            risk_id,
            Jsonb(lifetime_scenarios(f, source)),
            explicit["review_note"],
        ),
    ).fetchone()["id"]
    assessment = conn.execute(
        "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (prepared,),
    ).fetchone()
    measurement = assessment["measurement_snapshot"]
    assert measurement["risk_review"]["stage_label"] == successor_stage
    assert measurement["loss_horizon"] == (
        "lifetime" if successor_stage == "stage_2_lifetime" else "12_month"
    )
    assert "credit_impaired_interest" not in measurement
    conn.execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (prepared, f["actor_id"], assessment["confirmation_digest"]),
    )
    assert conn.execute(
        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
        (f["application_period_id"], f["loan_id"]),
    ).fetchone()["exact"]
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize(
    "successor_stage", ["stage_3_credit_impaired", "stage_1_12_month"]
)
def test_current_impaired_modification_retains_same_asset_risk_boundary(
    dated_native, monkeypatch, tmp_path, successor_stage
):
    f = completed_native_renewal(
        dated_native, monkeypatch, tmp_path, predecessor_credit_impaired=True
    )
    lineage = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.native_regular_asset_lineage WHERE operational_loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()
    )
    opening = lineage["anchor"]["impairment_opening"]
    assert lineage["accounting_asset_id"] == f["old_loan_id"]
    assert opening["credit_risk_review"]["id"] == f["predecessor_risk_review_id"]
    assert opening["credit_risk_review"]["stage_label"] == "stage_3_credit_impaired"
    assert opening["anchor_date"] == f["today"].isoformat()
    assert opening["net_interest_established"] is False
    assert Decimal(opening["boundary"]["allowance_unwind"]) == 0
    assert Decimal(opening["boundary"]["impairment_adjustment"]) == 0
    assert Decimal(opening["initial_allowance"]) == Decimal(
        f["candidate"]["old_allowance"]
    )
    assert (
        f["conn"]
        .execute(
            "SELECT exact_posted AND NOT correction_pending AS exact FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=%s",
            (f["journal_id"],),
        )
        .fetchone()["exact"]
    )
    # A new operational id cannot silently reset the continuing asset to Stage 1.
    with pytest.raises(psycopg.Error) as denied, f["conn"].transaction():
        assess_current_cash_cutoff(f, f["application_period_id"])
    assert denied.value.sqlstate == "23514"
    from test_native_credit_risk_assessment_postgres import (
        lifetime_scenarios,
        reviewed_stage,
    )

    # An explicit Stage 2 label alone is not an objective cure of the inherited asset.
    with pytest.raises(psycopg.Error) as uncured, f["conn"].transaction():
        uncured_id = reviewed_stage(f, "stage_2_lifetime")
        uncured_source = (
            f["conn"]
            .execute(
                "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
                (f["application_period_id"], f["loan_id"]),
            )
            .fetchone()["value"]
        )
        f["conn"].execute(
            "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s,%s,%s)",
            (
                f["application_period_id"],
                f["loan_id"],
                f["actor_id"],
                uncured_source["source_digest"],
                uncured_id,
                Jsonb(lifetime_scenarios(f, uncured_source)),
                "A new label without objective cure evidence must not reset the asset.",
            ),
        )
    assert uncured.value.sqlstate == "23514"
    assert "cure" in str(uncured.value).lower()

    # A later actual review of the old operational record is not a rewrite of
    # the exact review/version retained by the already completed renewal.
    reviewed_stage(f | {"loan_id": f["old_loan_id"]}, "stage_2_lifetime")
    assert (
        f["conn"]
        .execute(
            "SELECT exact_posted AND NOT correction_pending AS exact FROM accounting.loan_payout_accounting_posting_status WHERE journal_entry_id=%s",
            (f["journal_id"],),
        )
        .fetchone()["exact"]
    )
    if successor_stage == "stage_3_credit_impaired":
        risk_id = reviewed_stage(f, successor_stage)
    else:
        from test_current_credit_risk_review_postgres import REVIEW

        risk_source = (
            f["conn"]
            .execute(
                "SELECT accounting.current_credit_risk_review_context(%s,%s) AS value",
                (f["application_period_id"], f["loan_id"]),
            )
            .fetchone()["value"]
        )
        assert risk_source["ready"], risk_source["blockers"]
        assert risk_source["prior_review"] is None
        assert risk_source["inherited_review"]["loan_id"] == str(f["old_loan_id"])
        assert risk_source["inherited_review"]["id"] == f["predecessor_risk_review_id"]
        public_directory = os.environ.get("SPINA_NATIVE_RENEWAL_PUBLIC_FIXTURE_DIR")
        if public_directory:
            from gilbic_backend.current_credit_risk_review_repository import (
                public_context,
            )

            (
                Path(public_directory) / "native-renewal-inherited-risk-context.json"
            ).write_text(
                json.dumps(public_context(risk_source), indent=2, default=str),
                encoding="utf-8",
            )
        cure = REVIEW | {
            "stage_label": successor_stage,
            "recovery_label": "cured",
            "evidence_reference": "SYNTHETIC-OBJECTIVE-CURE-" + uuid4().hex,
            "review_note": "Verified subsequent borrower event objectively supports the explicitly reviewed current cure.",
        }
        args = (
            f["application_period_id"],
            f["loan_id"],
            UUID(f["candidate"]["book_id"]),
            risk_source["source_digest"],
            Jsonb(cure),
            f["actor_id"],
        )
        statement = "SELECT accounting.retain_current_credit_risk_review(%s,%s,%s,%s,%s,%s) AS id"
        risk_id = f["conn"].execute(statement, args).fetchone()["id"]
        assert f["conn"].execute(statement, args).fetchone()["id"] == risk_id
        current_review = (
            f["conn"]
            .execute(
                "SELECT loan_id,review_version,supersedes_review_id FROM accounting.ecl_credit_risk_label_reviews WHERE id=%s",
                (risk_id,),
            )
            .fetchone()
        )
        assert current_review["loan_id"] == f["loan_id"]
        assert current_review["review_version"] == 1
        assert current_review["supersedes_review_id"] == f["predecessor_risk_review_id"]
    source = (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
            (f["application_period_id"], f["loan_id"]),
        )
        .fetchone()["value"]
    )
    assert source["ready"], source["blockers"]
    preparation = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
            (
                f["application_period_id"],
                f["loan_id"],
                f["actor_id"],
                source["source_digest"],
                risk_id,
                Jsonb(lifetime_scenarios(f, source)),
                "Continuing impaired accounting asset retains its actual current Stage 3 evidence.",
            ),
        )
        .fetchone()["id"]
    )
    measured = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
            (preparation,),
        )
        .fetchone()
    )
    assert (
        measured["measurement_snapshot"]["risk_review"]["stage_label"]
        == successor_stage
    )
    if successor_stage == "stage_1_12_month":
        assert (
            measured["measurement_snapshot"]["risk_review"]["recovery_label"] == "cured"
        )
    assert (
        Decimal(
            measured["measurement_snapshot"]["credit_impaired_interest"][
                "allowance_unwind"
            ]
        )
        == 0
    )
    f["conn"].execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (preparation, f["actor_id"], measured["confirmation_digest"]),
    )
    old_source = (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
            (f["application_period_id"], f["old_loan_id"]),
        )
        .fetchone()["value"]
    )
    assert old_source["ready"], old_source["blockers"]
    old_risk = {
        "as_of_date": f["today"].isoformat(),
        "primary_evidence_basis": "exact_renewal",
        "evidence_reference": f["renewal_review"]["id"],
        "review_note": "Exact completed impairment boundary leaves zero old operational exposure and no repeated unwind.",
    }
    old_prepared = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
            (
                f["application_period_id"],
                f["old_loan_id"],
                f["actor_id"],
                old_source["source_digest"],
                Jsonb(old_risk),
                Jsonb([]),
                old_risk["review_note"],
            ),
        )
        .fetchone()["id"]
    )
    old_measurement = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
            (old_prepared,),
        )
        .fetchone()
    )
    assert old_measurement["measurement_snapshot"]["ecl_amount"] == 0
    assert old_measurement["measurement_snapshot"]["allowance_delta"] == 0
    assert "credit_impaired_interest" not in old_measurement["measurement_snapshot"]
    f["conn"].execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (old_prepared, f["actor_id"], old_measurement["confirmation_digest"]),
    )
    assert (
        f["conn"]
        .execute(
            "SELECT eir_journal_entry_id IS NULL AND allowance_journal_entry_id IS NULL AS no_repeated_journal "
            "FROM accounting.loan_elapsed_assessment_postings WHERE preparation_id=%s",
            (old_prepared,),
        )
        .fetchone()["no_repeated_journal"]
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    public_directory = os.getenv("SPINA_NATIVE_RENEWAL_PUBLIC_FIXTURE_DIR")
    if public_directory:
        (
            Path(public_directory) / "native-renewal-impaired-modification.json"
        ).write_text(
            json.dumps(
                {"candidate": f["candidate"], "completion": f["completion"]}, indent=2
            ),
            encoding="utf-8",
        )


def test_current_impaired_review_change_blocks_prepared_renewal(
    dated_native, monkeypatch, tmp_path
):
    from test_native_credit_risk_assessment_postgres import reviewed_stage

    f = completed_native_renewal(
        dated_native,
        monkeypatch,
        tmp_path,
        predecessor_credit_impaired=True,
        post_completion=False,
    )
    reviewed_stage(f | {"loan_id": f["old_loan_id"]}, "stage_2_lifetime")
    with (
        pytest.raises((TreasuryConflict, TreasuryUnavailable)),
        f["conn"].transaction(),
    ):
        f["repository"].post(f["actor"], **f["posting_args"])
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.native_regular_asset_lineage WHERE payout_id=%s",
            (f["payout_id"],),
        )
        .fetchone()["n"]
        == 0
    )


def test_current_impaired_derecognition_requires_supported_initial_credit_policy(
    dated_native, monkeypatch, tmp_path
):
    with (
        pytest.raises(TreasuryConflict, match="credit-adjusted EIR"),
        dated_native["conn"].transaction(),
    ):
        completed_native_renewal(
            dated_native,
            monkeypatch,
            tmp_path,
            treatment="derecognition",
            predecessor_credit_impaired=True,
        )
    assert (
        dated_native["conn"]
        .execute("SELECT count(*) AS n FROM accounting.native_regular_asset_lineage")
        .fetchone()["n"]
        == 0
    )


def test_current_impaired_inherited_opening_day_cash_interval(dated_native):
    # Pure interval arithmetic; this is not a backdated or future source claim.
    day = dated_native["today"]
    event = {
        "cash_date": day.isoformat(),
        "cash": "100.00",
        "full_payoff": False,
        "target_allowance": "250.00",
        "opening_day_cash": True,
    }
    statement = "SELECT accounting.native_credit_impaired_chain(%s,1000,300,0.01,%s,%s,%s) AS value"
    args = (day, day + timedelta(days=1), day + timedelta(days=30), Jsonb([event]))
    result = dated_native["conn"].execute(statement, args).fetchone()["value"]
    assert Decimal(str(result["gross_interest"])) == 9
    assert Decimal(str(result["allowance_unwind"])) == Decimal("2.50")
    assert Decimal(str(result["virtual_impairment_adjustment"])) == -50
    assert Decimal(str(result["gross_after"])) == 909
    assert Decimal(str(result["virtual_allowance_before_final_review"])) == Decimal(
        "252.50"
    )
    with pytest.raises(psycopg.Error), dated_native["conn"].transaction():
        dated_native["conn"].execute(
            statement, args[:-1] + (Jsonb([event | {"opening_day_cash": False}]),)
        )


def test_current_impaired_boundary_retains_exact_review_row(dated_native):
    from test_native_credit_risk_assessment_postgres import reviewed_stage

    f = dated_native
    # Match the protected boundary's UTC serialization of the same timestamp.
    f["conn"].execute("SET LOCAL timezone='UTC'")
    risk_id = reviewed_stage(f, "stage_3_credit_impaired")
    raw = (
        f["conn"]
        .execute(
            "SELECT to_jsonb(r) AS value FROM accounting.ecl_credit_risk_label_reviews r WHERE id=%s",
            (risk_id,),
        )
        .fetchone()["value"]
    )
    reviewed_stage(f, "stage_2_lifetime")
    # A calculator-only boundary: no dated fiscal posting or source authority
    # is asserted. Measurement annotations must not become retained row bytes.
    boundary = {
        "old_allowance": "0.00",
        "old_gross_carrying": "1000.00",
        "original_daily_eir": "0.01",
        "rollforward": {
            "anchor": {"contractual_due_date": f["today"].isoformat()},
            "cumulative_interest": "0.00",
            "cash_claims": [],
        },
        "prefixes": [
            {
                "id": str(uuid4()),
                "as_of_date": f["today"].isoformat(),
                "source_snapshot": {
                    "gross_carrying_amount": "1000.00",
                    "eir": {"cumulative_interest": "0.00"},
                },
                "measurement_snapshot": {
                    "ecl_amount": "0.00",
                    "risk_review": raw | {"as_of_date": f["today"].isoformat()},
                },
            }
        ],
    }
    value = (
        f["conn"]
        .execute(
            "SELECT accounting.native_renewal_impairment(%s,%s,%s) AS value",
            (f["loan_id"], f["today"], Jsonb(boundary)),
        )
        .fetchone()["value"]
    )
    assert value["predecessor_impairment_review"] == raw


def close_completed_native_renewal(f, monkeypatch):
    """Close both operational dimensions without committing the caller's transaction."""
    conn, period = f["conn"], f["application_period_id"]
    retain_application_tax(f, period, f["old_application_id"])
    retain_native_dst(
        f,
        disbursement_event_id=f["disbursement_event_id"],
        principal=f["principal"],
        period_id=period,
    )
    old = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
        (period, f["old_loan_id"]),
    ).fetchone()["source"]
    assert old["ready"], old["blockers"]
    assert old["snapshot"]["settled_by_exact_renewal"]
    monkeypatch.setattr(
        elapsed_period_assessment_repository,
        "_candidate_connection",
        lambda: nullcontext(conn),
    )
    assessments = PostgresElapsedPeriodAssessmentRepository()
    prepared = assessments.prepare_renewed(
        period_id=period,
        loan_id=f["old_loan_id"],
        expected_book_id=UUID(f["candidate"]["book_id"]),
        source_digest=old["source_digest"],
        renewal_review_id=UUID(f["renewal_review"]["id"]),
        review_rationale="Exact reviewed renewal has zero old-loan exposure after its protected completion.",
        actor_user_id=f["actor_id"],
    )
    assert prepared["settled_by_exact_renewal"]
    assert prepared["renewal_review_id"] == f["renewal_review"]["id"]
    assert prepared["scenario_count"] == 0
    confirmation = {
        "preparation_id": UUID(prepared["preparation_id"]),
        "expected_book_id": UUID(f["candidate"]["book_id"]),
        "confirmation_digest": prepared["confirmation_digest"],
        "actor_user_id": f["actor_id"],
    }
    assert assessments.confirm(**confirmation) == assessments.confirm(**confirmation)
    assess_current_cash_cutoff(f, period)
    retained_cash_policy(f, period)
    close_period(f, period)
    pack = report(f, period)
    assert pack["financial_position"]["balanced"]
    cash = pack["reporting_supplement"]["cash_flows"]
    assert (
        cash["reconciled"]
        and Decimal(cash["closing_cash"]) == f["receipt_amount"] - 2002
    )
    for loan in (f["old_loan_id"], f["loan_id"]):
        assert conn.execute(
            "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
            (period, loan),
        ).fetchone()["exact"]
    assert conn.execute(
        "SELECT accounting.period_review_manifest_state(%s) AS value",
        (f["period_id"],),
    ).fetchone()["value"]["current"]
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
