"""Offline amount-filled T02/T03 copies, never borrower-ready documents.

Uses fixed synthetic precomputed amounts and the existing template_amounts map.
No source authentication, tax pricing, signing, release, PDF or visual clearance.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs/forms-documents/2026-09-16/assets"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NOTICE = "SYNTHETIC AMOUNT PREVIEW - NOT FOR SIGNING OR RELEASE"
FILES = {
    "T02": "T02_Cash_Loan_Agreement_R4_DST_GRT.docx",
    "T03": "T03_Loan_Disclosure_R3_DST_GRT.docx",
}
EXPECTED = {
    "{Approved Principal/Gross Loan Amount}": "5,000.00",
    "{Approved Gross Principal}": "5,000.00",
    "{DST Upfront Amount}": "12.34",
    "{Renewal Offset Amount}": "250.00",
    "{Authoritative total deductions}": "300.23",
    "{Total Approved Deductions}": "300.23",
    "{Authoritative net proceeds}": "4,699.77",
    "{Authorized Net Proceeds}": "4,699.77",
    "{Total Contractual Interest}": "1,000.00",
    "{GRT Recovery in Repayments}": "56.78",
    "{Other Scheduled Charges}": "10.11",
    "{Authoritative Scheduled Total}": "6,066.89",
}


def _module():
    try:
        return import_module("synthetic_tax_documents")
    except ModuleNotFoundError as exc:
        if exc.name != "synthetic_tax_documents":
            raise
        pytest.fail("Synthetic T02/T03 amount-preview builder is not implemented", pytrace=False)


def _parts(path):
    with ZipFile(path) as package:
        assert package.testzip() is None
        return {name: package.read(name) for name in package.namelist()}


def _paragraphs(parts):
    root = ET.fromstring(parts["word/document.xml"])
    return [
        "".join(node.text or "" for node in paragraph.iter(W + "t"))
        for paragraph in root.iter(W + "p")
    ]


def _replaced(text):
    for token, amount in EXPECTED.items():
        text = text.replace(token, amount)
    return text


@pytest.fixture(params=tuple(FILES), ids=tuple(FILES))
def source(request, tmp_path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    path = source_dir / FILES[request.param]
    shutil.copyfile(ASSETS / path.name, path)
    return path


def test_fills_every_amount_occurrence_and_preserves_all_other_body_text(source, tmp_path):
    builder = _module()
    before = source.read_bytes()
    original = _paragraphs(_parts(source))
    output = tmp_path / "synthetic-amount-preview.docx"
    builder.build_tax_amount_preview(template=source, output=output)
    actual = _paragraphs(_parts(output))
    assert actual == [NOTICE] + [_replaced(text) for text in original]
    text = "\n".join(actual)
    assert not any(token in text for token in EXPECTED)
    assert "{Borrower Full Name}" in text
    assert "DRAFT" in text
    assert "within the agreed repayments" in text
    assert source.read_bytes() == before


def test_retains_logo_styles_headers_footers_and_folio_section_geometry(source, tmp_path):
    builder = _module()
    original = _parts(source)
    output = tmp_path / "synthetic-layout.docx"
    builder.build_tax_amount_preview(template=source, output=output)
    actual = _parts(output)
    protected = [
        name for name in original
        if name.startswith(("word/media/", "word/header", "word/footer"))
        or name == "word/styles.xml"
    ]
    assert protected and any(name.startswith("word/media/") for name in protected)
    for name in protected:
        assert actual[name] == original[name], name
    for tag in ("sectPr", "tblPr", "tcPr", "rPr"):
        def properties(parts):
            root = ET.fromstring(parts["word/document.xml"])
            return [ET.tostring(node) for node in root.iter(W + tag)]
        assert properties(actual) == properties(original), tag
    root = ET.fromstring(actual["word/document.xml"])
    size = next(root.iter(W + "pgSz"))
    assert size.get(W + "w") == "11520" and size.get(W + "h") == "18720"
    footer_xml = b"".join(data for name, data in actual.items() if name.startswith("word/footer"))
    assert b"PAGE" in footer_xml and b"NUMPAGES" in footer_xml


def test_preserves_every_unmapped_placeholder_and_does_not_add_execution_evidence(source, tmp_path):
    builder = _module()
    original = "\n".join(_paragraphs(_parts(source)))
    output = tmp_path / "synthetic-unresolved.docx"
    builder.build_tax_amount_preview(template=source, output=output)
    actual = "\n".join(_paragraphs(_parts(output)))
    tokens = lambda text: re.findall(r"\{[^{}]+\}", text)
    assert tokens(actual) == [token for token in tokens(original) if token not in EXPECTED]
    assert "{Borrower Full Name}" in actual
    assert "{Authoritative amount financed}" in actual or "{Authoritative Amount Financed}" in actual
    assert "SYNTHETIC AMOUNT PREVIEW" in actual
    # Partial amount substitution must not pretend to remove remaining release gates.
    assert "Do not sign or issue" in actual


def test_uses_existing_read_only_amount_map_once_per_output(source, tmp_path, monkeypatch):
    builder = _module()
    from gilbic_backend.loan_document_tax_breakdown import LoanDocumentTaxBreakdown
    original_method = LoanDocumentTaxBreakdown.template_amounts
    calls = []
    def tracked(self):
        values = original_method(self)
        calls.append(dict(values))
        return values
    monkeypatch.setattr(LoanDocumentTaxBreakdown, "template_amounts", tracked)
    output = tmp_path / "synthetic-shared-map.docx"
    builder.build_tax_amount_preview(template=source, output=output)
    assert calls == [EXPECTED]
    assert output.is_file()


def test_rejects_changed_source_bytes_before_creating_an_output(source, tmp_path):
    builder = _module()
    changed = source.read_bytes() + b"\n"
    source.write_bytes(changed)
    output = tmp_path / "blocked.docx"
    with pytest.raises(ValueError):
        builder.build_tax_amount_preview(template=source, output=output)
    assert not output.exists()
    assert source.read_bytes() == changed


def test_never_overwrites_an_existing_output(source, tmp_path):
    builder = _module()
    output = tmp_path / "existing.docx"
    output.write_bytes(b"existing evidence - must remain unchanged")
    before = source.read_bytes()
    with pytest.raises(ValueError):
        builder.build_tax_amount_preview(template=source, output=output)
    assert output.read_bytes() == b"existing evidence - must remain unchanged"
    assert source.read_bytes() == before


def test_never_overwrites_source_even_through_a_normalized_path(source):
    builder = _module()
    before = source.read_bytes()
    with pytest.raises(ValueError):
        builder.build_tax_amount_preview(template=source, output=source.parent / "." / source.name)
    assert source.read_bytes() == before


def test_repeated_preparation_has_same_visible_amounts_and_no_extra_charge(source, tmp_path):
    builder = _module()
    outputs = [tmp_path / "first.docx", tmp_path / "second.docx"]
    before = source.read_bytes()
    for output in outputs:
        builder.build_tax_amount_preview(template=source, output=output)
    assert _paragraphs(_parts(outputs[0])) == _paragraphs(_parts(outputs[1]))
    assert source.read_bytes() == before


def _pdf_amount_counts(text):
    return {
        amount: len(re.findall(r"(?<![\d.,])" + re.escape(amount) + r"(?![\d.,])", text))
        for amount in sorted(set(EXPECTED.values()))
    }


def test_pinned_pdf_preserves_amounts_pages_and_saves_review_evidence(source, tmp_path):
    """Exercise the existing builder and real converter on the isolated CI runner.

    Artifacts are partial synthetic previews, not an approved borrower packet.
    Missing pinned-runner prerequisites fail rather than silently skipping.
    """
    import hashlib
    import json
    import os
    import subprocess

    import fitz

    soffice = os.environ.get("SPINA_SOFFICE", "")
    proof_output = os.environ.get("SPINA_PROOF_OUTPUT", "")
    assert soffice and Path(soffice).is_file(), "Pinned SPINA_SOFFICE is required"
    assert proof_output, "SPINA_PROOF_OUTPUT is required"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=15,
    ).stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    assert event_path, "GitHub event is required to verify the proof revision"
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    expected_commit = event.get("pull_request", {}).get("head", {}).get(
        "sha", os.environ.get("GITHUB_SHA", "")
    )
    assert commit == expected_commit, "Proof must match the requested revision"
    version = subprocess.run(
        [soffice, "--version"], check=True, capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    assert "LibreOffice 26.2.5.2" in version, "Use the existing pinned converter"

    from font_gate import verify_arial_pdf

    before = source.read_bytes()
    expected_text = "\n".join(_replaced(text) for text in _paragraphs(_parts(source)))
    expected_counts = _pdf_amount_counts(expected_text)
    assert all(expected_counts.values()), "Every fixture amount must be exercised"
    output = Path(proof_output).resolve() / "Tax-Previews" / source.name.split("_")[0]
    assert not output.is_relative_to(ROOT.resolve()), "Keep proof files outside checkout"
    output.mkdir(parents=True, exist_ok=False)
    docx_path = tmp_path / (source.name.split("_")[0] + "_SYNTHETIC_AMOUNT_PREVIEW.docx")
    _module().build_tax_amount_preview(template=source, output=docx_path)
    profile = tmp_path / "lo-profile"
    profile.mkdir()
    converted = subprocess.run(
        [soffice, "-env:UserInstallation=" + profile.resolve().as_uri(),
         "--headless", "--norestore", "--convert-to", "pdf:writer_pdf_Export",
         "--outdir", str(output), str(docx_path.resolve())],
        check=True, capture_output=True, text=True, timeout=180,
    )
    (output / "conversion.txt").write_text(
        version + "\n" + converted.stdout + converted.stderr, encoding="utf-8"
    )
    pdf = output / (docx_path.stem + ".pdf")
    assert pdf.is_file() and pdf.stat().st_size > 0, "Converter did not create PDF"
    assert source.read_bytes() == before
    pages_dir = output / "Pages"
    pages_dir.mkdir()
    with fitz.open(pdf) as document:
        assert len(document) > 0
        # Preserve review evidence even if a subsequent font/layout check fails.
        for number, page in enumerate(document, 1):
            page.get_pixmap(dpi=144, alpha=False).save(pages_dir / f"page-{number}.png")
        page_texts = [page.get_text() for page in document]
        sizes = []
        for number, page in enumerate(document, 1):
            sizes.append([page.rect.width, page.rect.height])
            # Observe raw Folio export drift; never scale/rewrite the PDF to pass.
            assert abs(page.rect.width - 576) <= 1 and abs(page.rect.height - 936) <= 1
            assert not list(page.widgets() or ()), "Preview must not be a fillable PDF"
            assert re.search(
                rf"\bPage\s+{number}\s+of\s+{len(document)}\b", page_texts[number - 1],
                re.IGNORECASE,
            ), f"Incorrect page counter on page {number}"
            for word in page.get_text("words", clip=fitz.Rect(-10000, -10000, 10000, 10000)):
                assert (word[0] >= -0.5 and word[1] >= -0.5
                        and word[2] <= page.rect.width + 0.5
                        and word[3] <= page.rect.height + 0.5), (number, word)
        text = " ".join(" ".join(page_texts).split())
        assert NOTICE in " ".join(page_texts[0].split())
        assert _pdf_amount_counts(text) == expected_counts, "PDF changed an amount/occurrence"
        assert not any(token in text for token in EXPECTED)
        assert "{Borrower Full Name}" in text and "DRAFT" in text
        assert "Do not sign or issue" in text
        assert "within the agreed repayments" in text
        assert "Amount Financed}" in text or "amount financed}" in text
        fonts = verify_arial_pdf(pdf)  # Actual font check; no substitution bypass.
        report = {
            "scope": "SYNTHETIC_AMOUNT_PREVIEW_PDF_ONLY", "status": "PASS",
            "commit": commit, "template_sha256": hashlib.sha256(before).hexdigest(),
            "docx_sha256": hashlib.sha256(docx_path.read_bytes()).hexdigest(),
            "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "pdf_bytes": pdf.stat().st_size, "converter": version,
            "pages": len(document), "page_points": sizes,
            "folio_export_tolerance_pt": 1, "page_boxes_modified": False,
            "amount_occurrences": expected_counts, "fonts": fonts,
            "visual_review": "PENDING_MANUAL_REVIEW",
            "source_binding_implemented": False, "production_issuance_enabled": False,
        }
    (output / "verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
