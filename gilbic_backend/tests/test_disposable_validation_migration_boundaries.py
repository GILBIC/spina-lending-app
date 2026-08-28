from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_7X7_OPERATIONAL_READER_MIGRATION = 107
REQUIRED_7X7_EXTRA_PRINCIPAL_BRIDGE_MIGRATION = 108
CURRENT_7X7_READER_VALIDATORS = (
    ROOT
    / "tools"
    / "run_7x7_source_event_accounting_preview_disposable_postgres_validation.py",
    ROOT
    / "tools"
    / "run_combined_collection_renewal_disposable_postgres_validation.py",
)
CURRENT_7X7_EXTRA_PRINCIPAL_BRIDGE_VALIDATORS = (
    ROOT / "tools" / "run_7x7_extra_principal_bridge_disposable_postgres_validation.py",
)


def _bootstrap_through(path: Path) -> int:
    if not path.is_file():
        raise AssertionError(f"Disposable validator is missing: {path}")

    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "BOOTSTRAP_THROUGH"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
            return node.value.value
        raise AssertionError(
            f"{path} must assign BOOTSTRAP_THROUGH to an integer literal"
        )

    raise AssertionError(f"{path} must define BOOTSTRAP_THROUGH")


def test_current_7x7_reader_validators_include_required_migrations() -> None:
    stale: dict[str, int] = {}
    for path in CURRENT_7X7_READER_VALIDATORS:
        actual = _bootstrap_through(path)
        if actual < REQUIRED_7X7_OPERATIONAL_READER_MIGRATION:
            stale[path.relative_to(ROOT).as_posix()] = actual

    assert not stale, (
        "Current 7x7 reader validators must bootstrap through migration "
        f"{REQUIRED_7X7_OPERATIONAL_READER_MIGRATION:04d}: {stale}"
    )


def test_current_7x7_extra_principal_bridge_validators_include_required_migrations() -> (
    None
):
    stale: dict[str, int] = {}
    for path in CURRENT_7X7_EXTRA_PRINCIPAL_BRIDGE_VALIDATORS:
        actual = _bootstrap_through(path)
        if actual < REQUIRED_7X7_EXTRA_PRINCIPAL_BRIDGE_MIGRATION:
            stale[path.relative_to(ROOT).as_posix()] = actual

    assert not stale, (
        "Current 7x7 Extra Principal bridge validators must bootstrap through migration "
        f"{REQUIRED_7X7_EXTRA_PRINCIPAL_BRIDGE_MIGRATION:04d}: {stale}"
    )
