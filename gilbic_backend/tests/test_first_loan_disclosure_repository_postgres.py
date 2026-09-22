"""Task 3 service proofs on the existing explicitly disposable database.

Only connection acquisition and deliberate file-failure injection are replaced.
Source guards, SQL, transactions, private bytes and immutable rows stay real.
"""

from __future__ import annotations

import base64
import hashlib
from contextlib import contextmanager
from copy import deepcopy
from importlib import import_module
from uuid import uuid4

import pytest
import test_first_loan_disclosure_register_postgres as register_proof
from first_loan_disclosure_fixtures import SUPPORT
from gilbic_backend.first_loan_disclosure import (
    DisclosureReviewRequest,
    public_financial_snapshot,
)
from gilbic_backend.first_loan_repository import (
    FirstLoanAccessDenied,
    FirstLoanConflict,
)
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore

runtime_url = register_proof.runtime_url
connection = register_proof.connection
private_fixture_configuration = register_proof.private_fixture_configuration
pytestmark = register_proof.pytestmark
MODULE = "gilbic_backend.first_loan_disclosure_repository"


def _setup(connection, monkeypatch):
    try:
        module = import_module(MODULE)
    except ModuleNotFoundError as error:
        if error.name != MODULE:
            raise
        pytest.fail(
            "R1 Task 3: protected disclosure repository is not implemented",
            pytrace=False,
        )
    _, case = register_proof._case(connection, monkeypatch)

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", acquire)
    return module.PostgresFirstLoanDisclosureRepository(), case


def _actor(case):
    return {
        "actor_user_id": case["actor"],
        "registered_device_id": case["device"],
    }


def _context(repository, case, payload):
    return repository.context(
        **_actor(case),
        **{
            name: payload[name]
            for name in (
                "application_version_id",
                "cif_version_id",
                "dst_rule_id",
                "grt_rule_id",
                "terms",
            )
        },
    )


def _payload(connection, repository, case):
    payload = register_proof._values(connection, case)["input_snapshot"].obj
    payload["support_base64"] = base64.b64encode(SUPPORT).decode("ascii")
    payload["expected_context_digest"] = _context(repository, case, payload)[
        "context_digest"
    ]
    return payload


def _record(repository, case, payload):
    return repository.record(**_actor(case), request=payload)


def _row(connection, calculation_id):
    return connection.execute(
        "select * from lending.first_loan_disclosure_calculations where id = %s",
        (calculation_id,),
    ).fetchone()


def _state(connection):
    rows = connection.execute(
        "select * from lending.first_loan_disclosure_calculations order by id"
    ).fetchall()
    files = {
        path.name: path.read_bytes()
        for path in PrivateEvidenceStore().root.glob("*.bin")
    }
    return rows, register_proof._counts(connection), files


def _employee(connection, case):
    connection.execute(
        "delete from core.user_roles where user_id = %s", (case["actor"],)
    )
    role = connection.execute(
        "insert into core.user_roles (user_id, role_id) "
        "select %s, id from core.roles where code = 'employee' returning role_id",
        (case["actor"],),
    ).fetchone()
    assert role is not None
    # Explicit disposable fixture permission, never a production role change.
    connection.execute(
        "insert into core.role_permissions (role_id, permission_code) "
        "values (%s, 'client_onboarding.requirement.review') "
        "on conflict do nothing",
        (role["role_id"],),
    )


def test_context_is_source_bound_without_recording_a_review(connection, monkeypatch):
    repository, case = _setup(connection, monkeypatch)
    payload = register_proof._values(connection, case)["input_snapshot"].obj
    before = _state(connection)
    context = _context(repository, case, payload)
    assert context["source"]["application_id"] == str(case["app"].application_id)
    assert context["source"]["application_version_id"] == str(case["app"].id)
    assert context["source"]["client_id"] == str(case["client"])
    assert context["source"]["cif_version_id"] == str(case["cif"])
    assert len(context["context_digest"]) == 64
    assert _context(repository, case, payload) == context
    assert _state(connection) == before


