from __future__ import annotations

import importlib
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID

import pytest


CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")
CIF_ID = UUID("44444444-4444-4444-8444-444444444444")
CIF_ROW = {
    "id": CIF_ID,
    "client_id": CLIENT_ID,
    "version_number": 1,
    "is_current": True,
    "status": "draft",
    "full_name": "Synthetic CIF Borrower",
    "phone_number": "09170000000",
    "email": None,
    "present_address": "Synthetic office review address",
    "national_id_egov_evidence_reference": "SYNTHETIC-PRIVATE-NATIONAL-ID",
    "tin_id_egov_evidence_reference": "SYNTHETIC-PRIVATE-TIN-ID",
    "meralco_bill_evidence_reference": "SYNTHETIC-PRIVATE-RESIDENCE",
    "baseline_face_scan_evidence_reference": None,
    "baseline_liveness_status": "pending",
    "activated_at": None,
    "expires_at": None,
    "review_due_at": None,
    "reverification_required_at": None,
    "reverification_reason": None,
}


class ReadCursor:
    def __init__(self, row):
        self.row = row
        self.executions: list[tuple[str, tuple[object, ...]]] = []
        self.fetches = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, query, parameters=()):
        self.executions.append((" ".join(query.lower().split()), tuple(parameters)))

    def fetchone(self):
        self.fetches += 1
        assert self.fetches == 1, "Review should read one authoritative current CIF."
        return self.row


class ReadConnection:
    def __init__(self, row):
        self.reader = ReadCursor(row)

    def cursor(self, **kwargs):
        return self.reader


@contextmanager
def _open(connection):
    yield connection


def _repository(monkeypatch, row):
    module = importlib.import_module("gilbic_backend.client_cif_repository")
    connection = ReadConnection(row)
    monkeypatch.setattr(module, "open_connection", lambda: _open(connection))
    return module, module.PostgresClientCifRepository(), connection.reader


def _assert_read_only(reader: ReadCursor) -> str:
    assert len(reader.executions) == 1
    query, parameters = reader.executions[0]
    assert parameters == (CLIENT_ID,)
    assert query.startswith("select ")
    for forbidden in ("insert ", "update ", "delete ", "truncate ", "for share"):
        assert forbidden not in query
    return query


@pytest.mark.parametrize("cif_status", ["draft", "active"])
def test_review_reads_current_eligible_cif_without_creating_or_activating_it(
    monkeypatch: pytest.MonkeyPatch, cif_status: str
) -> None:
    row = {**CIF_ROW, "status": cif_status}
    if cif_status == "active":
        row.update(
            baseline_face_scan_evidence_reference="SYNTHETIC-PRIVATE-FACE",
            baseline_liveness_status="passed",
            activated_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
            expires_at=datetime(2031, 9, 15, tzinfo=timezone.utc),
            review_due_at=datetime(2031, 6, 17, tzinfo=timezone.utc),
        )
    module, repository, reader = _repository(monkeypatch, row)

    record = repository.get_review_summary(client_id=CLIENT_ID)

    assert isinstance(record, module.ClientCifVersion)
    assert record.id == CIF_ID
    assert record.client_id == CLIENT_ID
    assert record.version_number == 1
    assert record.status == cif_status
    assert record.full_name == row["full_name"]
    assert record.phone_number == row["phone_number"]
    assert record.email is None
    assert record.present_address == row["present_address"]
    # Viewing a draft is allowed before liveness; it is not confirmation/activation.
    assert record.baseline_liveness_status == row["baseline_liveness_status"]
    query = _assert_read_only(reader)
    assert "from lending.client_cif_versions cif" in query
    assert "join lending.client_onboarding_applicants applicant" in query
    assert "applicant.promoted_client_id = cif.client_id" in query
    assert "join lending.clients client" in query
    assert "client.id = cif.client_id" in query
    assert "cif.client_id = %s" in query
    assert "cif.is_current = true" in query
    assert "cif.status in ('draft', 'active')" in query
    assert "client.status in ('inactive', 'active')" in query
    assert "applicant.status = 'eligible_for_cif'" in query
    assert "for update" not in query


def test_review_without_authoritative_current_cif_fails_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, repository, reader = _repository(monkeypatch, None)

    with pytest.raises(module.ClientCifConflict):
        repository.get_review_summary(client_id=CLIENT_ID)

    _assert_read_only(reader)
