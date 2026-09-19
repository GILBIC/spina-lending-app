from datetime import date
from decimal import Decimal
from importlib import import_module
from uuid import uuid4

import pytest


def module():
    try:
        return import_module("gilbic_backend.first_loan_terms")
    except ModuleNotFoundError:
        pytest.fail("First-loan exact-term contract is not implemented", pytrace=False)


def values(**changes):
    return dict(
        loan_type_id=str(uuid4()),
        product_code="regular",
        principal="1000.00",
        contractual_interest="200.00",
        interest_rate_percent="20.0000",
        daily_interest_per_1000=None,
        payment_frequency="daily",
        schedule_basis_date="2026-09-19",
        first_due_date="2026-09-20",
        installment_count=12,
        installment_amount="100.00",
        account_email="synthetic@example.invalid",
        deductions=[],
        pricing_review_reference="SYNTHETIC-PRICING",
        **changes,
    )


def test_regular_terms_reuse_exact_rows_and_components():
    m = module()
    terms = m.FirstLoanTerms.model_validate(values())
    rows = m.generate_first_loan_schedule(terms)
    assert len(rows) == 12
    assert rows[0].due_date == date(2026, 9, 20)
    assert rows[-1].due_date == date(2026, 10, 1)
    assert sum(row.principal_component for row in rows) == Decimal("1000.00")
    assert sum(row.interest_component for row in rows) == Decimal("200.00")
    assert terms.net_cash == Decimal("1000.00")


def test_itemized_upfront_deductions_reconcile_cash_without_changing_schedule():
    m = module()
    data = values()
    data["deductions"] = [
        {"code": "dst", "amount": "10.00", "authority_reference": "SYNTHETIC-TAX"}
    ]
    terms = m.FirstLoanTerms.model_validate(data)
    assert terms.net_cash == Decimal("990.00")
    assert sum(
        row.contractual_amount for row in m.generate_first_loan_schedule(terms)
    ) == Decimal("1200.00")


def test_seven_by_seven_uses_existing_original_principal_interest_and_signed_maturity():
    m = module()
    data = values()
    data.update(
        product_code="seven_by_seven",
        contractual_interest=None,
        interest_rate_percent=None,
        daily_interest_per_1000="5.00",
        installment_amount="105.00",
        installment_count=None,
    )
    rows = m.generate_first_loan_schedule(m.FirstLoanTerms.model_validate(data))
    assert len(rows) == 10
    assert rows[-1].due_date == date(2026, 9, 29)
    assert sum(row.principal_component for row in rows) == Decimal("1000.00")
    assert sum(row.interest_component for row in rows) == Decimal("50.00")


@pytest.mark.parametrize(
    "field,value",
    [
        ("principal", "0.00"),
        ("principal", "1000.001"),
        ("principal", float("inf")),
        ("principal", 1000.0),
        ("principal", True),
        ("contractual_interest", "-1.00"),
        ("interest_rate_percent", "21.0000"),
        ("installment_count", True),
        ("installment_count", 5000),
        ("first_due_date", "2026-09-18"),
        ("account_email", ""),
        ("account_email", "not-an-email"),
        ("pricing_review_reference", "  "),
        ("product_code", "unknown"),
    ],
)
def test_invalid_or_contradictory_terms_fail_before_any_write(field, value):
    m = module()
    data = values()
    data[field] = value
    with pytest.raises(ValueError):
        m.generate_first_loan_schedule(m.FirstLoanTerms.model_validate(data))


def test_duplicate_or_excessive_deductions_are_rejected():
    m = module()
    for deductions in [
        [{"code": "dst", "amount": "1.00", "authority_reference": "A"}] * 2,
        [{"code": "dst", "amount": "1000.00", "authority_reference": "A"}],
    ]:
        data = values()
        data["deductions"] = deductions
        with pytest.raises(ValueError):
            m.FirstLoanTerms.model_validate(data)


def test_hash_is_stable_and_binds_all_packet_content():
    m = module()
    assert m.snapshot_digest({"a": 1, "b": 2}) == m.snapshot_digest({"b": 2, "a": 1})
    assert m.snapshot_digest({"a": 1}) != m.snapshot_digest({"a": 2})
