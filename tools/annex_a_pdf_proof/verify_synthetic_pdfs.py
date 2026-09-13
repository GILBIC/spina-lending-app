"""Check six OFFLINE synthetic Annex A PDFs against existing SPINA rows.

Requires PyMuPDF and the companion synthetic_annex_a.py. This verifier does not
replace visual review, prove legal rates or authorize a real document. Only use
with the five fixed 7x7 fixtures and one fixed Regular fixture. No PDF bytes are
changed here.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import fitz

from synthetic_annex_a import (
    CASES,
    NOTICE,
    make_case,
    make_regular_case,
    row_values,
)

MONEY = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
ROW = re.compile(
    r"^([1-9]\d*)\s*\n(\d{4}-\d{2}-\d{2})\s*\n"
    + r"\s*\n".join(f"({MONEY})" for _ in range(5)) + r"\s*$",
    re.MULTILINE,
)
TOTAL_LABELS = (
    'TOTAL SCHEDULED PRINCIPAL', 'TOTAL CONTRACTUAL INTEREST',
    'TOTAL OTHER LAWFUL SCHEDULED CHARGES', 'TOTAL AMOUNT PAYABLE',
    'FINAL SCHEDULED REMAINING PRINCIPAL',
)
ACKNOWLEDGMENT_LABELS = (
    'IV. BORROWER ACKNOWLEDGMENT',
    'I acknowledge receipt and review of the complete Schedule',
    'Borrower Printed Name',
    'Borrower Signature / Date',
    'Management Approval / Evidence',
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify(path: Path, count: int, *, regular: bool = False) -> dict:
    case = make_regular_case() if regular else make_case(count)
    result = case['projection']
    expected = [row_values(row) for row in result.rows]
    balance_label = 'Capital Recovery Balance' if regular else 'Scheduled Remaining Principal'
    total_labels = TOTAL_LABELS
    if regular:
        # Check the display independently; do not call the renderer's display helper.
        cumulative_due = Decimal('0.00')
        for source, cells in zip(result.rows, expected, strict=True):
            cumulative_due += source.contractual_amount
            balance = max(result.total_principal - cumulative_due, Decimal('0.00'))
            cells[-1] = f'{balance:,.2f}'
        total_labels = TOTAL_LABELS[:-1] + ('FINAL CAPITAL RECOVERY BALANCE',)
    identity = 'REGULAR-120' if regular else str(count)
    product_label = (
        'Regular Cash Loan (synthetic only)'
        if regular
        else '7x7 Cash Loan (synthetic only)'
    )
    with fitz.open(path) as doc:
        actual, per_page, texts, fonts = [], [], [], set()
        for number, page in enumerate(doc, start=1):
            require(abs(page.rect.width - 576) < 0.001 and abs(page.rect.height - 936) < 0.001,
                    f'{path.name}: not exact Folio 8x13')
            text = page.get_text()
            texts.append(text)
            require(NOTICE in text, f'{path.name} page {number}: synthetic warning missing')
            require(f'Page {number} of {len(doc)}' in text, 'Incorrect page numbering')
            require(f'Doc: SYN-ANNEX-{identity} |' in text, 'Wrong document identity')
            require('Packet: SYN-v1' in text and 'Schedule: SYN-v1' in text, 'Missing versions')
            require(not list(page.widgets() or []), 'Fillable PDF widget present')
            require(not any(s in text for s in ('{', '}', '\ufffd', 'Template instruction:', 'Working layout R2')),
                    'Unresolved placeholder, instruction or missing glyph')
            rows = [list(match.groups()) for match in ROW.finditer(text)]
            per_page.append([int(row[0]) for row in rows])
            actual.extend(rows)
            if rows:
                compact = ' '.join(text.split())
                require(balance_label + '*' in compact, 'Repeated schedule heading missing')
            for block in page.get_text('dict')['blocks']:
                if block['type'] != 0:
                    continue
                for line in block['lines']:
                    for span in line['spans']:
                        box = fitz.Rect(span['bbox'])
                        require(page.rect.contains(box), f'Text outside page: {span["text"]!r}')
                        require(span['color'] == 0, 'Colored PDF text outside logo')
                        fonts.add(span['font'])
            for drawing in page.get_drawings():
                for color in (drawing.get('color'), drawing.get('fill')):
                    if color is not None:
                        require(max(color) - min(color) < 0.002, 'Nonneutral PDF line or fill')
        require(actual == expected, f'{path.name}: PDF rows do not match source components and approved display')
        require(len(actual) == count and actual[-1][-1] == '0.00', 'Wrong final row/display balance')
        complete_text = '\n'.join(texts)
        compact_pages = [' '.join(text.split()) for text in texts]
        acknowledgment_pages = [
            [number for number, text in enumerate(compact_pages, 1) if label in text]
            for label in ACKNOWLEDGMENT_LABELS
        ]
        require(all(len(pages) == 1 for pages in acknowledgment_pages),
                'Acknowledgment text/name/signature/approval is missing or duplicated')
        require(len({pages[0] for pages in acknowledgment_pages}) == 1,
                'Acknowledgment text/name/signature/approval is split across pages')
        require(product_label in complete_text, 'Wrong product label')
        if regular:
            explanation = ' '.join(compact_pages).lower()
            for phrase in ('presentation only', 'not accounting principal',
                           'not a payoff', 'zero does not mean fully paid'):
                require(phrase in explanation, f'Missing Regular display explanation: {phrase}')
            require('Scheduled Remaining Principal*' not in ' '.join(compact_pages),
                    'Regular presentation balance is incorrectly labelled as principal')
            require(
                '20.00% fixed contractual interest (synthetic fixture)' in complete_text,
                'Wrong Regular synthetic interest disclosure',
            )
        summaries = [i for i, text in enumerate(texts) if all(label in text for label in total_labels)]
        require(len(summaries) == 1, 'Totals block is missing, duplicated or split')
        amounts = [result.total_principal, result.total_interest, 0, result.total_due, 0]
        for label, amount in zip(total_labels, amounts, strict=True):
            require(complete_text.count(label) == 1, f'Duplicated total: {label}')
            require(re.search(re.escape(label) + r'\s+PHP\s+' + re.escape(f'{amount:,.2f}') + r'(?:\s|$)',
                              texts[summaries[0]]) is not None, f'Wrong total: {label}')
        require('UNSIGNED TEST ONLY - DO NOT SIGN' in complete_text, 'Unsigned warning missing')
        require('NOT APPROVED OR SIGNED' in complete_text, 'Synthetic approval warning missing')
        require('SYSTEM-ALIGNED DRAFT FOR COUNSEL / ACCOUNTING REVIEW' in complete_text, 'Draft label missing')
        require(result.maturity_date.isoformat() in texts[0], 'Maturity detail missing')
        require('RA 10173' in complete_text, 'Original privacy reference lost')
        return {
            'file': path.name, 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'status': 'PASS',
            'product': 'Regular' if regular else '7x7',
            'installments': count, 'pages': len(doc), 'rows_by_page': per_page,
            'scheduled_principal': str(result.total_principal), 'contractual_interest': str(result.total_interest),
            'other_scheduled_charges': '0.00', 'total_payable': str(result.total_due),
            'final_scheduled_remaining_principal': str(result.rows[-1].scheduled_remaining_principal),
            'display_balance_label': balance_label, 'final_display_balance': expected[-1][-1],
            'display_balance_is_presentation_only': regular,
            'maturity': result.maturity_date.isoformat(),
            'page_points': [576, 936], 'fillable_widgets': 0,
            'acknowledgment_page': acknowledgment_pages[0][0],
            'fonts_observed': sorted(fonts), 'visual_review': 'SEPARATE_MANUAL_CHECK',
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    reports = []
    for count in CASES:
        name = f'SPINA_Annex_A_SYNTHETIC_{count:03d}_rows.pdf'
        matches = list(args.pdf_dir.rglob(name))
        require(len(matches) == 1, f'Expected exactly one {name}')
        reports.append(verify(matches[0], count))
    regular_name = 'SPINA_Annex_A_SYNTHETIC_REGULAR_120_rows.pdf'
    regular_matches = list(args.pdf_dir.rglob(regular_name))
    require(len(regular_matches) == 1, f'Expected exactly one {regular_name}')
    reports.append(verify(regular_matches[0], 120, regular=True))
    output = json.dumps({'scope': 'OFFLINE_SYNTHETIC_PROOF_ONLY', 'results': reports}, indent=2)
    if args.report:
        require(not args.report.exists(), 'Do not overwrite an existing report')
        args.report.write_text(output + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
