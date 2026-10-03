"""Real protected loan source plus an explicitly disposable Treasury database."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from first_loan_approval_fixtures import reviewed_setup
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from gilbic_backend.treasury_models import (
    AccountConfigure,
    DisbursementRecord,
    LoanPayoutPrepare,
    LoanPayoutPreview,
    LoanPayoutRecipientConfirm,
)
from gilbic_backend.treasury_repository import TreasuryService
from test_first_loan_postgres import private_fixture_configuration, ready  # noqa: F401
from treasury_test_support import actor, connect, evidence, version


@pytest.fixture
def payout_case(monkeypatch, tmp_path):
    with connect() as conn:
        _, repository, case = reviewed_setup(conn, monkeypatch)
        approved, release = ready(repository, case)
        collector = actor(conn, "collector")
        area = "SYNTHETIC-PAYOUT-" + uuid4().hex
        # Route is operational metadata, not a change to the signed borrower packet.
        conn.execute(
            "update lending.clients set area=%s where id=%s", (area, case["client"])
        )
        conn.execute(
            "insert into lending.collector_area_assignments(collector_user_id,area) values(%s,%s)",
            (collector.user_id, area),
        )
        conn.commit()
        owner = AccountContext(
            case["actor"],
            case["actor"],
            "synthetic",
            None,
            "Synthetic releasing owner",
            "active",
            ("management",),
            (),
            True,
            case["device"],
        )
        monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(owner.user_id))
        monkeypatch.setenv("SPINA_TREASURY_ENABLED", "true")
        service = TreasuryService(
            connection_factory=connect,
            store=PrivateEvidenceStore(tmp_path / "treasury-private"),
        )
        account_id, context_id = uuid4(), uuid4()
        service.execute(
            owner,
            AccountConfigure(
                action="account_configure",
                request_id=uuid4(),
                account_id=account_id,
                expected_version=0,
                ledger_context_id=context_id,
                context="synthetic",
                kind="gcash",
                alias="Synthetic payout wallet",
                ownership="synthetic",
                custodian_user_id=owner.user_id,
            ),
        )
        yield {
            "service": service,
            "owner": owner,
            "account_id": account_id,
            "context_id": context_id,
            "collector": collector,
            "client_id": case["client"],
            "approved": approved,
            "loan_id": UUID(approved["loan_id"]),
            "release": release,
            "repository": repository,
            "connection": conn,
        }


def source_input(f, **changes):
    values = {
        "account_id": f["account_id"],
        "expected_version": version(f),
        "source_kind": "first_loan",
        "source_id": f["loan_id"],
        "recipient_reference": "SYNTHETIC-RECIPIENT-001",
        "authorization_id": f["release"]["authorization_id"],
        "packet_hash": f["approved"]["packet_hash"],
        "contract_evidence_reference": f["release"]["contract_evidence_reference"],
    }
    values.update(changes)
    return values


def preview(f, **changes):
    operation = getattr(f["service"], "loan_payout_preview", None)
    assert operation is not None, "Protected source-bound payout preview is required"
    return operation(f["owner"], LoanPayoutPreview(**source_input(f, **changes)))


def prepare(f, **changes):
    reviewed = preview(f, **changes)
    command = LoanPayoutPrepare(
        action="loan_payout_prepare",
        request_id=uuid4(),
        source_digest=reviewed["source_digest"],
        **source_input(f, **changes),
    )
    return command, f["service"].execute(f["owner"], command)


@pytest.mark.parametrize("destination", ["collector", "borrower"])
def test_preparation_binds_exact_net_and_real_destination_without_money_or_loan_activation(
    payout_case, destination
):
    f = payout_case
    reviewed = preview(f, destination=destination)
    assert reviewed["amount"] == "1000.00"
    assert reviewed["destination"] == destination
    assert reviewed["payee_id"] == str(
        f["collector"].user_id if destination == "collector" else f["client_id"]
    )
    command, saved = prepare(f, destination=destination)
    assert saved["result"]["payout"]["status"] == "prepared"
    assert f["service"].execute(f["owner"], command) == saved
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 0
        )
        loan = conn.execute(
            "select status,date_released from lending.loans where id=%s",
            (f["loan_id"],),
        ).fetchone()
        assert loan == {"status": "approved", "date_released": None}
        assert (
            conn.execute(
                "select count(*) as n from lending.first_loan_releases where loan_id=%s",
                (f["loan_id"],),
            ).fetchone()["n"]
            == 0
        )


def test_default_collector_requires_current_assignment_and_changed_assignment_invalidates_review(
    payout_case,
):
    f = payout_case
    reviewed = preview(f)
    with connect() as conn:
        conn.execute(
            "update lending.collector_area_assignments set is_active=false where collector_user_id=%s",
            (f["collector"].user_id,),
        )
    with pytest.raises(TreasuryConflict):
        preview(f)
    with pytest.raises(TreasuryConflict):
        f["service"].execute(
            f["owner"],
            LoanPayoutPrepare(
                action="loan_payout_prepare",
                request_id=uuid4(),
                source_digest=reviewed["source_digest"],
                **source_input(f),
            ),
        )
    assert preview(f, destination="borrower")["payee_id"] == str(f["client_id"])


def test_two_destinations_cannot_prepare_two_active_payouts_for_the_same_source(
    payout_case,
):
    f = payout_case
    prepare(f)
    with pytest.raises(TreasuryConflict):
        prepare(f, destination="borrower")


def test_revoked_management_authorization_blocks_new_and_replayed_payout(payout_case):
    f = payout_case
    command, _ = prepare(f)
    f["repository"].revoke_release(
        actor_user_id=f["owner"].user_id,
        registered_device_id=f["owner"].registered_device_id,
        loan_id=f["loan_id"],
        authorization_id=f["release"]["authorization_id"],
        request_id=uuid4(),
        reason="Synthetic revoked approval",
    )
    f["connection"].commit()
    with pytest.raises(TreasuryConflict):
        f["service"].execute(f["owner"], command)


def debit(f, prepared, **changes):
    payout = prepared["result"]["payout"]
    values = {
        "action": "disbursement_record",
        "request_id": uuid4(),
        "account_id": f["account_id"],
        "expected_version": version(f),
        "amount": "1000.00",
        "provider": "gcash",
        "reference": "SYNTHETIC-" + uuid4().hex,
        "effective_at": datetime.now(timezone.utc) - timedelta(seconds=2),
        "evidence_id": evidence(f),
        "recipient_attestation": "Verified actual outgoing debit to the exact reviewed payout recipient.",
        "purpose": "loan_release",
        "source_id": UUID(payout["id"]),
        "source_version": payout["version"],
        "payee_id": f["collector"].user_id
        if payout["destination"] == "collector"
        else f["client_id"],
        "reason": "Synthetic loan payout debit",
    }
    values.update(changes)
    command = DisbursementRecord(**values)
    return command, f["service"].execute(f["owner"], command)


def confirm(f, payout_id, payout_version=2, **changes):
    values = {
        "action": "loan_payout_recipient_confirm",
        "request_id": uuid4(),
        "account_id": f["account_id"],
        "expected_version": version(f),
        "payout_id": payout_id,
        "payout_version": payout_version,
        "evidence_id": evidence(f),
        "reviewed_amount": "1000.00",
        "received": True,
        "acknowledged_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        "recipient_attestation": "Independent receipt from the exact named payout recipient was verified.",
    }
    values.update(changes)
    command = LoanPayoutRecipientConfirm(**values)
    return command, f["service"].execute(f["owner"], command)


@pytest.mark.parametrize("destination", ["collector", "borrower"])
def test_verified_debit_and_recipient_confirmation_do_not_activate_or_debit_again(
    payout_case, destination
):
    f = payout_case
    _, prepared = prepare(f, destination=destination)
    command, result = debit(f, prepared, destination_confirmed=True)
    assert result["result"]["source_link"]["status"] == "funded_pending_recipient"
    assert result["result"]["event"]["status"] == "debited_destination_unconfirmed"
    assert f["service"].execute(f["owner"], command) == result
    acknowledgment, received = confirm(f, prepared["target_id"])
    assert received["result"]["payout"]["status"] == "recipient_confirmed"
    assert (
        received["result"]["payout"]["payload"]["borrower_handover_status"] == "pending"
    )
    assert f["service"].execute(f["owner"], acknowledgment) == received
    with connect() as conn:
        assert conn.execute(
            "select sum(amount) as amount,count(*) as n from treasury.events where account_id=%s",
            (f["account_id"],),
        ).fetchone() == {"amount": 1000, "n": 1}
        assert (
            conn.execute(
                "select status from lending.loans where id=%s", (f["loan_id"],)
            ).fetchone()["status"]
            == "approved"
        )


@pytest.mark.parametrize("change", ["wrong_payee", "wrong_amount", "stale_version"])
def test_failed_loan_source_link_preserves_actual_debit_without_funding_the_loan(
    payout_case, change
):
    f = payout_case
    _, prepared = prepare(f)
    changes = {
        "wrong_payee": {"payee_id": uuid4()},
        "wrong_amount": {"amount": "999.00"},
        "stale_version": {"source_version": 2},
    }[change]
    _, result = debit(f, prepared, **changes)
    assert result["result"]["source_link"]["status"] == "blocked"
    with connect() as conn:
        row = conn.execute(
            "select status,event_id from treasury.loan_payouts where id=%s",
            (prepared["target_id"],),
        ).fetchone()
        assert row == {"status": "prepared", "event_id": None}
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )


@pytest.mark.parametrize("source_file", ["packet", "contract"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_unavailable_signed_source_file_preserves_observed_debit(
    payout_case, source_file, damage
):
    f = payout_case
    _, prepared = prepare(f)
    with connect() as conn:
        key = (
            conn.execute(
                "select storage_key from lending.first_loan_packet_documents where loan_id=%s",
                (f["loan_id"],),
            ).fetchone()["storage_key"]
            if source_file == "packet"
            else conn.execute(
                "select request_id from lending.office_review_evidence where id=%s",
                (f["release"]["contract_evidence_reference"].split(":")[1],),
            ).fetchone()["request_id"]
        )
    path = PrivateEvidenceStore().root / f"{key.hex}.bin"
    if damage == "missing":
        path.unlink()
    else:
        content = path.read_bytes()
        path.write_bytes(bytes([content[0] ^ 1]) + content[1:])
    command, saved = debit(f, prepared)
    assert saved["result"]["source_link"]["status"] == "blocked"
    assert (
        saved["result"]["source_link"]["requested_payout_id"] == prepared["target_id"]
    )
    assert f["service"].execute(f["owner"], command) == saved
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )
        assert conn.execute(
            "select status,event_id from treasury.loan_payouts where id=%s",
            (prepared["target_id"],),
        ).fetchone() == {"status": "prepared", "event_id": None}
        assert (
            conn.execute(
                "select status from lending.loans where id=%s", (f["loan_id"],)
            ).fetchone()["status"]
            == "approved"
        )


def test_second_real_debit_does_not_fund_the_same_payout_twice(payout_case):
    f = payout_case
    _, prepared = prepare(f)
    _, first = debit(f, prepared)
    _, second = debit(f, prepared)
    assert first["result"]["source_link"]["status"] == "funded_pending_recipient"
    assert second["result"]["source_link"]["status"] == "blocked"
    with connect() as conn:
        assert (
            str(
                conn.execute(
                    "select event_id from treasury.loan_payouts where id=%s",
                    (prepared["target_id"],),
                ).fetchone()["event_id"]
            )
            == first["target_id"]
        )
        assert (
            conn.execute(
                "select count(*) as n from treasury.source_links where source_kind='loan_payout_funding' and source_id=%s",
                (prepared["target_id"],),
            ).fetchone()["n"]
            == 1
        )


@pytest.mark.parametrize("change", ["no_debit", "wrong_amount", "backdated", "future"])
def test_unfunded_or_mismatched_recipient_confirmation_cannot_advance(
    payout_case, change
):
    f = payout_case
    _, prepared = prepare(f)
    current_version = 1
    if change != "no_debit":
        debit(f, prepared)
        current_version = 2
    changes = {
        "no_debit": {},
        "wrong_amount": {"reviewed_amount": "999.00"},
        "backdated": {
            "acknowledged_at": datetime.now(timezone.utc) - timedelta(days=1)
        },
        "future": {"acknowledged_at": datetime.now(timezone.utc) + timedelta(days=1)},
    }[change]
    with pytest.raises(TreasuryConflict):
        confirm(f, prepared["target_id"], current_version, **changes)


@pytest.mark.parametrize(
    "destination,method,revoked_recipient_device",
    [
        ("collector", "cash", False),
        ("collector", "gcash", False),
        ("borrower", "gcash", False),
        ("collector", "cash", True),
    ],
)
def test_protected_first_loan_completion_uses_actual_borrower_receipt_and_one_debit(
    payout_case, destination, method, revoked_recipient_device
):
    from gilbic_backend.treasury_models import COMMAND_ADAPTER

    f = payout_case
    _, prepared = prepare(f, destination=destination)
    debit(f, prepared)
    confirm(f, prepared["target_id"])
    command = COMMAND_ADAPTER.validate_python(
        {
            "action": "loan_payout_first_loan_complete",
            "request_id": uuid4(),
            "account_id": f["account_id"],
            "expected_version": version(f),
            "payout_id": prepared["target_id"],
            "payout_version": 3,
            "evidence_id": evidence(f),
            "reviewed_amount": "1000.00",
            "borrower_confirmed": True,
            "receipt_method": method,
            "acknowledged_at": datetime.now(timezone.utc),
            "borrower_attestation": "Office witnessed the named borrower acknowledge the full net proceeds with this signed receipt.",
        }
    )
    if revoked_recipient_device:
        from dataclasses import replace

        current_device = uuid4()
        with connect() as conn:
            conn.execute(
                "insert into core.devices(id,user_id,device_identifier_hash,platform) values(%s,%s,%s,'web')",
                (current_device, f["owner"].user_id, uuid4().hex),
            )
            conn.execute(
                "update core.devices set status='revoked' where id=%s",
                (f["owner"].registered_device_id,),
            )
        current_owner = replace(f["owner"], registered_device_id=current_device)
        with pytest.raises(TreasuryDenied):
            f["service"].execute(current_owner, command)
        with connect() as conn:
            assert (
                conn.execute(
                    "select status from lending.loans where id=%s", (f["loan_id"],)
                ).fetchone()["status"]
                == "approved"
            )
            assert (
                conn.execute(
                    "select count(*) as n from treasury.events where account_id=%s",
                    (f["account_id"],),
                ).fetchone()["n"]
                == 1
            )
        return
    result = f["service"].execute(f["owner"], command)
    assert result["result"]["payout"]["status"] == "completed"
    assert f["service"].execute(f["owner"], command) == result
    with connect() as conn:
        release = conn.execute(
            "select * from lending.first_loan_releases where loan_id=%s",
            (f["loan_id"],),
        ).fetchone()
        assert release["funding_payout_id"] == UUID(prepared["target_id"])
        assert release["cash_evidence_reference"] is None
        assert release["cash_amount"] is None
        assert release["receipt"]["actual_proceeds_received"] == "1000.00"
        assert release["receipt"]["receipt_method"] == method
        assert "actual_cash_received" not in release["receipt"]
        assert (
            conn.execute(
                "select status from lending.loans where id=%s", (f["loan_id"],)
            ).fetchone()["status"]
            == "active"
        )
        assert (
            conn.execute(
                "select count(*) as n from lending.loan_contract_schedules where loan_id=%s",
                (f["loan_id"],),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "select count(*) as n from lending.first_loan_credential_intents where loan_id=%s",
                (f["loan_id"],),
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
        assert (
            conn.execute(
                "select funding_account_system_key from lending.loan_disbursement_events where loan_id=%s",
                (f["loan_id"],),
            ).fetchone()["funding_account_system_key"]
            == "cash_bank_gcash"
        )


def test_active_payout_blocks_competing_legacy_cash_release(payout_case):
    from gilbic_backend.first_loan_repository import FirstLoanConflict

    f = payout_case
    prepare(f)
    with pytest.raises(FirstLoanConflict, match="payout"):
        f["repository"].release(**f["release"])


@pytest.fixture
def renewal_payout_case(payout_case):
    f = payout_case
    with connect() as conn:
        borrower = actor(conn, "client")
        conn.execute(
            "update lending.clients set user_id=%s where id=%s",
            (borrower.user_id, f["client_id"]),
        )
        ids = [uuid4(), uuid4(), uuid4()]
        old, new, request = ids
        for loan_id, status, number in ((old, "paid", "OLD"), (new, "active", "NEW")):
            conn.execute(
                """insert into lending.loans(id,loan_number,client_id,loan_type_id,principal,daily_amount,
                date_released,due_date,status,created_by_user_id)
                select %s,%s,client_id,loan_type_id,3000,100,(clock_timestamp() at time zone 'Asia/Manila')::date,
                (clock_timestamp() at time zone 'Asia/Manila')::date+30,%s,%s from lending.loans where id=%s""",
                (
                    loan_id,
                    "SYNTHETIC-" + number + uuid4().hex,
                    status,
                    f["owner"].user_id,
                    f["loan_id"],
                ),
            )
        conn.execute(
            "insert into lending.loan_collection_state(loan_id,remaining_balance) values(%s,0),(%s,3000)",
            (old, new),
        )
        conn.execute(
            """insert into lending.client_renewal_requests(id,client_id,loan_id,requested_by_user_id,
            requested_amount,status,approved_principal,client_decision,client_decided_at,signer_readiness_status,reviewed_by_user_id,reviewed_at)
            values(%s,%s,%s,%s,3000,'approved',3000,'accepted',now(),'ready',%s,now())""",
            (request, f["client_id"], old, borrower.user_id, f["owner"].user_id),
        )
        conn.execute(
            """insert into lending.renewal_required_signers(renewal_request_id,party_role,full_name,
            user_id,government_id_verified_at,selfie_verified_at,signed_at)
            values(%s,'borrower','Synthetic Borrower',%s,now(),now(),now())""",
            (request, borrower.user_id),
        )
        disbursement = conn.execute(
            """select accounting.record_loan_disbursement_evidence(%s,%s,'renewal_release',
            (clock_timestamp() at time zone 'Asia/Manila')::date,clock_timestamp(),1000,2000,0,
            'cash_bank_gcash',%s,'Synthetic renewal payout fixture') as id""",
            (new, f["owner"].user_id, uuid4().hex),
        ).fetchone()["id"]
        execution = conn.execute(
            """select accounting.record_loan_renewal_execution_evidence(%s,%s,%s,%s,
            (clock_timestamp() at time zone 'Asia/Manila')::date,clock_timestamp(),2000,%s,
            'Synthetic renewal payout fixture',%s) as id""",
            (old, new, disbursement, f["owner"].user_id, uuid4().hex, request),
        ).fetchone()["id"]
    return {
        **f,
        "renewal_id": request,
        "new_loan_id": new,
        "old_loan_id": old,
        "execution_id": execution,
        "disbursement_id": disbursement,
        "borrower": borrower,
    }


def renewal_input(f, **changes):
    return source_input(
        f,
        source_kind="renewal",
        source_id=f["renewal_id"],
        authorization_id=None,
        packet_hash=None,
        contract_evidence_reference=None,
        **changes,
    )


@pytest.mark.parametrize("destination", ["collector", "borrower"])
def test_renewal_preview_binds_authoritative_net_offset_and_destination(
    renewal_payout_case, destination
):
    f = renewal_payout_case
    reviewed = f["service"].loan_payout_preview(
        f["owner"], LoanPayoutPreview(**renewal_input(f, destination=destination))
    )
    assert reviewed["amount"] == "1000.00"
    assert reviewed["source_snapshot"]["source"]["offset_amount"] == "2000.00"
    assert reviewed["source_snapshot"]["source"]["loan_id"] == str(f["new_loan_id"])
    assert reviewed["source_snapshot"]["source"]["execution_id"] == str(
        f["execution_id"]
    )
    assert reviewed["destination"] == destination


def prepare_renewal(f, destination="collector"):
    values = renewal_input(f, destination=destination)
    reviewed = f["service"].loan_payout_preview(f["owner"], LoanPayoutPreview(**values))
    command = LoanPayoutPrepare(
        action="loan_payout_prepare",
        request_id=uuid4(),
        source_digest=reviewed["source_digest"],
        **values,
    )
    return f["service"].execute(f["owner"], command)


def own_ack(f, prepared, who, stage, payout_version, **changes):
    from gilbic_backend.treasury_models import COMMAND_ADAPTER

    values = {
        "action": "loan_payout_acknowledge",
        "request_id": uuid4(),
        "payout_id": prepared["target_id"],
        "payout_version": payout_version,
        "stage": stage,
        "received": True,
        "reviewed_amount": "1000.00",
        "receipt_method": "cash"
        if prepared["result"]["payout"]["destination"] == "collector"
        and stage != "recipient"
        else "gcash",
        "acknowledged_at": datetime.now(timezone.utc),
        "attestation": "I independently confirm the actual full amount and method for my own payout.",
    }
    values.update(changes)
    command = COMMAND_ADAPTER.validate_python(values)
    return command, f["service"].execute(who, command)


@pytest.mark.parametrize(
    "destination,revocation",
    [
        ("collector", None),
        ("borrower", None),
        ("collector", "collector_device"),
        ("borrower", "borrower_role"),
    ],
)
def test_renewal_completion_requires_independent_borrower_and_reviewed_proof(
    renewal_payout_case, destination, revocation
):
    from gilbic_backend.treasury_models import COMMAND_ADAPTER

    f = renewal_payout_case
    prepared = prepare_renewal(f, destination)
    debit(f, prepared, purpose="renewal")
    confirm(f, prepared["target_id"])
    payout_version = 3
    if destination == "collector":
        command, receipt = own_ack(
            f, prepared, f["collector"], "recipient", payout_version
        )
        assert f["service"].execute(f["collector"], command) == receipt
        payout_version += 1
        own_ack(f, prepared, f["collector"], "borrower_handover", payout_version)
        payout_version += 1
    with pytest.raises(TreasuryDenied):
        own_ack(f, prepared, f["owner"], "borrower", payout_version)
    command, receipt = own_ack(f, prepared, f["borrower"], "borrower", payout_version)
    assert f["service"].execute(f["borrower"], command) == receipt
    assert "source_snapshot" not in str(receipt)
    assert "recipient_reference" not in str(receipt)
    payout_version += 1
    command = COMMAND_ADAPTER.validate_python(
        {
            "action": "loan_payout_renewal_complete",
            "request_id": uuid4(),
            "account_id": f["account_id"],
            "expected_version": version(f),
            "payout_id": prepared["target_id"],
            "payout_version": payout_version,
            "evidence_id": evidence(f),
            "reviewed_amount": "1000.00",
            "proof_review_confirmed": True,
            "reason": "Management reviewed the actual borrower receipt and independent confirmation.",
        }
    )
    complete = f["service"].execute(f["owner"], command)
    assert complete["result"]["payout"]["status"] == "completed"
    assert f["service"].execute(f["owner"], command) == complete
    with connect() as conn:
        row = conn.execute(
            "select * from lending.client_renewal_requests where id=%s",
            (f["renewal_id"],),
        ).fetchone()
        assert row["activation_status"] == "active"
        assert row["handover_proof_status"] == "approved"
        assert row["net_release_amount"] == 1000
        assert all(
            row[key] is None
            for key in (
                "cash_released_to_collector_at",
                "collector_cash_received_at",
                "cash_given_to_client_at",
                "client_cash_confirmed_at",
            )
        )
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )

    if revocation:
        with connect() as conn:
            if revocation == "collector_device":
                conn.execute(
                    "update core.devices set status='revoked' where id=%s",
                    (f["collector"].registered_device_id,),
                )
            else:
                conn.execute(
                    "delete from core.user_roles where user_id=%s and role_id=(select id from core.roles where code='client')",
                    (f["borrower"].user_id,),
                )
        with pytest.raises(TreasuryDenied):
            f["service"].execute(f["owner"], command)
        history = f["service"].loan_payout_workspace(
            f["owner"], mode="staff", account_id=f["account_id"]
        )
        saved_row = next(
            row for row in history["items"] if row["id"] == prepared["target_id"]
        )
        assert saved_row["status"] == "completed"
        assert saved_row["blocker"]


def test_receipt_reviewers_revoked_device_blocks_later_reads_and_borrower_stage(
    renewal_payout_case,
):
    from dataclasses import replace

    f = renewal_payout_case
    prepared = prepare_renewal(f, "borrower")
    debit(f, prepared, purpose="renewal")
    confirm(f, prepared["target_id"])
    current_device = uuid4()
    with connect() as conn:
        conn.execute(
            "insert into core.devices(id,user_id,device_identifier_hash,platform) values(%s,%s,%s,'web')",
            (current_device, f["owner"].user_id, uuid4().hex),
        )
        conn.execute(
            "update core.devices set status='revoked' where id=%s",
            (f["owner"].registered_device_id,),
        )
    current_owner = replace(f["owner"], registered_device_id=current_device)
    history = f["service"].loan_payout_workspace(
        current_owner, mode="staff", account_id=f["account_id"]
    )
    assert history["items"][0]["blocker"]
    with pytest.raises(TreasuryDenied):
        own_ack(f, prepared, f["borrower"], "borrower", 3)


def test_denied_receipt_does_not_advance_and_can_be_followed_by_actual_receipt(
    payout_case,
):
    f = payout_case
    _, prepared = prepare(f)
    debit(f, prepared)
    _, denied = confirm(f, prepared["target_id"], received=False)
    assert denied["result"]["payout"]["status"] == "debited"
    _, received = confirm(f, prepared["target_id"], 3)
    assert received["result"]["payout"]["status"] == "recipient_confirmed"


@pytest.mark.parametrize("funded", [False, True])
def test_only_unfunded_preparation_can_be_cancelled(payout_case, funded):
    from gilbic_backend.treasury_models import COMMAND_ADAPTER

    f = payout_case
    _, prepared = prepare(f)
    if funded:
        debit(f, prepared)
    command = COMMAND_ADAPTER.validate_python(
        {
            "action": "loan_payout_cancel",
            "request_id": uuid4(),
            "account_id": f["account_id"],
            "expected_version": version(f),
            "payout_id": prepared["target_id"],
            "payout_version": 2 if funded else 1,
            "reason": "Cancel unchanged unfunded preparation.",
        }
    )
    if funded:
        with pytest.raises(TreasuryConflict):
            f["service"].execute(f["owner"], command)
    else:
        cancelled = f["service"].execute(f["owner"], command)
        assert cancelled["result"]["payout"]["status"] == "cancelled"
        assert f["service"].execute(f["owner"], command) == cancelled
        _, replacement = prepare(f, destination="borrower")
        assert replacement["target_id"] != prepared["target_id"]


def test_renewal_payout_blocks_legacy_cash_fields_and_activation(renewal_payout_case):
    import psycopg

    f = renewal_payout_case
    prepare_renewal(f)
    for field, value in (
        ("cash_released_to_collector_at", "now()"),
        ("client_cash_confirmed_at", "now()"),
        ("activation_status", "'active'"),
    ):
        with pytest.raises(psycopg.errors.CheckViolation), connect() as conn:
            conn.execute(
                f"update lending.client_renewal_requests set {field}={value} where id=%s",
                (f["renewal_id"],),
            )


def test_payout_reads_are_scoped_and_remain_visible_when_entry_disabled(
    payout_case, monkeypatch
):
    f = payout_case
    _, prepared = prepare(f)
    reader = getattr(f["service"], "loan_payout_workspace", None)
    assert reader is not None, "Scoped payout read projection is required"
    staff = reader(f["owner"], account_id=f["account_id"], mode="staff")
    assert staff["items"][0]["id"] == prepared["target_id"]
    own = reader(f["collector"], mode="own")
    assert own["items"][0]["id"] == prepared["target_id"]
    assert "source_snapshot" not in str(own)
    assert "recipient_reference" not in str(own)
    with pytest.raises(TreasuryDenied):
        reader(f["collector"], account_id=f["account_id"], mode="staff")
    monkeypatch.setenv("SPINA_TREASURY_ENABLED", "false")
    disabled = reader(f["owner"], account_id=f["account_id"], mode="staff")
    assert disabled["enabled"] is False
    assert disabled["items"][0]["id"] == prepared["target_id"]


def test_payout_catalogue_uses_signed_approved_source_and_current_net(payout_case):
    f = payout_case
    catalogue = getattr(f["service"], "loan_payout_sources", None)
    assert catalogue is not None, "Protected loan source selection is required"
    sources = catalogue(f["owner"], f["account_id"])
    item = next(
        item for item in sources["items"] if item["source_id"] == str(f["loan_id"])
    )
    assert item["amount"] == "1000.00"
    assert item["authorization_id"] == str(f["release"]["authorization_id"])
    assert (
        item["contract_evidence_reference"]
        == f["release"]["contract_evidence_reference"]
    )


def test_stale_unfunded_source_can_be_cancelled_without_releasing_money(payout_case):
    from gilbic_backend.treasury_models import LoanPayoutCancel

    f = payout_case
    _, prepared = prepare(f)
    with connect() as conn:
        conn.execute(
            "update lending.collector_area_assignments set is_active=false where collector_user_id=%s",
            (f["collector"].user_id,),
        )
    command = LoanPayoutCancel(
        action="loan_payout_cancel",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        payout_id=prepared["target_id"],
        payout_version=1,
        reason="Assignment changed before any actual debit.",
    )
    result = f["service"].execute(f["owner"], command)
    assert result["result"]["payout"]["status"] == "cancelled"
    assert f["service"].execute(f["owner"], command) == result


def test_database_cannot_skip_recipient_and_borrower_receipt_stages(payout_case):
    import psycopg

    f = payout_case
    _, prepared = prepare(f)
    debit(f, prepared)
    with connect() as conn, pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "update treasury.loan_payouts set status='completed',version=version+1 where id=%s",
            (prepared["target_id"],),
        )


def test_disbursement_delegate_can_upload_own_private_recipient_evidence(payout_case):
    from gilbic_backend.treasury_models import AccountGrant
    from treasury_test_support import PDF, grant_live

    f = payout_case
    with connect() as conn:
        delegate = actor(conn, "employee")
        grant_live(conn, delegate.user_id, "treasury.disbursement.record")
    f["service"].execute(
        f["owner"],
        AccountGrant(
            action="account_grant",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            user_id=delegate.user_id,
            permissions=["treasury.disbursement.record"],
            private_history=False,
        ),
    )
    from gilbic_backend.treasury_claims import upload_evidence

    result = upload_evidence(
        f["service"],
        delegate,
        uuid4(),
        f["account_id"],
        "recipient",
        PDF,
        "application/pdf",
    )
    metadata, content = f["service"].evidence_content(
        delegate, UUID(result["target_id"])
    )
    assert content == PDF and metadata["purpose"] == "recipient"
    assert (
        "recipient"
        in f["service"].workspace(delegate)["accounts"][0]["evidence_purposes"]
    )


def test_concurrent_preparations_keep_one_protected_source(payout_case):
    from concurrent.futures import ThreadPoolExecutor

    f = payout_case
    reviewed = preview(f)

    def attempt(_):
        try:
            return f["service"].execute(
                f["owner"],
                LoanPayoutPrepare(
                    action="loan_payout_prepare",
                    request_id=uuid4(),
                    source_digest=reviewed["source_digest"],
                    **source_input(f),
                ),
            )
        except TreasuryConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(result is not None for result in results) == 1


def test_completion_outcome_failure_rolls_back_loan_schedule_credentials_and_payout(
    payout_case, monkeypatch
):
    f = payout_case
    original = f["service"].save_result

    def fail_outcome(*args, **kwargs):
        if args[3] == "loan_payout_first_loan_complete":
            raise RuntimeError("Synthetic final audit/outcome unavailable")
        return original(*args, **kwargs)

    monkeypatch.setattr(f["service"], "save_result", fail_outcome)
    with pytest.raises(RuntimeError, match="Synthetic final audit"):
        test_protected_first_loan_completion_uses_actual_borrower_receipt_and_one_debit(
            f, "borrower", "gcash"
        )
    with connect() as conn:
        assert (
            conn.execute(
                "select status from lending.loans where id=%s", (f["loan_id"],)
            ).fetchone()["status"]
            == "approved"
        )
        for table in [
            "first_loan_releases",
            "loan_contract_schedules",
            "first_loan_credential_intents",
            "loan_disbursement_events",
        ]:
            assert (
                conn.execute(
                    "select count(*) as n from lending." + table + " where loan_id=%s",
                    (f["loan_id"],),
                ).fetchone()["n"]
                == 0
            )
        assert (
            conn.execute(
                "select status from treasury.loan_payouts where loan_id=%s",
                (f["loan_id"],),
            ).fetchone()["status"]
            == "recipient_confirmed"
        )
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )


def test_private_debit_bytes_are_rechecked_on_confirmation_and_replay(
    payout_case, monkeypatch
):
    from gilbic_backend.office_review_evidence_storage import EvidenceFileError

    f = payout_case
    command, prepared = prepare(f)
    debit(f, prepared)

    def unavailable(*args, **kwargs):
        raise EvidenceFileError("Synthetic missing private evidence")

    monkeypatch.setattr(f["service"].store, "read", unavailable)
    with pytest.raises((EvidenceFileError, TreasuryConflict)):
        confirm(f, prepared["target_id"])
    with pytest.raises((EvidenceFileError, TreasuryConflict)):
        f["service"].execute(f["owner"], command)


def test_recipient_cannot_borrow_another_actors_device_or_acknowledge_another_client(
    renewal_payout_case,
):
    from dataclasses import replace

    f = renewal_payout_case
    prepared = prepare_renewal(f, "borrower")
    debit(f, prepared, purpose="renewal")
    confirm(f, prepared["target_id"])
    for who in [
        f["collector"],
        replace(f["borrower"], registered_device_id=f["owner"].registered_device_id),
    ]:
        with pytest.raises(TreasuryDenied):
            own_ack(f, prepared, who, "borrower", 3)


def test_active_payout_blocks_approval_cancellation_and_reports_its_funding_route(
    payout_case,
):
    from gilbic_backend.first_loan_repository import FirstLoanConflict, _load, _public

    f = payout_case
    prepare(f)
    with pytest.raises(FirstLoanConflict, match="protected payout"):
        f["repository"].cancel_approval(
            actor_user_id=f["owner"].user_id,
            registered_device_id=f["owner"].registered_device_id,
            loan_id=f["loan_id"],
            packet_hash=f["approved"]["packet_hash"],
            reason="Synthetic cancellation",
            request_id=uuid4(),
        )
    with connect() as conn:
        view = _public(
            conn.cursor(), _load(conn.cursor(), f["loan_id"]), f["owner"].user_id
        )
        assert view["funding_payout"]["destination"] == "collector"
        assert "recipient_reference" not in view["funding_payout"]


@pytest.mark.parametrize(
    "table", ["loan_disbursement_events", "loan_renewal_execution_events"]
)
def test_prepared_renewal_prevents_voiding_its_authoritative_source(
    renewal_payout_case, table
):
    import psycopg

    f = renewal_payout_case
    prepared = prepare_renewal(f)
    source = prepared["result"]["payout"]["source_snapshot"]["source"]
    target = source[
        "disbursement_id" if table == "loan_disbursement_events" else "execution_id"
    ]
    function = (
        "void_loan_disbursement_evidence"
        if table == "loan_disbursement_events"
        else "void_loan_renewal_execution_evidence"
    )
    with (
        connect() as conn,
        pytest.raises(
            psycopg.Error,
            match="Reconcile the retained loan payout|linked to active renewal execution evidence",
        ),
    ):
        conn.execute(
            "select accounting." + function + "(%s,%s,%s)",
            (target, f["owner"].user_id, "Synthetic conflicting void"),
        )


def test_completed_first_loan_funding_cannot_be_voided_through_legacy_source(
    payout_case,
):
    import psycopg

    f = payout_case
    test_protected_first_loan_completion_uses_actual_borrower_receipt_and_one_debit(
        f, "borrower", "gcash"
    )
    with connect() as conn:
        event = conn.execute(
            "select id from lending.loan_disbursement_events where loan_id=%s",
            (f["loan_id"],),
        ).fetchone()["id"]
        with pytest.raises(
            psycopg.Error,
            match="Reconcile the retained loan payout|dedicated complete release reversal",
        ):
            conn.execute(
                "select accounting.void_loan_disbursement_evidence(%s,%s,%s)",
                (event, f["owner"].user_id, "Synthetic conflicting void"),
            )


def test_explicit_borrower_route_does_not_depend_on_an_uninvolved_collector_assignment(
    payout_case,
):
    f = payout_case
    command, prepared = prepare(f, destination="borrower")
    with connect() as conn:
        conn.execute(
            "update lending.collector_area_assignments set is_active=false where collector_user_id=%s",
            (f["collector"].user_id,),
        )
    assert f["service"].execute(f["owner"], command) == prepared
    assert (
        debit(f, prepared)[1]["result"]["source_link"]["status"]
        == "funded_pending_recipient"
    )
