from pathlib import Path


RUNNER = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "apply_stage5e43_migration.py"
).read_text(encoding="utf-8")
WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "spina-protected-maintenance.yml"
).read_text(encoding="utf-8")


def test_stage5e43_live_runner_uses_live_database_only() -> None:
    assert 'default="GILBIC_DATABASE_URL"' in RUNNER
    assert "GILBIC_TEST_DATABASE_URL" not in RUNNER


def test_stage5e43_live_runner_is_idempotent() -> None:
    assert "Stage 5E.4.3 is already installed; skipping migration application" in RUNNER


def test_stage5e43_live_runner_requires_0034_prerequisites() -> None:
    assert "lending.loan_contract_schedules" in RUNNER
    assert "lending.loan_contract_installments" in RUNNER
    assert "lending.loan_installment_payment_allocations" in RUNNER
    assert "accounting.loan_contract_dpd_summary" in RUNNER


def test_stage5e43_live_runner_does_not_change_live_schedule_state() -> None:
    assert "schedules, installments, or payment allocations changed during schema install" in RUNNER
    assert "DPD readiness or delinquency state changed during schema install" in RUNNER
    assert "must not create verified contract registrations" in RUNNER


def test_stage5e43_live_runner_protects_existing_business_and_accounting_data() -> None:
    assert "lending.loans changed during schema install" in RUNNER
    assert "collection transactions changed during schema install" in RUNNER
    assert "journal entries changed during schema install" in RUNNER
    assert "historical ECL outcome labels changed" in RUNNER


def test_stage5e43_live_runner_verifies_permission_and_immutability_guards() -> None:
    assert "lending.contract_schedule.manage" in RUNNER
    assert "lending_contract_schedule_registration_audit_guard" in RUNNER
    assert "lending_contract_installment_immutability_guard" in RUNNER
    assert "lending_contract_schedule_terms_guard" in RUNNER


def test_stage5e43_live_runner_keeps_default_ecl_and_posting_disabled() -> None:
    assert "automatic_default_label_written" in RUNNER
    assert "ecl_included" in RUNNER
    assert "ecl_amount" in RUNNER
    assert "ready_to_post" in RUNNER
    assert "unexpectedly enabled" in RUNNER


def test_workflow_runs_stage5e43_live_migration_only_by_manual_dispatch() -> None:
    trigger_block = WORKFLOW.split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "\n  push:" not in trigger_block

    name = "Manual Stage 5E.4.3 live verified contract registration migration"
    assert name in WORKFLOW
    step = WORKFLOW.split(f"      - name: {name}", 1)[1].split("\n      - name:", 1)[0]
    assert "inputs.operation == 'stage5e43-contract-registration'" in step
    assert "tools/stage5e43-live-migration.once" in step
    assert "tools\\apply_stage5e43_migration.py" in step
