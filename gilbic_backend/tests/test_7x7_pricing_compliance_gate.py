from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0117_add_7x7_pricing_compliance_readiness.sql"
API = (
    ROOT / "src" / "gilbic_backend" / "contract_schedule_registration_api.py"
).read_text(encoding="utf-8")
REPOSITORY = (
    ROOT / "src" / "gilbic_backend" / "contract_schedule_registration_repository.py"
).read_text(encoding="utf-8")


def test_priority6_pricing_compliance_readiness_migration_exists() -> None:
    assert MIGRATION.is_file(), (
        "Priority #6 requires forward migration 0117 for an exact-term, server-persisted "
        "7x7 pricing/compliance readiness gate before contract lock."
    )


def test_priority6_pricing_compliance_readiness_is_explicit_and_terms_bound() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()

    assert "seven_by_seven_pricing_compliance_reviews" in source
    assert "terms_fingerprint" in source
    assert "applicability_review_ready" in source
    assert "pricing_cap_review_ready" in source
    assert "disclosure_ready" in source
    assert "total_cost_cap_review_ready" in source
    assert "evidence_reference" in source
    assert "review_note" in source
    assert "reviewed_by_user_id" in source


def test_priority6_registration_checks_readiness_before_schedule_lock() -> None:
    assert "/contract-schedules/7x7-pricing-compliance/review" in API
    assert "applicability_review_ready" in API
    assert "pricing_cap_review_ready" in API
    assert "disclosure_ready" in API
    assert "total_cost_cap_review_ready" in API
    assert "record_7x7_pricing_compliance_review" in REPOSITORY
    assert "require_7x7_pricing_compliance_ready" in REPOSITORY

    readiness_call = API.index("require_7x7_pricing_compliance_ready")
    registration_call = API.index("registrations.register_schedule(")
    assert readiness_call < registration_call
