"""Cent validation must not depend on the process Decimal rounding context.

Large values probe precision only; they do not establish product amount limits.
"""
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from gilbic_backend.loan_application_information import LoanRequestInformation


@pytest.mark.parametrize(
    "amount, precision, valid",
    [
        ("100000000000000000000000000000.001", 28, False),
        ("100000000000000000000000000000.010", 28, True),
        ("123.451", 2, False),
        ("123.4500", 2, True),
    ],
)
def test_request_cent_precision_is_not_rounded_by_decimal_context(
    amount, precision, valid
):
    with localcontext() as context:
        context.prec = precision
        if valid:
            model = LoanRequestInformation(requested_amount=amount)
            assert model.requested_amount.as_tuple() == Decimal(amount).as_tuple()
        else:
            with pytest.raises(ValidationError):
                LoanRequestInformation(requested_amount=amount)
