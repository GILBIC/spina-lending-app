"""Synthetic saved-packet mapping; these fixtures are not approved legal assets."""

import hashlib
import io
import json
from copy import deepcopy
from decimal import localcontext
from uuid import uuid4

import pytest
from first_loan_disclosure_fixtures import disclosure_values, review_values
from gilbic_backend.first_loan_disclosure import public_financial_snapshot
from gilbic_backend.first_loan_repository import FirstLoanConflict
from gilbic_backend.first_loan_terms import (
    FirstLoanTerms,
    generate_first_loan_schedule,
    schedule_payload,
    snapshot_digest,
)
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from test_first_loan_documents import packet_fixture, synthetic_template

from gilbic_backend import first_loan_documents as documents


def bound_packet(tmp_path, monkeypatch):
    record, _, _ = packet_fixture(tmp_path, monkeypatch)
    reviewed = review_values(
        disclosure_values=disclosure_values(
            amount_financed="980.00",
            amount_financed_reference="PRIVATE financed basis",
            finance_charge_total="220.00",
            finance_charge_reference="PRIVATE finance basis",
            non_finance_charge_total="0.00",
            non_finance_charge_reference="PRIVATE nonfinance basis",
            effective_interest_rate="0.23456789",
            effective_interest_rate_reference="PRIVATE EIR basis",
            rate_period="per contractual term",
            calculation_method="SYNTHETIC reviewed method",
        )
    )
    terms = FirstLoanTerms.model_validate(reviewed["terms"])
    packet = record["packet"]
    packet.update(
        schema_version=2,
        terms=terms.model_dump(mode="json"),
        schedule=schedule_payload(generate_first_loan_schedule(terms)),
        net_cash="990.00",
        total_deductions="10.00",
        tax_disclosure={
            "calculation_id": str(uuid4()),
            "review_digest": "a" * 64,
            "financial_snapshot": public_financial_snapshot(reviewed),
        },
    )
    packet["terms"]["deductions"][0]["authority_reference"] = (
        "PRIVATE calculation source"
    )
    record["packet_hash"] = snapshot_digest(packet)
    return record


def test_saved_disclosure_maps_exact_independent_values_without_private_references(
    tmp_path, monkeypatch
):
    record = bound_packet(tmp_path, monkeypatch)
    before = deepcopy(record)
    with localcontext() as decimal_context:
        decimal_context.prec = 6
        result = documents.packet_fields(record)
    assert result["dst_upfront"] == "10.00"
    assert result["grt_in_repayments"] == "0.00"
    assert result["net_proceeds"] == result["net_cash"] == "990.00"
    assert result["total_upfront_deductions"] == result["total_deductions"] == "10.00"
    assert (
        result["total_scheduled_payable"]
        == result["total_scheduled_payments"]
        == "1200.00"
    )
    assert result["amount_financed"] == "980.00"
    assert result["finance_charge_total"] == "220.00"
    assert result["effective_interest_rate"] == "0.23456789"
    assert result["rate_period"] == "per contractual term"
    assert (
        result["disclosure_calculation_id"]
        == record["packet"]["tax_disclosure"]["calculation_id"]
    )
    assert result["disclosure_review_digest"] == "a" * 64
    assert "PRIVATE" not in str(result)
    assert "support" not in str(result)
    assert documents.packet_fields(record) == result
    assert record == before


@pytest.mark.parametrize(
    "change",
    [
        "hash",
        "binding",
        "identity",
        "digest",
        "net_cash",
        "schedule",
        "missing_value",
        "private_value",
        "positive_grt",
    ],
)
def test_unbound_or_inconsistent_new_packet_cannot_render(
    tmp_path, monkeypatch, change
):
    record = bound_packet(tmp_path, monkeypatch)
    packet = record["packet"]
    if change == "binding":
        del packet["tax_disclosure"]
    elif change in {"identity", "digest"}:
        packet["tax_disclosure"][
            "calculation_id" if change == "identity" else "review_digest"
        ] = "invalid"
    elif change == "net_cash":
        packet["net_cash"] = "980.00"
    elif change == "schedule":
        packet["schedule"][0]["contractual_amount"] = "1000.00"
    elif change == "missing_value":
        packet["tax_disclosure"]["financial_snapshot"]["disclosure_values"][
            "amount_financed"
        ] = None
    elif change == "private_value":
        packet["tax_disclosure"]["financial_snapshot"]["disclosure_values"][
            "support_storage_key"
        ] = "PRIVATE"
    elif change == "positive_grt":
        components = packet["tax_disclosure"]["financial_snapshot"]["components"]
        components.update(contractual_interest="190.00", grt_in_repayments="10.00")
    if change != "hash":
        record["packet_hash"] = snapshot_digest(packet)
    else:
        record["packet_hash"] = "b" * 64
    with pytest.raises(FirstLoanConflict):
        documents.packet_fields(record)


