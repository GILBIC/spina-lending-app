from __future__ import annotations

import os
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.cif_repository import (
    CifConflict,
    CifDraftData,
    PostgresCifRepository,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)
ROOT = Path(__file__).parents[2]
SQL_DIR = ROOT / "gilbic_backend" / "sql"


@pytest.fixture()
def repository_database(monkeypatch):
    assert DATABASE_URL is not None
    setup = psycopg.connect(DATABASE_URL, autocommit=True)
    for filename in (
        "0001_core_lending_foundation.sql",
        "0003_add_management_administration.sql",
        "0004_add_collector_routes.sql",
        "0005_add_idempotent_collections.sql",
        "0110_add_client_information_forms_and_restricted_evidence.sql",
    ):
        setup.execute((SQL_DIR / filename).read_text(encoding="utf-8"))

    suffix = uuid4().hex
    preparer_id = setup.execute(
        """
        insert into core.users (username, email, full_name, status)
        values (%s, %s, 'CIF Repository Preparer', 'active')
        returning id
        """,
        (f"cif-repo-preparer-{suffix}", f"cif-repo-preparer-{suffix}@example.com"),
    ).fetchone()[0]
    verifier_id = setup.execute(
        """
        insert into core.users (username, email, full_name, status)
        values (%s, %s, 'CIF Repository Verifier', 'active')
        returning id
        """,
        (f"cif-repo-verifier-{suffix}", f"cif-repo-verifier-{suffix}@example.com"),
    ).fetchone()[0]
    approver_id = setup.execute(
        """
        insert into core.users (username, email, full_name, status)
        values (%s, %s, 'CIF Repository Approver', 'active')
        returning id
        """,
        (f"cif-repo-approver-{suffix}", f"cif-repo-approver-{suffix}@example.com"),
    ).fetchone()[0]
    client_code = f"CIF-REPO-{suffix[:10]}"
    client_id = setup.execute(
        """
        insert into lending.clients (client_code, full_name, phone_number, area, status)
        values (%s, 'Repository Test Client', '09172223333', 'REPOSITORY TEST', 'active')
        returning id
        """,
        (client_code,),
    ).fetchone()[0]
    setup.close()

    import gilbic_backend.cif_repository as module

    monkeypatch.setattr(
        module,
        "open_connection",
        lambda: psycopg.connect(DATABASE_URL),
    )
    yield PostgresCifRepository(), preparer_id, verifier_id, approver_id, client_id, client_code


def _draft(*, name: str = "Repository Test Client") -> CifDraftData:
    return CifDraftData(
        legal_full_name=name,
        birth_date=date(1990, 1, 2),
        place_of_birth="Rizal",
        nationality="Filipino",
        civil_status="single",
        phone_number="09172223333",
        email="client@example.com",
        present_address={
            "line1": "Synthetic present address",
            "barangay": "San Juan",
            "province": "Rizal",
        },
        permanent_address={
            "line1": "Synthetic permanent address",
            "barangay": "San Juan",
            "province": "Rizal",
        },
        same_as_present_address=False,
        livelihood_profile={
            "kind": "self_employed",
            "description": "Synthetic test livelihood",
        },
        privacy_notice_version="privacy-v1",
        privacy_acknowledged_at=datetime.now(UTC),
        client_signature_reference="restricted-signature://repository-test",
        client_signature_digest="1" * 64,
        form_schema_version="1",
    )


