from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from gilbic_backend.treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
)
from gilbic_backend.treasury_claims import submit_claim
from gilbic_backend.treasury_models import (
    AccountGrant,
    ClaimMetadata,
    OpeningActivate,
    OpeningPrepare,
    ReceiptVerify,
)
from gilbic_backend.treasury_repository import account_snapshot
from treasury_test_support import PDF, actor, connect, evidence, grant_live, version


def test_missing_opening_is_unknown_and_exact_zero_is_evidenced(treasury):
    f = treasury
    with connect() as conn:
        assert account_snapshot(conn, f["account_id"])["expected_balance"] is None
    prepared = f["service"].execute(
        f["owner"],
        OpeningPrepare(
            action="opening_prepare",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            cutoff=datetime(2026, 10, 1, tzinfo=timezone.utc),
            amount="0.00",
            evidence_id=evidence(f, "opening"),
            reason="Actual synthetic count",
        ),
    )
    f["service"].execute(
        f["owner"],
        OpeningActivate(
            action="opening_activate",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            opening_id=prepared["target_id"],
            opening_version=prepared["version"],
            confirmed=True,
            reason="Activate synthetic evidenced zero",
        ),
    )
    with connect() as conn:
        assert account_snapshot(conn, f["account_id"])["expected_balance"] == "0.00"


def receipt(
    f, request_id=None, reference="000001", amount="1000.00", effective_at=None
):
    return ReceiptVerify(
        action="receipt_verify",
        request_id=request_id or uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        client_id=f["client_id"],
        amount=amount,
        provider="gcash",
        reference=reference,
        effective_at=effective_at or datetime(2026, 10, 2, tzinfo=timezone.utc),
        evidence_id=evidence(f),
        recipient_attestation="Checked recipient side history",
    )


def test_duplicate_external_receipt_once_and_unchanged_recovery(treasury):
    f = treasury
    command = receipt(f)
    result = f["service"].execute(f["owner"], command)
    assert f["service"].execute(f["owner"], command) == result
    assert f["service"].request_result(f["owner"], command.request_id) == result
    # Different request/reviewer evidence can link the same verified identity.
    duplicate = f["service"].execute(f["owner"], receipt(f))
    assert duplicate["target_id"] == result["target_id"]
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )
        assert conn.execute(
            "select sum(signed_amount) as amount from treasury.movement_lines where account_id=%s",
            (f["account_id"],),
        ).fetchone()["amount"] == Decimal("1000.00")
    with pytest.raises(TreasuryConflict):
        f["service"].execute(
            f["owner"], command.model_copy(update={"amount": "999.00"})
        )


def test_two_requests_race_one_reference_and_revoked_replay_denied(treasury):
    f = treasury
    commands = [receipt(f), receipt(f)]
    # Same original version intentionally forces one account conflict, never two movements.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(f["service"].execute, f["owner"], command)
            for command in commands
        ]
    saved = []
    for future in futures:
        try:
            saved.append(future.result())
        except TreasuryConflict:
            pass
    assert len(saved) == 1
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 1
        )
        conn.execute(
            "update core.devices set status='revoked' where id=%s",
            (f["owner"].registered_device_id,),
        )
    with pytest.raises(TreasuryDenied):
        f["service"].request_result(f["owner"], UUID(saved[0]["request_id"]))


def test_claim_upload_is_own_evidence_only_and_digest_recovery(treasury):
    f = treasury
    metadata = ClaimMetadata(
        request_id=uuid4(),
        account_id=f["account_id"],
        account_version=version(f),
        client_id=f["client_id"],
        loan_ids=[f["loan_id"]],
        amount="400.00",
        reference="000007",
        claimed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        sender_note="A relative paid",
    )
    result = submit_claim(
        f["service"], f["client_actor"], metadata, PDF, "application/pdf"
    )
    assert (
        submit_claim(f["service"], f["client_actor"], metadata, PDF, "application/pdf")
        == result
    )
    assert result["result"]["claim"]["official_payment_posted"] is False
    with connect() as conn:
        assert (
            conn.execute(
                "select count(*) as n from treasury.events where account_id=%s",
                (f["account_id"],),
            ).fetchone()["n"]
            == 0
        )
    with pytest.raises(TreasuryConflict):
        submit_claim(
            f["service"],
            f["client_actor"],
            metadata,
            PDF.replace(b"Synthetic", b"Alternate"),
            "application/pdf",
        )
    with connect() as conn:
        outsider = actor(conn, "client")
    with pytest.raises(TreasuryDenied):
        submit_claim(
            f["service"],
            outsider,
            metadata.model_copy(update={"request_id": uuid4()}),
            PDF,
            "application/pdf",
        )


