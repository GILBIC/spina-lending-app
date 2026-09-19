"""Preserve the delivered T02/T03 Word assets and their approved draft text.

Standard-library OOXML checks only; not a renderer, source-authority check,
tax calculator, signing endpoint or production document issuance test.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[2]
FORM_ROOT = ROOT / "docs/forms-documents/2026-09-16"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
LOGO_SHA256 = "97b8196dd8e7361168c82b26ad42d8b8eb7da742d57c7d3db06361c621556656"
ASSEMBLY_NOTE = (
    "ASSEMBLY NOTE: The abbreviated Annex A below is a retained source "
    "illustration, not a complete loan schedule. Replace it with ONE complete "
    "product-specific T05 before final signing. Regular uses Remaining Total "
    "Payable; 7x7 uses Scheduled Remaining Principal. Never issue two competing schedules."
)
CASES = {
    "T02": (
        "T02_Cash_Loan_Agreement_R4_DST_GRT.docx",
        "22f91c15860a0ad436c4b2d80f75e7b9c257b1ecf6fc23cdc10bf8192814fe20",
        "T02-cash-loan-agreement-r4-tax-itemization.md",
        "b10066a51acd05843d03a238077f62db70fc09a1",
        "e51c95eaeeadf8a35372b121d58745955657321f05ee07a34c7f46ceb65a9407",
        "R4",
    ),
    "T03": (
        "T03_Loan_Disclosure_R3_DST_GRT.docx",
        "c82b47da19a2b8f3e1dbcc7f5eec3e31eed902768979d00476f6bada053af5f6",
        "T03-loan-disclosure-r3-tax-itemization.md",
        "eaa60592fb2e11e938117c298fd2361f7d35c6ab",
        "6799c8d555ea8a677723144a049c665f14580240bcee8d4917bc93753d6bb585",
        "R3",
    ),
}


def _asset(document: str) -> Path:
    path = FORM_ROOT / "assets" / CASES[document][0]
    assert path.is_file(), f"Formatted draft asset is missing: {path.name}"
    return path


def _text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(W + "t"))


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _body_lines(root: ET.Element) -> list[str]:
    body = root.find(W + "body")
    assert body is not None
    lines: list[str] = []
    for element in body:
        if element.tag == W + "p":
            lines.append(_text(element))
        elif element.tag == W + "tbl":
            for row in element.findall(W + "tr"):
                cells = [
                    " / ".join(_text(p) for p in cell.findall(W + "p"))
                    for cell in row.findall(W + "tc")
                ]
                lines.append(" | ".join(cells))
    return [_normalize(line) for line in lines if line.strip()]


@pytest.mark.parametrize("document", CASES)
def test_formatted_asset_is_the_exact_delivered_copy_with_retained_source(document):
    path = _asset(document)
    manifest = json.loads((FORM_ROOT / "assets/manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "controlled-draft-unbound"
    assert manifest["source_binding_implemented"] is False
    assert manifest["production_issuance_enabled"] is False
    assert set(manifest["documents"]) == set(CASES)
    record = manifest["documents"][document]
    name, digest, mirror, blob, original, _ = CASES[document]
    assert record["file"] == name
    assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert record["source_docx_sha256"] == original
    assert record["review_mirror"] == f"templates/{mirror}"
    assert record["review_mirror_git_blob"] == blob
    with ZipFile(path) as package:
        assert package.testzip() is None


@pytest.mark.parametrize("document", CASES)
def test_word_body_matches_the_approved_text_including_tables_and_placeholders(document):
    with ZipFile(_asset(document)) as package:
        lines = _body_lines(ET.fromstring(package.read("word/document.xml")))
    mirror = (FORM_ROOT / "templates" / CASES[document][2]).read_bytes()
    # Git object identity for the reviewed source, not document signing security.
    blob = b"blob " + str(len(mirror)).encode("ascii") + b"\0" + mirror
    assert hashlib.sha1(blob, usedforsecurity=False).hexdigest() == CASES[document][3]
    source = mirror.decode("utf-8").split("```text\n", 1)[1].rsplit("\n```", 1)[0]
    expected = [_normalize(line) for line in source.splitlines() if line.strip()]
    if document == "T02":
        assert lines.count(ASSEMBLY_NOTE) == 1
        note_position = lines.index(ASSEMBLY_NOTE)
        table_position = next(
            index for index, line in enumerate(lines)
            if line.startswith("No. | Due Date | Principal | Interest |")
        )
        assert lines.index("ANNEX A - SCHEDULE OF PAYMENTS") < note_position < table_position
        lines.remove(ASSEMBLY_NOTE)
    else:
        assert ASSEMBLY_NOTE not in lines
    assert lines == expected


@pytest.mark.parametrize("document", CASES)
def test_original_layout_logo_and_dynamic_page_fields_remain_in_the_draft(document):
    with ZipFile(_asset(document)) as package:
        names = package.namelist()
        root = ET.fromstring(package.read("word/document.xml"))
        sizes = root.findall(".//" + W + "pgSz")
        assert sizes and all(
            size.get(W + "w") == "11520" and size.get(W + "h") == "18720"
            for size in sizes
        )  # Folio 8 x 13 inches in Word twips.
        styles = ET.fromstring(package.read("word/styles.xml"))
        normal = styles.find(f"{W}style[@{W}styleId='Normal']/{W}rPr/{W}rFonts")
        assert normal is not None
        assert normal.get(W + "ascii") == normal.get(W + "hAnsi") == "Arial"
        media = [name for name in names if name.startswith("word/media/")]
        assert media == ["word/media/image1.png"]
        assert hashlib.sha256(package.read(media[0])).hexdigest() == LOGO_SHA256
        footer = ET.fromstring(package.read("word/footer1.xml"))
        fields = {node.text.strip() for node in footer.iter(W + "instrText") if node.text}
        assert {"PAGE", "NUMPAGES"} <= fields
        assert f"Working {CASES[document][5]}" in _text(footer)
        assert "SYSTEM-ALIGNED DRAFT" in _text(root)
        assert not any(name.startswith(("word/fonts/", "word/embeddings/")) for name in names)
        assert not any("vbaproject" in name.lower() for name in names)
