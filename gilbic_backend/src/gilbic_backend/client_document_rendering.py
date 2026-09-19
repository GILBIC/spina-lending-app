"""Read-only record copies; no receipt numbering or financial calculations."""

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NOTICE = (
    "Read-only copy of current server records; not an original issued receipt or tax invoice. "
    "Corrections and voids are shown as recorded. This download does not post a payment."
)


def _paragraph(value, style):
    text = "Not recorded" if value is None else str(value)
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _table(items, styles, *, repeat_rows=0):
    table = Table(
        [
            [_paragraph(label, styles["label"]), _paragraph(value, styles["body"])]
            for label, value in items
        ],
        colWidths=[145, 362],
        hAlign="LEFT",
        splitInRow=1,
        repeatRows=repeat_rows,
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f2f4")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c3c9cf")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _payment_items(payment):
    return [
        ("Receipt reference", payment["receipt_number"]),
        ("Loan", payment["loan_number"]),
        ("Product", payment["loan_type_name"]),
        ("Collection date", payment["collection_date"]),
        ("Recorded at", payment["recorded_at"]),
        ("Record status", str(payment["status"]).upper()),
        ("Correction version", payment["edit_version"]),
        ("Entry type", payment["entry_type"]),
        ("Amount (PHP)", payment["amount"]),
        ("Previous balance (PHP)", payment["previous_balance"]),
        ("Recorded official balance (PHP)", payment["official_balance"]),
        ("Covered dates", ", ".join(payment["covered_dates"]) or "None recorded"),
        ("Voided at", payment["voided_at"]),
        ("Void reason", payment["void_reason"]),
        ("Note", payment["note"]),
    ]


def render_record_copy(
    *,
    title: str,
    client: dict,
    generated_at: datetime,
    loans=(),
    payments=(),
    voided=False,
) -> bytes:
    """Render the existing API values literally, including corrected/voided rows."""
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "RecordTitle", parent=base["Title"], alignment=0, fontSize=18, leading=22
        ),
        "heading": ParagraphStyle(
            "RecordHeading", parent=base["Heading2"], fontSize=11, leading=15
        ),
        "body": ParagraphStyle(
            "RecordBody",
            parent=base["BodyText"],
            fontSize=9,
            leading=12,
            spaceAfter=0,
            splitLongWords=True,
        ),
        "label": ParagraphStyle(
            "RecordLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            spaceAfter=0,
        ),
    }
    story = [
        _paragraph(title, styles["title"]),
        _paragraph(f"Generated at {generated_at.isoformat()} (UTC)", styles["body"]),
        Spacer(1, 10),
        _paragraph(NOTICE, styles["body"]),
        Spacer(1, 12),
        _table(
            [
                ("Client", client["client_name"]),
                ("Client reference", client["client_code"]),
            ],
            styles,
        ),
        Spacer(1, 12),
    ]
    for loan in loans:
        story.extend(
            [
                _paragraph(f"Loan {loan['loan_number']}", styles["heading"]),
                _table(
                    [
                        ("Product", loan["loan_type_name"]),
                        ("Status", loan["status"]),
                        ("Principal (PHP)", loan["principal"]),
                        ("Recorded daily amount (PHP)", loan["daily_amount"]),
                        ("Release date", loan["date_released"]),
                        ("Recorded due date", loan["due_date"]),
                        ("Recorded remaining balance (PHP)", loan["remaining_balance"]),
                        ("State version", loan["state_version"]),
                        ("Recorded payment count", loan["payment_count"]),
                    ],
                    styles,
                ),
                Spacer(1, 12),
            ]
        )
    if not payments:
        story.append(_paragraph("No payment records available.", styles["body"]))
    for payment in payments:
        status = "VOIDED" if payment["is_voided"] else "Payment record"
        story.extend(
            [
                _paragraph(f"{status}: {payment['receipt_number']}", styles["heading"]),
                _table(_payment_items(payment), styles, repeat_rows=1),
                Spacer(1, 12),
            ]
        )
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=40,
        bottomMargin=40,
        title=title,
        author="SPINA",
    )

    def page(canvas, document):
        canvas.saveState()
        if voided:
            canvas.setFillColor(colors.HexColor("#f9dddd"))
            canvas.setFont("Helvetica-Bold", 68)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "VOIDED")
        canvas.restoreState()
        canvas.saveState()
        canvas.setFont("Helvetica-Bold" if voided else "Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#a12727" if voided else "#555555"))
        canvas.drawString(
            44,
            22,
            "VOIDED - SPINA server record copy"
            if voided
            else "SPINA - server record copy",
        )
        canvas.drawRightString(A4[0] - 44, 22, f"Page {document.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
