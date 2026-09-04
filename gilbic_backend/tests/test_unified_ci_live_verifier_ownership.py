from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = (ROOT / ".github" / "workflows" / "spina-ci.yml").read_text(
    encoding="utf-8"
)
MAINTENANCE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "spina-protected-maintenance.yml"
).read_text(encoding="utf-8")


def test_unified_ci_has_three_hosted_validation_lanes() -> None:
    assert "name: SPINA CI" in CI_WORKFLOW
    for job in ("backend", "client-apps", "financial-database"):
        assert f"\n  {job}:\n" in CI_WORKFLOW
    assert CI_WORKFLOW.count("runs-on: ubuntu-latest") == 3
    assert "runs-on: [self-hosted" not in CI_WORKFLOW


def test_unified_ci_keeps_backend_client_and_database_coverage() -> None:
    for required in (
        "python -m pytest -q",
        "ruff check",
        "pyright --outputjson",
        "bandit -r",
        "pip-audit --local",
        "gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz",
        "npm test",
        "flutter analyze --fatal-infos",
        "flutter test",
        "flutter build apk --debug",
        "run_7x7_source_event_accounting_preview_disposable_postgres_validation.py",
        "run_mvp_private_schema_barrier_validation.py",
    ):
        assert required in CI_WORKFLOW


def test_completed_live_maintenance_is_not_owned_by_automatic_ci() -> None:
    for marker in (
        "stage5e2-import.once",
        "stage5e3-live-migration.once",
        "stage5e41-live-migration.once",
        "stage5e43-live-migration.once",
        "stage5e46a-live-migration.once",
        "C:\\GitHub\\spina-lending-app-clean\\.env",
        "C:\\SPINA_ONLINE\\spina_backend\\.env",
    ):
        assert marker not in CI_WORKFLOW


def test_legacy_stage5e_live_maintenance_is_manual_and_fail_closed() -> None:
    trigger_block = MAINTENANCE_WORKFLOW.split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "\n  push:" not in trigger_block
    assert '"refs/heads/main"' in MAINTENANCE_WORKFLOW
    assert "confirm_protected_live_database" in MAINTENANCE_WORKFLOW
    assert "SPINA-WINDOWS" in MAINTENANCE_WORKFLOW

    expected = {
        "stage5e2-history-import": "tools/stage5e2-import.once",
        "stage5e3-outcome-review": "tools/stage5e3-live-migration.once",
        "stage5e41-contractual-dpd": "tools/stage5e41-live-migration.once",
        "stage5e43-contract-registration": "tools/stage5e43-live-migration.once",
        "stage5e46a-contract-activation": "tools/stage5e46a-live-migration.once",
    }
    normalized = MAINTENANCE_WORKFLOW.replace("\\", "/")
    for operation, marker in expected.items():
        assert operation in MAINTENANCE_WORKFLOW
        assert marker in normalized


def test_automatic_ci_uses_loopback_disposable_postgres_only() -> None:
    assert "services:\n      postgres:" in CI_WORKFLOW
    assert "127.0.0.1:5432" in CI_WORKFLOW
    assert "SPINA_ALLOW_DISPOSABLE_DATABASE" in CI_WORKFLOW
    assert "GILBIC_DATABASE_URL" not in CI_WORKFLOW
    assert "secrets.GILBIC_TEST_DATABASE_URL" not in CI_WORKFLOW
