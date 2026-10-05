from importlib import import_module
from pathlib import Path
from uuid import uuid4

import pytest

PDF = b"%PDF-1.4\nSynthetic signed review scan\n%%EOF\n"


@pytest.mark.parametrize(
    "kind", ["transparent", "opaque-black", "single-dot", "oversized", "truncated"]
)
def test_screen_signature_requires_bounded_visible_strokes(kind):
    from io import BytesIO

    from PIL import Image, ImageDraw

    module = import_module("gilbic_backend.office_review_evidence_storage")
    size = (2049, 128) if kind == "oversized" else (640, 240)
    color = (
        (0, 0, 0, 0)
        if kind == "transparent"
        else "black"
        if kind == "opaque-black"
        else "white"
    )
    drawing = Image.new("RGBA", size, color)
    if kind == "single-dot":
        ImageDraw.Draw(drawing).point((50, 50), fill="black")
    if kind in ("oversized", "truncated"):
        ImageDraw.Draw(drawing).line(
            [(50, 130), (100, 60), (200, 170)], fill="black", width=4
        )
    output = BytesIO()
    drawing.save(output, format="PNG")
    content = output.getvalue()
    if kind == "truncated":
        content = content[:40]
    with pytest.raises(module.EvidenceFileError):
        module.validate_screen_signature(content, "image/png")


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
