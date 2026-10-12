"""Fresh installed-schema first-book, source, close and recovery verification.

Historical bounded runners remain separate. This suite includes complete current
schema replays in its cycle fixtures and never reinstalls an older close stack.
Native historical loan proof requires the separately retained dated fixture.
"""

from pathlib import Path

import run_accounting_controls_disposable_validation as controls

ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "test_accounting_book_postgres.py",
    "test_accounting_book_api.py",
    "test_database_book_pin.py",
    "test_accounting_increment_private_barrier_postgres.py",
    "test_reporting_source_proof_postgres.py",
    "test_reporting_export_postgres.py",
    "test_native_regular_assessment_integration_postgres.py",
    "test_native_regular_same_day_cash_postgres.py",
    "test_native_credit_risk_assessment_postgres.py",
    "test_native_credit_impaired_assessment_postgres.py",
    "test_native_impaired_cash_review_postgres.py",
    "test_native_impaired_rounding_current_postgres.py",
    "test_native_impaired_cash_api.py",
    "test_native_credit_risk_projection.py",
    "test_current_credit_risk_review_postgres.py",
    "test_current_credit_risk_review_api.py",
    "test_current_credit_risk_projection.py",
    "test_native_renewal_api.py",
    "test_loan_payout_accounting_api.py",
    "test_current_schema_accounting_cycle_postgres.py",
    "test_current_schema_period_close_guards_postgres.py",
    "test_period_close_api_contract.py",
    "test_period_source_api.py",
    "test_accounting_validation_boundaries.py",
)


def main():
    through = max(
        int(path.name[:4])
        for path in (ROOT / "gilbic_backend/sql").glob("*.sql")
        if path.name[:4].isdigit()
    )
    if through < 171:
        raise SystemExit(
            "Final accounting verification requires native lifecycle, reporting and current risk controls through 0171."
        )
    return controls.main(bootstrap_through=through, tests=TESTS, timeout_seconds=1800)


if __name__ == "__main__":
    raise SystemExit(main())
