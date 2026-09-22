"""Synthetic arithmetic only: no tax rate, legal authority or real evidence."""

import base64

from test_first_loan_terms import values


SUPPORT = b"%PDF-1.4\nSYNTHETIC CALCULATION SUPPORT ONLY\n%%EOF"


def component_values(**changes):
    result = dict(
        principal="1000.00", contractual_interest="200.00",
        dst_upfront="10.00", grt_in_repayments="0.00", renewal_offset="0.00",
        other_upfront_deductions="0.00", other_scheduled_charges="0.00",
        total_upfront_deductions="10.00", net_proceeds="990.00",
        total_scheduled_payable="1200.00",
    )
    result.update(changes)
    return result


def terms_values(**changes):
    result = values()
    result.update(
        loan_type_id="00000000-0000-4000-8000-000000000001",
        deductions=[{
            "code": "dst", "amount": "10.00",
            "authority_reference": "SYNTHETIC SUPPORT section 1",
        }],
    )
    result.update(changes)
    return result


def disclosure_values(**changes):
    result = dict(
        amount_financed=None, amount_financed_reference=None,
        finance_charge_total=None, finance_charge_reference=None,
        non_finance_charge_total=None, non_finance_charge_reference=None,
        effective_interest_rate=None, effective_interest_rate_reference=None,
        rate_period=None, calculation_method=None,
    )
    result.update(changes)
    return result


def review_values(**changes):
    result = dict(
        request_id="00000000-0000-4000-8000-000000000002",
        application_version_id="00000000-0000-4000-8000-000000000003",
        cif_version_id="00000000-0000-4000-8000-000000000004",
        dst_rule_id="00000000-0000-4000-8000-000000000005",
        grt_rule_id="00000000-0000-4000-8000-000000000006",
        terms=terms_values(), expected_context_digest="a" * 64,
        components=component_values(),
        charge_items=[{
            "item_id": "dst", "kind": "dst", "timing": "upfront",
            "amount": "10.00", "support_section_reference": "SYNTHETIC section 1",
        }],
        disclosure_values=disclosure_values(),
        borrower_charge_basis={
            "support_section_reference": "SYNTHETIC section 2",
            "rationale": "Synthetic borrower-charge review, not legal proof.",
            "dst_zero_reason": None,
            "grt_zero_reason": "Synthetic company-borne amount, not tax exemption.",
        },
        calculation_method="reviewed_precomputed_v1",
        review_rationale="Synthetic exact breakdown for Peña; no live tax decision.",
        support_media_type="application/pdf",
        support_base64=base64.b64encode(SUPPORT).decode("ascii"),
        supersedes_calculation_id=None,
    )
    result.update(changes)
    return result


def projection_references():
    return dict(
        loan_version_reference="SYN-TERMS-1", tax_loan_version_reference="SYN-TERMS-1",
        tax_rule_snapshot_reference="SYN-RULES-1", tax_calculation_reference="SYN-CALC-1",
    )