def test_management_role_does_not_bypass_account_or_private_history(treasury):
    f = treasury
    with connect() as conn:
        other = actor(conn)
    with pytest.raises(TreasuryDenied):
        f["service"].list_records(other, f["account_id"], "events")
    f["service"].execute(
        f["owner"],
        AccountGrant(
            action="account_grant",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            user_id=other.user_id,
            permissions=["treasury.view"],
            private_history=False,
        ),
    )
    # No live role permission is seeded by configuring account access.
    with pytest.raises(TreasuryDenied):
        f["service"].list_records(other, f["account_id"], "events")


def test_disabled_entry_preserves_existing_balance_and_history(treasury, monkeypatch):
    f = treasury
    result = f["service"].execute(f["owner"], receipt(f))
    monkeypatch.setenv("SPINA_TREASURY_ENABLED", "false")
    with pytest.raises(TreasuryUnavailable):
        f["service"].execute(f["owner"], receipt(f, reference="000002"))
    assert f["service"].request_result(f["owner"], UUID(result["request_id"])) == result
    assert (
        f["service"].list_records(f["owner"], f["account_id"], "events")["total_count"]
        == 1
    )


def test_delegated_receipt_verification_recovery_rechecks_live_grant_and_assignment(
    treasury,
):
    f = treasury
    with connect() as conn:
        delegate = actor(conn, "collector")
        grant_live(conn, delegate.user_id, "treasury.receipt.verify")
        conn.execute(
            "insert into lending.collector_area_assignments(collector_user_id,area) select %s,area from lending.clients where id=%s",
            (delegate.user_id, f["client_id"]),
        )
    f["service"].execute(
        f["owner"],
        AccountGrant(
            action="account_grant",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            user_id=delegate.user_id,
            permissions=["treasury.receipt.verify"],
            private_history=False,
        ),
    )
    command = receipt(f)
    result = f["service"].execute(delegate, command)
    assert result["result"]["actor_user_id"] == str(delegate.user_id)
    with connect() as conn:
        conn.execute(
            "update lending.collector_area_assignments set is_active=false where collector_user_id=%s",
            (delegate.user_id,),
        )
    with pytest.raises(TreasuryDenied):
        f["service"].request_result(delegate, command.request_id)


def test_private_history_requires_both_live_permission_and_restricted_grant(treasury):
    f = treasury
    with connect() as conn:
        delegate = actor(conn)
        role = grant_live(conn, delegate.user_id, "treasury.view")
    grant = AccountGrant(
        action="account_grant",
        request_id=uuid4(),
        account_id=f["account_id"],
        expected_version=version(f),
        user_id=delegate.user_id,
        permissions=["treasury.view"],
        private_history=False,
    )
    f["service"].execute(f["owner"], grant)
    with pytest.raises(TreasuryDenied):
        f["service"].list_records(delegate, f["account_id"], "events")
    f["service"].execute(
        f["owner"],
        grant.model_copy(
            update={
                "request_id": uuid4(),
                "expected_version": version(f),
                "private_history": True,
            }
        ),
    )
    assert (
        f["service"].list_records(delegate, f["account_id"], "events")["total_count"]
        == 0
    )
    with connect() as conn:
        conn.execute(
            "delete from core.user_roles where user_id=%s and role_id=%s",
            (delegate.user_id, role),
        )
    with pytest.raises(TreasuryDenied):
        f["service"].list_records(delegate, f["account_id"], "events")


