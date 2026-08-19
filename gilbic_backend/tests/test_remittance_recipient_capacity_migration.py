from pathlib import Path

from tools.apply_0099_remittance_recipient_capacity_migration import (
    BACKEND_SRC,
    CAPACITY_CONSTRAINT,
    CAPACITY_TRIGGER,
    MIGRATION,
    VALID_CAPACITIES,
    _transaction_body,
)


ROOT = Path(__file__).resolve().parents[2]
CROSS_REPOSITORY = (
    ROOT / "gilbic_backend" / "src" / "gilbic_backend" / "cross_remittance_repository.py"
)


def test_0099_is_transaction_wrapped_and_backfills_without_guessing() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    body = _transaction_body(source)

    assert "ADD COLUMN IF NOT EXISTS recipient_capacity TEXT" in body
    assert "SET recipient_capacity = 'legacy'" in body
    assert "WHERE recipient_capacity IS NULL" in body
    assert "ALTER COLUMN recipient_capacity SET NOT NULL" in body
    assert CAPACITY_CONSTRAINT in body
    assert CAPACITY_TRIGGER in body
    assert "ERRCODE = '55000'" in body


def test_0099_capacity_domain_matches_application_contract() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for capacity in VALID_CAPACITIES:
        assert f"'{capacity}'" in source

    cross_source = CROSS_REPOSITORY.read_text(encoding="utf-8")
    assert 'ASSIGNED_COLLECTOR_CAPACITY = "assigned_collector"' in cross_source
    assert 'MANAGEMENT_CAPACITY = "management"' in cross_source
    assert "recipient_capacity," in cross_source
    assert '"recipient_capacity": capacity' in cross_source


def test_0099_runner_guards_existing_financial_evidence() -> None:
    runner_path = ROOT / "tools" / "apply_0099_remittance_recipient_capacity_migration.py"
    runner = runner_path.read_text(encoding="utf-8")

    assert BACKEND_SRC == ROOT / "gilbic_backend" / "src"
    assert 'BACKEND_SRC = ROOT / "gilbic_backend" / "src"' in runner
    assert "for import_root in (ROOT, BACKEND_SRC):" in runner
    assert "LOCK TABLE lending.collection_remittances IN ACCESS EXCLUSIVE MODE" in runner
    assert "pre-existing remittance evidence changed" in runner
    assert "remittance row count or cash total changed" in runner
    assert "historical recipient intent was inferred" in runner
    assert "already installed and verified; no changes were made" in runner
