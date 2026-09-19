from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.errors import CheckViolation, InFailedSqlTransaction

from gilbic_backend import renewal_workflow_api as workflow
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from test_renewal_api import (
    CLIENT_ID,
    LOAN_ID,
    REQUEST_ID,
    FakeAccounts,
    FakeAuthClient,
)


HEADERS = {"Authorization": "Bearer test-token", "X-Device-Id": "test-device"}


def cif_conflict(constraint="client_cif_new_credit_ready"):
    return CheckViolation(
        "private database detail must not be returned",
        info={ord("n"): constraint.encode()},
    )


class WorkflowDatabase:
    def __init__(self, error):
        self.error = error
        self.state = {
            "row": {
                "request_id": REQUEST_ID,
                "client_id": CLIENT_ID,
                "loan_id": LOAN_ID,
                "handover_proof_status": "approved",
                "client_cash_confirmed_at": datetime(2026, 9, 19, tzinfo=UTC),
                "new_loan_id": LOAN_ID,
                "old_loan_status": "paid",
                "remaining_balance": Decimal("0.00"),
                "signer_readiness_status": "ready",
                "activation_status": "released_pending_management",
            },
            "audits": [],
        }
        self.result = None
        self.aborted = False

    @contextmanager
    def transaction(self):
        before = deepcopy(self.state)
        try:
            yield
        except Exception:
            self.state = before
            self.aborted = False
            raise

    @contextmanager
    def open(self):
        before = deepcopy(self.state)
        try:
            yield self
        except Exception:
            self.state = before
            self.aborted = False
            raise

    @contextmanager
    def cursor(self, **kwargs):
        yield self

    def execute(self, sql, params=None):
        if self.aborted:
            raise InFailedSqlTransaction("Transaction must be rolled back")
        normalized = " ".join(sql.split()).lower()
        if normalized.startswith("select request.id as request_id"):
            self.result = dict(self.state["row"])
        elif "set activation_status = 'active'" in normalized:
            if self.error:
                self.aborted = True
                raise self.error
            self.state["row"]["activation_status"] = "active"
        elif "set handover_proof_status=%s" in normalized:
            self.state["row"]["handover_proof_status"] = params[0]
        elif normalized.startswith("select id, party_role"):
            self.result = []
        elif normalized.startswith("delete from lending.renewal_required_signers"):
            self.state["signers_replaced"] = True
        elif "set status='approved', approved_principal" in normalized:
            if self.error:
                self.aborted = True
                raise self.error
            self.state["row"]["status"] = "approved"
        elif normalized.startswith("insert into core.audit_logs"):
            self.state["audits"].append(params[1])
        else:
            raise AssertionError(f"Unexpected database operation: {normalized}")
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result

    def prepare_proof_review(self):
        row = self.state["row"]
        row.update(
            {
                name: None
                for name in (
                    "area",
                    "recommended_at",
                    "reviewed_at",
                    "client_decided_at",
                    "amount_locked_at",
                    "cash_released_to_collector_at",
                    "collector_cash_received_at",
                    "cash_given_to_client_at",
                    "assigned_collector_user_id",
                )
            }
        )
        row.update(
            {
                name: ""
                for name in (
                    "client_code",
                    "client_name",
                    "loan_number",
                    "loan_type_name",
                    "client_message",
                    "collector_reason_code",
                    "collector_comment",
                    "management_override_reason",
                    "review_note",
                )
            }
        )
        row.update(
            {
                name: Decimal("100.00")
                for name in (
                    "contractual_total",
                    "paid_cash",
                    "current_principal",
                    "requested_amount",
                    "approved_principal",
                    "renewal_offset_amount",
                    "net_release_amount",
                )
            }
        )
        row.update(
            handover_proof_status="under_review",
            calculation_mode="fixed_daily",
            status="approved",
            submitted_at=datetime(2026, 9, 19, tzinfo=UTC),
            collector_recommendation="recommend",
            client_decision="accepted",
            office_processing_required=False,
        )


