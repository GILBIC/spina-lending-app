"""Approved repayment declarations, not verification, approval or full T01 readiness.

Use the existing application-information module. A source-appropriate narrative
avoids requiring employer fields for a business, pension or remittance source.
References and proof uploads are not prerequisites of this value-only block.
Actual applicant acknowledgment and persisted confirmation remain separate.
"""
from copy import deepcopy
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from gilbic_backend import loan_application_information as information


REQUIRED = (
    "repayment_source",
    "source_details",
    "monthly_gross_income",
    "monthly_net_income",
    "has_existing_obligations",
)
DEBT_REQUIRED = (
    "creditor", "outstanding_balance", "periodic_payment_amount", "payment_frequency"
)


def _model():
    model = getattr(information, "LoanRepaymentInformation", None)
    assert model is not None, "Repayment-information model is not implemented"
    return model


def _income(**changes):
    values = {
        "repayment_source": "business",
        "source_details": "Synthetic market stall; owner; operating for two years",
        "monthly_gross_income": "30000.00",
        "monthly_net_income": "18000.00",
        "has_existing_obligations": False,
    }
    values.update(changes)
    return values


def _debt(**changes):
    values = {
        "creditor": "Synthetic lender",
        "outstanding_balance": "2000.00",
        "periodic_payment_amount": "100.00",
        "payment_frequency": "Weekly on Friday",
    }
    values.update(changes)
    return values


def test_empty_draft_keeps_unknown_income_and_debts_distinct_from_zero_or_none():
    draft = _model()()

    assert draft.model_dump() == {**dict.fromkeys(REQUIRED), "obligations": ()}
    assert draft.missing_fields() == REQUIRED


@pytest.mark.parametrize("missing", REQUIRED)
def test_partial_repayment_draft_reports_exact_missing_fact(missing):
    values = _income()
    del values[missing]
    draft = _model()(**values)

    assert draft.missing_fields() == (missing,)
    assert getattr(draft, missing) is None


@pytest.mark.parametrize("source, details", [
    ("employment", "Synthetic employer; bookkeeper; three years"),
    ("business", "Synthetic home store; owner; two years"),
    ("professional", "Synthetic independent repair service; technician"),
    ("other", "Synthetic pension and remittance; declared sources and frequency"),
])
def test_source_details_do_not_force_employer_references_or_new_proof_fields(source, details):
    draft = _model()(**_income(repayment_source=source, source_details=details))

    assert draft.repayment_source == source
    assert draft.source_details == details
    assert draft.missing_fields() == ()  # This repayment block only, not full T01.
    assert set(draft.model_dump()) == {*REQUIRED, "obligations"}
    assert draft.obligations == ()


def test_blank_source_details_are_incomplete_not_a_no_income_declaration():
    draft = _model()(**_income(repayment_source="  ", source_details="\t\n"))

    assert draft.missing_fields() == ("repayment_source", "source_details")
    assert draft.repayment_source is None and draft.source_details is None
    assert draft.monthly_gross_income == Decimal("30000.00")


def test_explicit_zero_or_negative_net_is_a_declaration_not_automatic_credit_approval():
    draft = _model()(**_income(monthly_gross_income="0.00", monthly_net_income="-200.00"))

    assert draft.monthly_gross_income.as_tuple() == Decimal("0.00").as_tuple()
    assert draft.monthly_net_income.as_tuple() == Decimal("-200.00").as_tuple()
    assert draft.missing_fields() == ()
    assert draft.has_existing_obligations is False
    # Losses must remain truthful; this block does not decide creditworthiness.
    assert set(draft.model_dump()) == {*REQUIRED, "obligations"}


def test_declared_obligations_require_at_least_one_row_without_fabricating_it():
    draft = _model()(**_income(has_existing_obligations=True))

    assert draft.missing_fields() == ("obligations",)
    assert draft.obligations == ()


def test_entered_rows_do_not_silently_answer_the_debt_declaration():
    draft = _model()(**_income(has_existing_obligations=None, obligations=[_debt()]))

    assert draft.missing_fields() == ("has_existing_obligations",)
    assert draft.has_existing_obligations is None
    assert draft.obligations[0].creditor == "Synthetic lender"


@pytest.mark.parametrize("missing", DEBT_REQUIRED)
def test_incomplete_debt_rows_report_the_exact_row_and_field(missing):
    row = _debt()
    del row[missing]
    draft = _model()(**_income(has_existing_obligations=True, obligations=[row]))

    assert draft.missing_fields() == (f"obligations[0].{missing}",)
    assert getattr(draft.obligations[0], missing) is None
    assert draft.obligations[0].notes is None


