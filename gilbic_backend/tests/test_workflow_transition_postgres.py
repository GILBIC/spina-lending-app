"""Current-schema workflow regressions; run only on an owned disposable database."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from gilbic_backend import collection_void_repository
from gilbic_backend.collection_void_repository import PostgresCollectionVoidRepository
from gilbic_backend.concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from spina_mobile_collections.contracts import (
    CollectionCommand,
    CollectionEntryType,
    CollectionStatus,
    PastDueFollowupInput,
    PastDueReasonCode,
)
from spina_mobile_collections.postgres import PostgresCollectionExecutor
from test_combined_collection_renewal_workflow_postgres import (
    DATABASE_URL,
    _connect,
    _setup_combined_case,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)


def _command(case, sequence, version):
    return CollectionCommand(
        idempotency_key=uuid4(),
        route_entry_id=str(case.regular_loan_id),
        client_id=str(case.client_id),
        loan_id=str(case.regular_loan_id),
        collection_date=date(2097, 8, 2),
        entry_type=CollectionEntryType.PASS,
        amount=None,
        recorded_at=datetime(2097, 8, 2, 1, tzinfo=UTC),
        device_id=case.installation_id,
        device_sequence=sequence,
        route_revision=f"loan:{case.regular_loan_id}:v{version}",
        note="Synthetic unable to pay",
        # The original Past Due case survives void and needs no new reason.
        past_due_followup=(
            PastDueFollowupInput(
                reason_code=PastDueReasonCode.NO_CASH, note="Synthetic no cash today."
            )
            if version == 0
            else None
        ),
    )


def test_pass_save_void_replace_and_concurrent_replacement(monkeypatch):
    monkeypatch.setattr(collection_void_repository, "open_connection", _connect)
    case = _setup_combined_case()
    executor = PostgresCollectionExecutor(
        connection_factory=_connect,
        posting_bridge=ConcurrentReceiptSafeCollectionPostingBridge(),
    )

    def post(command):
        return executor.execute(
            actor=case.actor,
            command=command,
            canonical_payload={"synthetic_key": str(command.idempotency_key)},
            request_hash=command.idempotency_key.hex * 2,
        )

    original = _command(case, 1, 0)
    first = post(original)
    assert first.status == CollectionStatus.ACCEPTED
    voided = PostgresCollectionVoidRepository().void_unremitted(
        actor_user_id=case.collector_id,
        transaction_id=UUID(first.posted.server_transaction_id),
        reason="Synthetic corrected unable-to-pay evidence",
    )
    replay = post(original)
    assert replay.status == CollectionStatus.DUPLICATE
    assert replay.posted.server_transaction_id == first.posted.server_transaction_id
    replacement = post(_command(case, 2, voided.state_version))
    assert replacement.status == CollectionStatus.ACCEPTED, replacement
    duplicate = post(
        _command(case, 3, int(replacement.posted.route_revision.rsplit("v", 1)[1]))
    )
    assert duplicate.status == CollectionStatus.CONFLICT
    assert duplicate.code == "pass_already_recorded"
    # Independently of Python validation, the index prevents resurrection.
    with (
        _connect() as connection,
        pytest.raises(psycopg.errors.UniqueViolation),
        connection.transaction(),
    ):
        connection.execute(
            "update lending.collection_transactions set is_voided=false, voided_at=null, voided_by_user_id=null, void_reason=null where id=%s",
            (first.posted.server_transaction_id,),
        )
    second_void = PostgresCollectionVoidRepository().void_unremitted(
        actor_user_id=case.collector_id,
        transaction_id=UUID(replacement.posted.server_transaction_id),
        reason="Synthetic second correction",
    )
    barrier = Barrier(2)

    def compete(sequence):
        command = _command(case, sequence, second_void.state_version)
        barrier.wait(timeout=10)
        return post(command)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(compete, sequence) for sequence in (4, 5)]
        outcomes = [future.result(timeout=20) for future in futures]
    assert sorted(o.status.value for o in outcomes) == ["accepted", "conflict"]
    with _connect() as connection:
        counts = connection.execute(
            "select count(*), count(*) filter (where not is_voided) from lending.collection_transactions where loan_id=%s and entry_type=%s",
            (case.regular_loan_id, "pass"),
        ).fetchone()
        assert counts == (3, 1)
    assert (
        post(original).posted.server_transaction_id
        == first.posted.server_transaction_id
    )


@pytest.mark.parametrize("first_action", ["decline", "release"])
def test_renewal_decision_and_release_serialize_on_request_lock(
    monkeypatch, first_action
):
    from decimal import Decimal
    from threading import Event, current_thread
    from types import SimpleNamespace

    from fastapi import HTTPException
    from gilbic_backend import renewal_workflow_api as renewal
    from test_combined_collection_renewal_workflow_postgres import _setup_renewal_client

    borrower, _collector, client, loan = _setup_renewal_client(mode="fixed_daily")
    with _connect() as connection:
        request = connection.execute(
            """insert into lending.client_renewal_requests
            (client_id, loan_id, requested_by_user_id, requested_amount, status, client_decision,
             client_decided_at, signer_readiness_status, approved_principal, reviewed_by_user_id, reviewed_at)
            values (%s,%s,%s,3000,'approved','accepted',now(),'ready',3000,%s,now()) returning id""",
            (client, loan, borrower, _collector),
        ).fetchone()[0]
    monkeypatch.setattr(renewal, "open_connection", _connect)
    monkeypatch.setattr(
        renewal,
        "authenticated_device_context",
        lambda **kw: SimpleNamespace(user_id=borrower, roles=("client", "management")),
    )
    # Authoritative execution is separately covered by release tests. Here only
    # its payload is synthetic; request reads, row locks, writes and audits are real.
    monkeypatch.setattr(
        renewal,
        "_authoritative_execution",
        lambda *a, **kw: {
            "old_loan_settlement_amount": Decimal(1000),
            "cash_disbursed_amount": Decimal(2000),
            "new_loan_id": loan,
            "execution_id": uuid4(),
        },
    )
    monkeypatch.setattr(renewal, "_payload", lambda cursor, row: dict(row))
    original_read = renewal._renewal_row
    locked = Event()
    unblock = Event()
    second_started = Event()
    first_thread = []

    def held_read(cursor, **kwargs):
        row = original_read(cursor, **kwargs)
        if current_thread().ident == first_thread[0] and not locked.is_set():
            locked.set()
            assert unblock.wait(10)
        return row

    monkeypatch.setattr(renewal, "_renewal_row", held_read)
    routes = renewal.create_renewal_workflow_router().routes
    decision = next(
        r.endpoint
        for r in routes
        if r.path == "/api/v1/client/renewals/{request_id}/decision"
    )
    release = next(
        r.endpoint
        for r in routes
        if r.path == "/api/v1/management/renewals/{request_id}/release-to-collector"
    )

    def run(action, first=False):
        if first:
            first_thread.append(current_thread().ident)
        else:
            second_started.set()
        kwargs = {
            "request_id": request,
            "authorization": "synthetic",
            "x_device_id": "synthetic",
            "auth": None,
            "accounts": None,
        }
        try:
            if action == "decline":
                return decision(
                    body=renewal.ClientRenewalDecisionBody(decision="declined"),
                    **kwargs,
                )
            return release(**kwargs)
        except HTTPException as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, first_action, True)
        assert locked.wait(10)
        second = pool.submit(run, "release" if first_action == "decline" else "decline")
        assert second_started.wait(10)
        unblock.set()
        result1, result2 = first.result(timeout=15), second.result(timeout=15)
    assert result1["success"]
    assert isinstance(result2, HTTPException)
    assert result2.status_code == 409
    with _connect() as connection:
        row = connection.execute(
            "select client_decision, amount_locked_at, cash_released_to_collector_at from lending.client_renewal_requests where id=%s",
            (request,),
        ).fetchone()
    if first_action == "decline":
        assert result2.detail["code"] == "renewal_client_acceptance_required"
        assert row == ("declined", None, None)
    else:
        assert result2.detail["code"] == "renewal_decision_locked"
        assert row[0] == "accepted" and row[1] is not None and row[2] is not None
