from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from gilbic_backend.seven_by_seven_extra_principal_posting import (
    ExtraPrincipalPostingRejected,
    SevenBySevenExtraPrincipalPostingResult,
    require_modern_extra_principal_intent,
)
from spina_mobile_collections.contracts import PaymentAllocationIntent


@pytest.mark.parametrize(
    "intent",
    (
        PaymentAllocationIntent.SCHEDULED,
        PaymentAllocationIntent.VOLUNTARY_EXTRA,
        PaymentAllocationIntent.EXTRA_AS_ADVANCE,
    ),
)
def test_only_modern_principal_reduction_intent_can_activate_bridge(intent) -> None:
    with pytest.raises(ExtraPrincipalPostingRejected) as captured:
        require_modern_extra_principal_intent(intent)

    assert captured.value.code == "seven_by_seven_extra_principal_intent_required"


def test_modern_principal_reduction_intent_is_accepted() -> None:
    require_modern_extra_principal_intent(
        PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION
    )


def test_posting_result_metadata_preserves_exact_zero_interest_and_custody_split() -> (
    None
):
    adjustment_id = uuid4()
    result = SevenBySevenExtraPrincipalPostingResult(
        adjustment_id=adjustment_id,
        principal_reduction=Decimal("100.00"),
        resulting_future_principal=Decimal("4900.00"),
        removed_future_interest=Decimal("21.00"),
        retained_advance=Decimal("30.00"),
        refund_due=Decimal("5.00"),
        resulting_operational_version=3,
        operational_state_digest="a" * 64,
    )

    assert result.response_metadata() == {
        "allocation_type": "seven_by_seven_extra_principal",
        "adjustment_id": str(adjustment_id),
        "principal_reduction": "100.00",
        "interest_contribution": "0.00",
        "resulting_future_principal": "4900.00",
        "removed_future_interest": "21.00",
        "retained_advance": "30.00",
        "refund_due": "5.00",
        "resulting_operational_version": 3,
        "operational_state_digest": "a" * 64,
        "automatic_source_posting": False,
    }
