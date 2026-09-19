"""Prepare an exported synthetic specimen PDF, without changing text layout.

Corrects sub-point export page-box drift to the original 576x936 pt Folio page
and labels PDF metadata as synthetic. Existing text, images and pagination are
not scaled, moved or rewritten. An input outside a 1 pt tolerance is rejected.
This is an offline proof utility, NOT a production document-generation API.
"""
import argparse
from pathlib import Path

import fitz

from synthetic_annex_a import NOTICE


def prepare(source: Path, target: Path) -> None:
    if source.resolve() == target.resolve() or target.exists():
        raise ValueError('Do not overwrite an input or an existing output')
    with fitz.open(source) as doc:
        for page in doc:
            if NOTICE not in page.get_text():
                raise ValueError('Only stamped synthetic specimens are accepted')
            if abs(page.rect.width - 576) > 1 or abs(page.rect.height - 936) > 1:
                raise ValueError('Exported page size is not within 1 pt of source Folio')
            page.set_mediabox(fitz.Rect(0, 0, 576, 936))
            page.set_cropbox(fitz.Rect(0, 0, 576, 936))
        metadata = doc.metadata
        metadata['title'] = 'SYNTHETIC Annex A - NOT FOR SIGNING OR RELEASE'
        metadata['subject'] = 'Offline test data only; not approved, signed, issued or released'
        metadata['keywords'] = 'SPINA, synthetic, PDF layout proof, unsigned, not for release'
        doc.set_metadata(metadata)
        target.parent.mkdir(parents=True, exist_ok=True)
        doc.save(target)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('target', type=Path)
    a = p.parse_args()
    prepare(a.source, a.target)
