from importlib import import_module
from uuid import uuid4

import pytest
from pathlib import Path


PDF = b"%PDF-1.4\nSynthetic signed review scan\n%%EOF\n"


def test_private_evidence_is_immutable_and_detects_tampering(tmp_path):
    module = import_module("gilbic_backend.office_review_evidence_storage")
    store = module.PrivateEvidenceStore(tmp_path / "private")
    key = uuid4()
    digest = store.put(key, PDF, "application/pdf")
    assert store.read(key, digest, len(PDF)) == PDF
    assert store.put(key, PDF, "application/pdf") == digest
    with pytest.raises(module.EvidenceFileError):
        store.put(key, PDF.replace(b"Synthetic", b"Different"), "application/pdf")
    (tmp_path / "private" / f"{key.hex}.bin").write_bytes(b"tampered")
    with pytest.raises(module.EvidenceFileError):
        store.read(key, digest, len(PDF))


@pytest.mark.parametrize(
    "content,media",
    [
        (b"", "application/pdf"),
        (PDF, "text/html"),
        (b"<svg/>", "image/png"),
        (b"%PDF-1.4\ntruncated", "application/pdf"),
    ],
)
def test_unsupported_empty_and_truncated_files_are_rejected_before_storage(
    tmp_path, content, media
):
    module = import_module("gilbic_backend.office_review_evidence_storage")
    store = module.PrivateEvidenceStore(tmp_path / "private")
    with pytest.raises(module.EvidenceFileError):
        store.put(uuid4(), content, media)
    assert list(store.root.iterdir()) == []


def test_oversized_file_and_non_uuid_key_never_create_a_file(tmp_path):
    module = import_module("gilbic_backend.office_review_evidence_storage")
    store = module.PrivateEvidenceStore(tmp_path / "private")
    with pytest.raises(module.EvidenceFileError):
        store.put(uuid4(), b"a" * (module.MAX_EVIDENCE_BYTES + 1), "application/pdf")
    with pytest.raises(module.EvidenceFileError):
        store.put("../escape", PDF, "application/pdf")
    assert list(store.root.iterdir()) == []


def test_relative_or_served_storage_is_rejected(monkeypatch):
    module = import_module("gilbic_backend.office_review_evidence_storage")
    with pytest.raises(module.EvidenceFileError):
        module.PrivateEvidenceStore(Path("relative"))
    with pytest.raises(module.EvidenceFileError):
        module.PrivateEvidenceStore(
            Path(__file__).resolve().parents[2] / "spina_portal" / "uploads"
        )
    monkeypatch.delenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", raising=False)
    with pytest.raises(module.EvidenceFileError):
        module.PrivateEvidenceStore()
