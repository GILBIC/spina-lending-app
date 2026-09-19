"""Exact private signed privacy snapshots on the guarded disposable PostgreSQL DB."""

from contextlib import contextmanager
import json
from uuid import UUID, uuid4

import psycopg
import pytest

from gilbic_backend import privacy_record_repository as privacy
from gilbic_backend import office_review_evidence_repository as evidence
from office_review_evidence_test_support import (
    PDF,
    private_evidence_root as private_evidence_root,
)
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    connection as connection,
    runtime_url as runtime_url,
    _summary_state,
)
from test_loan_application_repository_postgres import _seed
from test_privacy_records import configure

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)


def repositories(connection, monkeypatch):
    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(privacy, "open_connection", acquire)
    monkeypatch.setattr(evidence, "open_connection", acquire)
    return (
        privacy.PostgresPrivacyRecordRepository(),
        evidence.PostgresOfficeReviewEvidenceRepository(),
    )


def source(case, optional=False):
    return dict(
        actor_user_id=case["actor"],
        client_id=case["client"],
        cif_version_id=case["cif"],
        optional_service_communications=optional,
    )


def captured(repository, case, optional=False):
    arguments = {**source(case, optional), "purpose": "privacy_acknowledgment"}
    context = repository.get_context(**arguments)
    return repository.capture(
        **arguments,
        expected_snapshot_sha256=context["snapshot_sha256"],
        request_id=uuid4(),
        content=PDF,
        media_type="application/pdf",
    )


def state(connection, case):
    return {
        "source": _summary_state(connection, case),
        "privacy": connection.execute(
            "select * from lending.client_privacy_acknowledgments order by id"
        ).fetchall(),
        "evidence": connection.execute(
            "select * from lending.office_review_evidence order by id"
        ).fetchall(),
        "audit": connection.execute(
            "select * from core.audit_logs order by id"
        ).fetchall(),
    }


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("optional", [False, True])
def test_exact_optional_choice_and_document_versions_are_immutable_and_retry_is_read_only(
    connection, monkeypatch, tmp_path, role, optional
):
    configure(tmp_path, monkeypatch)
    repository, captures = repositories(connection, monkeypatch)
    case = _seed(connection, role)
    context = repository.context(**source(case, optional))
    record = captured(captures, case, optional)
    saved = repository.confirm(
        **source(case, optional), evidence_reference=record.evidence_reference
    )
    row = connection.execute(
        "select * from lending.client_privacy_acknowledgments where id=%s",
        (UUID(saved["id"]),),
    ).fetchone()
    assert row["optional_service_communications"] is optional
    assert (
        row["review_snapshot"] == context["review_snapshot"] == record.review_snapshot
    )
    assert (
        row["evidence_id"] == record.id
        and row["acknowledged_by_user_id"] == case["actor"]
    )
    assert saved["notice_sha256"] == context["review_snapshot"]["notice"]["sha256"]
    assert saved["consent_version"] == context["review_snapshot"]["consent"]["version"]
    before = state(connection, case)
    assert (
        repository.confirm(
            **source(case, optional), evidence_reference=record.evidence_reference
        )
        == saved
    )
    assert repository.context(**source(case, optional))["acknowledgment"] == saved
    assert state(connection, case) == before
    for sql in (
        "update lending.client_privacy_acknowledgments set optional_service_communications=not optional_service_communications where id=%s",
        "delete from lending.client_privacy_acknowledgments where id=%s",
    ):
        with pytest.raises(psycopg.Error), connection.transaction():
            connection.execute(sql, (row["id"],))
    assert state(connection, case) == before


def test_optional_false_and_true_are_separate_review_evidence_without_rewriting_history(
    connection, monkeypatch, tmp_path
):
    configure(tmp_path, monkeypatch)
    repository, captures = repositories(connection, monkeypatch)
    case = _seed(connection)
    no = captured(captures, case, False)
    first = repository.confirm(
        **source(case, False), evidence_reference=no.evidence_reference
    )
    with pytest.raises(evidence.OfficeReviewEvidenceConflict):
        repository.confirm(
            **source(case, True), evidence_reference=no.evidence_reference
        )
    yes = captured(captures, case, True)
    second = repository.confirm(
        **source(case, True), evidence_reference=yes.evidence_reference
    )
    assert first["id"] != second["id"] and no.snapshot_sha256 != yes.snapshot_sha256
    rows = connection.execute(
        "select optional_service_communications from lending.client_privacy_acknowledgments where client_id=%s order by optional_service_communications",
        (case["client"],),
    ).fetchall()
    assert rows == [
        {"optional_service_communications": False},
        {"optional_service_communications": True},
    ]