def test_repository_creates_updates_verifies_and_activates_versioned_cif(
    repository_database,
) -> None:
    repository, preparer_id, verifier_id, approver_id, client_id, client_code = (
        repository_database
    )

    clients = repository.search_clients(query=client_code, limit=20)
    assert [(item.client_id, item.client_code) for item in clients] == [
        (client_id, client_code)
    ]

    draft = repository.create_draft(
        actor_user_id=preparer_id,
        client_id=client_id,
        draft=_draft(),
    )
    assert draft.client_id == client_id
    assert draft.form_version == 1
    assert draft.public_status == "Draft"
    assert draft.source_digest is None
    assert draft.has_client_signature is True

    changed = repository.update_draft(
        actor_user_id=preparer_id,
        cif_id=draft.cif_id,
        expected_updated_at=draft.updated_at,
        draft=_draft(name="Repository Test Client Updated"),
    )
    assert changed.legal_full_name == "Repository Test Client Updated"
    assert changed.verified_at is None

    with pytest.raises(CifConflict, match="changed"):
        repository.update_draft(
            actor_user_id=preparer_id,
            cif_id=draft.cif_id,
            expected_updated_at=draft.updated_at,
            draft=_draft(name="Stale Update"),
        )

    verified = repository.verify(
        actor_user_id=verifier_id,
        cif_id=changed.cif_id,
        expected_updated_at=changed.updated_at,
        review_note="Identity and ordinary CIF fields verified from synthetic evidence.",
    )
    assert verified.verified_by_user_id == verifier_id
    assert verified.verified_at is not None
    assert verified.source_digest is not None
    assert len(verified.source_digest) == 64

    requirement = repository.open_reverification(
        actor_user_id=approver_id,
        client_id=client_id,
        reason="address_change",
        severity="standard",
        note="Synthetic address change requires replacement CIF.",
    )
    assert requirement.status == "open"

    with pytest.raises(CifConflict, match="different verifier and approver"):
        repository.activate(
            actor_user_id=verifier_id,
            cif_id=verified.cif_id,
            expected_source_digest=verified.source_digest,
            review_note="Self approval must fail.",
        )

    active = repository.activate(
        actor_user_id=approver_id,
        cif_id=verified.cif_id,
        expected_source_digest=verified.source_digest,
        review_note="Synthetic Management approval completed.",
    )
    assert active.public_status == "Active"
    assert active.is_eligible_for_new_credit is True
    assert active.approved_by_user_id == approver_id
    assert active.expires_at is not None

    requirements = repository.list_reverification_for_client(client_id=client_id)
    assert [(item.requirement_id, item.status, item.resolution_cif_id) for item in requirements] == [
        (requirement.requirement_id, "resolved", active.cif_id)
    ]

    versions = repository.list_for_client(client_id=client_id)
    assert [item.form_version for item in versions] == [1]
    assert versions[0].cif_id == active.cif_id


def test_repository_supersedes_prior_active_version_and_keeps_safe_audit(
    repository_database,
) -> None:
    repository, preparer_id, verifier_id, approver_id, client_id, _ = repository_database

    first = repository.create_draft(
        actor_user_id=preparer_id,
        client_id=client_id,
        draft=_draft(name="First Active Version"),
    )
    first = repository.verify(
        actor_user_id=verifier_id,
        cif_id=first.cif_id,
        expected_updated_at=first.updated_at,
        review_note="First synthetic verification.",
    )
    first = repository.activate(
        actor_user_id=approver_id,
        cif_id=first.cif_id,
        expected_source_digest=first.source_digest or "",
        review_note="First synthetic approval.",
    )

    second = repository.create_draft(
        actor_user_id=preparer_id,
        client_id=client_id,
        draft=_draft(name="Second Active Version"),
    )
    assert second.form_version == 2
    assert second.supersedes_cif_id == first.cif_id
    second = repository.verify(
        actor_user_id=verifier_id,
        cif_id=second.cif_id,
        expected_updated_at=second.updated_at,
        review_note="Second synthetic verification.",
    )
    second = repository.activate(
        actor_user_id=approver_id,
        cif_id=second.cif_id,
        expected_source_digest=second.source_digest or "",
        review_note="Second synthetic approval.",
    )

    versions = repository.list_for_client(client_id=client_id)
    assert [(item.form_version, item.public_status) for item in versions] == [
        (2, "Active"),
        (1, "Superseded"),
    ]

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        audit_rows = connection.execute(
            """
            select action, details::text
            from core.audit_logs
            where target_type in ('client_information_form', 'client_cif_reverification')
              and target_id in (%s, %s)
            order by created_at, id
            """,
            (first.cif_id, second.cif_id),
        ).fetchall()
        assert audit_rows
        audit_text = "\n".join(str(row) for row in audit_rows).lower()
        for forbidden in (
            "synthetic present address",
            "09172223333",
            "restricted-signature",
            "client@example.com",
            "second active version",
        ):
            assert forbidden not in audit_text
        assert connection.execute(
            "select count(*) from lending.loans where client_id = %s",
            (client_id,),
        ).fetchone()[0] == 0
        assert connection.execute(
            "select count(*) from lending.collection_transactions where client_id = %s",
            (client_id,),
        ).fetchone()[0] == 0
