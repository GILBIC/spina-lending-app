from __future__ import annotations

import importlib
from contextlib import contextmanager
from uuid import UUID

import pytest


ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
CIF_ID = UUID("33333333-3333-4333-8333-333333333333")
INFORMATION = {
    "full_name": "Synthetic CIF Borrower",
    "phone_number": "09170000000",
    "email": None,
    "present_address": "Synthetic office review address",
}
CORRECTED = {**INFORMATION, "phone_number": "09171111111"}
REASON = "Applicant corrected a typing error during office review."
DRAFT = {
    **INFORMATION,
    "id": CIF_ID,
    "client_id": CLIENT_ID,
    "version_number": 1,
    "is_current": True,
    "status": "draft",
    "national_id_egov_evidence_reference": "PRIVATE-NATIONAL-REF",
    "tin_id_egov_evidence_reference": "PRIVATE-TIN-REF",
    "meralco_bill_evidence_reference": "PRIVATE-RESIDENCE-REF",
    "baseline_face_scan_evidence_reference": None,
    "baseline_liveness_status": "pending",
    "activated_at": None,
    "expires_at": None,
    "review_due_at": None,
    "reverification_required_at": None,
    "reverification_reason": None,
}


class AuditFailure(RuntimeError):
    pass


class Cursor:
    def __init__(self, responses, *, fail_audit=False):
        self.responses = list(responses)
        self.executions = []
        self.fail_audit = fail_audit

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, query, parameters=()):
        normalized = " ".join(query.lower().split())
        self.executions.append((normalized, parameters))
        if self.fail_audit and "insert into core.audit_logs" in normalized:
            raise AuditFailure("Synthetic audit storage failure")

    def fetchone(self):
        assert self.responses, "Unexpected extra database read"
        return self.responses.pop(0)


class Connection:
    def __init__(self, responses, *, fail_audit=False):
        self.reader = Cursor(responses, fail_audit=fail_audit)
        self.committed = False
        self.rolled_back = False

    def cursor(self, **kwargs):
        return self.reader


@contextmanager
def _transaction(connection):
    try:
        yield connection
    except BaseException:
        connection.rolled_back = True
        raise
    else:
        connection.committed = True


def _repository(monkeypatch, responses, *, fail_audit=False):
    module = importlib.import_module("gilbic_backend.client_cif_repository")
    connection = Connection(responses, fail_audit=fail_audit)
    monkeypatch.setattr(module, "open_connection", lambda: _transaction(connection))
    return module, module.PostgresClientCifRepository(), connection


def _correct(repository, **overrides):
    arguments = {
        "actor_user_id": ACTOR_ID,
        "client_id": CLIENT_ID,
        "cif_version_id": CIF_ID,
        "expected_information": dict(INFORMATION),
        "corrected_information": dict(CORRECTED),
        "reason": REASON,
    }
    arguments.update(overrides)
    return repository.correct_draft_information(**arguments)


def _writes(connection):
    return [
        (query, params) for query, params in connection.reader.executions
        if query.startswith(("insert ", "update ", "delete ", "truncate "))
    ]