@pytest.mark.parametrize(
    "mismatch", ["client", "cif", "actor", "changed_cif", "file", "arbitrary_reference"]
)
def test_privacy_acknowledgment_rejects_binding_changes_without_any_state_write(
    connection, monkeypatch, tmp_path, mismatch
):
    configure(tmp_path, monkeypatch)
    repository, captures = repositories(connection, monkeypatch)
    case = _seed(connection)
    record = captured(captures, case)
    arguments = {**source(case), "evidence_reference": record.evidence_reference}
    if mismatch == "client":
        arguments["client_id"] = case["other"]
    elif mismatch == "cif":
        arguments["cif_version_id"] = uuid4()
    elif mismatch == "actor":
        arguments["actor_user_id"] = _seed(connection)["actor"]
    elif mismatch == "changed_cif":
        connection.execute(
            "update lending.client_cif_versions set phone_number='00000000001' where id=%s",
            (case["cif"],),
        )
    elif mismatch == "file":
        (tmp_path / "private-evidence" / f"{record.request_id.hex}.bin").write_bytes(
            b"corrupt"
        )
    else:
        arguments["evidence_reference"] = "external-unprotected-reference"
    before = state(connection, case)
    with pytest.raises(evidence.OfficeReviewEvidenceConflict):
        repository.confirm(**arguments)
    assert state(connection, case) == before


def test_unconfigured_privacy_package_is_read_only_and_cannot_capture_or_acknowledge(
    connection, monkeypatch
):
    monkeypatch.delenv("GILBIC_PRIVACY_PACKAGE_MANIFEST", raising=False)
    repository, captures = repositories(connection, monkeypatch)
    case = _seed(connection)
    before = state(connection, case)
    context = repository.context(**source(case))
    assert (
        context["issuable"] is False
        and context["review_snapshot"]["optional_service_communications"] is False
    )
    assert "notice" not in context["review_snapshot"]
    with pytest.raises(evidence.OfficeReviewEvidenceConflict):
        captured(captures, case)
    with pytest.raises(evidence.OfficeReviewEvidenceConflict):
        repository.confirm(
            **source(case), evidence_reference=f"office-evidence:{uuid4()}"
        )
    assert state(connection, case) == before


@pytest.mark.parametrize(
    "change", ["new_version", "same_version_changed_pdf", "changed_facts"]
)
def test_old_signed_snapshot_cannot_acknowledge_changed_privacy_package(
    connection, monkeypatch, tmp_path, change
):
    path, data, pdf = configure(tmp_path, monkeypatch)
    repository, captures = repositories(connection, monkeypatch)
    case = _seed(connection)
    record = captured(captures, case)
    if change == "new_version":
        data["notice"]["version"] = "SYNTHETIC-2"
    elif change == "changed_facts":
        data["facts"]["dpo_email"] = "updated-synthetic@example.test"
    else:
        import hashlib

        pdf.write_bytes(b"%PDF-1.4\nSynthetic changed privacy\n%%EOF")
        for kind in ("notice", "consent"):
            data[kind]["sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    before = state(connection, case)
    with pytest.raises(evidence.OfficeReviewEvidenceConflict):
        repository.confirm(**source(case), evidence_reference=record.evidence_reference)
    assert state(connection, case) == before


def test_recorded_template_version_cannot_be_reused_with_changed_content(
    connection, monkeypatch, tmp_path
):
    import hashlib

    path, data, pdf = configure(tmp_path, monkeypatch)
    repository, captures = repositories(connection, monkeypatch)
    case = _seed(connection)
    record = captured(captures, case)
    repository.confirm(**source(case), evidence_reference=record.evidence_reference)
    pdf.write_bytes(b"%PDF-1.4\nSynthetic other content\n%%EOF")
    for kind in ("notice", "consent"):
        data[kind]["sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    path.write_text(json.dumps(data))
    before = state(connection, case)
    with pytest.raises(
        evidence.OfficeReviewEvidenceConflict, match="without a new version"
    ):
        repository.context(**source(case))
    assert state(connection, case) == before


@pytest.mark.parametrize("role", ["collector", "client"])
def test_persisted_nonoffice_role_cannot_read_or_confirm_even_with_permission(
    connection, monkeypatch, tmp_path, role
):
    configure(tmp_path, monkeypatch)
    repository, _ = repositories(connection, monkeypatch)
    case = _seed(connection, role)
    before = state(connection, case)
    with pytest.raises(evidence.OfficeReviewEvidenceAccessDenied):
        repository.context(**source(case))
    with pytest.raises(evidence.OfficeReviewEvidenceAccessDenied):
        repository.confirm(
            **source(case), evidence_reference=f"office-evidence:{uuid4()}"
        )
    assert state(connection, case) == before


def test_revoked_persisted_actor_cannot_confirm_existing_signed_evidence(
    connection, monkeypatch, tmp_path
):
    configure(tmp_path, monkeypatch)
    repository, captures = repositories(connection, monkeypatch)
    case = _seed(connection)
    record = captured(captures, case)
    connection.execute(
        "update core.users set status='inactive' where id=%s", (case["actor"],)
    )
    before = state(connection, case)
    with pytest.raises(evidence.OfficeReviewEvidenceAccessDenied):
        repository.confirm(**source(case), evidence_reference=record.evidence_reference)
    assert state(connection, case) == before
