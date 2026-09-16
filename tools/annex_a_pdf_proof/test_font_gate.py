"""Font-gate contracts; accepting names alone is not PDF/rendering acceptance."""
from importlib import import_module
from importlib.util import find_spec

import fitz
import pytest


def gate():
    assert find_spec('font_gate') is not None, 'Arial PDF font gate is missing (TDD RED)'
    return import_module('font_gate')


@pytest.mark.parametrize('name', [
    'Arial', 'ArialMT', 'Arial-BoldMT', 'Arial-ItalicMT',
    'Arial-BoldItalicMT', 'Arial-Bold', 'AAAAAA+ArialMT',
])
def test_accepts_exact_arial_names_and_pdf_subset_prefix(name):
    assert gate().require_arial_names([name]) == [name]


@pytest.mark.parametrize('name', [
    'LiberationSans', 'Arimo', 'Helvetica', 'ArialUnicodeMS',
    'NotArialMT', '', 'ArialMT-Fallback',
])
def test_rejects_substitutions_and_loose_name_matches(name):
    with pytest.raises(ValueError):
        gate().require_arial_names([name])


def test_no_fonts_is_not_a_pass():
    with pytest.raises(ValueError):
        gate().require_arial_names([])


def test_real_pdf_using_helvetica_is_rejected(tmp_path):
    path = tmp_path / 'substitution.pdf'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 50), 'Synthetic font test', fontname='helv')
        doc.save(path)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        gate().verify_arial_pdf(path)
    assert path.read_bytes() == before


def test_blank_pdf_is_not_font_evidence(tmp_path):
    path = tmp_path / 'blank.pdf'
    with fitz.open() as doc:
        doc.new_page()
        doc.save(path)
    with pytest.raises(ValueError):
        gate().verify_arial_pdf(path)


def test_arial_name_without_embedded_font_is_rejected(tmp_path):
    path = tmp_path / 'unembedded.pdf'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 50), 'Synthetic font resource test', fontname='helv')
        # Deliberately label an unembedded Base14 resource as Arial: a name alone
        # must not satisfy the PDF gate. This is not a real Arial test fixture.
        xref = page.get_fonts()[0][0]
        doc.xref_set_key(xref, 'BaseFont', '/ArialMT')
        doc.save(path)
    with pytest.raises(ValueError, match='not embedded'):
        gate().verify_arial_pdf(path)
