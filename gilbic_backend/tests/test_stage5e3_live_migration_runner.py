from pathlib import Path


RUNNER = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "apply_stage5e3_migration.py"
).read_text(encoding="utf-8")
WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "spina-ci.yml"
).read_text(encoding="utf-8")


def test_stage5e3_live_runner_uses_live_database_only() -> None:
    assert 'default="GILBIC_DATABASE_URL"' in RUNNER
    assert "GILBIC_TEST_DATABASE_URL" not in RUNNER


def test_stage5e3_live_runner_requires_expected_dataset_counts() -> None:
    assert 'default=992' in RUNNER
    assert 'default=919' in RUNNER
    assert "Live dataset gate failed" in RUNNER


def test_stage5e3_live_runner_keeps_ecl_and_posting_disabled() -> None:
    assert "ecl_included" in RUNNER
    assert "ecl_amount" in RUNNER
    assert "ready_to_post" in RUNNER
    assert "unexpectedly enabled" in RUNNER


def test_stage5e3_live_runner_is_idempotent() -> None:
    assert "Stage 5E.3 is already installed; skipping migration application" in RUNNER


def test_workflow_runs_stage5e3_live_migration_only_by_manual_dispatch() -> None:
    name = "Manual Stage 5E.3 live outcome-review migration"
    assert name in WORKFLOW
    step = WORKFLOW.split(f"      - name: {name}", 1)[1].split("\n      - name:", 1)[0]
    assert "github.event_name == 'workflow_dispatch'" in step
    assert "inputs.run_legacy_live_migrations" in step
    assert "github.event_name == 'push'" not in step
    assert "tools/stage5e3-live-migration.once" in step
    assert "--expected-episodes 992 --expected-usable 919" in step