@pytest.mark.parametrize("kind", ["disclosure", "agreement"])
def test_new_packet_rejects_old_template_missing_bound_breakdown(
    tmp_path, monkeypatch, kind
):
    record = bound_packet(tmp_path, monkeypatch)
    values = documents.packet_fields(record)
    # Exercise the actual renderer's per-document contract, not legal approval.
    required = (
        getattr(documents, "DISCLOSURE_FIELDS", set())
        if kind == "disclosure"
        else getattr(documents, "COMPONENT_FIELDS", set())
    )
    assert required, "Bound document fields are not enforced"
    with pytest.raises(FirstLoanConflict):
        documents._filled_pdf(synthetic_template(), values, required_fields=required)


def _bound_template(fields):
    output = io.BytesIO()
    canvas = Canvas(output, pagesize=(595, 842), invariant=1)
    for index, name in enumerate(sorted(documents.REQUIRED_FIELDS | set(fields))):
        if index and index % 10 == 0:
            canvas.showPage()
        y = 755 - (index % 10) * 70
        canvas.drawString(40, y, name)
        canvas.acroForm.textfield(
            name=name, x=40, y=y - 26, width=510, height=22, fontSize=10
        )
    canvas.showPage()
    canvas.save()
    return output.getvalue()


@pytest.mark.parametrize("missing_kind", [None, "disclosure", "agreement"])
def test_assembled_new_packet_requires_and_renders_saved_disclosure(
    tmp_path, monkeypatch, missing_kind
):
    record = bound_packet(tmp_path, monkeypatch)
    manifest_path = tmp_path / "templates.json"
    manifest = json.loads(manifest_path.read_text())
    for kind in documents.KINDS:
        fields = (
            documents.DISCLOSURE_FIELDS
            if kind == "disclosure"
            else documents.COMPONENT_FIELDS
            if kind == "agreement"
            else set()
        )
        content = _bound_template(fields if kind != missing_kind else set())
        path = tmp_path / f"{kind}.pdf"
        path.write_bytes(content)
        manifest["documents"][kind] = {
            "path": str(path),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    manifest_path.write_text(json.dumps(manifest))
    record["packet"]["template"]["content_sha256"] = documents.template_bundle()[2]
    record["packet_hash"] = snapshot_digest(record["packet"])
    # Conversion and embedded font acceptance have separate existing tests.
    # This exercises actual manifest verification, template filling and assembly.
    monkeypatch.setattr(
        documents,
        "convert_annex_pdf",
        lambda _: documents._filled_pdf(
            _bound_template(set()), documents.packet_fields(record)
        ),
    )
    monkeypatch.setattr(documents, "verify_arial_pdf", lambda _: None)
    if missing_kind:
        with pytest.raises(FirstLoanConflict, match="unsupported financial values"):
            documents.render_packet(record)
        return
    pdf = PdfReader(io.BytesIO(documents.render_packet(record)))
    assert not pdf.get_fields()
    text = "\n".join(page.extract_text() for page in pdf.pages)
    for value in ("990.00", "980.00", "220.00", "0.23456789", "1200.00"):
        assert value in text
    assert record["packet"]["tax_disclosure"]["calculation_id"] in text
    assert "a" * 64 in text
    assert "PRIVATE" not in text


@pytest.mark.parametrize("kind", ["disclosure", "agreement"])
def test_bound_document_requires_individual_deductions(tmp_path, monkeypatch, kind):
    record = bound_packet(tmp_path, monkeypatch)
    required = (
        documents.DISCLOSURE_FIELDS
        if kind == "disclosure"
        else documents.COMPONENT_FIELDS
    )
    with pytest.raises(FirstLoanConflict, match="unsupported financial values"):
        documents._filled_pdf(
            _bound_template(required - {"deductions"}),
            documents.packet_fields(record),
            required_fields=required,
        )


def test_historical_packet_mapping_stays_unchanged(tmp_path, monkeypatch):
    record, _, _ = packet_fixture(tmp_path, monkeypatch)
    record["packet"]["schema_version"] = 1
    record["packet_hash"] = snapshot_digest(record["packet"])
    before = deepcopy(record)
    fields = documents.packet_fields(record)
    assert "dst_upfront" not in fields
    assert "tax_disclosure" not in record["packet"]
    assert before == record


def test_explicit_zero_repayment_charge_uses_saved_contract_timing(
    tmp_path, monkeypatch
):
    record = bound_packet(tmp_path, monkeypatch)
    record["packet"]["tax_disclosure"]["financial_snapshot"]["charge_items"].append(
        {
            "item_id": "grt",
            "kind": "grt_recovery",
            "timing": "repayments",
            "amount": "0.00",
        }
    )
    record["packet_hash"] = snapshot_digest(record["packet"])
    assert documents.packet_fields(record)["grt_in_repayments"] == "0.00"
