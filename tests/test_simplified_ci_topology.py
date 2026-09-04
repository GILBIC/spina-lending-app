from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PRIMARY = WORKFLOWS / "spina-ci.yml"
RETIRED = (
    "spina-code-quality.yml",
    "spina-security-compliance.yml",
    "spina-reliability-performance.yml",
    "spina-financial-database.yml",
    "mvp-cross-platform-smoke.yml",
    "spina-ci-deep-review.yml",
)


def test_primary_ci_has_three_clear_hosted_lanes() -> None:
    source = PRIMARY.read_text(encoding="utf-8")

    assert "name: SPINA CI" in source
    assert "\n  backend:\n" in source
    assert "\n  client-apps:\n" in source
    assert "\n  financial-database:\n" in source
    assert source.count("runs-on: ubuntu-latest") == 3
    assert "runs-on: [self-hosted" not in source
    assert "services:\n      postgres:" in source
    assert 'GITLEAKS_VERSION: "8.30.1"' in source
    assert "python -m pytest -q" in source
    assert "flutter analyze --fatal-infos" in source
    assert "flutter build apk --debug" in source
    assert "npm test" in source
    assert (
        "run_7x7_source_event_accounting_preview_disposable_postgres_validation.py"
        in source
    )


def test_hosted_ci_uses_current_node_24_action_runtimes() -> None:
    source = PRIMARY.read_text(encoding="utf-8")

    for action in (
        "actions/checkout@v7.0.1",
        "actions/setup-python@v7.0.0",
        "actions/setup-node@v7.0.0",
        "actions/setup-java@v6.0.0",
        "actions/upload-artifact@v7.0.0",
    ):
        assert action in source
    for retired in (
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "actions/setup-node@v4",
        "actions/setup-java@v4",
        "actions/upload-artifact@v4",
    ):
        assert retired not in source


def test_private_schema_validator_uses_an_explicit_test_database() -> None:
    source = PRIMARY.read_text(encoding="utf-8")

    assert "mvp_private_schema_test" in source
    assert "/privateschema?" not in source
    assert '--health-cmd "pg_isready -U postgres"' in source


def test_retired_broad_workflows_are_removed() -> None:
    for filename in RETIRED:
        assert not (WORKFLOWS / filename).exists(), filename


def test_protected_database_maintenance_is_manual_only() -> None:
    source = (WORKFLOWS / "spina-protected-maintenance.yml").read_text(
        encoding="utf-8"
    )
    trigger_block = source.split("\njobs:", 1)[0]

    assert "workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "\n  push:" not in trigger_block
    for operation in (
        "ecl-credit-risk-labels",
        "v1-tax-accounting",
        "stage5e2-history-import",
        "stage5e3-outcome-review",
        "stage5e41-contractual-dpd",
        "stage5e43-contract-registration",
        "stage5e46a-contract-activation",
    ):
        assert operation in source
