from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

import gilbic_backend.contract_schedule_registration_repository as registration_repository
import gilbic_backend.contract_schedule_registration_service as registration_service
from gilbic_backend.contract_schedule_service import ContractScheduleConflict
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)


def _review(*, complete_penalty_authority: bool):
    kwargs = {
        "id": 17,
        "loan_id": uuid4(),
        "terms_fingerprint": "a" * 64,
        "applicability_review_ready": True,
        "pricing_cap_review_ready": True,
        "disclosure_ready": True,
        "total_cost_cap_review_ready": True,
        "evidence_reference": "P6-SLICE6-TERMS",
        "review_note": "Exact signed penalty policy and legal cap evidence reviewed.",
        "reviewed_by_user_id": uuid4(),
        "reviewed_at": datetime(2099, 1, 1, tzinfo=timezone.utc),
        "penalty_policy_version": (
            "7x7-penalty-v1" if complete_penalty_authority else None
        ),
        "penalty_monthly_rate": (
            Decimal("0.030000") if complete_penalty_authority else None
        ),
        "penalty_proration_days": 30 if complete_penalty_authority else None,
        "penalty_rate_ceiling": (
            Decimal("0.050000") if complete_penalty_authority else None
        ),
        "lifetime_nonprincipal_cost_ceiling": (
            Decimal("3000.00") if complete_penalty_authority else None
        ),
        "counted_nonprincipal_cost_at_contract_lock": (
            Decimal("1260.00") if complete_penalty_authority else None
        ),
    }
    return registration_repository.SevenBySevenPricingComplianceReview(**kwargs)


def test_pricing_review_uses_bigserial_id_and_separate_penalty_readiness() -> None:
    id_annotation = registration_repository.SevenBySevenPricingComplianceReview.__annotations__[
        "id"
    ]
    assert id_annotation in {int, "int"}

    legacy_review = _review(complete_penalty_authority=False)
    assert legacy_review.ready is True
    assert legacy_review.penalty_authority_ready is False

    complete_review = _review(complete_penalty_authority=True)
    assert complete_review.ready is True
    assert complete_review.penalty_authority_ready is True


def test_complete_review_builds_deterministic_signed_schedule_penalty_snapshot() -> None:
    review = _review(complete_penalty_authority=True)

    settings = registration_repository.build_7x7_penalty_policy_schedule_settings(
        review=review
    )

    assert settings == {
        "seven_by_seven_penalty_policy": {
            "policy_version": "7x7-penalty-v1",
            "review_id": 17,
            "terms_fingerprint": "a" * 64,
            "contractual_monthly_rate": "0.030000",
            "proration_days": 30,
            "legal_rate_ceiling": "0.050000",
            "lifetime_nonprincipal_cost_ceiling": "3000.00",
            "counted_nonprincipal_cost_at_contract_lock": "1260.00",
        }
    }


def test_legacy_boolean_ready_review_cannot_build_penalty_snapshot() -> None:
    review = _review(complete_penalty_authority=False)

    with pytest.raises(
        registration_repository.ContractScheduleRegistrationConflict,
        match="penalty",
    ):
        registration_repository.build_7x7_penalty_policy_schedule_settings(
            review=review
        )


def test_verified_registration_threads_penalty_snapshot_into_schedule_store(
    monkeypatch,
) -> None:
    loan_id = uuid4()
    actor_id = uuid4()
    schedule_id = uuid4()
    release_date = date(2099, 1, 1)
    rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("3000.00"),
        agreed_daily_payment=Decimal("50.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=release_date + timedelta(days=1),
    )
    schedule_settings = {
        "seven_by_seven_penalty_policy": {
            "policy_version": "7x7-penalty-v1",
            "review_id": 17,
            "terms_fingerprint": "a" * 64,
            "contractual_monthly_rate": "0.030000",
            "proration_days": 30,
            "legal_rate_ceiling": "0.050000",
            "lifetime_nonprincipal_cost_ceiling": "3000.00",
            "counted_nonprincipal_cost_at_contract_lock": "1260.00",
        }
    }
    captured: dict[str, object] = {}

    def fake_store_contract_schedule(*args, **kwargs):
        captured.update(kwargs)
        return schedule_id

    monkeypatch.setattr(
        registration_service,
        "store_contract_schedule",
        fake_store_contract_schedule,
    )

    class RecordingCursor:
        def __init__(self) -> None:
            self.statements: list[tuple[str, tuple[object, ...] | None]] = []

        def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
            self.statements.append((" ".join(query.split()), params))

    cursor = RecordingCursor()
    result = registration_service.register_verified_contract_schedule(
        cursor,
        loan_id=loan_id,
        payment_frequency="daily",
        contract_reference="P6-SLICE6-CONTRACT",
        contract_signed_date=release_date,
        effective_from=release_date,
        grace_days=0,
        installments=rows,
        evidence_basis="signed_contract",
        evidence_reference="P6-SLICE6-SIGNED-EVIDENCE",
        verification_note="Borrower accepted the exact penalty disclosure.",
        verified_by_user_id=actor_id,
        agreed_daily_payment=Decimal("50.00"),
        schedule_settings=schedule_settings,
        confirmed=True,
    )

    assert result == schedule_id
    assert captured["settings"] == schedule_settings


def test_incomplete_penalty_review_cannot_be_treated_as_signed_authority() -> None:
    review = _review(complete_penalty_authority=False)
    assert review.ready is True

    with pytest.raises(ContractScheduleConflict):
        registration_repository.build_7x7_penalty_policy_schedule_settings(
            review=review
        )
