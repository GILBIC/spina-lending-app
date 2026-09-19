"""Shared exact-template binding primitives; no schedule generation or pricing."""

from copy import deepcopy
from decimal import Decimal
from docx.oxml.ns import qn
from docx.table import _Row
from docx.text.paragraph import Paragraph


def all_paragraphs(doc):
    roots = [doc.element]
    for section in doc.sections:
        roots.extend([section.header._element, section.footer._element])
    seen = set()
    for root in roots:
        if id(root) in seen:
            continue
        seen.add(id(root))
        for el in root.iter(qn("w:p")):
            yield Paragraph(el, doc)


def replace_tokens(paragraph, mapping):
    # Replace across runs without erasing unaffected Word fields or pictures.
    for token, value in mapping.items():
        while token in paragraph.text:
            start = paragraph.text.index(token)
            end = start + len(token)
            offset = 0
            for run in paragraph.runs:
                text = run.text
                run_end = offset + len(text)
                if offset < end and run_end > start:
                    left = max(0, start - offset)
                    right = min(len(text), end - offset)
                    insert = value if offset <= start < run_end else ""
                    run.text = text[:left] + insert + text[right:]
                offset = run_end


def set_text(paragraph, text):
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


def row_values(row):
    return [
        str(row.installment_number),
        row.due_date.isoformat(),
        f"{row.principal_component:,.2f}",
        f"{row.interest_component:,.2f}",
        "0.00",
        f"{row.contractual_amount:,.2f}",
        f"{row.scheduled_remaining_principal:,.2f}",
    ]


def _display_rows(case: dict) -> list[list[str]]:
    """Prepare display cells without changing contractual principal/interest rows."""
    result = case["projection"]
    values = [row_values(row) for row in result.rows]
    if case.get("product") == "Regular":
        cumulative_due = Decimal("0.00")
        for source, cells in zip(result.rows, values, strict=True):
            cumulative_due += source.contractual_amount
            balance = result.total_due - cumulative_due
            cells[-1] = f"{balance:,.2f}"
    return values


def fill_table(table, rows):
    model = deepcopy(table.rows[1]._tr)
    for row in list(table.rows)[1:]:
        table._tbl.remove(row._tr)
    for values in rows:
        element = deepcopy(model)
        table._tbl.append(element)
        row = _Row(element, table)
        for cell, value in zip(row.cells, values, strict=True):
            set_text(cell.paragraphs[0], value)
