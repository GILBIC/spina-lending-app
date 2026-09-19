from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import errors

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.employee_authorization import EmployeeAccessDenied
from gilbic_backend.employee_operations import EmployeeConflict
from gilbic_backend.employee_operations_api import (
    create_employee_operations_router,
    employee_operations_context,
    employee_operations_repository_dependency,
)


class Repository:
    def __init__(self):
        self.error = None
        self.commands = []

    def execute(self, *, actor, command):
        if self.error:
            raise self.error
        self.commands.append(command)
        return {
            "request_id": str(command.request_id),
            "id": str(command.id),
            "version": 1,
            "status": "accepted",
            "replayed": False,
            "message": "Recorded",
        }

    def workspace(self, *, actor, request_id):
        return {
            "actor": {"user_id": str(actor.user_id)},
            "last_result": {"request_id": str(request_id)} if request_id else None,
        }


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(create_employee_operations_router())
    actor = AccountContext(
        uuid4(),
        uuid4(),
        "synthetic",
        None,
        "Synthetic",
        "active",
        ("collector",),
        (),
        True,
        uuid4(),
    )
    repository = Repository()
    app.dependency_overrides[employee_operations_context] = lambda: actor
    app.dependency_overrides[employee_operations_repository_dependency] = lambda: (
        repository
    )
    with TestClient(app) as client:
        yield client, actor, repository


def request_payload(actor):
    return {
        "action": "advance_request",
        "request_id": str(uuid4()),
        "id": str(uuid4()),
        "expected_version": 0,
        "employee_id": str(actor.user_id),
        "amount": "100.00",
        "reason": "Synthetic principal-only request",
        "installments": [{"due_date": "2026-10-03", "amount": "100.00"}],
        "employee_acknowledgment": "I agree",
        "payroll_authorization": "Reviewed authorized terms",
    }


def test_strict_finite_command_money_and_nested_shape(client):
    http, actor, repo = client
    payload = request_payload(actor)
    assert (
        http.post("/api/v1/employee-operations/actions", json=payload).status_code
        == 200
    )
    assert (
        http.post(
            "/api/v1/employee-operations/actions", json=dict(payload, amount=100)
        ).status_code
        == 422
    )
    assert (
        http.post(
            "/api/v1/employee-operations/actions",
            json=dict(payload, action="generic_update"),
        ).status_code
        == 422
    )
    assert (
        http.post(
            "/api/v1/employee-operations/actions",
            json=dict(payload, staff_manager=True),
        ).status_code
        == 422
    )
    bad = dict(payload, installments=[dict(payload["installments"][0], interest="10")])
    assert http.post("/api/v1/employee-operations/actions", json=bad).status_code == 422
    assert len(repo.commands) == 1


@pytest.mark.parametrize(
    "error,code",
    [
        (EmployeeAccessDenied("Not authorized"), 403),
        (EmployeeConflict("Stale"), 409),
        (errors.RaiseException("private SQL detail"), 409),
        (errors.UniqueViolation("private SQL detail"), 409),
    ],
)
def test_domain_denial_and_database_validation_are_controlled(client, error, code):
    http, actor, repo = client
    repo.error = error
    response = http.post(
        "/api/v1/employee-operations/actions", json=request_payload(actor)
    )
    assert response.status_code == code and "private SQL" not in response.text


def test_uncertain_action_readback_and_timestamp_validation(client):
    http, actor, repo = client
    request_id = uuid4()
    result = http.get(
        "/api/v1/employee-operations/workspace", params={"request_id": str(request_id)}
    )
    assert result.json()["last_result"]["request_id"] == str(request_id)
    payload = {
        "action": "attendance_record",
        "request_id": str(uuid4()),
        "id": str(uuid4()),
        "expected_version": 0,
        "employee_id": str(actor.user_id),
        "device_id": str(actor.registered_device_id),
        "captured_at": "2026-09-20T06:00:00",
        "event_type": "clock_in",
        "previous_event_id": None,
        "sequence": 1,
        "offline": True,
    }
    assert (
        http.post("/api/v1/employee-operations/actions", json=payload).status_code
        == 422
    )