def test_private_evidence_loss_blocks_recovery_instead_of_phantom_success(treasury):
    from gilbic_backend.office_review_evidence_storage import EvidenceFileError

    f = treasury
    command = receipt(f)
    f["service"].execute(f["owner"], command)
    # Corrupt only this fixture's own temporary private file.
    path = f["service"].store.root / (command.evidence_id.hex + ".bin")
    path.write_bytes(b"corrupted synthetic file")
    with pytest.raises(EvidenceFileError):
        f["service"].request_result(f["owner"], command.request_id)


def test_receipt_delegate_cannot_open_owner_personal_movement_file(treasury):
    from test_treasury_reconciliation_postgres import movement

    f = treasury
    result = movement(f, "owner-only-history", "50.00")
    with connect() as conn:
        delegate = actor(conn)
        grant_live(conn, delegate.user_id, "treasury.receipt.verify")
    f["service"].execute(
        f["owner"],
        AccountGrant(
            action="account_grant",
            request_id=uuid4(),
            account_id=f["account_id"],
            expected_version=version(f),
            user_id=delegate.user_id,
            permissions=["treasury.receipt.verify"],
            private_history=False,
        ),
    )
    with pytest.raises(TreasuryDenied):
        f["service"].evidence_content(
            delegate, UUID(result["result"]["event"]["evidence_id"])
        )


pytest_plugins = ["treasury_test_support"]


def test_parent_area_authority_and_delegation_follow_current_specific_owner(treasury):
    from gilbic_backend.treasury_authorization import require_borrower

    f = treasury
    parent = "Synthetic parent " + uuid4().hex
    child = parent + " › Child"
    with connect() as conn:
        assigned = actor(conn, "collector")
        visitor = actor(conn, "collector")
        child_owner = actor(conn, "collector")
        for who in [assigned, visitor, child_owner]:
            grant_live(conn, who.user_id, "treasury.proof.submit.assigned")
            conn.execute(
                """insert into treasury.account_access(account_id,user_id,permissions,granted_by)
                values(%s,%s,%s,%s)""",
                (
                    f["account_id"],
                    who.user_id,
                    ["treasury.proof.submit.assigned"],
                    f["owner"].user_id,
                ),
            )
        conn.execute(
            "update lending.clients set area=%s where id=%s", (child, f["client_id"])
        )
        assignment = conn.execute(
            "insert into lending.collector_area_assignments(collector_user_id,area) values(%s,%s) returning id",
            (assigned.user_id, parent),
        ).fetchone()["id"]

    def allowed(who):
        with connect() as conn:
            return require_borrower(
                conn,
                who,
                f["client_id"],
                [],
                staff_permission="treasury.proof.submit.assigned",
                account_id=f["account_id"],
            )

    assert allowed(assigned)["id"] == f["client_id"]
    with connect() as conn:
        grant = uuid4()
        conn.execute(
            """insert into lending.collector_area_access_grants(id,grantor_user_id,visiting_collector_user_id,effective_at,expires_at)
            values(%s,%s,%s,now()-interval '1 hour',now()+interval '1 day')""",
            (grant, assigned.user_id, visitor.user_id),
        )
        conn.execute(
            """insert into lending.collector_area_access_grant_scopes(grant_id,source_assignment_id,area_path,include_descendants)
            values(%s,%s,%s,true)""",
            (grant, assignment, parent),
        )
    assert allowed(visitor)["id"] == f["client_id"]
    with connect() as conn:
        conn.execute(
            "insert into lending.collector_area_assignments(collector_user_id,area) values(%s,%s)",
            (child_owner.user_id, child),
        )
    for who in [assigned, visitor]:
        with pytest.raises(TreasuryDenied):
            allowed(who)
    assert allowed(child_owner)["id"] == f["client_id"]
    with connect() as conn:
        conn.execute(
            "update lending.collector_area_assignments set is_active=false where collector_user_id=%s",
            (child_owner.user_id,),
        )
        conn.execute(
            "update lending.collector_area_access_grants set revoked_at=now(),revoked_by_user_id=%s,revocation_reason='Synthetic revocation' where id=%s",
            (assigned.user_id, grant),
        )
    with pytest.raises(TreasuryDenied):
        allowed(visitor)
    assert allowed(assigned)["id"] == f["client_id"]
