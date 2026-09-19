from datetime import UTC, datetime
from io import BytesIO

from pypdf import PdfReader

from gilbic_backend.client_document_rendering import render_record_copy
from gilbic_backend.client_payment_api import _payment_payload
from test_client_payment_api import CLIENT_USER_ID, FakePayments


def test_literal_unicode_markup_and_exact_money_are_not_interpreted_or_recomputed():
    payment = _payment_payload(
        FakePayments().list_for_user(user_id=CLIENT_USER_ID).payments[0]
    )
    payment.update(
        amount="987654321.09",
        official_balance="999999999.99",
        previous_balance="1.00",
        edit_version=7,
        note='<img src="https://invalid.example/private"> & <b>literal</b>',
        loan_type_name="José & Mañalac",
    )
    content = render_record_copy(
        title="Payment record copy",
        client={"client_name": "José Mañalac", "client_code": "SYNTHETIC"},
        generated_at=datetime(2026, 9, 19, tzinfo=UTC),
        payments=[payment],
    )
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
    for value in (
        "José Mañalac",
        "José & Mañalac",
        "987654321.09",
        "999999999.99",
        "1.00",
        '<img src="https://invalid.example/private">',
        "& <b>literal</b>",
        "Correction version",
        "2026-09-19T00:00:00+00:00",
    ):
        assert value in text


def test_long_voided_record_splits_without_losing_note_and_marks_every_page():
    payment = _payment_payload(
        FakePayments().list_for_user(user_id=CLIENT_USER_ID).payments[1]
    )
    payment.update(
        note=("Synthetic long note with exact recorded facts. " * 160) + " END_OF_NOTE",
        edit_version=3,
    )
    content = render_record_copy(
        title="Payment record copy",
        client={"client_name": "Synthetic Client", "client_code": "SYNTHETIC"},
        generated_at=datetime(2026, 9, 19, tzinfo=UTC),
        payments=[payment],
        voided=True,
    )
    pages = PdfReader(BytesIO(content)).pages
    assert len(pages) > 1
    assert "END_OF_NOTE" in pages[-1].extract_text()
    for number, page in enumerate(pages, start=1):
        assert "VOIDED" in page.extract_text()
        assert "VOIDED - SPINA server record copy" in page.extract_text()
        assert "GBC-20260805-00000008" in page.extract_text()
        assert f"Page {number}" in page.extract_text()
