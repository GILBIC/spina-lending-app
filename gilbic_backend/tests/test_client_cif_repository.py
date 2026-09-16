from __future__ import annotations

import importlib
from contextlib import contextmanager
from datetime import datetime, timezone
from types import ModuleType
from uuid import UUID

import pytest


ACTOR_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
APPLICANT_ID = UUID("33333333-3333-4333-8333-333333333333")
CIF_ID = UUID("44444444-4444-4444-8444-444444444444")


ELIGIBLE_SOURCE = {
    "applicant_id": APPLICANT_ID,
    "client_id": CLIENT_ID,
    "client_status": "inactive",
    "full_name": "Maria Santos",
    "phone_number": "09171234567",
    "email": "maria@example.com",
    "present_address": "123 Test Street, Rizal",
    "national_id_egov_evidence_reference": "FAKE-NATIONAL-ID",
    "tin_id_egov_evidence_reference": "FAKE-TIN-ID",
    "meralco_bill_evidence_reference": "FAKE-MERALCO",
}

DRAFT_ROW = {
    "id": CIF_ID,
    "client_id": CLIENT_ID,
    "version_number": 1,
    "is_current": True,
    "status": "draft",
    "full_name": "Maria Santos",
    "phone_number": "09171234567",
    "email": "maria@example.com",
    "present_address": "123 Test Street, Rizal",
    "national_id_egov_evidence_reference": "FAKE-NATIONAL-ID",
    "tin_id_egov_evidence_reference": "FAKE-TIN-ID",
    "meralco_bill_evidence_reference": "FAKE-MERALCO",
    "baseline_face_scan_evidence_reference": None,
    "baseline_liveness_status": "pending",
    "activated_at": None,
    "expires_at": None,
    "review_due_at": None,
    "reverification_required_at": None,
    "reverification_reason": None,
}

READY_DRAFT_ROW = {
    **DRAFT_ROW,
    "baseline_face_scan_evidence_reference": "FAKE-FACE",
    "baseline_liveness_status": "passed",
}

FAILED_LIVENESS_ROW = {
    **DRAFT_ROW,
    "baseline_face_scan_evidence_reference": "FAKE-FACE-FAILED",
    "baseline_liveness_status": "failed",
}

ACTIVE_ROW = {
    **READY_DRAFT_ROW,
    "status": "active",
    "activated_at": datetime(2026, 9, 11, 0, 0, tzinfo=timezone.utc),
    "expires_at": datetime(2031, 9, 11, 0, 0, tzinfo=timezone.utc),
    "review_due_at": datetime(2031, 6, 13, 0, 0, tzinfo=timezone.utc),
}


class FakeCursor:
    def __init__(self, responses: list[dict[str, object] | None]) -> None:
        self.responses = list(responses)
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, query: str, parameters: tuple[object, ...] = ()) -> None:
        self.executions.append((query, parameters))

    def fetchone(self):
        if not self.responses:
            raise AssertionError("Unexpected fetchone() call")
        return self.responses.pop(0)


class FakeConnection:
    def __init__(self, responses: list[dict[str, object] | None]) -> None:
        self.cursor_instance = FakeCursor(responses)

    def cursor(self, **kwargs):
        return self.cursor_instance


@contextmanager
def fake_open_connection(connection: FakeConnection):
    yield connection


def _load_repository_module() -> ModuleType:
    return importlib.import_module("gilbic_backend.client_cif_repository")


def _wire_repository(monkeypatch: pytest.MonkeyPatch, connection: FakeConnection):
    module = _load_repository_module()
    monkeypatch.setattr(
        module,
        "open_connection",
        lambda: fake_open_connection(connection),
    )
    return module, module.PostgresClientCifRepository()


def _sql(connection: FakeConnection) -> list[str]:
    return [" ".join(query.lower().split()) for query, _ in connection.cursor_instance.executions]


def test_begin_draft_requires_eligible_promoted_inactive_client_and_seeds_version_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection([ELIGIBLE_SOURCE, None, DRAFT_ROW])
    module, repository = _wire_repository(monkeypatch, connection)

    record = repository.begin_draft(
        actor_user_id=ACTOR_USER_ID,
        client_id=CLIENT_ID,
    )

    assert isinstance(record, module.ClientCifVersion)
    assert record.id == CIF_ID
    assert record.client_id == CLIENT_ID
    assert record.version_number == 1
    assert record.status == "draft"
    assert record.is_current is True
    assert record.baseline_liveness_status == "pending"

    queries = _sql(connection)
    assert "from lending.client_onboarding_applicants applicant" in queries[0]
    assert "join lending.clients client on client.id = applicant.promoted_client_id" in queries[0]
    assert "applicant.promoted_client_id = %s" in queries[0]
    assert "applicant.status = 'eligible_for_cif'" in queries[0]
    assert "client.status = 'inactive'" in queries[0]
    assert "for update" in queries[0]

    insert_query = next(
        query for query in queries if "insert into lending.client_cif_versions" in query
    )
    for expected in (
        "client_id",
        "version_number",
        "is_current",
        "status",
        "full_name",
        "phone_number",
        "email",
        "present_address",
        "national_id_egov_evidence_reference",
        "tin_id_egov_evidence_reference",
        "meralco_bill_evidence_reference",
        "created_by_user_id",
    ):
        assert expected in insert_query

    combined = "\n".join(queries)
    for forbidden in (
        "insert into core.users",
        "insert into lending.loans",
        "insert into lending.loan_contract",
        "insert into lending.loan_disbursement",
        "insert into accounting.journal",
        "insert into lending.loan_contract_installments",
    ):
        assert forbidden not in combined


