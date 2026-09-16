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
