"""Public impaired measurements retain exact rounding and hide private sources."""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from gilbic_backend.office_review_evidence_storage import EvidenceFileError
from gilbic_backend.retained_cutoff_assessment_repository import (
    CutoffAssessmentConflict,
)
from test_elapsed_period_assessment_api import BODY

from gilbic_backend import elapsed_period_assessment_repository as repository


@pytest.mark.parametrize("renewal", [False, True])
def test_impaired_cash_projection_preserves_raw_pv_and_currency_rounding(renewal):
    opening = uuid4()
    row = {
        key: uuid4()
        for key in ("id", "book_id", "fiscal_period_id", "loan_id", "application_id")
    } | {
        "as_of_date": date(2030, 1, 2),
        "calculated_at": datetime(2030, 1, 2, tzinfo=timezone.utc),
        "source_digest": "a" * 64,
        "confirmation_digest": "b" * 64,
        "source_snapshot": {
            "gross_carrying_amount": "100.00",
            "opening_assessment": {
                "id": None if renewal else str(opening),
                "as_of_date": "2030-01-01",
                **({"renewal_review_id": str(opening)} if renewal else {}),
            },
            "private": "PRIVATE-SOURCE-BYTES",
        },
        "measurement_snapshot": {
            "policy_version": "native_impaired_cash_expected_receipts_v1",
            "loss_basis": "gross_carrying_less_expected_pv",
            "expected_cash_present_value": "100.00",
            "weighted_expected_cash_present_value_raw": "99.9950000000000000000000000000",
            "currency_rounding_adjustment": "0.01",
            "ecl_amount": "0.01",
            "private": "PRIVATE-SOURCE-BYTES",
        },
        "scenarios": BODY["scenarios"],
        "review_rationale": BODY["review_rationale"],
    }
    public = repository._impaired_cash_review_payload(row)
    assert public["weighted_expected_cash_present_value_raw"] == (
        "99.9950000000000000000000000000"
    )
    assert public["ecl_amount"] == public["currency_rounding_adjustment"] == "0.01"
    assert public["opening_assessment_id"] == (None if renewal else str(opening))
    if renewal:
        assert public["opening_renewal_review_id"] == str(opening)
        candidate = repository._impaired_cash_source_payload(
            {
                "ready": True,
                "blockers": [],
                "source_digest": "a" * 64,
                "gross_carrying_amount": "100.00",
                "opening_assessment_id": None,
                "opening_renewal_review_id": str(opening),
                "opening_cutoff_date": "2030-01-01",
            }
        )
        assert candidate["opening_renewal_review_id"] == str(opening)
        interest = repository._impaired_interest_payload(
            {
                "basis": "original_eir_on_reviewed_net_carrying",
                "opening_assessment_id": None,
                "opening_renewal_review_id": str(opening),
                "opening_cutoff_date": "2030-01-01",
                "impairment_boundary_date": "2030-01-01",
                "gross_interest": "1.00",
                "net_interest": "0.80",
                "allowance_unwind": "0.20",
                "private": "PRIVATE-SOURCE-BYTES",
            }
        )
        assert interest["opening_renewal_review_id"] == str(opening)
        assert "PRIVATE-SOURCE-BYTES" not in repr(interest)
    assert public["review_inputs"]["scenarios"] == BODY["scenarios"]
    assert "PRIVATE-SOURCE-BYTES" not in repr(public)


def test_impaired_cash_source_blocking_clears_confirmable_fields():
    public = repository._impaired_cash_source_payload(
        {
            "ready": False,
            "blockers": ["source_changed"],
            "source_digest": "a" * 64,
            "gross_carrying_amount": "100.00",
            "opening_assessment_id": str(uuid4()),
            "opening_renewal_review_id": str(uuid4()),
        }
    )
    assert not public["ready"]
    assert public["source_digest"] is None
    assert public["gross_carrying_amount"] is None
    assert public["opening_assessment_id"] is None
    assert public.get("opening_renewal_review_id") is None


@pytest.mark.parametrize("renewal", [False, True])
def test_interest_projection_retains_signed_currency_reconciliation(renewal):
    opening = str(uuid4())
    measured = {
        "basis": "original_eir_on_reviewed_net_carrying",
        "opening_assessment_id": None if renewal else opening,
        "opening_cutoff_date": "2030-01-04",
        "impairment_boundary_date": "2030-01-04",
        "gross_interest": "1.63",
        "net_interest": "1.64",
        "allowance_unwind": "-0.01",
        "currency_rounding_adjustment": "-0.01",
        "cash_measurements": [{"private_receipt": "PRIVATE-SOURCE-BYTES"}],
        "private": "PRIVATE-SOURCE-BYTES",
        **({"opening_renewal_review_id": opening} if renewal else {}),
    }
    public = repository._impaired_interest_payload(measured)
    assert public["currency_rounding_adjustment"] == "-0.01"
    assert public["allowance_unwind"] == "-0.01"
    assert public["gross_interest"] == "1.63"
    assert public["net_interest"] == "1.64"
    assert public["opening_assessment_id"] == (None if renewal else opening)
    if renewal:
        assert public["opening_renewal_review_id"] == opening
    assert "cash_measurements" not in public
    assert "PRIVATE-SOURCE-BYTES" not in repr(public)


def test_impaired_cash_checks_exact_private_receipt_bytes(monkeypatch):
    evidence = {"id": str(uuid4()), "sha256": "c" * 64, "byte_count": 51}
    calls = []

    class Store:
        def read(self, identity, digest, size):
            calls.append((str(identity), digest, size))
            raise EvidenceFileError("Retained receipt bytes changed")

    monkeypatch.setattr(repository, "PrivateEvidenceStore", Store)
    with pytest.raises(CutoffAssessmentConflict):
        repository._verify_impaired_cash_files(
            {"application_preparation": {"snapshot": {"evidence": evidence}}}
        )
    assert calls == [(evidence["id"], evidence["sha256"], evidence["byte_count"])]