def test_all_incomplete_rows_are_preserved_and_reported_in_input_order():
    draft = _model()(**_income(has_existing_obligations=True, obligations=[
        _debt(creditor=" ", periodic_payment_amount=None),
        _debt(outstanding_balance=None, payment_frequency="\t"),
    ]))

    assert len(draft.obligations) == 2
    assert draft.missing_fields() == (
        "obligations[0].creditor", "obligations[0].periodic_payment_amount",
        "obligations[1].outstanding_balance", "obligations[1].payment_frequency",
    )


def test_no_obligations_with_entered_rows_is_rejected_without_dropping_disclosures():
    model = _model()
    with pytest.raises(ValidationError):
        model(**_income(obligations=[_debt()]))


@pytest.mark.parametrize("declaration", ["false", "true", 0, 1, ""])
def test_debt_declaration_requires_an_actual_boolean_not_truthy_coercion(declaration):
    model = _model()
    with pytest.raises(ValidationError):
        model(**_income(has_existing_obligations=declaration))


def test_declarations_copy_input_preserve_rows_and_reject_ordinary_mutation():
    values = _income(has_existing_obligations=True, source_details=" Synthetic   shop ",
                     obligations=[_debt(creditor=" Synthetic   lender ", notes="  "),
                                  _debt(periodic_payment_amount="0.00",
                                        payment_frequency="Deferred; no payment currently due")])
    before = deepcopy(values)
    draft = _model()(**values)

    assert values == before
    assert draft.source_details == "Synthetic shop"
    assert isinstance(draft.obligations, tuple) and len(draft.obligations) == 2
    assert draft.obligations[0].creditor == "Synthetic lender"
    assert draft.obligations[0].notes is None
    assert draft.obligations[1].periodic_payment_amount == Decimal("0.00")
    assert draft.missing_fields() == ()
    values["obligations"][0]["outstanding_balance"] = "9999.00"
    values["obligations"].clear()
    assert draft.obligations[0].outstanding_balance == Decimal("2000.00")
    assert len(draft.obligations) == 2
    with pytest.raises(ValidationError):
        draft.monthly_net_income = Decimal("1.00")
    with pytest.raises(ValidationError):
        draft.obligations[0].creditor = "Changed"


@pytest.mark.parametrize("field, value", [
    ("monthly_gross_income", "-0.01"),
    ("monthly_gross_income", "NaN"),
    ("monthly_net_income", "Infinity"),
    ("monthly_net_income", True),
    ("outstanding_balance", "-1.00"),
    ("outstanding_balance", 2000.1),
    ("periodic_payment_amount", "-1.00"),
    ("periodic_payment_amount", "not money"),
])
def test_invalid_declared_money_is_rejected_not_rounded_or_replaced(field, value):
    model = _model()
    values = _income(has_existing_obligations=True, obligations=[_debt()])
    target = values if field.startswith("monthly_") else values["obligations"][0]
    target[field] = value
    with pytest.raises(ValidationError):
        model(**values)


@pytest.mark.parametrize("field", [
    "monthly_gross_income", "monthly_net_income", "outstanding_balance", "periodic_payment_amount"
])
@pytest.mark.parametrize("amount, valid", [("123.451", False), ("123.4500", True)])
def test_declared_money_uses_exact_cents_independent_of_decimal_context(field, amount, valid):
    model = _model()
    values = _income(has_existing_obligations=True, obligations=[_debt()])
    target = values if field.startswith("monthly_") else values["obligations"][0]
    target[field] = amount
    with localcontext() as context:
        context.prec = 2
        if valid:
            draft = model(**values)
            record = draft if field.startswith("monthly_") else draft.obligations[0]
            assert getattr(record, field).as_tuple() == Decimal(amount).as_tuple()
        else:
            with pytest.raises(ValidationError):
                model(**values)


@pytest.mark.parametrize("field, value", [
    ("source_details", {"not": "text"}),
    ("monthly_net_income", "invalid"),
    ("confirmed_at", "2026-09-17T09:00:00Z"),
    ("approved_principal", "10000.00"),
    ("privacy_consent", True),
    ("cif_version_id", "11111111-1111-4111-8111-111111111111"),
])
def test_repayment_input_rejects_malformed_or_authoritative_extra_fields(field, value):
    model = _model()
    with pytest.raises(ValidationError):
        model(**_income(**{field: value}))


@pytest.mark.parametrize("changes", [
    {"creditor": 123}, {"payment_frequency": 7}, {"notes": []},
    {"verified": True}, {"collection_contact_authorized": True},
])
def test_debt_rows_do_not_coerce_text_or_accept_verification_and_collection_authority(changes):
    model = _model()
    with pytest.raises(ValidationError):
        model(**_income(has_existing_obligations=True, obligations=[_debt(**changes)]))
