"""Read-only, fail-closed Arial/embedding check for generated proof PDFs.

Checks reported font identity and embedded resources. This is not visual,
licensing, source-ownership, signature or production-document acceptance.
No font bytes are written, logged or returned.
"""
from __future__ import annotations

from pathlib import Path
import re

import fitz

_ARIAL_NAMES = frozenset({
    'arial', 'arialmt', 'arialbold', 'arialboldmt', 'arialitalic',
    'arialitalicmt', 'arialbolditalic', 'arialbolditalicmt',
})


def _name(value: str) -> str:
    without_subset = re.sub(r'^[A-Z]{6}\+', '', value)
    return re.sub(r'[ -]', '', without_subset).casefold()


def require_arial_names(names) -> list[str]:
    """Reject empty evidence and substitutes; never use an Arial substring test."""
    observed = tuple(names)
    if not observed or any(not isinstance(n, str) or _name(n) not in _ARIAL_NAMES for n in observed):
        raise ValueError(f'Expected Arial faces only; observed {observed!r}')
    return sorted(set(observed))


def verify_arial_pdf(path: Path) -> dict:
    """Require every text page's visible fonts to be Arial and embedded."""
    names, embedded = set(), set()
    with fitz.open(path) as doc:
        if not len(doc):
            raise ValueError('A PDF with no pages is not font evidence')
        for number, page in enumerate(doc, start=1):
            visible = {
                span['font']
                for block in page.get_text('dict')['blocks'] if block['type'] == 0
                for line in block['lines'] for span in line['spans']
                if span['text'].strip()
            }
            require_arial_names(visible)
            names.update(visible)
            available = set()
            for resource in page.get_fonts(full=True):
                xref, base_font = resource[0], resource[3]
                normalized = _name(base_font)
                if normalized not in {_name(n) for n in visible}:
                    continue
                if not xref or not doc.extract_font(xref)[3]:
                    raise ValueError(f'Page {number}: font is not embedded: {base_font}')
                available.add(normalized)
                embedded.add(xref)
            if not {_name(n) for n in visible}.issubset(available):
                raise ValueError(f'Page {number}: visible Arial font has no embedded resource')
    return {
        'status': 'PASS', 'fonts_observed': sorted(names),
        'embedded_font_resources': len(embedded),
        'scope': 'FONT_IDENTITY_AND_EMBEDDING_ONLY',
    }