def test_correction_updates_only_unconfirmed_current_draft_with_audit(monkeypatch):
    updated = {**DRAFT, **CORRECTED}
    module, repository, connection = _repository(monkeypatch, [DRAFT, None, updated])

    record = _correct(repository)

    assert isinstance(record, module.ClientCifVersion)
    assert record.id == CIF_ID and record.client_id == CLIENT_ID
    assert record.version_number == 1 and record.status == "draft"
    assert record.phone_number == CORRECTED["phone_number"]
    assert record.baseline_liveness_status == "pending"
    assert record.national_id_egov_evidence_reference == DRAFT["national_id_egov_evidence_reference"]
    first_query, first_params = connection.reader.executions[0]
    assert "for update" in first_query
    assert "cif.is_current = true" in first_query and "cif.status = 'draft'" in first_query
    assert "client.status = 'inactive'" in first_query
    assert "applicant.status = 'eligible_for_cif'" in first_query
    assert "applicant.promoted_client_id = cif.client_id" in first_query
    assert "cif.id = %s" in first_query and "cif.client_id = %s" in first_query
    assert CIF_ID in first_params and CLIENT_ID in first_params
    assert any("from lending.client_cif_review_confirmations" in q
               for q, _ in connection.reader.executions)
    writes = _writes(connection)
    assert len(writes) == 2
    update, audit = writes
    assert update[0].startswith("update lending.client_cif_versions ")
    assignments = update[0].split(" set ", 1)[1].split(" where ", 1)[0]
    for column in INFORMATION:
        assert f"{column} = %s" in assignments
    assert "updated_at = now()" in assignments
    for forbidden in ("status", "version_number", "is_current", "evidence", "liveness", "activated"):
        assert forbidden not in assignments
    assert audit[0].startswith("insert into core.audit_logs ")
    audit_text = str(audit)
    assert "client_cif.draft_information_corrected" in audit_text
    assert "client_cif_version" in audit_text
    assert ACTOR_ID in audit[1] and CIF_ID in audit[1]
    assert "phone_number" in audit_text and REASON in audit_text
    assert "PRIVATE-" not in audit_text
    assert connection.committed and not connection.rolled_back


@pytest.mark.parametrize("field", tuple(INFORMATION))
def test_stale_review_snapshot_cannot_overwrite_newer_draft_values(monkeypatch, field):
    current = {**DRAFT, field: "Changed since the displayed review"}
    module, repository, connection = _repository(monkeypatch, [current, None])

    with pytest.raises(module.ClientCifConflict):
        _correct(repository)

    assert _writes(connection) == []


def test_missing_eligible_draft_cannot_create_or_modify_anything(monkeypatch):
    module, repository, connection = _repository(monkeypatch, [None])
    with pytest.raises(module.ClientCifConflict):
        _correct(repository)
    assert _writes(connection) == []


def test_already_confirmed_draft_is_not_edited_in_place(monkeypatch):
    confirmation = {"id": UUID("44444444-4444-4444-8444-444444444444")}
    module, repository, connection = _repository(monkeypatch, [DRAFT, confirmation])
    with pytest.raises(module.ClientCifConflict):
        _correct(repository)
    # A later correction needs a separate review/version cycle, not this path.
    assert _writes(connection) == []


def test_no_change_does_not_write_or_add_a_spurious_audit(monkeypatch):
    module, repository, connection = _repository(monkeypatch, [DRAFT, None])
    record = _correct(repository, corrected_information=dict(INFORMATION))
    assert isinstance(record, module.ClientCifVersion)
    assert record.id == CIF_ID and record.phone_number == INFORMATION["phone_number"]
    assert _writes(connection) == []


def test_audit_failure_propagates_out_of_the_same_transaction(monkeypatch):
    module, repository, connection = _repository(
        monkeypatch, [DRAFT, None, {**DRAFT, **CORRECTED}], fail_audit=True
    )
    with pytest.raises(AuditFailure):
        _correct(repository)
    assert connection.rolled_back and not connection.committed
    # This checks transaction control flow; actual rollback needs PostgreSQL proof.


@pytest.mark.parametrize("argument", ["expected_information", "corrected_information"])
def test_repository_rejects_fields_outside_the_information_contract(monkeypatch, argument):
    module, repository, connection = _repository(monkeypatch, [])
    with pytest.raises(ValueError):
        _correct(repository, **{argument: {**INFORMATION, "status": "active"}})
    assert _writes(connection) == []


@pytest.mark.parametrize("field", ["full_name", "phone_number", "present_address"])
def test_blank_required_information_is_rejected_without_writes(monkeypatch, field):
    module, repository, connection = _repository(monkeypatch, [])
    with pytest.raises(ValueError):
        _correct(repository, corrected_information={**CORRECTED, field: "   "})
    assert _writes(connection) == []


def test_correction_requires_nonblank_reason_without_writes(monkeypatch):
    module, repository, connection = _repository(monkeypatch, [])
    with pytest.raises(ValueError):
        _correct(repository, reason="   ")
    assert _writes(connection) == []
