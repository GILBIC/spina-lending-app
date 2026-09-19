from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from test_client_cif_review_confirmation_postgres import (
    connection as connection,
    runtime_url as runtime_url,
)
from office_review_evidence_test_support import (
    private_evidence_root as private_evidence_root,
)
from psycopg.types.json import Jsonb
from gilbic_backend import office_review_evidence_repository as evidence
from gilbic_backend import client_cif_repository as cif
from test_client_cif_review_confirmation_postgres import DATABASE_URL, _insert
from test_loan_application_repository_postgres import _seed
from office_review_evidence_test_support import PDF, capture_cif

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)


def repositories(connection, monkeypatch):
    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(evidence, "open_connection", acquire)
    monkeypatch.setattr(cif, "open_connection", acquire)
    return (
        evidence.PostgresOfficeReviewEvidenceRepository(),
        cif.PostgresClientCifRepository(),
    )


def source(case):
    return dict(
        actor_user_id=case["actor"],
        client_id=case["client"],
        cif_version_id=case["cif"],
        purpose="cif_review",
    )


def test_capture_is_exact_immutable_and_retry_does_not_create_more_metadata(
    connection, monkeypatch
):
    repo, _ = repositories(connection, monkeypatch)
    case = _seed(connection)
    context = repo.get_context(**source(case))
    key = uuid4()
    values = dict(
        **source(case),
        expected_snapshot_sha256=context["snapshot_sha256"],
        request_id=key,
        content=PDF,
        media_type="application/pdf",
    )
    first = repo.capture(**values)
    assert repo.capture(**values) == first
    assert first.review_snapshot == context["review_snapshot"]
    assert (
        repo.get_content(
            actor_user_id=case["actor"], client_id=case["client"], record_id=first.id
        )[1]
        == PDF
    )
    assert (
        connection.execute(
            "select count(*) as n from lending.office_review_evidence where request_id=%s",
            (key,),
        ).fetchone()["n"]
        == 1
    )
    with pytest.raises(evidence.OfficeReviewEvidenceConflict):
        repo.capture(**{**values, "content": PDF.replace(b"TEST", b"OTHER")})
    for sql in (
        "update lending.office_review_evidence set byte_count=1 where id=%s",
        "delete from lending.office_review_evidence where id=%s",
    ):
        with pytest.raises(psycopg.Error), connection.transaction():
            connection.execute(sql, (first.id,))


@pytest.mark.parametrize(
    "difference", ["client", "purpose", "subject", "snapshot", "actor", "file"]
)
def test_confirmation_proof_rejects_every_binding_mismatch(
    connection, monkeypatch, tmp_path, difference
):
    repo, _ = repositories(connection, monkeypatch)
    case = _seed(connection)
    context = repo.get_context(**source(case))
    record = repo.capture(
        **source(case),
        expected_snapshot_sha256=context["snapshot_sha256"],
        request_id=uuid4(),
        content=PDF,
        media_type="application/pdf",
    )
    values = dict(
        evidence_reference=record.evidence_reference,
        actor_user_id=case["actor"],
        client_id=case["client"],
        purpose="cif_review",
        subject_id=case["cif"],
        review_snapshot=context["review_snapshot"],
    )
    if difference == "client":
        values["client_id"] = uuid4()
    elif difference == "purpose":
        values["purpose"] = "application_review"
    elif difference == "subject":
        values["subject_id"] = uuid4()
    elif difference == "snapshot":
        values["review_snapshot"] = {"changed": True}
    elif difference == "actor":
        values["actor_user_id"] = uuid4()
    else:
        (tmp_path / "private-evidence" / f"{record.request_id.hex}.bin").write_bytes(
            b"corrupted"
        )
    with pytest.raises(evidence.OfficeReviewEvidenceConflict):
        evidence.require_evidence(connection.cursor(), **values)


def test_changed_facts_cannot_use_old_capture_or_arbitrary_string(
    connection, monkeypatch
):
    repo, cif_repo = repositories(connection, monkeypatch)
    case = _seed(connection)
    context = repo.get_context(**source(case))
    record = repo.capture(
        **source(case),
        expected_snapshot_sha256=context["snapshot_sha256"],
        request_id=uuid4(),
        content=PDF,
        media_type="application/pdf",
    )
    expected = context["review_snapshot"]["information"]
    for reference in ("arbitrary acknowledgement", f"office-evidence:{uuid4()}"):
        with pytest.raises(cif.ClientCifConflict):
            cif_repo.confirm_review(
                actor_user_id=case["actor"],
                client_id=case["client"],
                cif_version_id=case["cif"],
                expected_information=expected,
                applicant_confirmation_evidence_reference=reference,
            )
    connection.execute(
        "update lending.client_cif_versions set phone_number='09172222222' where id=%s",
        (case["cif"],),
    )
    with pytest.raises(evidence.OfficeReviewEvidenceConflict, match="changed"):
        repo.capture(
            **source(case),
            expected_snapshot_sha256=context["snapshot_sha256"],
            request_id=uuid4(),
            content=PDF,
            media_type="application/pdf",
        )
    with pytest.raises(cif.ClientCifConflict, match="changed"):
        cif_repo.confirm_review(
            actor_user_id=case["actor"],
            client_id=case["client"],
            cif_version_id=case["cif"],
            expected_information=expected,
            applicant_confirmation_evidence_reference=record.evidence_reference,
        )


