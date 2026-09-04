from pathlib import Path


RUNNER = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "apply_stage5e41_migration.py"
).read_text(encoding="utf-8")
WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "spina-protected-maintenance.yml"
).read_text(encoding="utf-8")


def test_stage5e41_live_runner_uses_live_database_only() -> None:
    assert 'default="GILBIC_DATABASE_URL"' in RUNNER
    assert "GILBIC_TEST_DATABASE_URL" not in RUNNER


def test_stage5e41_live_runner_is_idempotent() -> None:
    assert "Stage 5E.4.1 is already installed; skipping migration application" in RUNNER


def test_stage5e41_live_runner_forbids_automatic_live_schedule_creation() -> None:
    assert "loan_contract_schedules" in RUNNER
    assert "loan_contract_installments" in RUNNER
    assert "loan_installment_payment_allocations" in RUNNER
    assert "must not auto-create" in RUNNER
    assert "existing loans must remain contract_schedule_required" in RUNNER


def test_stage5e41_live_runner_protects_existing_business_data() -> None:
    assert "lending.loans changed during schema install" in RUNNER
    assert "collection transactions changed during schema install" in RUNNER
    assert "journal entries changed during schema install" in RUNNER
    assert "historical ECL outcome labels changed" in RUNNER


def test_stage5e41_live_runner_keeps_classification_ecl_and_posting_disabled() -> None:
    assert "automatic_default_label_written" in RUNNER
    assert "ecl_included" in RUNNER
    assert "ecl_amount" in RUNNER
    assert "ready_to_post" in RUNNER
    assert "unexpectedly enabled" in RUNNER


def test_workflow_runs_stage5e41_live_migration_only_by_manual_dispatch() -> None:
    trigger_block = WORKFLOW.split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "\n  push:" not in trigger_block

    name = "Manual Stage 5E.4.1 live contractual DPD migration"
    assert name in WORKFLOW
    step = WORKFLOW.split(f"      - name: {name}", 1)[1].split("\n      - name:", 1)[0]
    assert "inputs.operation == 'stage5e41-contractual-dpd'" in step
    assert "tools/stage5e41-live-migration.once" in step
    assert "tools\\apply_stage5e41_migration.py" in step
