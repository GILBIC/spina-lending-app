from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.restricted_identity_repository import (
    PostgresRestrictedIdentityRepository,
    RestrictedEvidenceData,
    RestrictedIdentityConflict,
    RestrictedIdentityInvalid,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)
ROOT = Path(__file__).parents[2]
SQL_DIR = ROOT / "gilbic_backend" / "sql"


@pytest.fixture()
def restricted_database(monkeypatch):
    assert DATABASE_URL is not None
    connection = psycopg.connect(DATABASE_URL, autocommit=True)
    for filename in (
        "0001_core_lending_foundation.sql",
        "0003_add_management_administration.sql",
        "0004_add_collector_routes.sql",
        "0005_add_idempotent_collections.sql",
        "0110_add_client_information_forms_and_restricted_evidence.sql",
    ):
        connection.execute((SQL_DIR / filename).read_text(encoding="utf-8"))

    suffix = uuid4().hex
    recorder_id = connection.execute(
        """
        insert into core.users (username, email, full_name, status)
        values (%s, %s, 'Restricted Evidence Recorder', 'active')
        returning id
        """,
        (f"restricted-recorder-{suffix}", f"restricted-recorder-{suffix}@example.com"),
    ).fetchone()[0]
    reviewer_id = connection.execute(
        """
        insert into core.users (username, email, full_name, status)
        values (%s, %s, 'Restricted Evidence Reviewer', 'active')
        returning id
        """,
        (f"restricted-reviewer-{suffix}", f"restricted-reviewer-{suffix}@example.com"),
    ).fetchone()[0]
    recorder_device_id = connection.execute(
        """
        insert into core.devices (
            user_id, device_identifier_hash, platform, app_version, status
        ) values (%s, %s, 'web', 'restricted-test', 'active')
        returning id
        """,
        (recorder_id, f"restricted-recorder-device-{suffix}"),
    ).fetchone()[0]
    reviewer_device_id = connection.execute(
        """
        insert into core.devices (
            user_id, device_identifier_hash, platform, app_version, status
        ) values (%s, %s, 'web', 'restricted-test', 'active')
        returning id
        """,
        (reviewer_id, f"restricted-reviewer-device-{suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, area, status)
        values (%s, 'Restricted Repository Client', 'RESTRICTED TEST', 'active')
        returning id
        """,
        (f"RESTRICTED-{suffix[:10]}",),
    ).fetchone()[0]
    effective_at = datetime.now(UTC).replace(microsecond=0)
    cif_id = connection.execute(
        """
        insert into lending.client_information_forms (
            client_id, form_version, lifecycle_state, effective_at, expires_at,
            legal_full_name, birth_date, nationality, phone_number,
            present_address, permanent_address, livelihood_profile,
            privacy_notice_version, privacy_acknowledged_at,
            client_signature_reference, client_signature_digest,
            prepared_by_user_id, verified_by_user_id, verified_at,
            verification_note, approved_by_user_id, approved_at,
            approval_note, source_digest
        ) values (
            %s, 1, 'active', %s, %s,
            'Restricted Repository Client', '1990-01-02', 'Filipino', '09170000000',
            '{"line1":"Synthetic present"}'::jsonb,
            '{"line1":"Synthetic permanent"}'::jsonb,
            '{"kind":"synthetic"}'::jsonb,
            'privacy-v1', now(), 'restricted-signature://synthetic', %s,
            %s, %s, now(), 'Synthetic verification.', %s, now(),
            'Synthetic approval.', %s
        )
        returning id
        """,
        (
            client_id,
            effective_at,
            effective_at.replace(year=effective_at.year + 5),
            "a" * 64,
            recorder_id,
            recorder_id,
            reviewer_id,
            "b" * 64,
        ),
    ).fetchone()[0]
    connection.close()

    import gilbic_backend.restricted_identity_repository as module

    monkeypatch.setattr(
        module,
        "open_connection",
        lambda: psycopg.connect(DATABASE_URL),
    )
    yield (
        PostgresRestrictedIdentityRepository(),
        recorder_id,
        reviewer_id,
        recorder_device_id,
        reviewer_device_id,
        client_id,
        cif_id,
    )


def _evidence() -> RestrictedEvidenceData:
    checked_at = datetime.now(UTC).replace(microsecond=0)
    return RestrictedEvidenceData(
        evidence_type="national_id_check",
        verification_method="approved-test-adapter",
        verification_outcome="verified",
        checked_at=checked_at,
        document_date=date.today(),
        document_expires_at=date.today() + timedelta(days=365),
        masked_reference="****-****-1234",
        external_evidence_reference="restricted://synthetic/evidence-object",
        evidence_digest="c" * 64,
        retention_class="identity_verification",
        retain_until=date.today() + timedelta(days=3650),
        legal_hold=False,
        supersedes_evidence_id=None,
    )


def test_restricted_repository_records_lists_reviews_and_logs_access(
    restricted_database,
) -> None:
    (
        repository,
        recorder_id,
        reviewer_id,
        recorder_device_id,
        reviewer_device_id,
        client_id,
        cif_id,
    ) = restricted_database

    evidence = repository.record(
        actor_user_id=recorder_id,
        registered_device_id=recorder_device_id,
        request_id=uuid4(),
        purpose_code="cif_verification",
        client_id=client_id,
        cif_id=cif_id,
        data=_evidence(),
    )
    assert evidence.client_id == client_id
    assert evidence.cif_id == cif_id
    assert evidence.masked_reference == "****-****-1234"
    assert evidence.review_decision is None

    listed = repository.list_for_cif(
        actor_user_id=reviewer_id,
        registered_device_id=reviewer_device_id,
        request_id=uuid4(),
        purpose_code="compliance_review",
        cif_id=cif_id,
    )
    assert [item.evidence_id for item in listed] == [evidence.evidence_id]

    reviewed = repository.review(
        actor_user_id=reviewer_id,
        registered_device_id=reviewer_device_id,
        request_id=uuid4(),
        purpose_code="compliance_review",
        evidence_id=evidence.evidence_id,
        decision="approved",
        review_note="Synthetic independent evidence review completed.",
    )
    assert reviewed.review_decision == "approved"
    assert reviewed.reviewed_by_user_id == reviewer_id

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        actions = [
            row[0]
            for row in connection.execute(
                """
                select action
                from restricted_identity.evidence_access_events
                where evidence_id = %s
                order by occurred_at, id
                """,
                (evidence.evidence_id,),
            ).fetchall()
        ]
        assert actions == ["record", "view", "review"]
        audit_text = "\n".join(
            row[0]
            for row in connection.execute(
                """
                select details::text
                from core.audit_logs
                where target_type = 'restricted_identity_evidence'
                  and target_id = %s
                order by created_at, id
                """,
                (evidence.evidence_id,),
            ).fetchall()
        ).lower()
        for forbidden in (
            "****-****-1234",
            "restricted://synthetic",
            "approved-test-adapter",
            "verified",
            "cccccccccccc",
        ):
            assert forbidden not in audit_text


def test_restricted_repository_fails_closed_on_purpose_masking_device_and_self_review(
    restricted_database,
) -> None:
    (
        repository,
        recorder_id,
        reviewer_id,
        recorder_device_id,
        reviewer_device_id,
        client_id,
        cif_id,
    ) = restricted_database

    with pytest.raises(RestrictedIdentityInvalid, match="approved access purpose"):
        repository.record(
            actor_user_id=recorder_id,
            registered_device_id=recorder_device_id,
            request_id=uuid4(),
            purpose_code="free_form_reason",
            client_id=client_id,
            cif_id=cif_id,
            data=_evidence(),
        )

    unmasked = _evidence()
    unmasked = RestrictedEvidenceData(
        evidence_type=unmasked.evidence_type,
        verification_method=unmasked.verification_method,
        verification_outcome=unmasked.verification_outcome,
        checked_at=unmasked.checked_at,
        document_date=unmasked.document_date,
        document_expires_at=unmasked.document_expires_at,
        masked_reference="123456789012",
        external_evidence_reference=unmasked.external_evidence_reference,
        evidence_digest=unmasked.evidence_digest,
        retention_class=unmasked.retention_class,
        retain_until=unmasked.retain_until,
        legal_hold=unmasked.legal_hold,
        supersedes_evidence_id=None,
    )
    with pytest.raises(RestrictedIdentityInvalid, match="masked"):
        repository.record(
            actor_user_id=recorder_id,
            registered_device_id=recorder_device_id,
            request_id=uuid4(),
            purpose_code="cif_verification",
            client_id=client_id,
            cif_id=cif_id,
            data=unmasked,
        )

    evidence = repository.record(
        actor_user_id=recorder_id,
        registered_device_id=recorder_device_id,
        request_id=uuid4(),
        purpose_code="cif_verification",
        client_id=client_id,
        cif_id=cif_id,
        data=_evidence(),
    )
    with pytest.raises(RestrictedIdentityConflict, match="active registered device"):
        repository.list_for_cif(
            actor_user_id=recorder_id,
            registered_device_id=reviewer_device_id,
            request_id=uuid4(),
            purpose_code="cif_verification",
            cif_id=cif_id,
        )
    with pytest.raises(RestrictedIdentityConflict, match="differ"):
        repository.review(
            actor_user_id=recorder_id,
            registered_device_id=recorder_device_id,
            request_id=uuid4(),
            purpose_code="cif_verification",
            evidence_id=evidence.evidence_id,
            decision="approved",
            review_note="Self review must fail.",
        )

    repository.review(
        actor_user_id=reviewer_id,
        registered_device_id=reviewer_device_id,
        request_id=uuid4(),
        purpose_code="compliance_review",
        evidence_id=evidence.evidence_id,
        decision="approved",
        review_note="Independent review.",
    )
    with pytest.raises(RestrictedIdentityConflict):
        repository.review(
            actor_user_id=reviewer_id,
            registered_device_id=reviewer_device_id,
            request_id=uuid4(),
            purpose_code="compliance_review",
            evidence_id=evidence.evidence_id,
            decision="rejected",
            review_note="A second review must fail.",
        )


def test_ordinary_cif_repository_never_queries_restricted_schema() -> None:
    source = (
        ROOT
        / "gilbic_backend"
        / "src"
        / "gilbic_backend"
        / "cif_repository.py"
    ).read_text(encoding="utf-8").lower()

    assert "restricted_identity" not in source
