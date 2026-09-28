"""Fill three controlled legal PDFs and append the exact approved schedule.

This is a template adapter, not a pricing engine. Legal language and layout come
from hash-pinned, operator-approved PDFs. Unknown fields and unapproved assets
block issuance. No template or legal approval is seeded by the application.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
from decimal import Context, Decimal, localcontext
from pathlib import Path

from fitz import FileDataError
from pydantic import TypeAdapter
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import NameObject

from .document_font_gate import verify_arial_pdf
from .first_loan_annex import (
    ANNEX_R2_SHA256,
    bind_annex_docx,
    convert_annex_pdf,
    project_packet_schedule,
)
from .first_loan_disclosure import (
    DisclosureInput,
    ExactMoney,
    ExactRate,
    Reference,
    parse_components,
    project_components,
)
from .first_loan_disclosure_binding import source_pair
from .first_loan_repository import FirstLoanConflict
from .first_loan_terms import snapshot_digest

KINDS = ("disclosure", "agreement", "promissory_note")
REQUIRED_FIELDS = {
    "loan_number",
    "borrower_name",
    "principal",
    "installment_amount",
    "first_payment_date",
    "maturity_date",
}
COMPONENT_FIELDS = {
    "deductions",
    "dst_upfront",
    "grt_in_repayments",
    "other_upfront_deductions",
    "other_scheduled_charges",
    "total_upfront_deductions",
    "net_proceeds",
    "contractual_interest",
    "total_scheduled_payable",
    "disclosure_calculation_id",
    "disclosure_review_digest",
}
DISCLOSURE_FIELDS = COMPONENT_FIELDS | {
    "amount_financed",
    "finance_charge_total",
    "non_finance_charge_total",
    "effective_interest_rate",
    "rate_period",
    "calculation_method",
}


class _DocumentDisclosureValues(DisclosureInput):
    amount_financed: ExactMoney
    finance_charge_total: ExactMoney
    non_finance_charge_total: ExactMoney
    effective_interest_rate: ExactRate
    rate_period: Reference
    calculation_method: Reference


def _bound_disclosure_fields(packet):
    """Project the saved public snapshot; source authority is checked by its owner."""
    try:
        binding = packet["tax_disclosure"]
        if set(binding) != {"calculation_id", "review_digest", "financial_snapshot"}:
            raise ValueError("Invalid source binding")
        identity, digest = source_pair(
            binding["calculation_id"], binding["review_digest"]
        )
        financial = binding["financial_snapshot"]
        if set(financial) != {"components", "disclosure_values", "charge_items"}:
            raise ValueError("Invalid public snapshot")
        components = parse_components(financial["components"])
        values = _DocumentDisclosureValues.model_validate(
            financial["disclosure_values"]
        )
        projection = project_packet_schedule(packet)
        money = TypeAdapter(ExactMoney)
        terms = packet["terms"]
        deductions = {
            item["code"].strip().casefold(): money.validate_python(item["amount"])
            for item in terms["deductions"]
        }
        if len(deductions) != len(terms["deductions"]):
            raise ValueError("Duplicate deduction")
        if (
            components.principal != projection.total_principal
            or components.contractual_interest != projection.total_interest
            or components.total_scheduled_payable != projection.total_due
            or components.grt_in_repayments != 0
            or components.other_scheduled_charges != 0
            or components.renewal_offset != 0
            or components.net_proceeds != money.validate_python(packet["net_cash"])
            or components.total_upfront_deductions
            != money.validate_python(packet["total_deductions"])
            or components.total_upfront_deductions
            != sum(deductions.values(), Decimal(0))
        ):
            raise ValueError("Components differ from approved schedule/cash")
        # Public items deliberately have no retained support-section references.
        items = financial["charge_items"]
        if not isinstance(items, list) or len(items) > 30:
            raise ValueError("Invalid charge items")
        upfront = {}
        totals = {
            kind: Decimal(0)
            for kind in ("dst", "grt_recovery", "other_upfront", "other_scheduled")
        }
        identities = set()
        for item in items:
            if set(item) != {"item_id", "kind", "timing", "amount"}:
                raise ValueError("Invalid public charge")
            item_id = TypeAdapter(Reference).validate_python(item["item_id"]).casefold()
            kind = item["kind"]
            timing = "upfront" if kind in {"dst", "other_upfront"} else "repayments"
            if item_id in identities or kind not in totals or item["timing"] != timing:
                raise ValueError("Duplicate or inconsistent charge")
            identities.add(item_id)
            amount = money.validate_python(item["amount"])
            totals[kind] += amount
            if timing == "upfront":
                upfront[item_id] = amount
        if upfront != deductions or totals != {
            "dst": components.dst_upfront,
            "grt_recovery": components.grt_in_repayments,
            "other_upfront": components.other_upfront_deductions,
            "other_scheduled": components.other_scheduled_charges,
        }:
            raise ValueError("Itemization differs")
        projected = project_components(
            components,
            references={
                "loan_version_reference": packet["packet_id"],
                "tax_loan_version_reference": packet["packet_id"],
                # The immutable review digest covers its exact saved rule snapshot.
                "tax_rule_snapshot_reference": f"review:{digest}",
                "tax_calculation_reference": identity,
            },
        )
        return {
            **projected,
            **values.model_dump(mode="json"),
            "disclosure_calculation_id": identity,
            "disclosure_review_digest": digest,
            "deductions": "\n".join(
                f"{code}: PHP {amount:.2f}" for code, amount in upfront.items()
            )
            or "None / PHP 0.00",
        }
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise FirstLoanConflict(
            "The packet requires a complete, consistent saved disclosure."
        ) from error


def template_bundle() -> tuple[dict, dict[str, bytes], str]:
    configured = os.getenv("GILBIC_FIRST_LOAN_TEMPLATE_MANIFEST", "").strip()
    try:
        path = Path(configured)
        if not configured or not path.is_absolute():
            raise ValueError("missing manifest")
        manifest = json.loads(path.read_text(encoding="utf8"))
        if manifest.get("approved_for_execution") is not True or not manifest.get(
            "version"
        ):
            raise ValueError("unapproved manifest")
        files = {}
        canonical = {"version": manifest["version"], "documents": {}}
        for kind in KINDS:
            record = manifest["documents"][kind]
            asset = Path(record["path"])
            if not asset.is_absolute() or asset.suffix.lower() != ".pdf":
                raise ValueError("invalid asset")
            content = asset.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if (
                not content.startswith(b"%PDF-")
                or len(content) > 10485760
                or digest != record["sha256"]
            ):
                raise ValueError("asset integrity")
            files[kind] = content
            canonical["documents"][kind] = {"sha256": digest}
        annex = manifest["annex_a"]
        annex_path = Path(annex["path"])
        if not annex_path.is_absolute() or annex_path.suffix.lower() != ".docx":
            raise ValueError("invalid Annex A source")
        annex_bytes = annex_path.read_bytes()
        annex_digest = hashlib.sha256(annex_bytes).hexdigest()
        if annex_digest != ANNEX_R2_SHA256 or annex_digest != annex["sha256"]:
            raise ValueError("unapproved Annex A layout")
        files["annex_a"] = annex_bytes
        canonical["annex_a"] = {"sha256": annex_digest}
        rules = manifest["disclosure_rules"]
        if set(rules) != {"regular", "seven_by_seven"}:
            raise ValueError("missing product-specific disclosures")
        for product in rules.values():
            if set(product) != {"allocation", "post_maturity", "interest_basis"} or any(
                not isinstance(text, str)
                or not text.strip()
                or "{" in text
                or "}" in text
                for text in product.values()
            ):
                raise ValueError("unresolved product-specific disclosure")
        canonical["disclosure_rules"] = rules
        if manifest.get("agreement_annex_mode") != "separate_complete_annex":
            raise ValueError("agreement must exclude its competing abbreviated Annex")
        canonical["agreement_annex_mode"] = manifest["agreement_annex_mode"]
        # Stable across deployment paths; the actual source bytes remain pinned.
        digest = snapshot_digest(canonical)
        return manifest, files, digest
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise FirstLoanConflict(
            "Approved legal PDF templates are not configured or failed their integrity check."
        ) from error


def packet_fields(record: dict) -> dict[str, str]:
    with localcontext(Context(prec=40)):
        return _packet_fields(record)


def _packet_fields(record: dict) -> dict[str, str]:
    packet = record["packet"]
    terms = packet["terms"]
    rows = packet["schedule"]
    if snapshot_digest(packet) != record["packet_hash"] or not rows:
        raise FirstLoanConflict("The approved packet failed its integrity check.")
    borrower = packet["borrower"]
    facts = packet["privacy"]["review_snapshot"]["facts"]
    fields = {
        "loan_number": record["loan_number"],
        "packet_reference": packet["packet_id"],
        "packet_hash": record["packet_hash"],
        "borrower_name": borrower["full_name"],
        "borrower_address": borrower["present_address"],
        "borrower_phone": borrower["phone_number"],
        "borrower_email": borrower["email"] or "Not provided",
        "lender_name": facts["registered_lender_name"],
        "lender_address": facts["registered_office_address"],
        "product_name": packet["product_name"],
        "loan_purpose": packet["application"]["information"]["request"]["purpose"],
        "principal": terms["principal"],
        "net_cash": packet["net_cash"],
        "total_deductions": packet["total_deductions"],
        "installment_amount": terms["installment_amount"],
        "installment_count": str(len(rows)),
        "payment_frequency": terms["payment_frequency"],
        "release_date_basis": terms["schedule_basis_date"],
        "first_payment_date": rows[0]["due_date"],
        "maturity_date": rows[-1]["due_date"],
        "contractual_interest": str(
            sum((Decimal(row["interest_component"]) for row in rows), Decimal(0))
        ),
        "total_scheduled_payments": str(
            sum((Decimal(row["contractual_amount"]) for row in rows), Decimal(0))
        ),
        "interest_rate_percent": terms.get("interest_rate_percent") or "Not applicable",
        "daily_interest_per_1000": terms.get("daily_interest_per_1000")
        or "Not applicable",
        "deductions": "\n".join(
            f"{row['code']}: PHP {row['amount']} ({row['authority_reference']})"
            for row in terms["deductions"]
        )
        or "None / PHP 0.00",
        "privacy_notice_version": packet["privacy"]["review_snapshot"]["notice"][
            "version"
        ],
        "privacy_consent_version": packet["privacy"]["review_snapshot"]["consent"][
            "version"
        ],
    }
    if packet.get("schema_version", 1) == 2:
        fields.update(_bound_disclosure_fields(packet))
    elif packet.get("schema_version", 1) != 1 or "tax_disclosure" in packet:
        raise FirstLoanConflict("The approved packet schema is unsupported.")
    return {key: str(value) for key, value in fields.items()}


def _filled_pdf(content: bytes, values: dict[str, str], *, required_fields=()) -> bytes:
    try:
        return _fill_template_pdf(content, values, required_fields=required_fields)
    except PdfReadError as error:
        raise FirstLoanConflict("The controlled PDF template is malformed.") from error


def _fill_template_pdf(
    content: bytes, values: dict[str, str], *, required_fields=()
) -> bytes:
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted:
        raise FirstLoanConflict("Controlled templates must not be encrypted.")
    root = reader.trailer["/Root"]
    form = root.get("/AcroForm")
    form = form.get_object() if form else {}
    if root.get("/OpenAction") or root.get("/AA") or "/XFA" in form:
        raise FirstLoanConflict(
            "Active PDF content is not permitted in a legal template."
        )
    fields = reader.get_fields() or {}
    if not (REQUIRED_FIELDS | set(required_fields)).issubset(fields) or any(
        name not in values for name in fields
    ):
        raise FirstLoanConflict(
            "Legal template fields are incomplete or require unsupported financial values."
        )
    if any(field.get("/FT") != "/Tx" for field in fields.values()):
        raise FirstLoanConflict(
            "Legal template fields must be plain text; wet signatures remain separate."
        )
    # Fail on field/widget ambiguity rather than repairing an untrusted form.
    for page in reader.pages:
        if page.get("/AA"):
            raise FirstLoanConflict("Active PDF content is not permitted.")
        for reference in page.get("/Annots", []):
            widget = reference.get_object()
            if widget.get("/A") or widget.get("/AA"):
                raise FirstLoanConflict("Active PDF annotations are not permitted.")
            if widget.get("/Subtype") == "/Widget":
                source = widget.get("/Parent", reference).get_object()
                name = source.get("/T")
                if name not in fields or source.get("/FT") != "/Tx":
                    raise FirstLoanConflict(
                        "Ambiguous or unsupported legal template widget."
                    )
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    try:
        writer.update_page_form_field_values(
            None,
            {name: values[name] for name in fields},
            auto_regenerate=False,
            flatten=True,
        )
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise FirstLoanConflict(
            "The controlled template cannot represent its required field values."
        ) from error
    writer.remove_annotations(subtypes="/Widget")
    writer.root_object.pop(NameObject("/AcroForm"), None)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _schedule_pdf(
    record: dict, values: dict[str, str], template: bytes, rules: dict
) -> bytes:
    return convert_annex_pdf(bind_annex_docx(record, values, template, rules))


def render_packet(record: dict) -> bytes:
    try:
        return _render_packet(record)
    except PdfReadError as error:
        raise FirstLoanConflict("The assembled legal PDF could not be read.") from error


def _render_packet(record: dict) -> bytes:
    manifest, files, digest = template_bundle()
    template = record["packet"]["template"]
    if template != {"version": manifest["version"], "content_sha256": digest}:
        raise FirstLoanConflict(
            "The configured templates do not match this exact approved packet."
        )
    values = packet_fields(record)
    writer = PdfWriter()
    for kind in KINDS:
        required = ()
        if record["packet"].get("schema_version") == 2:
            if kind == "disclosure":
                required = DISCLOSURE_FIELDS
            elif kind == "agreement":
                required = COMPONENT_FIELDS
        writer.append(
            PdfReader(
                io.BytesIO(_filled_pdf(files[kind], values, required_fields=required))
            )
        )
    writer.append(
        PdfReader(
            io.BytesIO(
                _schedule_pdf(
                    record, values, files["annex_a"], manifest["disclosure_rules"]
                )
            )
        )
    )
    writer.add_metadata(
        {
            "/Title": f"Loan packet {values['loan_number']}",
            "/Subject": values["packet_hash"],
        }
    )
    output = io.BytesIO()
    writer.write(output)
    content = output.getvalue()
    verified = PdfReader(io.BytesIO(content))
    if verified.get_fields() or any(
        a.get_object().get("/Subtype") == "/Widget"
        for p in verified.pages
        for a in p.get("/Annots", [])
    ):
        raise FirstLoanConflict("Issued packet must be non-fillable.")
    try:
        with tempfile.TemporaryDirectory(
            prefix="spina-private-packet-check-"
        ) as workspace:
            artifact = Path(workspace) / "packet.pdf"
            artifact.write_bytes(content)
            verify_arial_pdf(artifact)
    except (OSError, ValueError, FileDataError) as error:
        raise FirstLoanConflict(
            "The issued packet failed embedded Arial verification."
        ) from error
    return content
