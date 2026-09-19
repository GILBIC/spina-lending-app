"""Offline synthetic adapter proof with real embedded Arial and real conversion.

No database, production approval, signature or cash release occurs. Retains the
exact Annex A R2 source and requires installed Arial plus configured LibreOffice.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
from uuid import uuid4

import fitz
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from gilbic_backend.document_font_gate import verify_arial_pdf
from gilbic_backend.annex_a_template_binding import _display_rows
from gilbic_backend.first_loan_annex import (
    ANNEX_R2_SHA256,
    bind_annex_docx,
    convert_annex_pdf,
    project_packet_schedule,
)
from gilbic_backend.first_loan_documents import (
    KINDS,
    REQUIRED_FIELDS,
    packet_fields,
    render_packet,
    template_bundle,
)
from gilbic_backend.first_loan_terms import (
    FirstLoanTerms,
    generate_first_loan_schedule,
    schedule_payload,
    snapshot_digest,
)


def verify_packet_projection(path: Path, record: dict) -> dict:
    """Check real rendered values and page bounds after conversion and assembly."""
    packet = record["packet"]
    projection = project_packet_schedule(packet)
    rows = _display_rows(
        {
            "projection": projection,
            "product": "Regular"
            if packet["terms"]["product_code"] == "regular"
            else "7x7",
        }
    )
    with fitz.open(path) as document:
        text = "\n".join(page.get_text() for page in document)
        lines = "\n".join(line.strip() for line in text.splitlines())
        for row in rows:
            assert lines.count("\n".join(row)) == 1, (
                f"Missing or duplicated rendered installment {row[0]} in {path.name}"
            )
        compact = "".join(text.split())
        assert record["packet_hash"] in compact
        assert "{" not in text and "}" not in text
        for value in (
            record.get("pricing_snapshot", {})
            .get("seven_by_seven_penalty_policy", {})
            .values()
        ):
            assert "".join(str(value).split()) in compact
        for page in document:
            assert not list(page.widgets() or []), "Issued PDF is still editable"
            bounds = page.rect + (-1, -1, 1, 1)
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        assert not span["text"].strip() or bounds.contains(
                            fitz.Rect(span["bbox"])
                        ), (
                            f"Text exceeds page bounds in {path.name} page {page.number + 1}"
                        )
    return {"exact_rendered_installments": len(rows), "page_bounds": "pass"}


def synthetic_template(kind: str, font: Path) -> bytes:
    pdfmetrics.registerFont(TTFont("ProofArial", str(font)))
    output = io.BytesIO()
    canvas = Canvas(output, pagesize=(576, 936), invariant=1)
    canvas.setFont("ProofArial", 14)
    canvas.drawString(36, 892, f"SYNTHETIC {kind.replace('_', ' ').upper()}")
    canvas.setFont("ProofArial", 10)
    canvas.drawString(36, 870, "ADAPTER TEST ONLY - NOT FOR SIGNING OR CASH RELEASE")
    for index, name in enumerate(sorted(REQUIRED_FIELDS)):
        y = 810 - index * 70
        canvas.drawString(36, y, name.replace("_", " ").title())
        canvas.acroForm.textfield(
            name=name, x=36, y=y - 30, width=500, height=24, fontSize=10
        )
    canvas.showPage()
    canvas.save()
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(io.BytesIO(output.getvalue())))
    fonts = writer.pages[0]["/Resources"]["/Font"]
    arial = next(
        ref
        for ref in fonts.values()
        if "Arial" in str(ref.get_object().get("/BaseFont"))
    )
    # This synthetic fixture uses ASCII fields; its embedded subset maps ASCII
    # glyph codes to their WinAnsi equivalents explicitly for form appearances.
    arial.get_object()[NameObject("/Encoding")] = NameObject("/WinAnsiEncoding")
    form = writer.root_object["/AcroForm"]
    form["/DR"][NameObject("/Font")] = DictionaryObject({NameObject("/Arial"): arial})
    form[NameObject("/DA")] = TextStringObject("/Arial 10 Tf 0 g")
    for reference in form["/Fields"]:
        reference.get_object()[NameObject("/DA")] = TextStringObject("/Arial 10 Tf 0 g")
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--converter", type=Path)
    parser.add_argument(
        "--arial", type=Path, default=Path("C:/Windows/Fonts/arial.ttf")
    )
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not args.arial.is_file():
        raise RuntimeError(
            "Installed original Arial is required; no font substitute is accepted."
        )
    source = (
        Path(__file__).resolve().parents[1]
        / "tools/annex_a_pdf_proof/assets/SPINA_Schedule_of_Payments_Annex_A_R2_Black_White_Draft.docx"
    )
    manifest = {
        "version": "SYNTHETIC-ADAPTER-PROOF-1",
        "approved_for_execution": True,
        "documents": {},
        "annex_a": {"path": str(source), "sha256": ANNEX_R2_SHA256},
        "agreement_annex_mode": "separate_complete_annex",
        "disclosure_rules": {
            product: {
                "allocation": "SYNTHETIC fixture only. No production allocation authority.",
                "post_maturity": "SYNTHETIC fixture only. No production penalty authority.",
                "interest_basis": "SYNTHETIC fixed interest on original principal; fixture only.",
            }
            for product in ("regular", "seven_by_seven")
        },
    }
    for kind in KINDS:
        path = output / f"synthetic-{kind}.pdf"
        content = synthetic_template(kind, args.arial)
        path.write_bytes(content)
        manifest["documents"][kind] = {
            "path": str(path),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    manifest_path = output / "synthetic-only-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf8")
    os.environ["GILBIC_FIRST_LOAN_TEMPLATE_MANIFEST"] = str(manifest_path)
    if args.converter:
        os.environ["GILBIC_OFFICE_DOCUMENT_CONVERTER"] = str(args.converter.resolve())
    manifest, files, digest = template_bundle()
    report = []
    for product, count in [("regular", n) for n in (1, 7, 8, 104)] + [
        ("seven_by_seven", 1),
        ("seven_by_seven", 104),
    ]:
        regular = product == "regular"
        identity = str(count) if regular else f"7x7-{count}"
        principal = (
            Decimal("80.00") * count
            if regular
            else Decimal("1000.00" if count == 1 else "3000.00")
        )
        interest = Decimal("20.00") * count if regular else None
        terms = FirstLoanTerms(
            loan_type_id=uuid4(),
            product_code=product,
            principal=principal,
            contractual_interest=interest,
            interest_rate_percent="25.00" if regular else None,
            daily_interest_per_1000=None if regular else "7.00",
            payment_frequency="daily",
            schedule_basis_date=date(2026, 9, 19),
            first_due_date=date(2026, 9, 20),
            installment_count=count,
            installment_amount="100.00"
            if regular
            else ("1007.00" if count == 1 else "50.00"),
            account_email="synthetic@example.invalid",
            pricing_review_reference="SYNTHETIC-ONLY",
        )
        packet = {
            "packet_id": str(uuid4()),
            "cif_version_id": str(uuid4()),
            "cif_version_number": 1,
            "borrower": {
                "full_name": f"SYNTHETIC TEST BORROWER {identity}",
                "present_address": "SYNTHETIC ADDRESS ONLY",
                "phone_number": "00000000000",
                "email": None,
            },
            "product_name": "SYNTHETIC Regular" if regular else "SYNTHETIC 7x7",
            "net_cash": str(principal),
            "total_deductions": "0.00",
            "privacy": {
                "review_snapshot": {
                    "facts": {
                        "registered_lender_name": "SYNTHETIC LENDER - NOT REGISTERED",
                        "registered_office_address": "SYNTHETIC OFFICE",
                    },
                    "notice": {"version": "SYN-N"},
                    "consent": {"version": "SYN-C"},
                }
            },
            "template": {"version": manifest["version"], "content_sha256": digest},
            "application": {
                "information": {"request": {"purpose": "SYNTHETIC ADAPTER TEST ONLY"}}
            },
            "terms": terms.model_dump(mode="json"),
            "schedule": schedule_payload(generate_first_loan_schedule(terms)),
        }
        record = {
            "loan_number": f"SYN-LOAN-{identity}",
            "packet": packet,
            "packet_hash": snapshot_digest(packet),
            "approved_by_user_id": str(uuid4()),
            "approved_at": datetime(2026, 9, 19, tzinfo=timezone.utc),
            "pricing_snapshot": {}
            if regular
            else {
                "seven_by_seven_penalty_policy": {
                    "policy_version": "SYNTHETIC-POLICY-ONLY",
                    "review_id": str(uuid4()),
                    "terms_fingerprint": snapshot_digest(packet["terms"]),
                    "contractual_monthly_rate": "0.01",
                    "proration_days": 30,
                    "legal_rate_ceiling": "0.02",
                    "lifetime_nonprincipal_cost_ceiling": str(principal),
                    "counted_nonprincipal_cost_at_contract_lock": str(
                        sum(
                            Decimal(row["interest_component"])
                            for row in packet["schedule"]
                        )
                    ),
                }
            },
        }
        values = packet_fields(record)
        document = bind_annex_docx(
            record, values, files["annex_a"], manifest["disclosure_rules"]
        )
        (output / f"annex-{identity}.docx").write_bytes(document)
        (output / f"record-{identity}.json").write_text(
            json.dumps(record, default=str), encoding="utf8"
        )
        if args.prepare_only:
            continue
        annex_path = output / f"annex-{identity}.pdf"
        annex_path.write_bytes(convert_annex_pdf(document))
        full_path = output / f"packet-{identity}.pdf"
        full_path.write_bytes(render_packet(record))
        report.append(
            {
                "count": count,
                "product": product,
                "annex": str(annex_path),
                "packet": str(full_path),
                "annex_fonts": verify_arial_pdf(annex_path),
                "packet_fonts": verify_arial_pdf(full_path),
                "annex_projection": verify_packet_projection(annex_path, record),
                "packet_projection": verify_packet_projection(full_path, record),
                "pages": len(PdfReader(full_path).pages),
            }
        )
    (output / "proof-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "prepared_only": args.prepare_only,
                "cases": report,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
