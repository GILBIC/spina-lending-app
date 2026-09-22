"""Pure pre-release disclosure values; never tax, source or release authority.

These checks establish exact arithmetic and supported component representation.
Repositories must independently verify the source, rules, retained calculation,
borrower-charge basis, permissions and current readiness before any new action.
No database, private-file access, tax calculation or financial write occurs here.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from datetime import date
from decimal import Context, Decimal, DecimalException, localcontext
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    field_validator,
    model_validator,
)

from .first_loan_terms import (
    FirstLoanTerms,
    Money,
    StrictInput,
    generate_first_loan_schedule,
    snapshot_digest,
)
from .loan_document_tax_breakdown import project_loan_document_tax_breakdown

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_MONEY = Decimal("9999999999999999.99")
MAX_SUPPORT_BYTES = 10 * 1024 * 1024
MAX_SUPPORT_BASE64 = 4 * ((MAX_SUPPORT_BYTES + 2) // 3)


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Use exact decimal text, integers or Decimal values.")
    if isinstance(value, str) and len(value) > 128:
        raise ValueError("The decimal representation is too long.")
    try:
        result = Decimal(value)
        if not result.is_finite() or result < 0:
            raise ValueError("Amounts must be finite and nonnegative.")
        return result
    except DecimalException as error:
        raise ValueError("An exact finite decimal is required.") from error


def _exact_money(value: object) -> Decimal:
    result = _decimal(value)
    if result > MAX_MONEY:
        raise ValueError("Money exceeds the existing 18-digit/2-decimal boundary.")
    try:
        with localcontext(Context(prec=40)):
            normalized = result.quantize(CENT)
            if normalized != result:
                raise ValueError(
                    "Money must contain exact cents; rounding is forbidden."
                )
            return ZERO if normalized == 0 else normalized
    except DecimalException as error:
        raise ValueError("Money must contain supported exact cents.") from error


def _exact_rate(value: object) -> Decimal:
    result = _decimal(value)
    # Bound representation work, not the legal rate or its time unit. Preserve
    # all supplied decimal places; this is not a currency-cent conversion.
    exponent = result.as_tuple().exponent
    if (
        not isinstance(exponent, int)
        or abs(exponent) > 128
        or len(result.as_tuple().digits) > 128
    ):
        raise ValueError("The rate representation is outside supported precision.")
    return result


ExactMoney = Annotated[
    Money,
    BeforeValidator(_exact_money),
    PlainSerializer(lambda value: format(value, ".2f"), return_type=str),
]
ExactRate = Annotated[
    Decimal,
    BeforeValidator(_exact_rate),
    PlainSerializer(lambda value: format(value, "f"), return_type=str),
]
Reference = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=250
    ),
]
Rationale = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=2000
    ),
]


class DisclosureInput(StrictInput):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    @model_validator(mode="wrap")
    @classmethod
    def bounded_decimal_context(cls, value, handler):
        # Nested existing FirstLoanTerms arithmetic must not depend on a caller's
        # low-precision Decimal context. No global context is modified.
        with localcontext(Context(prec=40)):
            return handler(value)


class DisclosureComponents(DisclosureInput):
    principal: ExactMoney
    contractual_interest: ExactMoney
    dst_upfront: ExactMoney
    grt_in_repayments: ExactMoney
    renewal_offset: ExactMoney
    other_upfront_deductions: ExactMoney
    other_scheduled_charges: ExactMoney
    total_upfront_deductions: ExactMoney
    net_proceeds: ExactMoney
    total_scheduled_payable: ExactMoney

    @model_validator(mode="after")
    def reconcile(self):
        with localcontext(Context(prec=40)):
            if self.principal <= ZERO or self.net_proceeds <= ZERO:
                raise ValueError("Principal and net cash must be positive.")
            if self.renewal_offset != ZERO:
                raise ValueError("First-loan renewal offset must be explicitly zero.")
            if self.total_upfront_deductions != (
                self.dst_upfront + self.other_upfront_deductions
            ):
                raise ValueError("Upfront deductions must reconcile exactly once.")
            if self.net_proceeds != self.principal - self.total_upfront_deductions:
                raise ValueError(
                    "Net cash does not reconcile to principal and deductions."
                )
            if self.total_scheduled_payable != (
                self.principal
                + self.contractual_interest
                + self.grt_in_repayments
                + self.other_scheduled_charges
            ):
                raise ValueError("The scheduled component total does not reconcile.")
            return self


class DisclosureChargeItem(DisclosureInput):
    item_id: Annotated[
        str, StringConstraints(strict=True, min_length=1, max_length=80)
    ]
    kind: Literal["dst", "grt_recovery", "other_upfront", "other_scheduled"]
    timing: Literal["upfront", "repayments"]
    amount: ExactMoney
    support_section_reference: Reference

    @field_validator("item_id")
    @classmethod
    def canonical_identity(cls, value):
        value = value.strip().casefold()
        if not value or len(value) > 80:
            raise ValueError("Each normalized charge identity needs 1 to 80 characters.")
        return value

    @model_validator(mode="after")
    def classification(self):
        expected = (
            "upfront" if self.kind in ("dst", "other_upfront") else "repayments"
        )
        if self.timing != expected:
            raise ValueError("Charge timing conflicts with its classification.")
        reserved = {
            "dst": "dst",
            "grt": "grt_recovery",
            "grt_recovery": "grt_recovery",
        }
        if self.item_id in reserved and self.kind != reserved[self.item_id]:
            raise ValueError("A reserved tax identity cannot become another charge.")
        return self


def _itemized_upfront(
    items: tuple[DisclosureChargeItem, ...], components: DisclosureComponents
) -> dict[str, Decimal]:
    if len(items) > 30:
        raise ValueError("At most thirty charge items are supported.")
    with localcontext(Context(prec=40)):
        ids = [item.item_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Every charge identity must appear once.")
        for kind in ("dst", "grt_recovery"):
            if sum(item.kind == kind for item in items) > 1:
                raise ValueError("Each tax classification must appear at most once.")
        totals = {
            kind: sum(
                (item.amount for item in items if item.kind == kind), ZERO
            )
            for kind in ("dst", "grt_recovery", "other_upfront", "other_scheduled")
        }
        expected = {
            "dst": components.dst_upfront,
            "grt_recovery": components.grt_in_repayments,
            "other_upfront": components.other_upfront_deductions,
            "other_scheduled": components.other_scheduled_charges,
        }
        if totals != expected:
            raise ValueError("Every component must equal its exact itemization.")
        upfront = {
            item.item_id: item.amount for item in items if item.timing == "upfront"
        }
        return upfront


class DisclosureValues(DisclosureInput):
    amount_financed: ExactMoney | None
    amount_financed_reference: Reference | None
    finance_charge_total: ExactMoney | None
    finance_charge_reference: Reference | None
    non_finance_charge_total: ExactMoney | None
    non_finance_charge_reference: Reference | None
    effective_interest_rate: ExactRate | None
    effective_interest_rate_reference: Reference | None
    rate_period: Reference | None
    calculation_method: Reference | None

    @model_validator(mode="after")
    def independent_sources(self):
        for amount, reference in (
            (self.amount_financed, self.amount_financed_reference),
            (self.finance_charge_total, self.finance_charge_reference),
            (self.non_finance_charge_total, self.non_finance_charge_reference),
            (self.effective_interest_rate, self.effective_interest_rate_reference),
        ):
            if (amount is None) != (reference is None):
                raise ValueError(
                    "Each disclosure value needs its own source reference."
                )
        if self.effective_interest_rate is not None:
            if self.rate_period is None or self.calculation_method is None:
                raise ValueError("A supplied EIR needs its explicit period and method.")
        elif self.rate_period is not None or self.calculation_method is not None:
            raise ValueError(
                "An absent EIR cannot have a supplied rate period or method."
            )
        return self


class BorrowerChargeBasis(DisclosureInput):
    support_section_reference: Reference
    rationale: Rationale
    dst_zero_reason: Rationale | None
    grt_zero_reason: Rationale | None


class DisclosureReviewRequest(DisclosureInput):
    request_id: UUID
    application_version_id: UUID
    cif_version_id: UUID
    dst_rule_id: UUID
    grt_rule_id: UUID
    terms: FirstLoanTerms
    expected_context_digest: Annotated[
        str,
        StringConstraints(
            strict=True, min_length=64, max_length=64, pattern="^[0-9a-f]{64}$"
        ),
    ]
    components: DisclosureComponents
    charge_items: tuple[DisclosureChargeItem, ...] = Field(max_length=30)
    disclosure_values: DisclosureValues
    borrower_charge_basis: BorrowerChargeBasis
    calculation_method: Literal["reviewed_precomputed_v1"]
    review_rationale: Rationale
    support_media_type: Literal["application/pdf", "image/png", "image/jpeg"]
    support_base64: Annotated[
        str,
        StringConstraints(
            strict=True, min_length=1, max_length=MAX_SUPPORT_BASE64
        ),
    ]
    supersedes_calculation_id: UUID | None

    @field_validator("terms", mode="before")
    @classmethod
    def revalidate_terms(cls, value):
        if isinstance(value, FirstLoanTerms):
            return value.model_dump(mode="python", warnings=False)
        return value

    @field_validator("support_base64")
    @classmethod
    def bounded_support(cls, value):
        try:
            content = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Support must be valid base64.") from error
        if not content or len(content) > MAX_SUPPORT_BYTES:
            raise ValueError("A support file of at most 10 MiB is required.")
        # No file authenticity claim: PrivateEvidenceStore must still validate
        # actual type, bytes, integrity and authorized ownership at recording.
        return base64.b64encode(content).decode("ascii")

    @model_validator(mode="after")
    def itemization(self):
        with localcontext(Context(prec=40)):
            upfront = _itemized_upfront(self.charge_items, self.components)
            deductions = {
                item.code.strip().casefold(): item.amount
                for item in self.terms.deductions
            }
            if upfront != deductions:
                raise ValueError(
                    "Each existing deduction must map once by identity and amount."
                )
            if (
                self.components.principal != self.terms.principal
                or self.components.net_proceeds != self.terms.net_cash
                or self.components.total_upfront_deductions
                != self.terms.total_deductions
            ):
                raise ValueError(
                    "The reviewed cash components differ from the proposed terms."
                )
            for amount, reason in (
                (
                    self.components.dst_upfront,
                    self.borrower_charge_basis.dst_zero_reason,
                ),
                (
                    self.components.grt_in_repayments,
                    self.borrower_charge_basis.grt_zero_reason,
                ),
            ):
                if (amount == ZERO) != (reason is not None):
                    raise ValueError(
                        "Explicit zero charges need a reason; positive charges must not use it."
                    )
            return self


def parse_components(payload: dict) -> DisclosureComponents:
    return DisclosureComponents.model_validate(payload)


# Names have semantic money meaning in this contract. Never normalize an
# arbitrary numeric-looking string (such as a source reference) or round a rate.
_MONEY_NAMES = frozenset(DisclosureComponents.model_fields) | frozenset({
    "amount", "installment_amount", "daily_interest_per_1000", "contractual_amount",
    "principal_component", "interest_component", "amount_financed",
    "finance_charge_total", "non_finance_charge_total", "net_cash", "total_deductions",
})


def _canonical(value: object, name: str | None = None, depth: int = 0):
    if depth > 32:
        raise ValueError("The review exceeds the supported nesting depth.")
    if name in _MONEY_NAMES and value is not None:
        return format(_exact_money(value), ".2f")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Decimal):
        exponent = value.as_tuple().exponent
        if (
            not value.is_finite()
            or not isinstance(exponent, int)
            or abs(exponent) > 128
            or len(value.as_tuple().digits) > 128
        ):
            raise ValueError("The review requires bounded finite exact decimals.")
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        if name == "terms":
            with localcontext(Context(prec=40)):
                value = FirstLoanTerms.model_validate(dict(value)).model_dump(
                    mode="python"
                )
        if not all(isinstance(key, str) for key in value):
            raise ValueError("Review objects require string keys.")
        return {
            key: _canonical(item, key, depth + 1) for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item, depth=depth + 1) for item in value]
    raise ValueError("The review contains an inexact or non-JSON value.")


def canonical_review_digest(payload: dict) -> str:
    """Hash normalized JSON using first-loan conventions; not source approval."""
    if not isinstance(payload, dict):
        raise ValueError("A review object is required.")
    return snapshot_digest(_canonical(payload))


def project_components(
    components: DisclosureComponents, *, references: dict[str, str]
) -> dict[str, str]:
    expected_references = {
        "loan_version_reference", "tax_loan_version_reference",
        "tax_rule_snapshot_reference", "tax_calculation_reference",
    }
    if (
        not isinstance(references, dict)
        or set(references) != expected_references
    ):
        raise ValueError("Supply exactly the four verified source references.")
    components = DisclosureComponents.model_validate(components)
    with localcontext(Context(prec=40)):
        projected = project_loan_document_tax_breakdown(
            loan_version_reference=references["loan_version_reference"],
            tax_loan_version_reference=references["tax_loan_version_reference"],
            tax_rule_snapshot_reference=references["tax_rule_snapshot_reference"],
            tax_calculation_reference=references["tax_calculation_reference"],
            principal=components.principal,
            contractual_interest=components.contractual_interest,
            dst_upfront=components.dst_upfront,
            grt_in_repayments=components.grt_in_repayments,
            renewal_offset=components.renewal_offset,
            other_upfront_deductions=components.other_upfront_deductions,
            other_scheduled_charges=components.other_scheduled_charges,
            expected_total_upfront_deductions=components.total_upfront_deductions,
            expected_net_proceeds=components.net_proceeds,
            expected_total_scheduled=components.total_scheduled_payable,
        )
    taxes = {line.code: line.amount for line in projected.tax_lines}
    return {
        name: format(value, ".2f") for name, value in {
            "principal": projected.principal,
            "contractual_interest": projected.contractual_interest,
            "dst_upfront": taxes["dst"],
            "grt_in_repayments": taxes["grt_recovery"],
            "renewal_offset": projected.renewal_offset,
            "other_upfront_deductions": projected.other_upfront_deductions,
            "other_scheduled_charges": projected.other_scheduled_charges,
            "total_upfront_deductions": projected.total_upfront_deductions,
            "net_proceeds": projected.net_proceeds,
            "total_scheduled_payable": projected.total_scheduled_payable,
        }.items()
    }


def public_financial_snapshot(review_snapshot: dict) -> dict:
    """Allowlist financial values; caller must authorize access to the source."""
    components = parse_components(review_snapshot["components"])
    values = DisclosureValues.model_validate(review_snapshot["disclosure_values"])
    items = tuple(
        DisclosureChargeItem.model_validate(item)
        for item in review_snapshot["charge_items"]
    )
    _itemized_upfront(items, components)
    return {
        "components": components.model_dump(mode="json"),
        "disclosure_values": values.model_dump(mode="json", include={
            "amount_financed", "finance_charge_total", "non_finance_charge_total",
            "effective_interest_rate", "rate_period", "calculation_method",
        }),
        "charge_items": [item.model_dump(mode="json", include={
            "item_id", "kind", "timing", "amount",
        }) for item in items],
    }


def require_component_compatibility(
    terms: FirstLoanTerms, rows: tuple, components: DisclosureComponents
) -> None:
    """Reject unsupported splits without mutating terms or approved schedules.

    ValueError keeps this pure boundary independent of the database repository.
    The owning repository translates it to its conflict response where needed.
    Passing is representation compatibility, not authorization or issuance.
    """
    components = DisclosureComponents.model_validate(components)
    if (
        components.grt_in_repayments != ZERO
        or components.other_scheduled_charges != ZERO
    ):
        raise ValueError("component integration required")
    with localcontext(Context(prec=40)):
        if not isinstance(terms, FirstLoanTerms):
            raise ValueError("Validated first-loan terms are required.")
        terms = FirstLoanTerms.model_validate(
            terms.model_dump(mode="python", warnings=False)
        )
        if not isinstance(rows, tuple):
            raise ValueError("A tuple of authoritative schedule rows is required.")
        for row in rows:
            number = getattr(row, "installment_number", None)
            if isinstance(number, bool) or not isinstance(number, int):
                raise ValueError("Each installment number must remain an integer.")
            for name in (
                "contractual_amount", "principal_component", "interest_component"
            ):
                amount = getattr(row, name, None)
                if not isinstance(amount, Decimal):
                    raise ValueError(
                        "Schedule components must remain exact Decimal values."
                    )
                _exact_money(amount)
        expected_rows = generate_first_loan_schedule(terms)
        if tuple(rows) != tuple(expected_rows):
            raise ValueError("The rows differ from the exact proposed signed schedule.")
        if (
            terms.principal != components.principal
            or terms.total_deductions != components.total_upfront_deductions
            or terms.net_cash != components.net_proceeds
            or sum((row.contractual_amount for row in rows), ZERO)
            != components.total_scheduled_payable
            or sum((row.principal_component for row in rows), ZERO)
            != components.principal
            or sum((row.interest_component for row in rows), ZERO)
            != components.contractual_interest
        ):
            raise ValueError("The proposed terms and disclosed components differ.")
