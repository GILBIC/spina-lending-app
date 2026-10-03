"""A retained host guard must reject a cash-only runtime after treasury rollout."""

import importlib.util
import json
from pathlib import Path


def guard_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "ops/digitalocean/treasury_runtime_guard.py"
    )
    spec = importlib.util.spec_from_file_location("treasury_runtime_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_and_missing_runtime_are_rejected(tmp_path):
    guard = guard_module()
    assert not guard.compatible(tmp_path)
    (tmp_path / "release-capabilities.json").write_text(
        json.dumps({"treasury_funding_schema": 0})
    )
    assert not guard.compatible(tmp_path)


def test_incomplete_claimed_runtime_is_rejected(tmp_path):
    guard = guard_module()
    (tmp_path / "release-capabilities.json").write_text(
        json.dumps({"treasury_funding_schema": 1})
    )
    assert not guard.compatible(tmp_path)


def test_current_source_aware_release_is_accepted():
    assert guard_module().compatible(Path(__file__).resolve().parents[1])


def test_treasury_only_runtime_cannot_replace_retained_surplus_runtime(tmp_path):
    guard = guard_module()
    for relative in guard.REQUIRED_FILES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic compatibility fixture")
    (tmp_path / "release-capabilities.json").write_text(
        json.dumps({"treasury_funding_schema": 1})
    )
    assert not guard.compatible(tmp_path)
    (tmp_path / "release-capabilities.json").write_text(
        json.dumps({"treasury_funding_schema": 1, "collector_surplus_schema": 1})
    )
    assert not guard.compatible(tmp_path)
    (tmp_path / "release-capabilities.json").write_text(
        json.dumps(
            {
                "treasury_funding_schema": 1,
                "collector_surplus_schema": 1,
                "loan_payout_schema": 1,
            }
        )
    )
    assert guard.compatible(tmp_path)
    (tmp_path / "gilbic_backend/sql/0138_add_collector_surplus.sql").unlink()
    assert not guard.compatible(tmp_path)


def test_host_guard_survives_ordinary_release_rollback():
    root = Path(__file__).resolve().parents[1]
    script = (root / "ops/digitalocean/bootstrap.sh").read_text(encoding="utf-8")
    assert 'install_treasury_runtime_guard "$RELEASE_DIR"' in script
    assert script.index('install_treasury_runtime_guard "$RELEASE_DIR"') < script.index(
        "ACTIVATION_STARTED=true"
    )
    assert "spina-api.service.d/treasury-funding.conf" in script
    assert (
        "ExecStartPre=/usr/bin/python3 /opt/spina/guards/treasury_runtime_guard.py /opt/spina/current"
        in script
    )
    rollback = script[
        script.index("rollback_deployment() {") : script.index("deployment_exit() {")
    ]
    assert "treasury-funding.conf" not in rollback
