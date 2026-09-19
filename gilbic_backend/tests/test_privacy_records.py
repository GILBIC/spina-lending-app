import hashlib
import json
from uuid import uuid4
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gilbic_backend import privacy_record_api as api
from gilbic_backend.privacy_record_repository import REQUIRED_FACTS, privacy_package


def configure(tmp_path, monkeypatch):
    pdf = tmp_path / "privacy.pdf"
    pdf.write_bytes(b"%PDF-1.4\nSYNTHETIC\n%%EOF")
    item = {
        "path": str(pdf),
        "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "version": "SYNTHETIC-1",
    }
    data = {
        "approved_for_issuance": True,
        "facts": {key: "Synthetic " + key for key in REQUIRED_FACTS},
        "notice": dict(item),
        "consent": dict(item),
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data))
    monkeypatch.setenv("GILBIC_PRIVACY_PACKAGE_MANIFEST", str(path))
    return path, data, pdf


def test_privacy_package_requires_explicit_approved_facts_and_matching_pdf_hashes(
    tmp_path, monkeypatch
):
    path, data, pdf = configure(tmp_path, monkeypatch)
    assert privacy_package()["issuable"] is True
    pdf.write_bytes(b"%PDF-1.4\nchanged\n%%EOF")
    assert privacy_package()["issuable"] is False


@pytest.mark.parametrize("missing", REQUIRED_FACTS)
def test_missing_production_fact_never_becomes_issuable(tmp_path, monkeypatch, missing):
    path, data, _ = configure(tmp_path, monkeypatch)
    data["facts"][missing] = "[To be finalized]"
    path.write_text(json.dumps(data))
    assert privacy_package()["issuable"] is False


def test_unconfigured_package_returns_pending_without_invented_facts(monkeypatch):
    monkeypatch.delenv("GILBIC_PRIVACY_PACKAGE_MANIFEST", raising=False)
    assert privacy_package()["issuable"] is False


def client(repository):
    app = FastAPI()
    app.include_router(api.create_privacy_record_router())
    app.dependency_overrides[api._actor] = lambda: SimpleNamespace(user_id=uuid4())
    app.dependency_overrides[api.privacy_repository_dependency] = lambda: repository
    return TestClient(app)


def test_optional_choice_defaults_false_and_strict_boolean_cannot_be_smuggled():
    calls = []
    repo = SimpleNamespace(
        confirm=lambda **kwargs: calls.append(kwargs) or {"recorded": True}
    )
    app = client(repo)
    prefix = f"/api/v1/management/clients/{uuid4()}/privacy/acknowledgments"
    payload = {
        "cif_version_id": str(uuid4()),
        "evidence_reference": "office-evidence:" + str(uuid4()),
    }
    result = app.post(prefix, json=payload)
    assert result.status_code == 201 and result.headers["cache-control"] == "no-store"
    assert calls[0]["optional_service_communications"] is False
    assert (
        app.post(
            prefix, json={**payload, "optional_service_communications": "true"}
        ).status_code
        == 422
    )
    assert len(calls) == 1


def test_download_rejects_digest_different_from_displayed_notice(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    package = privacy_package()
    repo = SimpleNamespace(
        context=lambda **kwargs: {
            "issuable": True,
            "review_snapshot": {"notice": {"sha256": package["notice"]["sha256"]}},
        }
    )
    app = client(repo)
    response = app.get(
        f"/api/v1/management/clients/{uuid4()}/privacy/documents/notice?cif_version_id={uuid4()}&expected_sha256="
        + ("0" * 64)
    )
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
