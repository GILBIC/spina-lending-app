"""Read-only document projection of supplied, precomputed DST/GRT amounts.

The caller must supply authorized, itemized amounts from one loan/tax version.
Reference equality and arithmetic do not verify provenance, ownership, legal
applicability, approval, signing, payment or BIR remittance. Non-tax totals must
exclude DST/GRT; this helper cannot detect an upstream mislabeled charge.
It does not select rates, calculate tax/gross-up, price or schedule a loan,
allocate payments, post accounting, render documents or write to any record.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, DecimalException, Inexact, localcontext
from types import MappingProxyType


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class LoanDocumentTaxBreakdownError(ValueError):
    """Supplied document amounts or references cannot reconcile without guessing."""


@dataclass(frozen=True, slots=True)
class LoanDocumentTaxLine:
    code: str
    label: str
    amount: Decimal
    collection_timing: str


@dataclass(frozen=True, slots=True)
class LoanDocumentTaxBreakdown:
    loan_version_reference: str
    tax_loan_version_reference: str
    tax_rule_snapshot_reference: str
    tax_calculation_reference: str
    principal: Decimal
    contractual_interest: Decimal
    renewal_offset: Decimal
    other_upfront_deductions: Decimal
    other_scheduled_charges: Decimal
    total_upfront_deductions: Decimal
    net_proceeds: Decimal
    total_scheduled_payable: Decimal
    tax_lines: tuple[LoanDocumentTaxLine, ...]

    def template_amounts(self) -> Mapping[str, str]:
        """Format reconciled amounts for the existing T02/T03 placeholders.

        This does not authenticate sources or fill unrelated disclosure fields.
        Repeated tokens and document-specific aliases reuse the same amounts.
        """
        taxes = {line.code: line.amount for line in self.tax_lines}
        amounts = {
            "{Approved Principal/Gross Loan Amount}": self.principal,
            "{Approved Gross Principal}": self.principal,
            "{DST Upfront Amount}": taxes["dst"],
            "{Renewal Offset Amount}": self.renewal_offset,
            "{Authoritative total deductions}": self.total_upfront_deductions,
            "{Total Approved Deductions}": self.total_upfront_deductions,
            "{Authoritative net proceeds}": self.net_proceeds,
            "{Authorized Net Proceeds}": self.net_proceeds,
            "{Total Contractual Interest}": self.contractual_interest,
            "{GRT Recovery in Repayments}": taxes["grt_recovery"],
            "{Other Scheduled Charges}": self.other_scheduled_charges,
            "{Authoritative Scheduled Total}": self.total_scheduled_payable,
        }
        return MappingProxyType(
            {token: format(amount, ",.2f") for token, amount in amounts.items()}
        )


def _require_money(value: Decimal, field: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
        raise LoanDocumentTaxBreakdownError(
            f"{field} must be a finite nonnegative Decimal."
        )
    # Check exact cents without replacing or rounding the supplied amount.
    if value != value.quantize(CENT):
        raise LoanDocumentTaxBreakdownError(f"{field} must contain exact cents.")


def project_loan_document_tax_breakdown(
    *,
    loan_version_reference: str,
    tax_loan_version_reference: str,
    tax_rule_snapshot_reference: str,
    tax_calculation_reference: str,
    principal: Decimal,
    contractual_interest: Decimal,
    dst_upfront: Decimal,
    grt_in_repayments: Decimal,
    renewal_offset: Decimal,
    other_upfront_deductions: Decimal,
    other_scheduled_charges: Decimal,
    expected_total_upfront_deductions: Decimal,
    expected_net_proceeds: Decimal,
    expected_total_scheduled: Decimal,
) -> LoanDocumentTaxBreakdown:
    """Keep DST upfront and GRT recovery in reconciled, agreed repayments.

    All amounts, including zeros and locked expected totals, must be explicit.
    References are retained verbatim; matching them does not authenticate them.
    """
    for field, reference in (
        ("loan_version_reference", loan_version_reference),
        ("tax_loan_version_reference", tax_loan_version_reference),
        ("tax_rule_snapshot_reference", tax_rule_snapshot_reference),
        ("tax_calculation_reference", tax_calculation_reference),
    ):
        if not isinstance(reference, str) or not reference.strip():
            raise LoanDocumentTaxBreakdownError(
                f"{field} must be a nonblank string."
            )
    if tax_loan_version_reference != loan_version_reference:
        raise LoanDocumentTaxBreakdownError(
            "Tax amounts must reference the same supplied loan terms version."
        )

    try:
        # Match the existing projection boundary: fail closed if the caller's
        # Decimal context cannot represent exact cents/sums. No pricing rounding.
        with localcontext() as context:
            context.traps[Inexact] = True
            for field, amount in (
                ("principal", principal),
                ("contractual_interest", contractual_interest),
                ("dst_upfront", dst_upfront),
                ("grt_in_repayments", grt_in_repayments),
                ("renewal_offset", renewal_offset),
                ("other_upfront_deductions", other_upfront_deductions),
                ("other_scheduled_charges", other_scheduled_charges),
                ("expected_total_upfront_deductions", expected_total_upfront_deductions),
                ("expected_net_proceeds", expected_net_proceeds),
                ("expected_total_scheduled", expected_total_scheduled),
            ):
                _require_money(amount, field)
            if principal <= ZERO:
                raise LoanDocumentTaxBreakdownError("Principal must be positive.")

            total_upfront = dst_upfront + renewal_offset + other_upfront_deductions
            if total_upfront > principal:
                raise LoanDocumentTaxBreakdownError(
                    "Total upfront deductions cannot exceed principal."
                )
            net_proceeds = principal - total_upfront
            total_scheduled = (
                principal + contractual_interest + grt_in_repayments
                + other_scheduled_charges
            )
            for field, actual, expected in (
                ("Total upfront deductions", total_upfront, expected_total_upfront_deductions),
                ("Net proceeds", net_proceeds, expected_net_proceeds),
                ("Total scheduled payable", total_scheduled, expected_total_scheduled),
            ):
                if actual != expected:
                    raise LoanDocumentTaxBreakdownError(
                        f"{field} does not match the supplied expected total."
                    )
    except DecimalException as exc:
        raise LoanDocumentTaxBreakdownError(
            "Document amounts must reconcile exactly without Decimal rounding."
        ) from exc

    return LoanDocumentTaxBreakdown(
        loan_version_reference=loan_version_reference,
        tax_loan_version_reference=tax_loan_version_reference,
        tax_rule_snapshot_reference=tax_rule_snapshot_reference,
        tax_calculation_reference=tax_calculation_reference,
        principal=principal,
        contractual_interest=contractual_interest,
        renewal_offset=renewal_offset,
        other_upfront_deductions=other_upfront_deductions,
        other_scheduled_charges=other_scheduled_charges,
        total_upfront_deductions=total_upfront,
        net_proceeds=net_proceeds,
        total_scheduled_payable=total_scheduled,
        tax_lines=(
            LoanDocumentTaxLine(
                code="dst", label="Documentary Stamp Tax (DST)",
                amount=dst_upfront, collection_timing="upfront",
            ),
            LoanDocumentTaxLine(
                code="grt_recovery", label="Passed-on Gross Receipts Tax (GRT)",
                amount=grt_in_repayments, collection_timing="repayments",
            ),
        ),
    )
