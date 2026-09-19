"""Offline fixed-amount T02/T03 previews, never approved borrower documents.

Only the two hash-pinned draft templates and one synthetic amount fixture are
supported. Unmapped fields and draft warnings deliberately remain unresolved.
No loan pricing, source authentication, signing, cash release or PDF issuance.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
from io import BytesIO
from pathlib import Path

from docx import Document

from gilbic_backend.loan_document_tax_breakdown import project_loan_document_tax_breakdown
from synthetic_annex_a import all_paragraphs, replace_tokens


NOTICE = "SYNTHETIC AMOUNT PREVIEW - NOT FOR SIGNING OR RELEASE"
TEMPLATE_HASHES = frozenset({
    "22f91c15860a0ad436c4b2d80f75e7b9c257b1ecf6fc23cdc10bf8192814fe20",
    "c82b47da19a2b8f3e1dbcc7f5eec3e31eed902768979d00476f6bada053af5f6",
})


def build_tax_amount_preview(*, template: Path, output: Path) -> None:
    """Write a new synthetic copy using the existing shared amount mapping."""
    template, output = Path(template), Path(output)
    if template.resolve() == output.resolve() or output.exists() or output.is_symlink():
        raise ValueError("Never overwrite the source template or an existing output.")
    data = template.read_bytes()
    if hashlib.sha256(data).hexdigest() not in TEMPLATE_HASHES:
        raise ValueError("The exact controlled T02 R4 or T03 R3 draft is required.")

    # Deliberately precomputed fixture amounts, not tax rates or a live offer.
    amounts = project_loan_document_tax_breakdown(
        loan_version_reference="SYN-LOAN-V3",
        tax_loan_version_reference="SYN-LOAN-V3",
        tax_rule_snapshot_reference="SYN-RULE-V2",
        tax_calculation_reference="SYN-CALC-V4",
        principal=Decimal("5000.00"),
        contractual_interest=Decimal("1000.00"),
        dst_upfront=Decimal("12.34"),
        grt_in_repayments=Decimal("56.78"),
        renewal_offset=Decimal("250.00"),
        other_upfront_deductions=Decimal("37.89"),
        other_scheduled_charges=Decimal("10.11"),
        expected_total_upfront_deductions=Decimal("300.23"),
        expected_net_proceeds=Decimal("4699.77"),
        expected_total_scheduled=Decimal("6066.89"),
    ).template_amounts()

    # Parse the same verified bytes; do not re-open a potentially changed source.
    document = Document(BytesIO(data))
    for paragraph in all_paragraphs(document):
        replace_tokens(paragraph, amounts)
    notice = document.paragraphs[0].insert_paragraph_before(NOTICE, style="Caption")
    notice.paragraph_format.keep_with_next = True
    notice.paragraph_format.space_after = 0

    # Serialize before creating output. Exclusive creation also prevents a race
    # from overwriting an output that appeared after the initial path check.
    buffer = BytesIO()
    document.save(buffer)
    try:
        with output.open("xb") as target:
            target.write(buffer.getvalue())
    except FileExistsError as exc:
        raise ValueError("Never overwrite an existing output.") from exc
