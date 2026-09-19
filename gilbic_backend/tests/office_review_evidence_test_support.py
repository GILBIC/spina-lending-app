from uuid import uuid4

import pytest

from gilbic_backend.client_cif_identity_information import cif_information_from_row
from gilbic_backend.office_review_evidence_repository import (
    application_review_snapshot,
    capture_evidence,
    cif_review_snapshot,
)

PDF = b"%PDF-1.4\nSYNTHETIC TEST signed review scan\n%%EOF\n"


@pytest.fixture(autouse=True)
def private_evidence_root(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", str(tmp_path / "private-evidence")
    )


def capture_cif(connection, case):
    information = cif_information_from_row(
        connection.execute(
            "select * from lending.client_cif_versions where id=%s",
            (case["cif"],),
        ).fetchone()
    )
    return capture_evidence(
        connection.cursor(),
        actor_user_id=case["actor"],
        client_id=case["client"],
        cif_version_id=case["cif"],
        purpose="cif_review",
        subject_id=case["cif"],
        review_snapshot=cif_review_snapshot(
            client_id=case["client"],
            cif_version_id=case["cif"],
            information=information,
        ),
        content=PDF,
        media_type="application/pdf",
        request_id=uuid4(),
    ).evidence_reference


def capture_application(connection, case, version):
    information = cif_information_from_row(
        connection.execute(
            "select * from lending.client_cif_versions where id=%s",
            (version.cif_version_id,),
        ).fetchone()
    )
    return capture_evidence(
        connection.cursor(),
        actor_user_id=case["actor"],
        client_id=case["client"],
        cif_version_id=version.cif_version_id,
        purpose="application_review",
        subject_id=version.id,
        application_id=version.application_id,
        application_version_id=version.id,
        review_snapshot=application_review_snapshot(
            client_id=case["client"],
            cif_version_id=version.cif_version_id,
            application_id=version.application_id,
            application_version_id=version.id,
            information=version.information.model_dump(mode="json"),
            cif_information=information,
        ),
        content=PDF,
        media_type="application/pdf",
        request_id=uuid4(),
    ).evidence_reference
