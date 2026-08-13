from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / "src" / "gilbic_backend"
API = (PACKAGE / "ecl_quantitative_measurement_api.py").read_text(encoding="utf-8")
REPOSITORY = (PACKAGE / "ecl_quantitative_measurement_repository.py").read_text(
    encoding="utf-8"
)
MAIN = (PACKAGE / "main.py").read_text(encoding="utf-8")


def test_read_only_ecl_router_is_registered() -> None:
    assert (
        "from .ecl_quantitative_measurement_api import create_ecl_quantitative_measurement_router"
        in MAIN
    )
    assert "app.include_router(create_ecl_quantitative_measurement_router())" in MAIN


def test_read_only_ecl_api_requires_management_and_dedicated_measure_permission() -> None:
    assert 'MEASURE_PERMISSION = "accounting.ecl.measurement.review"' in API
    assert '"management" not in actor.roles' in API
    assert "Quantitative ECL measurement Management permission is required." in API
    assert "Management access is required for quantitative ECL measurement." in API


def test_read_only_ecl_api_requires_explicit_probability_and_cash_flow_evidence() -> None:
    assert "probability: Decimal" in API
    assert "evidence_reference: str" in API
    assert "management_rationale: str" in API
    assert "forward_evidence_ids: list[UUID]" in API
    assert "expected_cash_flows: list[ExpectedCashFlowRequest]" in API
    assert "Scenario probabilities must sum exactly to 1.000000000000." in API
    assert "Scenario probability supports at most 12 decimal places." in API
    assert "Expected cash-flow amounts must use exact currency-cent precision." in API


def test_read_only_ecl_repository_uses_only_protected_measurement_function_and_views() -> None:
    assert "accounting.record_read_only_quantitative_ecl_measurement" in REPOSITORY
    assert "accounting.ecl_quantitative_measurement_queue" in REPOSITORY
    assert "accounting.ecl_quantitative_measurement_summary" in REPOSITORY
    assert "accounting.ecl_quantitative_measurements" in REPOSITORY
    assert "insert into accounting.journal_entries" not in REPOSITORY.lower()
    assert "insert into accounting.journal_lines" not in REPOSITORY.lower()


def test_read_only_ecl_api_exposes_no_posting_action() -> None:
    assert '"account_1190_posting_enabled": False' in API
    assert '"automatic_source_posting": False' in API
    assert "post_manual_journal_entry" not in API
    assert "A3 is read-only quantitative ECL" in API
    assert "account 1190 posting and automatic source posting remain disabled" in API
