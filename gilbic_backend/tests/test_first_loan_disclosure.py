"""Task 1 pure-contract proofs, not database or legal/charge authority tests."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, getcontext, localcontext
from importlib import import_module

import pytest
from first_loan_disclosure_fixtures import (
    component_values,
    disclosure_values,
    projection_references,
    review_values,
    terms_values,
)
from gilbic_backend.first_loan_terms import (
    FirstLoanTerms,
    generate_first_loan_schedule,
    snapshot_digest,
)


def subject():
    try:
        return import_module("gilbic_backend.first_loan_disclosure")
    except ModuleNotFoundError as error:
        if error.name != "gilbic_backend.first_loan_disclosure":
            raise
        pytest.fail("R1 disclosure contract is not implemented", pytrace=False)


@pytest.mark.parametrize(
    "bad",
    [
        True,
        False,
        10.0,
        "10.001",
        "-1.00",
        "NaN",
        "Infinity",
        "10000000000000000.00",
        None,
        "1e1000000",
        "1e-1000000",
        [],
        {},
    ],
)
def test_money_rejects_inexact_or_out_of_range(bad):
    with pytest.raises(ValueError):
        subject().parse_components(component_values(dst_upfront=bad))


@pytest.mark.parametrize("field", list(component_values()))
def test_every_component_is_required_and_missing_is_not_zero(field):
    data = component_values()
    del data[field]
    with pytest.raises(ValueError):
        subject().parse_components(data)


@pytest.mark.parametrize(
    "field",
    [
        "total_upfront_deductions",
        "net_proceeds",
        "total_scheduled_payable",
        "principal",
    ],
)
def test_component_equations_must_reconcile(field):
    with pytest.raises(ValueError):
        subject().parse_components(component_values(**{field: "1.00"}))


def test_first_loan_cannot_hide_a_renewal_offset():
    with pytest.raises(ValueError):
        subject().parse_components(
            component_values(
                renewal_offset="1.00",
                total_upfront_deductions="11.00",
                net_proceeds="989.00",
            )
        )


def test_positive_net_cash_and_principal_are_required():
    for data in [
        component_values(
            dst_upfront="1000.00",
            total_upfront_deductions="1000.00",
            net_proceeds="0.00",
        ),
        component_values(
            principal="0.00",
            dst_upfront="0.00",
            total_upfront_deductions="0.00",
            net_proceeds="0.00",
            total_scheduled_payable="200.00",
        ),
    ]:
        with pytest.raises(ValueError):
            subject().parse_components(data)


def test_exact_projection_never_mutates_inputs():
    data, references = component_values(), projection_references()
    before = deepcopy((data, references))
    result = subject().project_components(
        subject().parse_components(data), references=references
    )
    assert result == data
    assert (data, references) == before


@pytest.mark.parametrize("change", ["missing", "extra", "mismatch", "blank"])
def test_projection_requires_exact_supplied_references(change):
    references = projection_references()
    if change == "missing":
        del references["tax_calculation_reference"]
    if change == "extra":
        references["invented"] = "SYN"
    if change == "mismatch":
        references["tax_loan_version_reference"] = "SYN-OTHER"
    if change == "blank":
        references["tax_calculation_reference"] = " "
    with pytest.raises(ValueError):
        subject().project_components(
            subject().parse_components(component_values()), references=references
        )


def test_maximum_exact_cent_value_and_local_context_are_preserved():
    data = component_values(
        principal="9999999999999999.99",
        contractual_interest="0.00",
        dst_upfront="0.00",
        total_upfront_deductions="0.00",
        net_proceeds="9999999999999999.99",
        total_scheduled_payable="9999999999999999.99",
    )
    m = subject()
    with localcontext() as context:
        context.prec = 6
        before = context.copy()
        result = m.project_components(
            m.parse_components(data), references=projection_references()
        )
        assert result == data
        assert getcontext().prec == before.prec
        assert getcontext().traps == before.traps


def test_exact_amounts_are_normalized_without_rounding():
    m = subject()
    for spelling in [10, "10", "10.0", "10.00", Decimal("10.000")]:
        parsed = m.parse_components(component_values(dst_upfront=spelling))
        assert parsed.model_dump(mode="json")["dst_upfront"] == "10.00"


def test_review_digest_is_key_stable_exact_and_preserves_unicode_convention():
    m = subject()
    data = {
        "components": component_values(),
        "note": "Peña",
        "source_reference": "0010",
    }
    before = deepcopy(data)
    expected = snapshot_digest(data)
    for spelling in [10, "10", "10.0", "10.00", Decimal("10.00")]:
        changed = deepcopy(data)
        changed["components"]["dst_upfront"] = spelling
        assert (
            m.canonical_review_digest(dict(reversed(list(changed.items())))) == expected
        )
    changed["components"]["dst_upfront"] = "10.01"
    assert m.canonical_review_digest(changed) != expected
    assert data == before


def test_digest_normalizes_nested_terms_money_but_not_reference_strings_or_rate_scale():
    m = subject()
    data = review_values()
    normalized = m.DisclosureReviewRequest.model_validate(data).model_dump(mode="json")
    assert m.canonical_review_digest(data) == m.canonical_review_digest(normalized)
    changed = deepcopy(data)
    changed["terms"]["principal"] = "1000"
    changed["terms"]["deductions"][0]["amount"] = "10.0"
    assert m.canonical_review_digest(changed) == m.canonical_review_digest(data)
    assert m.canonical_review_digest(
        {"reference": "0010"}
    ) != m.canonical_review_digest({"reference": "10"})
    assert m.canonical_review_digest(
        {"rate": Decimal("0.01234567890")}
    ) == snapshot_digest({"rate": "0.01234567890"})


@pytest.mark.parametrize(
    "bad", [float("nan"), 10.0, Decimal("sNaN"), {1: "bad"}, {"x"}]
)
def test_digest_rejects_non_json_or_inexact_values(bad):
    with pytest.raises(ValueError):
        subject().canonical_review_digest({"nested": [bad]})


def test_model_is_frozen_and_rejects_unplanned_fields():
    m = subject()
    parsed = m.parse_components(component_values())
    with pytest.raises(ValueError):
        parsed.principal = Decimal("1.00")
    with pytest.raises(ValueError):
        m.parse_components(component_values(ready=True))
    for field in [
        "approved",
        "reviewed_by_user_id",
        "reviewed_at",
        "client_id",
        "approval_ready",
    ]:
        with pytest.raises(ValueError):
            m.DisclosureReviewRequest.model_validate(
                review_values(**{field: "spoofed"})
            )


def test_duplicate_charge_ids_and_duplicate_tax_classifications_are_rejected():
    m = subject()
    data = review_values()
    duplicate = deepcopy(data["charge_items"][0])
    duplicate["item_id"] = " DST "
    data["charge_items"].append(duplicate)
    with pytest.raises(ValueError):
        m.DisclosureReviewRequest.model_validate(data)
    data = review_values()
    data["charge_items"][0]["amount"] = "5.00"
    data["charge_items"].append(dict(data["charge_items"][0], item_id="another_dst"))
    with pytest.raises(ValueError):
        m.DisclosureReviewRequest.model_validate(data)


@pytest.mark.parametrize(
    "kind,timing",
    [
        ("grt_recovery", "upfront"),
        ("dst", "repayments"),
        ("other_upfront", "repayments"),
        ("other_scheduled", "upfront"),
    ],
)
def test_charge_timing_cannot_be_switched(kind, timing):
    data = review_values()
    data["charge_items"][0].update(kind=kind, timing=timing)
    with pytest.raises(ValueError):
        subject().DisclosureReviewRequest.model_validate(data)


def test_reserved_dst_or_grt_cannot_masquerade_as_generic_deductions():
    for item_id in ["DST", "grt", "GRT_RECOVERY"]:
        data = review_values()
        data["charge_items"][0].update(item_id=item_id, kind="other_upfront")
        with pytest.raises(ValueError):
            subject().DisclosureReviewRequest.model_validate(data)


def test_charge_item_totals_must_equal_exact_components():
    data = review_values()
    data["charge_items"][0]["amount"] = "9.99"
    with pytest.raises(ValueError):
        subject().DisclosureReviewRequest.model_validate(data)


def test_every_existing_deduction_maps_once_by_identity_and_amount():
    for change in ["missing", "extra", "wrong_amount", "renamed", "grt"]:
        data = review_values()
        if change == "missing":
            data["terms"]["deductions"] = []
        if change == "extra":
            data["terms"]["deductions"].append(
                {"code": "another", "amount": "10.00", "authority_reference": "SYN"}
            )
        if change == "wrong_amount":
            data["terms"]["deductions"][0]["amount"] = "9.99"
        if change == "renamed":
            data["terms"]["deductions"][0]["code"] = "other"
        if change == "grt":
            data["terms"]["deductions"][0]["code"] = "grt"
        with pytest.raises(ValueError):
            subject().DisclosureReviewRequest.model_validate(data)


def test_explicit_supported_zero_requires_review_reason_not_assumed_exemption():
    m = subject()
    data = review_values()
    assert (
        m.DisclosureReviewRequest.model_validate(data).components.grt_in_repayments == 0
    )
    data["borrower_charge_basis"]["grt_zero_reason"] = None
    with pytest.raises(ValueError):
        m.DisclosureReviewRequest.model_validate(data)
    data = review_values()
    data["borrower_charge_basis"]["dst_zero_reason"] = "contradicts positive amount"
    with pytest.raises(ValueError):
        m.DisclosureReviewRequest.model_validate(data)


@pytest.mark.parametrize(
    "field",
    [
        "request_id",
        "cif_version_id",
        "dst_rule_id",
        "grt_rule_id",
        "supersedes_calculation_id",
        "borrower_charge_basis",
        "charge_items",
    ],
)
def test_review_does_not_default_required_fields(field):
    data = review_values()
    del data[field]
    with pytest.raises(ValueError):
        subject().DisclosureReviewRequest.model_validate(data)


@pytest.mark.parametrize("bad", ["A" * 64, "a" * 63, "a" * 64 + "\n", "not-a-hash"])
def test_context_digest_shape_is_exact(bad):
    with pytest.raises(ValueError):
        subject().DisclosureReviewRequest.model_validate(
            review_values(expected_context_digest=bad)
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("calculation_method", "automatic_v1"),
        ("support_base64", "%%bad"),
        ("support_base64", ""),
        ("support_media_type", "text/html"),
        ("review_rationale", "   "),
        ("review_rationale", "a" * 2001),
    ],
)
def test_review_metadata_is_bounded_explicit_and_not_a_provider_claim(field, value):
    with pytest.raises(ValueError):
        subject().DisclosureReviewRequest.model_validate(
            review_values(**{field: value})
        )


def test_independent_disclosure_values_require_their_own_references():
    m = subject()
    for name in [
        "amount_financed",
        "finance_charge_total",
        "non_finance_charge_total",
        "effective_interest_rate",
    ]:
        data = review_values()
        data["disclosure_values"][name] = "10.00"
        with pytest.raises(ValueError):
            m.DisclosureReviewRequest.model_validate(data)


def test_public_snapshot_is_an_explicit_allowlist_and_preserves_unknown_values():
    m = subject()
    data = review_values(
        disclosure_values=disclosure_values(
            amount_financed="980.00", amount_financed_reference="SYN support A"
        )
    )
    data["support_storage_key"] = "PRIVATE STORAGE"
    data["extra_internal"] = {"principal": "do not expose"}
    before = deepcopy(data)
    result = m.public_financial_snapshot(data)
    assert set(result) == {"components", "charge_items", "disclosure_values"}
    assert result["components"] == component_values()
    assert result["disclosure_values"]["amount_financed"] == "980.00"
    assert result["disclosure_values"]["effective_interest_rate"] is None
    encoded = json.dumps(result)
    for private in ["support", "PRIVATE", "rationale", "expected_context_digest"]:
        assert private not in encoded
    result["components"]["principal"] = "1.00"
    assert data == before


def test_eir_keeps_supplied_precision_and_unit_without_money_rounding():
    data = review_values(
        disclosure_values=disclosure_values(
            effective_interest_rate="0.1234567890",
            effective_interest_rate_reference="SYN EIR",
            rate_period="annual",
            calculation_method="SYN-METHOD",
        )
    )
    m = subject()
    result = m.public_financial_snapshot(
        m.DisclosureReviewRequest.model_validate(data).model_dump(mode="json")
    )
    assert result["disclosure_values"]["effective_interest_rate"] == "0.1234567890"
    assert result["disclosure_values"]["rate_period"] == "annual"
    assert result["disclosure_values"]["amount_financed"] is None


def test_compatible_regular_rows_are_unchanged():
    m = subject()
    terms = FirstLoanTerms.model_validate(terms_values())
    rows = generate_first_loan_schedule(terms)
    before = deepcopy((terms.model_dump(), rows))
    assert (
        m.require_component_compatibility(
            terms, rows, m.parse_components(component_values())
        )
        is None
    )
    assert (terms.model_dump(), rows) == before


@pytest.mark.parametrize("field", ["grt_in_repayments", "other_scheduled_charges"])
def test_positive_unsupported_scheduled_components_cannot_relabel_interest(field):
    m = subject()
    terms = FirstLoanTerms.model_validate(terms_values())
    rows = generate_first_loan_schedule(terms)
    components = m.parse_components(
        component_values(contractual_interest="190.00", **{field: "10.00"})
    )
    with pytest.raises(ValueError, match="component integration required"):
        m.require_component_compatibility(terms, rows, components)
    assert sum(r.interest_component for r in rows) == Decimal("200.00")


def test_reviewable_positive_grt_does_not_mean_compatible_for_issuance():
    m = subject()
    data = review_values()
    data["components"].update(
        grt_in_repayments="10.00", total_scheduled_payable="1210.00"
    )
    data["charge_items"].append(
        {
            "item_id": "grt",
            "kind": "grt_recovery",
            "timing": "repayments",
            "amount": "10.00",
            "support_section_reference": "SYN grt",
        }
    )
    data["borrower_charge_basis"]["grt_zero_reason"] = None
    reviewed = m.DisclosureReviewRequest.model_validate(data)
    with pytest.raises(ValueError, match="component integration required"):
        m.require_component_compatibility(
            reviewed.terms,
            generate_first_loan_schedule(reviewed.terms),
            reviewed.components,
        )


def test_7x7_components_use_existing_signed_schedule_interest():
    m = subject()
    terms = FirstLoanTerms.model_validate(
        terms_values(
            product_code="seven_by_seven",
            contractual_interest=None,
            interest_rate_percent=None,
            daily_interest_per_1000="5.00",
            installment_amount="105.00",
            installment_count=None,
        )
    )
    rows = generate_first_loan_schedule(terms)
    components = m.parse_components(
        component_values(
            contractual_interest="50.00", total_scheduled_payable="1050.00"
        )
    )
    assert m.require_component_compatibility(terms, rows, components) is None


def test_empty_or_tampered_schedule_and_inconsistent_term_binding_are_rejected():
    m = subject()
    terms = FirstLoanTerms.model_validate(terms_values())
    rows = generate_first_loan_schedule(terms)
    components = m.parse_components(component_values())
    changed = (
        replace(rows[0], due_date=rows[0].due_date + timedelta(days=1)),
        *rows[1:],
    )
    for bad_rows in [(), rows[:-1], changed]:
        with pytest.raises(ValueError):
            m.require_component_compatibility(terms, bad_rows, components)
    no_deduction = FirstLoanTerms.model_validate(terms_values(deductions=[]))
    with pytest.raises(ValueError):
        m.require_component_compatibility(no_deduction, rows, components)


def test_prevalidated_terms_cannot_bypass_exact_money_checks_via_model_copy():
    m = subject()
    poisoned = FirstLoanTerms.model_validate(terms_values()).model_copy(
        update={"principal": 1000.0}
    )
    with pytest.raises(ValueError):
        m.DisclosureReviewRequest.model_validate(review_values(terms=poisoned))


def test_compatibility_rejects_float_values_even_when_dataclass_equality_matches():
    m = subject()
    terms = FirstLoanTerms.model_validate(terms_values())
    rows = generate_first_loan_schedule(terms)
    altered = (replace(rows[0], contractual_amount=100.0), *rows[1:])
    assert altered == rows  # Python numeric equality is not exact-input validation.
    with pytest.raises(ValueError):
        m.require_component_compatibility(
            terms, altered, m.parse_components(component_values())
        )


def test_compatibility_revalidates_preconstructed_terms():
    m = subject()
    terms = FirstLoanTerms.model_validate(terms_values())
    rows = generate_first_loan_schedule(terms)
    poisoned = terms.model_copy(update={"interest_rate_percent": Decimal("99.00")})
    with pytest.raises(ValueError):
        m.require_component_compatibility(
            poisoned, rows, m.parse_components(component_values())
        )


def test_projection_revalidates_immutable_model_copies():
    m = subject()
    components = m.parse_components(component_values()).model_copy(
        update={"dst_upfront": 10.0}
    )
    with pytest.raises(ValueError):
        m.project_components(components, references=projection_references())


def test_duplicate_charges_cannot_be_shown_by_public_projection():
    m = subject()
    data = review_values()
    data["charge_items"].append(deepcopy(data["charge_items"][0]))
    with pytest.raises(ValueError):
        m.public_financial_snapshot(data)


def test_component_overflow_is_rejected_without_changing_decimal_context():
    m = subject()
    data = component_values(
        principal="9999999999999999.99",
        dst_upfront="0.00",
        total_upfront_deductions="0.00",
        net_proceeds="9999999999999999.99",
        contractual_interest="0.01",
        total_scheduled_payable="10000000000000000.00",
    )
    with localcontext() as context:
        context.prec = 6
        with pytest.raises(ValueError):
            m.parse_components(data)
        assert context.prec == 6


def test_more_than_thirty_charge_items_fail_without_truncating():
    data = review_values()
    data["charge_items"].extend(
        {
            "item_id": f"other-{i}",
            "kind": "other_scheduled",
            "timing": "repayments",
            "amount": "0.00",
            "support_section_reference": "SYN",
        }
        for i in range(30)
    )
    with pytest.raises(ValueError):
        subject().DisclosureReviewRequest.model_validate(data)
    assert len(data["charge_items"]) == 31


def test_zero_money_has_one_canonical_spelling():
    m = subject()
    for value in ["0", "-0.00", Decimal("-0E-50")]:
        assert (
            m.parse_components(component_values(grt_in_repayments=value)).model_dump(
                mode="json"
            )["grt_in_repayments"]
            == "0.00"
        )


def test_full_request_validation_does_not_change_low_precision_caller():
    with localcontext() as context:
        context.prec = 4
        before = context.copy()
        parsed = subject().DisclosureReviewRequest.model_validate(review_values())
        assert parsed.components.total_scheduled_payable == Decimal("1200.00")
        assert context.prec == before.prec
        assert context.traps == before.traps


@pytest.mark.parametrize("value", ["NaN", "-0.01", 0.1, True, "1E1000000"])
def test_disclosed_rates_reject_inexact_or_unbounded_representation(value):
    data = review_values(
        disclosure_values=disclosure_values(
            effective_interest_rate=value,
            effective_interest_rate_reference="SYN EIR",
            rate_period="annual",
            calculation_method="SYN METHOD",
        )
    )
    with pytest.raises(ValueError):
        subject().DisclosureReviewRequest.model_validate(data)


def test_support_decoded_size_limit_is_not_just_base64_length():
    import base64

    m = subject()
    allowed = base64.b64encode(b"x" * m.MAX_SUPPORT_BYTES).decode("ascii")
    rejected = base64.b64encode(b"x" * (m.MAX_SUPPORT_BYTES + 1)).decode("ascii")
    # The same encoded length can contain different decoded byte counts.
    assert len(allowed) == len(rejected)
    assert m.DisclosureReviewRequest.model_validate(
        review_values(support_base64=allowed)
    )
    with pytest.raises(ValueError):
        m.DisclosureReviewRequest.model_validate(review_values(support_base64=rejected))


def test_digest_rejects_cycles_and_extreme_decimal_exponents():
    m = subject()
    cycle = {}
    cycle["nested"] = cycle
    for payload in [cycle, {"rate": Decimal("1E1000000")}, {"rate": Decimal("NaN")}]:
        with pytest.raises(ValueError):
            m.canonical_review_digest(payload)


def test_first_loan_public_contract_cannot_enable_issuance():
    m = subject()
    request = m.DisclosureReviewRequest.model_validate(review_values())
    public = m.public_financial_snapshot(request.model_dump(mode="json"))
    assert not (
        {"ready", "approval_ready", "approved", "tax_due", "journal_id"} & set(public)
    )
    assert public["disclosure_values"]["amount_financed"] is None


def test_normalized_charge_identity_keeps_its_length_bound():
    data = review_values()
    data["charge_items"][0]["item_id"] = "ß" * 41
    data["terms"]["deductions"][0]["code"] = "ß" * 41
    with pytest.raises(ValueError):
        subject().DisclosureReviewRequest.model_validate(data)


@pytest.mark.parametrize("value", [True, 1.0])
def test_installment_number_must_remain_an_integer_not_numeric_equality(value):
    m = subject()
    terms = FirstLoanTerms.model_validate(terms_values())
    rows = generate_first_loan_schedule(terms)
    altered = (replace(rows[0], installment_number=value), *rows[1:])
    assert altered == rows
    with pytest.raises(ValueError):
        m.require_component_compatibility(
            terms, altered, m.parse_components(component_values())
        )