def make_client(monkeypatch, database):
    monkeypatch.setattr(workflow, "open_connection", database.open)
    app = FastAPI()
    app.include_router(workflow.create_renewal_workflow_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role="management"
    )
    return TestClient(app)


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_explicit_activation_maps_only_cif_constraint_to_safe_conflict(
    monkeypatch, prefix
):
    database = WorkflowDatabase(cif_conflict())
    client = make_client(monkeypatch, database)

    response = client.post(
        f"{prefix}/management/renewals/{REQUEST_ID}/activate", headers=HEADERS
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "client_cif_new_credit_not_ready",
        "message": "Refresh the client record and complete any required CIF re-verification before approving or releasing new credit.",
    }
    assert response.headers["cache-control"] == "no-store"
    assert database.state["row"]["activation_status"] == "released_pending_management"
    assert database.state["audits"] == []


def test_blocked_auto_activation_retains_proof_review_but_no_activation(monkeypatch):
    database = WorkflowDatabase(cif_conflict())
    database.prepare_proof_review()
    client = make_client(monkeypatch, database)

    response = client.post(
        f"/api/v1/management/renewals/{REQUEST_ID}/proof-review",
        json={"decision": "approved", "note": "Cash handover evidence reviewed"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["request"]["handover_proof_status"] == "approved"
    assert data["request"]["activation_status"] == "released_pending_management"
    assert data["request"]["ready_for_activation"] is False
    assert data["message"] == (
        "Refresh the client record and complete any required CIF re-verification before approving or releasing new credit."
    )
    assert database.state["audits"] == ["renewal.handover_proof.approved"]
    assert database.state["row"]["activation_status"] == "released_pending_management"


@pytest.mark.parametrize("operation", ["activate", "proof-review"])
@pytest.mark.parametrize(
    "error",
    [
        cif_conflict("client_cif_new_credit_ready_other"),
        CheckViolation("an unrelated check failed"),
        RuntimeError("an unrelated programming error"),
    ],
)
def test_unrelated_errors_propagate_and_roll_back_entire_request(
    monkeypatch, operation, error
):
    database = WorkflowDatabase(error)
    database.prepare_proof_review()
    if operation == "activate":
        database.state["row"]["handover_proof_status"] = "approved"
    before = deepcopy(database.state)
    client = make_client(monkeypatch, database)

    with pytest.raises(type(error)) as raised:
        client.post(
            f"/api/v1/management/renewals/{REQUEST_ID}/{operation}",
            json={"decision": "approved", "note": "Reviewed actual handover"},
            headers=HEADERS,
        )

    assert raised.value is error
    assert database.state == before


def test_successful_legacy_proof_review_retains_existing_activation_contract(
    monkeypatch,
):
    database = WorkflowDatabase(None)
    database.prepare_proof_review()
    client = make_client(monkeypatch, database)

    response = client.post(
        f"/api/v1/management/renewals/{REQUEST_ID}/proof-review",
        json={"decision": "approved", "note": "Reviewed actual handover"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert set(response.json()["data"]) == {"request"}
    assert response.json()["data"]["request"]["activation_status"] == "active"
    assert database.state["audits"] == [
        "renewal.handover_proof.approved",
        "renewal.activation.completed",
    ]


def test_terms_constraint_rolls_back_financial_approval_and_signer_changes(monkeypatch):
    database = WorkflowDatabase(cif_conflict())
    database.state["row"].update(status="pending", collector_recommendation="recommend")
    before = deepcopy(database.state)
    client = make_client(monkeypatch, database)

    response = client.post(
        f"/api/v1/management/renewals/{REQUEST_ID}/terms",
        json={
            "decision": "approved",
            "approved_principal": "100.00",
            "office_processing_required": True,
        },
        headers=HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "client_cif_new_credit_not_ready"
    assert response.headers["cache-control"] == "no-store"
    assert database.state == before
