import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from gilbic_backend import renewal_workflow_api as renewal
from gilbic_backend.collection_posting import PostgresCollectionPostingBridge
from spina_mobile_collections.service import CollectionConflict


@pytest.fixture
def decision_case(monkeypatch):
    stamp = datetime(2026, 10, 1, tzinfo=timezone.utc)
    row = {
        "request_id": uuid4(),
        "borrower_user_id": uuid4(),
        "status": "approved",
        "client_decision": "accepted",
        "client_decided_at": stamp,
        "amount_locked_at": None,
        "cash_released_to_collector_at": None,
        "activation_status": "pending",
        "handover_proof_status": "approved",
        "client_cash_confirmed_at": stamp,
        "new_loan_id": uuid4(),
        "old_loan_status": "paid",
        "remaining_balance": Decimal(0),
        "signer_readiness_status": "ready",
    }

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, parameters=None):
            if "set client_decision=" in query:
                row["client_decision"] = parameters[0]
                row["client_decided_at"] = "overwritten"
            if "set activation_status = 'active'" in query:
                row["activation_status"] = "active"

    @contextmanager
    def opened():
        yield SimpleNamespace(cursor=lambda **kwargs: Cursor())

    monkeypatch.setattr(renewal, "open_connection", opened)
    monkeypatch.setattr(
        renewal,
        "authenticated_device_context",
        lambda **kw: SimpleNamespace(
            user_id=row["borrower_user_id"], roles=("client",)
        ),
    )
    monkeypatch.setattr(renewal, "_renewal_row", lambda *a, **kw: row)
    monkeypatch.setattr(renewal, "_payload", lambda *a: dict(row))
    endpoint = next(
        r.endpoint
        for r in renewal.create_renewal_workflow_router().routes
        if r.path == "/api/v1/client/renewals/{request_id}/decision"
    )

    def decide(value):
        return endpoint(
            request_id=row["request_id"],
            body=renewal.ClientRenewalDecisionBody(decision=value),
            authorization="synthetic",
            x_device_id="synthetic",
            auth=None,
            accounts=None,
        )

    return row, decide, Cursor()


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount_locked_at", True),
        ("cash_released_to_collector_at", True),
        ("activation_status", "released_pending_management"),
        ("activation_status", "active"),
    ],
)
def test_late_conflicting_decision_is_rejected(decision_case, field, value):
    row, decide, _ = decision_case
    row[field] = value
    original = dict(row)
    with pytest.raises(HTTPException) as error:
        decide("declined")
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "renewal_decision_locked"
    assert row == original


@pytest.mark.parametrize("locked", [False, True])
def test_identical_decision_retry_preserves_original_evidence(decision_case, locked):
    row, decide, _ = decision_case
    row["amount_locked_at"] = True if locked else None
    original = dict(row)
    assert decide("accepted")["success"]
    assert row == original


def test_decline_before_release_remains_available(decision_case):
    row, decide, _ = decision_case
    assert decide("declined")["success"]
    assert row["client_decision"] == "declined"


@pytest.mark.parametrize(
    "status,decision",
    [("approved", "declined"), ("approved", "pending"), ("pending", "accepted")],
)
def test_activation_requires_approved_accepted_request(decision_case, status, decision):
    row, _, cursor = decision_case
    row.update(status=status, client_decision=decision)
    activated, _ = renewal._try_activate(cursor, row=row, actor_user_id=uuid4())
    assert not activated
    assert row["activation_status"] != "active"


@pytest.mark.parametrize("voided", [True, False])
def test_pass_duplicate_rule_only_counts_active_receipts(voided):
    with sqlite3.connect(":memory:") as connection:
        connection.execute("ATTACH DATABASE ':memory:' AS lending")
        connection.execute(
            "CREATE TABLE lending.collection_covered_dates (transaction_id TEXT, loan_id TEXT, covered_date TEXT)"
        )
        connection.execute(
            "CREATE TABLE lending.collection_transactions (id TEXT, loan_id TEXT, collection_date TEXT, entry_type TEXT, is_voided BOOLEAN)"
        )
        connection.execute(
            "INSERT INTO lending.collection_transactions VALUES ('receipt','loan','2026-10-01','pass',?)",
            (voided,),
        )

        class Cursor:
            def execute(self, query, params):
                self.result = connection.execute(
                    query.replace("%s", "?"), tuple(str(p) for p in params)
                )

            def fetchone(self):
                return self.result.fetchone()

        if voided:
            PostgresCollectionPostingBridge._apply_pass_rules(
                Cursor(), loan_id="loan", collection_date=date(2026, 10, 1)
            )
        else:
            with pytest.raises(CollectionConflict, match="already recorded"):
                PostgresCollectionPostingBridge._apply_pass_rules(
                    Cursor(), loan_id="loan", collection_date=date(2026, 10, 1)
                )