def test_begin_draft_rejects_client_without_authoritative_eligible_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection([None])
    module, repository = _wire_repository(monkeypatch, connection)

    with pytest.raises(module.ClientCifConflict):
        repository.begin_draft(
            actor_user_id=ACTOR_USER_ID,
            client_id=CLIENT_ID,
        )

    queries = _sql(connection)
    assert len(queries) == 1
    assert "insert into lending.client_cif_versions" not in queries[0]


def test_begin_draft_is_idempotent_when_current_draft_already_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection([ELIGIBLE_SOURCE, DRAFT_ROW])
    module, repository = _wire_repository(monkeypatch, connection)

    record = repository.begin_draft(
        actor_user_id=ACTOR_USER_ID,
        client_id=CLIENT_ID,
    )

    assert isinstance(record, module.ClientCifVersion)
    assert record.id == CIF_ID
    assert record.version_number == 1
    assert record.status == "draft"

    queries = _sql(connection)
    assert sum("insert into lending.client_cif_versions" in query for query in queries) == 0


def test_record_baseline_live_face_updates_only_the_current_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection([READY_DRAFT_ROW])
    module, repository = _wire_repository(monkeypatch, connection)

    record = repository.record_baseline_live_face(
        client_id=CLIENT_ID,
        evidence_reference="  FAKE-FACE  ",
        liveness_status="passed",
    )

    assert isinstance(record, module.ClientCifVersion)
    assert record.status == "draft"
    assert record.baseline_face_scan_evidence_reference == "FAKE-FACE"
    assert record.baseline_liveness_status == "passed"

    queries = _sql(connection)
    assert len(queries) == 1
    assert "update lending.client_cif_versions" in queries[0]
    assert "baseline_face_scan_evidence_reference = %s" in queries[0]
    assert "baseline_liveness_status = %s" in queries[0]
    assert "where client_id = %s" in queries[0]
    assert "is_current = true" in queries[0]
    assert "status = 'draft'" in queries[0]
    assert "update lending.clients" not in queries[0]
    parameters = connection.cursor_instance.executions[0][1]
    assert parameters[:2] == ("FAKE-FACE", "passed")


def test_record_baseline_live_face_rejects_blank_evidence_without_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection([])
    module, repository = _wire_repository(monkeypatch, connection)

    with pytest.raises(ValueError):
        repository.record_baseline_live_face(
            client_id=CLIENT_ID,
            evidence_reference="   ",
            liveness_status="passed",
        )

    assert connection.cursor_instance.executions == []


@pytest.mark.parametrize("draft_row", [DRAFT_ROW, FAILED_LIVENESS_ROW])
def test_activate_current_requires_passed_liveness_and_face_evidence(
    monkeypatch: pytest.MonkeyPatch,
    draft_row: dict[str, object],
) -> None:
    connection = FakeConnection([draft_row])
    module, repository = _wire_repository(monkeypatch, connection)

    with pytest.raises(module.ClientCifConflict):
        repository.activate_current(
            actor_user_id=ACTOR_USER_ID,
            client_id=CLIENT_ID,
        )

    queries = _sql(connection)
    assert len(queries) == 1
    assert "from lending.client_cif_versions cif" in queries[0]
    assert "join lending.client_onboarding_applicants applicant" in queries[0]
    assert "applicant.status = 'eligible_for_cif'" in queries[0]
    assert "for update" in queries[0]
    assert "update lending.client_cif_versions" not in queries[0]
    assert "update lending.clients" not in queries[0]


def test_activate_current_marks_cif_and_existing_client_active_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection([READY_DRAFT_ROW, ACTIVE_ROW])
    module, repository = _wire_repository(monkeypatch, connection)

    record = repository.activate_current(
        actor_user_id=ACTOR_USER_ID,
        client_id=CLIENT_ID,
    )

    assert isinstance(record, module.ClientCifVersion)
    assert record.status == "active"
    assert record.activated_at == ACTIVE_ROW["activated_at"]
    assert record.expires_at == ACTIVE_ROW["expires_at"]
    assert record.review_due_at == ACTIVE_ROW["review_due_at"]

    queries = _sql(connection)
    cif_update = next(
        query for query in queries if "update lending.client_cif_versions" in query
    )
    assert "status = 'active'" in cif_update
    assert "activated_at = now()" in cif_update
    assert "expires_at = now() + interval '5 years'" in cif_update
    assert "review_due_at = now() + interval '5 years' - interval '90 days'" in cif_update
    assert "activated_by_user_id = %s" in cif_update

    client_update = next(query for query in queries if "update lending.clients" in query)
    assert "status = 'active'" in client_update
    assert "where id = %s" in client_update
    assert "status = 'inactive'" in client_update

    combined = "\n".join(queries)
    for forbidden in (
        "insert into core.users",
        "insert into lending.loans",
        "insert into lending.loan_contract",
        "insert into lending.loan_disbursement",
        "insert into accounting.journal",
        "insert into lending.loan_contract_installments",
    ):
        assert forbidden not in combined


def test_activate_current_is_idempotent_after_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection([ACTIVE_ROW])
    module, repository = _wire_repository(monkeypatch, connection)

    record = repository.activate_current(
        actor_user_id=ACTOR_USER_ID,
        client_id=CLIENT_ID,
    )

    assert isinstance(record, module.ClientCifVersion)
    assert record.status == "active"

    queries = _sql(connection)
    assert len(queries) == 1
    assert "update lending.client_cif_versions" not in queries[0]
    assert "update lending.clients" not in queries[0]