@pytest.mark.parametrize("stage", ["confirmed_draft", "active"])
def test_successor_preserves_old_confirmation_activation_and_client_servicing(
    connection, monkeypatch, stage
):
    repo, cif_repo = repositories(connection, monkeypatch)
    case = _seed(connection)
    expected = repo.get_context(**source(case))["review_snapshot"]["information"]
    confirmation = _insert(
        connection,
        case,
        review_snapshot=Jsonb(expected),
        applicant_confirmation_evidence_reference=capture_cif(connection, case),
    )
    if stage == "active":
        connection.execute(
            "update lending.clients set status='active' where id=%s", (case["client"],)
        )
        connection.execute(
            "update lending.client_cif_versions set status='active',baseline_liveness_status='passed',baseline_face_scan_evidence_reference='SYNTHETIC-EXTERNAL-PROVIDER',activated_at=now(),expires_at=now()+interval '5 years',review_due_at=now()+interval '4 years' where id=%s",
            (case["cif"],),
        )
    before = connection.execute(
        "select * from lending.client_cif_versions where id=%s", (case["cif"],)
    ).fetchone()
    client_before = connection.execute(
        "select * from lending.clients where id=%s", (case["client"],)
    ).fetchone()
    corrected = {
        **expected,
        "phone_number": "09175555555",
        "identity_information": {
            "birth_date": "1990-01-02",
            "birth_place": "Synthetic town",
            "civil_status": None,
            "citizenship": None,
        },
    }
    values = dict(
        actor_user_id=case["actor"],
        client_id=case["client"],
        cif_version_id=case["cif"],
        expected_information=expected,
        corrected_information=corrected,
        reason="Applicant corrected saved information",
    )
    successor = cif_repo.begin_review_cycle(**values)
    assert cif_repo.begin_review_cycle(**values) == successor
    assert (
        successor.id != case["cif"]
        and successor.is_current
        and successor.status == "draft"
    )
    assert (
        successor.baseline_liveness_status == "pending"
        and successor.activated_at is None
    )
    assert successor.identity_information == corrected["identity_information"]
    after = connection.execute(
        "select * from lending.client_cif_versions where id=%s", (case["cif"],)
    ).fetchone()
    assert after == {**before, "is_current": False}
    assert (
        connection.execute(
            "select * from lending.clients where id=%s", (case["client"],)
        ).fetchone()
        == client_before
    )
    assert (
        connection.execute(
            "select * from lending.client_cif_review_confirmations where id=%s",
            (confirmation["id"],),
        ).fetchone()
        == confirmation
    )
    summary = cif_repo.get_review_summary(
        client_id=case["client"],
        include_correction_availability=True,
        include_identity_information=True,
    )
    assert summary.can_correct_information is True
    assert summary.identity_information == corrected["identity_information"]
    assert (
        repo.get_context(**{**source(case), "cif_version_id": successor.id})[
            "review_snapshot"
        ]["information"]
        == corrected
    )


@pytest.mark.parametrize("role", ["collector", "client"])
def test_persisted_nonoffice_actor_cannot_capture_or_start_successor(
    connection, monkeypatch, role
):
    repo, cif_repo = repositories(connection, monkeypatch)
    case = _seed(connection, role)
    with pytest.raises(evidence.OfficeReviewEvidenceAccessDenied):
        repo.get_context(**source(case))
    with pytest.raises(cif.ClientCifAccessDenied):
        cif_repo.begin_review_cycle(
            actor_user_id=case["actor"],
            client_id=case["client"],
            cif_version_id=case["cif"],
            expected_information={
                "full_name": "Synthetic CIF Borrower",
                "phone_number": "00000000000",
                "email": None,
                "present_address": "Synthetic office test address",
            },
            corrected_information={
                "full_name": "Synthetic CIF Borrower",
                "phone_number": "00000000000",
                "email": None,
                "present_address": "Synthetic office test address",
            },
            reason="Applicant correction",
        )


def test_activation_requires_exact_protected_confirmation_after_passed_baseline(
    connection, monkeypatch
):
    repo, cif_repo = repositories(connection, monkeypatch)
    case = _seed(connection, "management")
    cif_repo.record_baseline_live_face(
        client_id=case["client"],
        cif_version_id=case["cif"],
        evidence_reference="SYNTHETIC-CONTROLLED-PROVIDER",
        liveness_status="passed",
    )
    with pytest.raises(cif.ClientCifConflict, match="confirmation"):
        cif_repo.activate_current(
            actor_user_id=case["actor"],
            client_id=case["client"],
            cif_version_id=case["cif"],
        )
    context = repo.get_context(**source(case))
    captured = repo.capture(
        **source(case),
        expected_snapshot_sha256=context["snapshot_sha256"],
        request_id=uuid4(),
        content=PDF,
        media_type="application/pdf",
    )
    cif_repo.confirm_review(
        actor_user_id=case["actor"],
        client_id=case["client"],
        cif_version_id=case["cif"],
        expected_information=context["review_snapshot"]["information"],
        applicant_confirmation_evidence_reference=captured.evidence_reference,
    )
    active = cif_repo.activate_current(
        actor_user_id=case["actor"],
        client_id=case["client"],
        cif_version_id=case["cif"],
    )
    assert active.status == "active"
    assert (
        cif_repo.activate_current(
            actor_user_id=case["actor"],
            client_id=case["client"],
            cif_version_id=case["cif"],
        )
        == active
    )
