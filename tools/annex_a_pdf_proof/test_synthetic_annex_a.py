"""Explicit local proof tests; require the original hash-locked Annex A R2.

Run with SPINA_ANNEX_TEMPLATE set; missing assets fail rather than skip.
These tests are not an application integration or production authorization.
"""
from importlib import import_module
from importlib.util import find_spec
import os
from pathlib import Path
import zipfile

from docx import Document
import pytest

KEYS = (
    'borrower_name', 'company_line', 'document_id', 'loan_id', 'cif_version',
    'packet_id', 'packet_version', 'schedule_id', 'schedule_version',
    'generated_at', 'approval_evidence',
)


def module():
    assert find_spec('synthetic_annex_a') is not None, 'Synthetic template binder is missing (TDD RED)'
    return import_module('synthetic_annex_a')


def template():
    p = Path(os.environ['SPINA_ANNEX_TEMPLATE'])
    assert p.is_file(), 'The approved original Annex A R2 is required'
    return p


@pytest.mark.parametrize('count', [1, 7, 8, 60, 104])
def test_every_row_exact_once_with_matching_source_money(count, tmp_path):
    m = module()
    before = template().read_bytes()
    case = m.make_case(count)
    source = case['source']
    out = tmp_path / 'proof.docx'
    m.build_docx(template(), out, case, m.synthetic_context(count))
    doc = Document(out)
    tables = [t for t in doc.tables if len(t.columns) == 7]
    actual = [[c.text for c in r.cells] for t in tables for r in t.rows[1:]]
    assert actual == [m.row_values(row) for row in case['projection'].rows]
    assert len(actual) == count
    assert actual[-1][-1] == '0.00'
    assert len(tables) == (1 if count <= 7 else 2)
    assert case['source'] == source
    assert template().read_bytes() == before


@pytest.mark.parametrize('key', KEYS)
def test_missing_context_blocks_output(key, tmp_path):
    m = module()
    context = m.synthetic_context(8)
    context.pop(key)
    out = tmp_path / 'must-not-exist.docx'
    with pytest.raises(m.SyntheticProofError):
        m.build_docx(template(), out, m.make_case(8), context)
    assert not out.exists()


@pytest.mark.parametrize('value', ['', '   ', '{unresolved}', None])
def test_blank_or_unresolved_context_blocks_output(value, tmp_path):
    m = module()
    context = m.synthetic_context(1)
    context['borrower_name'] = value
    out = tmp_path / 'must-not-exist.docx'
    with pytest.raises(m.SyntheticProofError):
        m.build_docx(template(), out, m.make_case(1), context)
    assert not out.exists()


def test_modified_template_is_rejected(tmp_path):
    m = module()
    changed = tmp_path / 'wrong.docx'
    changed.write_bytes(template().read_bytes() + b'changed')
    with pytest.raises(m.SyntheticProofError):
        m.build_docx(changed, tmp_path / 'no.docx', m.make_case(1), m.synthetic_context(1))


def test_no_placeholder_and_logo_and_word_fields_preserved(tmp_path):
    m = module()
    out = tmp_path / 'proof.docx'
    m.build_docx(template(), out, m.make_case(104), m.synthetic_context(104))
    d = Document(out)
    all_text = '\n'.join(p.text for p in m.all_paragraphs(d))
    assert '{' not in all_text and '}' not in all_text
    assert 'Template instruction:' not in all_text
    assert 'Working layout R2' not in all_text
    assert 'SYNTHETIC TEST COPY - NOT FOR SIGNING OR RELEASE' in all_text
    assert 'UNSIGNED TEST ONLY' in all_text
    assert 'Scheduled Remaining Principal' in all_text
    with zipfile.ZipFile(template()) as old, zipfile.ZipFile(out) as new:
        images = [n for n in old.namelist() if n.startswith('word/media/')]
        assert images
        assert all(old.read(n) == new.read(n) for n in images)
        footer = new.read('word/footer1.xml').decode()
        assert 'NUMPAGES' in footer and 'PAGE' in footer
        assert not any(n.startswith('word/fonts/') for n in new.namelist())


def test_output_cannot_overwrite_template(tmp_path):
    m = module()
    with pytest.raises(m.SyntheticProofError):
        m.build_docx(template(), template(), m.make_case(1), m.synthetic_context(1))


def test_totals_summary_stays_together(tmp_path):
    m = module()
    out = tmp_path / 'proof.docx'
    m.build_docx(template(), out, m.make_case(104), m.synthetic_context(104))
    d = Document(out)
    totals = next(t for t in d.tables if t.cell(0, 0).text == 'TOTAL SCHEDULED PRINCIPAL')
    for row in totals.rows[:-1]:
        assert all(p.paragraph_format.keep_with_next for cell in row.cells for p in cell.paragraphs)