def test_record_retains_exact_support_without_financial_or_generic_evidence_writes(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    before = _state(connection)
    record = _record(repository, case, payload)
    saved = _row(connection, record["id"])
    request = DisclosureReviewRequest.model_validate(payload)
    assert saved["request_id"] == request.request_id
    assert saved["input_snapshot"] == request.model_dump(
        mode="json", exclude={"support_base64"}
    )
    assert saved["support_sha256"] == hashlib.sha256(SUPPORT).hexdigest()
    assert saved["support_byte_count"] == len(SUPPORT)
    assert saved["reviewed_by_user_id"] == case["actor"]
    assert saved["reviewed_device_id"] == case["device"]
    assert record["version_number"] == 1
    assert record["review_digest"] == saved["review_digest"]
    assert record["financial_snapshot"] == public_financial_snapshot(payload)
    assert (
        not {
            "support_storage_key",
            "input_snapshot",
            "source_snapshot",
            "rule_snapshot",
            "support_base64",
            "ready",
            "approved",
        }
        & record.keys()
    )
    assert repository.get(**_actor(case), calculation_id=record["id"]) == record
    metadata, content = repository.support(**_actor(case), calculation_id=record["id"])
    assert content == SUPPORT
    assert metadata["content_sha256"] == saved["support_sha256"]
    assert "storage_key" not in metadata and "path" not in metadata
    after = _state(connection)
    assert len(after[0]) == len(before[0]) + 1
    assert after[1] == before[1]
    assert len(after[2]) == len(before[2]) + 1


def test_identical_retry_returns_original_after_successor_without_writes(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    first = _record(repository, case, payload)
    successor = deepcopy(payload)
    successor.update(request_id=str(uuid4()), supersedes_calculation_id=first["id"])
    second = _record(repository, case, successor)
    assert second["id"] != first["id"] and second["version_number"] == 2
    before = _state(connection)
    assert _record(repository, case, payload) == first
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["rationale", "support", "context", "predecessor"])
def test_changed_request_reuse_never_creates_a_second_record(
    connection, monkeypatch, change
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    _record(repository, case, payload)
    before = _state(connection)
    changed = deepcopy(payload)
    if change == "rationale":
        changed["review_rationale"] = "Different synthetic Management review."
    elif change == "support":
        changed["support_base64"] = base64.b64encode(
            SUPPORT.replace(b"SUPPORT", b"REVISED")
        ).decode("ascii")
    elif change == "context":
        changed["expected_context_digest"] = "c" * 64
    else:
        changed["supersedes_calculation_id"] = str(uuid4())
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, changed)
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["digest", "application", "cif"])
def test_stale_or_foreign_context_has_no_file_or_database_side_effects(
    connection, monkeypatch, change
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    if change == "digest":
        payload["expected_context_digest"] = "c" * 64
    elif change == "application":
        payload["application_version_id"] = str(uuid4())
    else:
        payload["cif_version_id"] = str(uuid4())
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, payload)
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["employee", "permission", "device"])
def test_only_authorized_management_can_record(connection, monkeypatch, change):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    if change == "employee":
        _employee(connection, case)
    elif change == "permission":
        connection.execute(
            "delete from core.role_permissions "
            "where permission_code = 'lending.first_loan.approve'"
        )
    else:
        case["device"] = uuid4()
    before = _state(connection)
    with pytest.raises(FirstLoanAccessDenied):
        _record(repository, case, payload)
    assert _state(connection) == before


def test_office_can_read_financial_values_but_not_calculation_file(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    record = _record(repository, case, payload)
    _employee(connection, case)
    before = _state(connection)
    assert repository.get(**_actor(case), calculation_id=record["id"]) == record
    with pytest.raises(FirstLoanAccessDenied):
        repository.support(**_actor(case), calculation_id=record["id"])
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["missing", "corrupt"])
def test_private_support_read_checks_actual_retained_bytes(
    connection, monkeypatch, change
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    record = _record(repository, case, payload)
    saved = _row(connection, record["id"])
    path = PrivateEvidenceStore().root / f"{saved['support_storage_key'].hex}.bin"
    if change == "missing":
        path.unlink()
    else:
        content = path.read_bytes()
        path.write_bytes(content.replace(b"SUPPORT", b"CORRUPT"))
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.support(**_actor(case), calculation_id=record["id"])
    assert _state(connection) == before


def test_next_review_requires_explicit_current_predecessor(connection, monkeypatch):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    _record(repository, case, payload)
    payload["request_id"] = str(uuid4())
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, payload)
    assert _state(connection) == before


def test_invalid_file_bytes_cannot_become_a_retained_review(connection, monkeypatch):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    payload["support_base64"] = base64.b64encode(b"not a PDF").decode("ascii")
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, payload)
    assert _state(connection) == before
