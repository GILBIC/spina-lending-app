from pathlib import Path


RUNNER = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "apply_stage5e46a_migration.py"
).read_text(encoding="utf-8")
WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "spina-protected-maintenance.yml"
).read_text(encoding="utf-8")


def test_stage5e46a_live_runner_uses_live_database_only() -> None:
    assert 'default="GILBIC_DATABASE_URL"' in RUNNER
    assert "GILBIC_TEST_DATABASE_URL" not in RUNNER


def test_stage5e46a_live_runner_is_idempotent() -> None:
    assert "Stage 5E.4.6A is already installed; skipping migration application" in RUNNER


def test_stage5e46a_live_runner_requires_verified_schedule_foundation() -> None:
    assert "lending.loan_contract_schedules" in RUNNER
    assert "lending.loan_contract_installments" in RUNNER
    assert "lending.loan_installment_payment_allocations" in RUNNER
    assert "lending.loan_contract_schedule_registrations" in RUNNER
    assert "accounting.loan_contract_dpd_summary" in RUNNER


def test_stage5e46a_live_runner_requires_zero_initial_activation() -> None:
    assert "zero activation events and zero active loans" in RUNNER
    assert "activation_events=" in RUNNER
    assert "active_activations=" in RUNNER


def test_stage5e46a_live_runner_protects_business_and_accounting_state() -> None:
    assert "lending.loans changed during schema install" in RUNNER
    assert "collection transactions changed during schema install" in RUNNER
    assert "journal entries changed during schema install" in RUNNER
    assert "historical ECL outcome labels changed" in RUNNER
    assert "schedules, installments, payment allocations, or registrations changed" in RUNNER
    assert "DPD readiness or delinquency state changed" in RUNNER


def test_stage5e46a_live_runner_verifies_permission_and_audit_guards() -> None:
    assert "lending.contract_collection.activate" in RUNNER
    assert "lending_contract_collection_activation_validate" in RUNNER
    assert "lending_contract_collection_activation_audit_guard" in RUNNER


def test_stage5e46a_live_runner_keeps_default_ecl_and_posting_disabled() -> None:
    assert "automatic_default_label_written" in RUNNER
    assert "ecl_included" in RUNNER
    assert "ecl_amount" in RUNNER
    assert "ready_to_post" in RUNNER
    assert "unexpectedly enabled" in RUNNER


def test_workflow_runs_stage5e46a_live_migration_only_by_manual_dispatch() -> None:
    trigger_block = WORKFLOW.split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "\n  push:" not in trigger_block

    name = "Manual Stage 5E.4.6A live per-loan activation schema migration"
    assert name in WORKFLOW
    step = WORKFLOW.split(f"      - name: {name}", 1)[1].split("\n      - name:", 1)[0]
    assert "inputs.operation == 'stage5e46a-contract-activation'" in step
    assert "tools/stage5e46a-live-migration.once" in step
    assert "tools\\apply_stage5e46a_migration.py" in step
